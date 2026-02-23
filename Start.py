"""
Smart Document Organizer - FastAPI Application Entry Point
=========================================================

A Legal AI platform for intelligent document analysis, entity extraction,
legal reasoning, and document organization.
"""

import asyncio
import argparse
import atexit
import json
import hashlib
import logging
import os  # noqa: E402
import re
import sqlite3
import subprocess
import sys  # noqa: E402
import time
import traceback
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional  # noqa: E402

from fastapi import Depends, FastAPI, Header, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, ValidationError  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse, Response  # noqa: E402

# Add current directory to Python path for absolute imports
sys.path.insert(0, os.path.dirname(__file__))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY_ENV = os.getenv("API_KEY", "")
STARTUP_ENFORCED = True
STARTUP_PROFILE = os.getenv("STARTUP_PROFILE", "full").strip().lower()
if STARTUP_PROFILE not in {"api", "minimal", "full", "gui"}:
    STARTUP_PROFILE = "full"

_agents_lazy_env = os.getenv("AGENTS_LAZY_INIT")
if _agents_lazy_env is None:
    AGENTS_LAZY_INIT = True
else:
    AGENTS_LAZY_INIT = _agents_lazy_env.strip().lower() in {"1", "true", "yes", "on"}

_offline_safe_env = os.getenv("STARTUP_OFFLINE_SAFE")
if _offline_safe_env is None:
    STARTUP_OFFLINE_SAFE = True
else:
    STARTUP_OFFLINE_SAFE = _offline_safe_env.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

STARTUP_PHASE_BUDGET_MS = {
    "config_load": 500,
    "dependency_injection": 1500,
    "module_initialization": 8000,
    "plugin_loading": 500,
    "schema_validation": 1000,
    "migration_checks": 1200,
}
DEFAULT_REQUIRED_PRODUCTION_AGENTS = [
    "document_processor",
    "entity_extractor",
    "legal_reasoning",
    "irac_analyzer",
]

DEFAULT_INTEGRITY_LAYER_TARGETS: dict[str, dict[str, list[str]]] = {
    "h1": {
        "paths": [
            "routes",
            "services",
            "agents",
            "gui",
            "mem_db",
        ],
        "must_include_any": ["AgentService", "_v(", "STARTUP_OFFLINE_SAFE", "AnalysisVersion"],
    },
    "p0_contracts": {
        "paths": ["services/contracts", "gui/services"],
        "must_include_any": [
            "CanonicalArtifact",
            "AnalysisVersion",
            "ProvenanceRecord",
            "HeuristicEntry",
            "PlannerRun",
            "JudgeRun",
            "EvidenceSpan",
            "AuditDelta",
        ],
    },
    "canonical": {
        "paths": ["services", "routes", "gui/tabs"],
        "must_include_any": ["CanonicalArtifactService", "CanonicalRepository"],
    },
    "ontology": {
        "paths": ["services", "routes", "agents/extractors", "gui/tabs"],
        "must_include_any": ["OntologyRegistryService", "OntologyType"],
    },
    "provenance": {
        "paths": ["services", "routes", "gui/tabs"],
        "must_include_any": ["Provenance", "provenance"],
    },
    "planner_judge": {
        "paths": ["services", "routes", "gui/tabs"],
        "must_include_any": ["Judge", "judge", "Planner", "planner"],
    },
    "heuristics": {
        "paths": ["services", "routes", "gui/tabs"],
        "must_include_any": ["Heuristic", "heuristic"],
    },
    "generative_instructional": {
        "paths": ["services", "routes", "gui/tabs"],
        "must_include_any": ["Generative", "LearningPath", "learning"],
    },
    "ontology_enforcement": {
        "paths": ["agents/extractors", "services", "routes", "gui/tabs"],
        "must_include_any": ["ontology", "entity_type", "entity"],
    },
    "measurement": {
        "paths": ["services", "routes", "gui/tabs"],
        "must_include_any": ["metrics", "measurement", "KPI", "evaluation"],
    },
}


def _load_integrity_layer_targets() -> dict[str, dict[str, list[str]]]:
    config_path = Path(__file__).resolve().parent / "config" / "integrity_rules.json"
    if not config_path.exists():
        logger.warning("Integrity rules file not found, using defaults: %s", config_path)
        return DEFAULT_INTEGRITY_LAYER_TARGETS
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to parse integrity rules file: %s", exc)
        return DEFAULT_INTEGRITY_LAYER_TARGETS

    layers = raw.get("layers")
    if not isinstance(layers, dict) or not layers:
        logger.error("Integrity rules config missing valid 'layers', using defaults")
        return DEFAULT_INTEGRITY_LAYER_TARGETS

    out: dict[str, dict[str, list[str]]] = {}
    for layer_name, layer_cfg in layers.items():
        if not isinstance(layer_cfg, dict):
            continue
        paths = layer_cfg.get("paths")
        markers = layer_cfg.get("must_include_any")
        if not isinstance(paths, list) or not isinstance(markers, list):
            continue
        if not all(isinstance(x, str) and x.strip() for x in paths):
            continue
        if not all(isinstance(x, str) and x.strip() for x in markers):
            continue
        out[layer_name] = {
            "paths": [p.strip() for p in paths],
            "must_include_any": [m.strip() for m in markers],
        }
    if not out:
        logger.error("Integrity rules config contains no valid layers, using defaults")
        return DEFAULT_INTEGRITY_LAYER_TARGETS
    return out


INTEGRITY_LAYER_TARGETS = _load_integrity_layer_targets()


class IntegrityReportModel(BaseModel):
    schema_version: str
    status: str
    layer: str
    checked_paths: list[str]
    files_scanned: int
    required_marker_hits: int
    fallback_count: int
    placeholder_count: int
    generated_at: str


try:
    RATE_LIMIT_REQUESTS_PER_MINUTE = int(
        os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60")
    )
except Exception:
    RATE_LIMIT_REQUESTS_PER_MINUTE = 60


def _required_production_agents() -> list[str]:
    raw = os.getenv(
        "REQUIRED_PRODUCTION_AGENTS",
        ",".join(DEFAULT_REQUIRED_PRODUCTION_AGENTS),
    )
    vals = [v.strip().lower() for v in raw.split(",") if v.strip()]
    # Preserve order while de-duplicating
    seen = set()
    out = []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _count_file_markers(path: Path, markers: list[str]) -> int:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 0
    
    count = 0
    for marker in markers:
        # For 'placeholder', we ignore common UI methods like setPlaceholderText
        if marker.lower() == "placeholder":
            # Find all 'placeholder' occurrences
            matches = re.finditer(re.escape(marker), content, re.IGNORECASE)
            for m in matches:
                # Get surrounding context to check for 'setPlaceholderText'
                start, end = m.span()
                context = content[max(0, start-20):min(len(content), end+20)]
                if "setPlaceholderText" not in context and "placeholder_text" not in context:
                    count += 1
        else:
            # Standard count for other markers
            count += len(re.findall(re.escape(marker), content, re.IGNORECASE))
    return count


def _count_text_markers(base: Path, roots: list[str], markers: list[str]) -> int:
    total = 0
    for rel_root in roots:
        root = (base / rel_root).resolve()
        if not root.exists():
            continue
        if root.is_file() and root.suffix == ".py":
            total += _count_file_markers(root, markers)
            continue
        for path in root.rglob("*.py"):
            total += _count_file_markers(path, markers)
    return total


def _collect_python_files(base: Path, roots: list[str]) -> int:
    count = 0
    for rel_root in roots:
        root = (base / rel_root).resolve()
        if not root.exists():
            continue
        if root.is_file() and root.suffix == ".py":
            count += 1
            continue
        count += sum(1 for _ in root.rglob("*.py"))
    return count


def _run_integrity_check(
    layer: str,
    output: Optional[str] = None,
    *,
    json_only: bool = False,
) -> int:
    base = Path(__file__).resolve().parent
    target = INTEGRITY_LAYER_TARGETS.get(layer, INTEGRITY_LAYER_TARGETS["h1"])
    marker_hits = _count_text_markers(
        base=base,
        roots=target["paths"],
        markers=target["must_include_any"],
    )
    # H1 remains a global debt gate; later phases should evaluate their own layer scope.
    fallback_roots = (
        ["routes", "services", "agents", "gui", "mem_db"]
        if layer == "h1"
        else target["paths"]
    )
    fallback_count = _count_text_markers(
        base=base,
        roots=fallback_roots,
        markers=["fallback", "placeholder", "mock response", "stub"],
    )
    file_count = _collect_python_files(base=base, roots=target["paths"])
    status = "pass" if marker_hits > 0 and fallback_count == 0 else "fail"

    report = {
        "schema_version": "1.0.0",
        "status": status,
        "layer": layer,
        "checked_paths": target["paths"],
        "files_scanned": file_count,
        "required_marker_hits": marker_hits,
        "fallback_count": fallback_count,
        "placeholder_count": _count_text_markers(
            base=base,
            roots=fallback_roots,
            markers=["placeholder"],
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    validation_errors = _validate_integrity_report(report)
    if validation_errors:
        report["status"] = "fail"
        report["validation_errors"] = validation_errors
    text = json.dumps(report, indent=2)
    if output:
        output_path = Path(output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
        if not json_only:
            print(f"[integrity] wrote report: {output_path}")
    print(text if not json_only else json.dumps(report, separators=(",", ":")))
    return 0 if report.get("status") == "pass" else 1


def _validate_integrity_report(report: dict) -> list[str]:
    errors: list[str] = []
    try:
        model = IntegrityReportModel.model_validate(report)
    except ValidationError as exc:
        return [f"schema_validation_error: {msg}" for msg in exc.errors()]

    if model.status not in {"pass", "fail"}:
        errors.append("status must be pass or fail")
    if model.layer not in INTEGRITY_LAYER_TARGETS:
        errors.append("layer not in allowed integrity layers")
    return errors


def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Optional API key auth; enabled when env var API_KEY is set."""
    if not API_KEY_ENV:
        return
    if not x_api_key or x_api_key != API_KEY_ENV:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


protected_dependencies = [Depends(verify_api_key)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    await _startup_services()
    try:
        yield
    finally:
        await _shutdown_services()


app = FastAPI(title="Smart Document Organizer API", version="1.0.0", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.services = None
app.state.agent_manager = None
app.state.taskmaster_scheduler_task = None
app.state.metrics = {"requests_total": 0, "per_path": {}, "per_method": {}}
app.state.router_load_report = []
app.state.startup_report = {}
app.state.startup_steps = []
app.state.debug_mode = False
app.state.boot_time = time.time()
app.state.awareness_events = []
app.state.rate_limit_state = {}
app.state.rate_limit_lock = asyncio.Lock()
app.state.startup_profile = STARTUP_PROFILE
app.state.agents_lazy_init = AGENTS_LAZY_INIT
app.state.startup_offline_safe = STARTUP_OFFLINE_SAFE


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_awareness(level: str, message: str, details: Optional[dict] = None) -> None:
    event = {
        "at": _iso_now(),
        "level": level,
        "message": message,
        "details": details or {},
    }
    app.state.awareness_events.append(event)
    app.state.awareness_events = app.state.awareness_events[-200:]


async def _rate_limit_check(client_id: str) -> tuple[bool, float]:
    """Token-bucket limiter; returns (allowed, retry_after_seconds)."""
    if RATE_LIMIT_REQUESTS_PER_MINUTE <= 0:
        return True, 0.0

    now = time.monotonic()
    capacity = float(RATE_LIMIT_REQUESTS_PER_MINUTE)
    refill_per_sec = capacity / 60.0

    async with app.state.rate_limit_lock:
        state = app.state.rate_limit_state
        entry = state.get(client_id)
        if entry is None:
            tokens = capacity - 1.0
            state[client_id] = {"tokens": tokens, "last": now}
            return True, 0.0

        last = float(entry.get("last", now))
        tokens = float(entry.get("tokens", capacity))
        tokens = min(capacity, tokens + max(0.0, now - last) * refill_per_sec)

        if tokens >= 1.0:
            tokens -= 1.0
            entry["tokens"] = tokens
            entry["last"] = now
            return True, 0.0

        entry["tokens"] = tokens
        entry["last"] = now
        retry_after = (1.0 - tokens) / refill_per_sec if refill_per_sec > 0 else 1.0
        return False, max(0.1, retry_after)


def _start_step(name: str) -> dict:
    step = {
        "name": name,
        "status": "Running",
        "started_at": _iso_now(),
        "ended_at": None,
        "elapsed_ms": None,
        "error": None,
        "traceback": None,
        "_t0": time.perf_counter(),
    }
    app.state.startup_steps.append(step)
    return step


def _finish_step(step: dict, status: str = "Complete", error: Optional[str] = None) -> None:
    step["status"] = status
    step["ended_at"] = _iso_now()
    step["elapsed_ms"] = round((time.perf_counter() - step.get("_t0", time.perf_counter())) * 1000, 2)
    budget_ms = STARTUP_PHASE_BUDGET_MS.get(str(step.get("name", "")))
    step["budget_ms"] = budget_ms
    if budget_ms is None:
        step["budget_status"] = "NotApplicable"
    elif float(step["elapsed_ms"]) <= float(budget_ms):
        step["budget_status"] = "WithinBudget"
    else:
        step["budget_status"] = "OverBudget"
    if error:
        step["error"] = error
    step.pop("_t0", None)


def _fail_step(step: dict, exc: Exception) -> None:
    step["traceback"] = traceback.format_exc(limit=10)
    _finish_step(step, status="Failed", error=str(exc))


def _record_router(
    name: str,
    prefix: str,
    ok: bool,
    error: Optional[str] = None,
    optional: bool = False,
) -> None:
    app.state.router_load_report.append(
        {
            "name": name,
            "prefix": prefix,
            "ok": ok,
            "error": error,
            "optional": optional,
        }
    )


def _split_router_failures() -> tuple[list[dict], list[dict]]:
    failed = [r for r in app.state.router_load_report if not r.get("ok")]
    critical = [r for r in failed if not r.get("optional")]
    optional = [r for r in failed if r.get("optional")]
    return critical, optional

# Include routers from routes/ directory
from app.bootstrap.routers import include_default_routers  # noqa: E402

include_default_routers(
    app,
    protected_dependencies=protected_dependencies,
    logger=logger,
    record_router=_record_router,
)

# Web GUI migration Phase 1: Serve React frontend at /web (SPA mode)
try:
    import os
    from fastapi.staticfiles import StaticFiles

    dist_path = "frontend/dist"
    assets_path = os.path.join(dist_path, "assets")
    if os.path.exists(dist_path):
        # SPA entrypoint
        app.mount("/web", StaticFiles(directory=dist_path, html=True), name="web_gui")
        # Vite build currently emits absolute /assets/* paths; serve them explicitly.
        if os.path.exists(assets_path):
            app.mount("/assets", StaticFiles(directory=assets_path), name="web_gui_assets")
        logger.info("Web GUI mounted at /web (with /assets)")
        _record_router("web_gui", "/web", True)
    else:
        logger.warning(f"Web GUI dist not found: {dist_path}")
        _record_router("web_gui", "/web", False, "dist missing", optional=True)
except Exception as e:
    logger.warning(f"Failed to mount web GUI: {e}")
    _record_router("web_gui", "/web", False, str(e), optional=True)


async def _taskmaster_scheduler_loop() -> None:
    from app.bootstrap.lifecycle import taskmaster_scheduler_loop  # noqa: E402

    await taskmaster_scheduler_loop(logger=logger)


def _module_available(module_name: str) -> bool:
    from diagnostics.startup_report import module_available  # noqa: E402

    return module_available(module_name)


def _timed_check(fn):
    from diagnostics.startup_report import timed_check  # noqa: E402

    return timed_check(fn)


def _service_checks() -> dict:
    from diagnostics.startup_report import service_checks  # noqa: E402

    return service_checks(api_key_enabled=bool(API_KEY_ENV))


def _environment_snapshot() -> dict:
    from diagnostics.startup_report import environment_snapshot  # noqa: E402

    return environment_snapshot()


def _build_info() -> dict:
    from diagnostics.startup_report import build_info  # noqa: E402

    return build_info()


def _migration_snapshot() -> dict:
    from diagnostics.startup_report import migration_snapshot  # noqa: E402

    return migration_snapshot()


def _build_startup_report() -> dict:
    from diagnostics.startup_report import build_startup_report  # noqa: E402

    report = build_startup_report(
        app=app,
        startup_enforced=True,
        required_production_agents=_required_production_agents(),
        api_key_enabled=bool(API_KEY_ENV),
        rate_limit_requests_per_minute=RATE_LIMIT_REQUESTS_PER_MINUTE,
    )
    report.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    report.setdefault("optional_dependencies", {})
    if "routers" in report and "items" not in report["routers"]:
        report["routers"]["items"] = getattr(app.state, "router_load_report", []) or []
    if "security" in report:
        report["security"].setdefault("rate_limit_per_minute", RATE_LIMIT_REQUESTS_PER_MINUTE)
        report["security"].setdefault("rate_limit_enabled", RATE_LIMIT_REQUESTS_PER_MINUTE > 0)
    return report


def _config_digest() -> str:
    keys = [
        "RATE_LIMIT_REQUESTS_PER_MINUTE",
        "TASKMASTER_SCHEDULER_INTERVAL_SECONDS",
        "TASKMASTER_SCHEDULER_MAX_DUE_PER_TICK",
        "ORGANIZER_LLM_PROVIDER",
        "ORGANIZER_LLM_MODEL",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "ENV",
    ]
    blob = "\n".join(f"{k}={os.getenv(k, '')}" for k in keys)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _tail_logs(lines: int = 200) -> dict:
    candidate = os.getenv("APP_LOG_FILE") or str(Path(__file__).resolve().parent / "logs" / "app.log")
    p = Path(candidate)
    if not p.exists() or not p.is_file():
        return {"available": False, "path": str(p), "lines": []}
    text = p.read_text(encoding="utf-8", errors="replace").splitlines()
    n = max(1, min(int(lines), 2000))
    return {"available": True, "path": str(p), "lines": text[-n:]}


async def _startup_services():
    """Initialize services and enforce strict production-agent readiness."""
    app.state.startup_steps = []
    step_config = _start_step("config_load")
    try:

        if STARTUP_OFFLINE_SAFE:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
            os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
            os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")

        from agents import get_agent_manager  # noqa: E402
        from core.container.service_container_impl import ProductionServiceContainer  # noqa: E402

        _finish_step(step_config)

        # Initialize tracing (non-fatal). Best-effort bootstrap using OpenTelemetry.
        try:
            from core.tracing import init_tracing  # noqa: E402
            init_tracing(app=app, service_name="smart_document_organizer")
            logger.info("Tracing initialized")
        except Exception as _tr_err:
            logger.warning(f"Tracing initialization skipped/failed: {_tr_err}")
    except Exception as e:
        _fail_step(step_config, e)
        logger.error(f"Startup self-check failed: {e}")
        _record_awareness("error", "startup_failed_config_load", {"error": str(e)})
        raise

    try:
        step_di = _start_step("dependency_injection")
        services = ProductionServiceContainer()
        app.state.services = services
        logger.info("Service container initialized")

        # Centralized bootstrap: register core runtime services
        try:
            from core.container import bootstrap  # noqa: E402

            await bootstrap.configure(services, app)
            logger.info("Service container bootstrap completed")
        except Exception as e:
            raise RuntimeError(f"Service container bootstrap failed: {e}") from e
        _finish_step(step_di)

        step_agents = _start_step("module_initialization")
        manager = get_agent_manager()
        if AGENTS_LAZY_INIT:
            initialized = False
            logger.info("Agent manager initialization deferred (AGENTS_LAZY_INIT=true)")
        else:
            if not hasattr(manager, "initialize"):
                raise RuntimeError("Production agent manager has no initialize() method")
            initialized = await manager.initialize()
            if not initialized:
                raise RuntimeError("Production agent manager failed to initialize")
        app.state.agent_manager = manager

        try:
            await services.register_instance(
                type(manager), manager, aliases=["agent_manager"]
            )
        except Exception as e:
            logger.warning(f"Agent manager registration failed: {e}")

        available = set()
        for key in getattr(manager, "agents", {}).keys():
            available.add(getattr(key, "value", str(key)).strip().lower())

        required = _required_production_agents()
        if initialized:
            missing = [agent for agent in required if agent not in available]
        else:
            missing = []

        memory_ready = False
        try:
            from mem_db.memory.unified_memory_manager import UnifiedMemoryManager  # noqa: E402

            mm = await services.get_service(UnifiedMemoryManager)
            memory_ready = mm is not None
        except Exception:
            memory_ready = False

        app.state.agent_startup = {
            "required": required,
            "available": sorted(available),
            "missing": missing,
            "deferred_required": required if not initialized else [],
            "memory_required": True,
            "memory_ready": memory_ready,
            "lazy_init": AGENTS_LAZY_INIT,
        }

        if not memory_ready:
            msg = "Unified memory manager not available (required)"
            raise RuntimeError(msg)

        if missing:
            msg = (
                "Missing required production agents: "
                + ", ".join(missing)
                + f" (available: {sorted(available)})"
            )
            raise RuntimeError(msg)
        else:
            logger.info("Production agent startup check passed")
        _finish_step(step_agents)

        step_plugins = _start_step("plugin_loading")
        failed_critical, failed_optional = _split_router_failures()
        if failed_critical:
            raise RuntimeError(
                f"Router/plugin load failures: critical={failed_critical} optional={failed_optional}"
            )
        if failed_optional:
            logger.warning("Optional router/plugin load failures: %s", failed_optional)
        plugin_status = "Complete"
        plugin_error = None
        _finish_step(step_plugins, status=plugin_status, error=plugin_error)

        step_schema = _start_step("schema_validation")
        try:
            db_path = Path(__file__).resolve().parent / "mem_db" / "data" / "documents.db"
            con = sqlite3.connect(str(db_path))
            cur = con.cursor()
            cur.execute("PRAGMA quick_check;")
            quick_check = cur.fetchone()
            con.close()
            if quick_check and str(quick_check[0]).lower() != "ok":
                raise RuntimeError(f"PRAGMA quick_check failed: {quick_check}")
            _finish_step(step_schema)
        except Exception as e:
            _fail_step(step_schema, e)
            raise

        step_migrations = _start_step("migration_checks")
        try:
            db_path = Path(__file__).resolve().parent / "mem_db" / "data" / "documents.db"
            con = sqlite3.connect(str(db_path))
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='organization_proposals'")
            proposal_table = cur.fetchone()
            con.close()
            if not proposal_table:
                raise RuntimeError("Expected table 'organization_proposals' not found")
            _finish_step(step_migrations)
        except Exception as e:
            _fail_step(step_migrations, e)
            raise

        # Start internal TaskMaster scheduler loop
        app.state.taskmaster_scheduler_task = asyncio.create_task(_taskmaster_scheduler_loop())
        logger.info("TaskMaster scheduler loop started")

        app.state.startup_report = _build_startup_report()
        logger.info("Startup compliance report: %s", json.dumps(app.state.startup_report))
        _record_awareness(
            "info",
            "startup_completed",
            {
                "routers_loaded": app.state.startup_report.get("routers", {}).get("loaded"),
                "routers_total": app.state.startup_report.get("routers", {}).get("total"),
            },
        )

    except Exception as e:
        for step in app.state.startup_steps:
            if step.get("status") == "Running":
                _fail_step(step, e)
                break
        logger.error(f"Startup self-check failed: {e}")
        _record_awareness("error", "startup_failed", {"error": str(e)})
        raise

async def _shutdown_services():
    """Cleanup services on shutdown."""
    t = getattr(app.state, "taskmaster_scheduler_task", None)
    if t is not None:
        try:
            t.cancel()
            await t
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        app.state.taskmaster_scheduler_task = None

    services = getattr(app.state, "services", None)
    if services and hasattr(services, "shutdown"):
        try:
            await services.shutdown()
        except Exception as e:
            logger.warning(f"Service container shutdown failed: {e}")
    app.state.agent_manager = None


def _is_wsl_runtime() -> bool:
    if os.getenv("WSL_DISTRO_NAME"):
        return True
    try:
        text = Path("/proc/version").read_text(encoding="utf-8", errors="replace").lower()
        return "microsoft" in text or "wsl" in text
    except Exception:
        return False


def _is_headless_runtime() -> bool:
    if str(os.getenv("CI", "")).strip().lower() in {"1", "true", "yes", "on"}:
        return True
    has_display = bool(os.getenv("DISPLAY")) or bool(os.getenv("WAYLAND_DISPLAY"))
    if not has_display:
        return True
    return False


def _resolve_launch_mode(
    *,
    backend_requested: bool,
    gui_requested: bool,
    startup_profile: str,
    headless: bool,
) -> str:
    if backend_requested:
        return "backend"
    if gui_requested:
        return "gui"
    profile = startup_profile.strip().lower()
    if profile in {"api", "minimal"}:
        return "backend"
    if profile == "gui":
        return "gui"
    if headless:
        return "backend"
    return "gui"


def _backend_readiness_urls(port: int = 8000) -> list[str]:
    base = f"http://127.0.0.1:{port}"
    return [
        f"{base}/api/health",
        f"{base}/api/startup/report",
        f"{base}/api/health/details",
    ]


def _wait_for_backend(
    urls: list[str],
    timeout_s: int = 120,
    initial_interval_s: float = 0.25,
    max_interval_s: float = 2.0,
) -> bool:
    deadline = time.monotonic() + max(1, int(timeout_s))
    interval = max(0.1, float(initial_interval_s))
    max_interval = max(interval, float(max_interval_s))
    while time.monotonic() < deadline:
        for url in urls:
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if 200 <= int(response.status) < 300:
                        return True
            except Exception:
                continue
        time.sleep(interval)
        interval = min(max_interval, interval * 1.5)
    return False

@app.middleware("http")
async def _rate_limit_middleware(request: Request, call_next):
    if RATE_LIMIT_REQUESTS_PER_MINUTE > 0 and request.url.path not in {"/", "/api/health"}:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        client_host = forwarded or (request.client.host if request.client else "unknown")
        allowed, retry_after = await _rate_limit_check(client_host)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": "rate_limited",
                    "detail": "Rate limit exceeded",
                    "retry_after_seconds": round(retry_after, 2),
                    "limit_per_minute": RATE_LIMIT_REQUESTS_PER_MINUTE,
                },
                headers={"Retry-After": str(max(1, int(retry_after)))},
            )
    return await call_next(request)


@app.middleware("http")
async def _metrics_middleware(request: Request, call_next):
    metrics = app.state.metrics
    path = request.url.path
    method = request.method
    try:
        metrics["requests_total"] += 1
        metrics["per_path"][path] = metrics["per_path"].get(path, 0) + 1
        metrics["per_method"][method] = metrics["per_method"].get(method, 0) + 1
    except Exception:
        pass
    response: Response = await call_next(request)
    return response


@app.get("/")
async def root():
    return {"message": "Welcome to the Smart Document Organizer API"}


@app.get("/api/startup/report")
async def startup_report():
    report = getattr(app.state, "startup_report", None) or _build_startup_report()
    return {"success": True, "report": report}


@app.get("/api/startup/steps")
async def startup_steps():
    report = getattr(app.state, "startup_report", None) or _build_startup_report()
    return {"success": True, "items": report.get("startup_steps", [])}


@app.get("/api/startup/services")
async def startup_services():
    return {"success": True, **_service_checks()}


@app.get("/api/startup/environment")
async def startup_environment():
    return {"success": True, "snapshot": _environment_snapshot()}


@app.get("/api/startup/migrations")
async def startup_migrations():
    return {"success": True, **_migration_snapshot()}


@app.get("/api/startup/diagnostics/export")
async def startup_diagnostics_export():
    return {
        "success": True,
        "exported_at": _iso_now(),
        "config_digest": _config_digest(),
        "report": _build_startup_report(),
        "awareness_events": (getattr(app.state, "awareness_events", []) or [])[-100:],
    }


@app.get("/api/startup/logs/tail")
async def startup_logs_tail(lines: int = 200):
    out = _tail_logs(lines=lines)
    return {"success": True, **out}


@app.get("/api/startup/awareness")
async def startup_awareness(limit: int = 50):
    services = _service_checks().get("items", [])
    failed = [s for s in services if s.get("status") == "Failed"]
    slow = [s for s in services if isinstance(s.get("latency_ms"), (int, float)) and s.get("latency_ms", 0) > 1000]
    level = "OK"
    if failed:
        level = "FAIL"
    elif slow:
        level = "DEGRADED"
    return {
        "success": True,
        "level": level,
        "uptime_seconds": round(max(0.0, time.time() - float(getattr(app.state, "boot_time", time.time()))), 2),
        "failed_services": failed,
        "slow_services": slow,
        "events": (getattr(app.state, "awareness_events", []) or [])[-max(1, min(limit, 500)):],
    }


@app.get("/api/startup/control")
async def startup_control_state():
    restart_supported = str(os.getenv("ALLOW_STARTUP_RESTART_HOOK", "0")).strip().lower() in {"1", "true", "yes", "on"}
    log_meta = _tail_logs(lines=1)
    return {
        "success": True,
        "safe_shutdown": True,
        "restart_supported": restart_supported,
        "open_logs_supported": bool(log_meta.get("available")),
        "debug_mode": bool(getattr(app.state, "debug_mode", False)),
    }


@app.post("/api/startup/control/debug")
async def startup_control_debug(payload: dict):
    enabled = bool(payload.get("enabled", False))
    app.state.debug_mode = enabled
    _record_awareness("info", "debug_mode_changed", {"enabled": enabled})
    return {"success": True, "debug_mode": enabled}


@app.post("/api/startup/control/retry-check")
async def startup_control_retry_check(payload: dict):
    check = str(payload.get("check", "services")).strip().lower()
    if check == "services":
        out = _service_checks()
    elif check == "environment":
        out = {"snapshot": _environment_snapshot()}
    elif check == "migrations":
        out = _migration_snapshot()
    else:
        raise HTTPException(status_code=400, detail="check must be one of: services, environment, migrations")
    _record_awareness("info", "retry_check_executed", {"check": check})
    return {"success": True, "check": check, "result": out}


@app.post("/api/startup/control/restart")
async def startup_control_restart(payload: dict):
    allow = str(os.getenv("ALLOW_STARTUP_RESTART_HOOK", "0")).strip().lower() in {"1", "true", "yes", "on"}
    if not allow:
        raise HTTPException(status_code=403, detail="restart hook disabled by policy")
    delay = max(0, min(int(payload.get("delay_seconds", 1)), 30))
    _record_awareness("warning", "restart_requested", {"delay_seconds": delay})
    raise HTTPException(status_code=501, detail="restart hook allowed but not wired in this runtime")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Document Organizer launcher")
    parser.add_argument(
        "--check-integrity",
        action="store_true",
        help="Run static integrity checks and exit",
    )
    parser.add_argument(
        "--layer",
        default="h1",
        choices=list(INTEGRITY_LAYER_TARGETS.keys()),
        help="Integrity target layer",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output JSON report path for integrity checks",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON-only integrity output (single line)",
    )
    parser.add_argument(
        "--backend",
        action="store_true",
        help="Start backend API instead of GUI dashboard",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Start GUI dashboard mode explicitly",
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("STARTUP_PROFILE", STARTUP_PROFILE),
        choices=["api", "minimal", "full", "gui"],
        help="Startup profile (api|minimal|full|gui)",
    )
    args = parser.parse_args()
    if args.check_integrity:
        raise SystemExit(
            _run_integrity_check(
                layer=str(args.layer),
                output=str(args.output or ""),
                json_only=bool(args.json),
            )
        )

    selected_mode = _resolve_launch_mode(
        backend_requested=bool(args.backend),
        gui_requested=bool(args.gui),
        startup_profile=str(args.profile),
        headless=_is_headless_runtime(),
    )
    STARTUP_PROFILE = str(args.profile).strip().lower()
    if STARTUP_PROFILE not in {"api", "minimal", "full", "gui"}:
        STARTUP_PROFILE = "full"
    if _agents_lazy_env is None:
        AGENTS_LAZY_INIT = True
    if _offline_safe_env is None:
        STARTUP_OFFLINE_SAFE = True
    app.state.startup_profile = STARTUP_PROFILE
    app.state.agents_lazy_init = AGENTS_LAZY_INIT
    app.state.startup_offline_safe = STARTUP_OFFLINE_SAFE

    if selected_mode == "backend":
        import uvicorn  # noqa: E402
        
        # --- Port Sovereignty: Self-Healing Port Lock ---
        def _clear_port(port: int):
            import subprocess
            if os.name != "nt":
                return
            try:
                # Find PIDs on the target port
                cmd = f"netstat -ano | findstr :{port} | findstr LISTENING"
                output = subprocess.check_output(cmd, shell=True).decode()
                for line in output.splitlines():
                    if "LISTENING" in line:
                        pid = line.strip().split()[-1]
                        if pid and int(pid) > 0:
                            logger.info(f"Port {port} occupied by PID {pid}. Reclaiming...")
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, check=False)
            except Exception:
                pass # Port likely clear or netstat failed

        _clear_port(8000)

        logger.info("Starting backend API on port 8000 (profile=%s)...", STARTUP_PROFILE)
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        logger.info("Starting GUI dashboard...")
        backend_proc = None
        backend_urls = _backend_readiness_urls(port=8000)
        if not _wait_for_backend(backend_urls, timeout_s=2, initial_interval_s=0.25, max_interval_s=0.5):
            logger.info("Starting backend for GUI...")
            backend_proc = subprocess.Popen(
                [sys.executable, __file__, "--backend"],
                cwd=os.path.dirname(__file__) or None,
            )
            launch_timeout_s = int(os.getenv("GUI_BACKEND_START_TIMEOUT_SECONDS", "120"))
            if not _wait_for_backend(
                backend_urls,
                timeout_s=launch_timeout_s,
                initial_interval_s=0.25,
                max_interval_s=2.0,
            ):
                raise RuntimeError("Backend readiness check failed before GUI launch")

            def _cleanup_backend() -> None:
                if backend_proc is None:
                    return
                try:
                    if backend_proc.poll() is None:
                        backend_proc.terminate()
                except Exception:
                    pass

            atexit.register(_cleanup_backend)
        else:
            logger.info("Backend already running, launching GUI only...")

        os.environ["GUI_SKIP_WSL_BACKEND_START"] = "1"
        logger.info("Starting GUI dashboard...")
        try:
            try:
                from gui.professional_manager import main as gui_main  # noqa: E402
            except ImportError:
                # Legacy compatibility path while gui_dashboard wrapper still exists.
                from gui.gui_dashboard import launch_professional_manager as gui_main  # type: ignore # noqa: E402
            gui_main()
        except Exception:
            logger.exception("Failed to start GUI dashboard")
            raise
