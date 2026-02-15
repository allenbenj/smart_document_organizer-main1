"""
Smart Document Organizer - FastAPI Application Entry Point
=========================================================

A Legal AI platform for intelligent document analysis, entity extraction,
legal reasoning, and document organization.
"""

import asyncio
import json
import hashlib
import logging
import os  # noqa: E402
import sqlite3
import sys  # noqa: E402
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional  # noqa: E402

from fastapi import Depends, FastAPI, Header, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse, Response  # noqa: E402

# Add current directory to Python path for absolute imports
sys.path.insert(0, os.path.dirname(__file__))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY_ENV = os.getenv("API_KEY", "")
STRICT_PRODUCTION_STARTUP = (
    os.getenv("STRICT_PRODUCTION_STARTUP", "1").strip().lower()
    not in {"0", "false", "no", "off"}
)
DEFAULT_REQUIRED_PRODUCTION_AGENTS = [
    "document_processor",
    "entity_extractor",
    "legal_reasoning",
    "irac_analyzer",
]


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
    if error:
        step["error"] = error
    step.pop("_t0", None)


def _fail_step(step: dict, exc: Exception) -> None:
    step["traceback"] = traceback.format_exc(limit=10)
    _finish_step(step, status="Failed", error=str(exc))


def _record_router(name: str, prefix: str, ok: bool, error: Optional[str] = None) -> None:
    app.state.router_load_report.append(
        {
            "name": name,
            "prefix": prefix,
            "ok": ok,
            "error": error,
        }
    )

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
        _record_router("web_gui", "/web", False, "dist missing")
except Exception as e:
    logger.warning(f"Failed to mount web GUI: {e}")
    _record_router("web_gui", "/web", False, str(e))


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
        strict_startup=STRICT_PRODUCTION_STARTUP,
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
        "STRICT_PRODUCTION_STARTUP",
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
        from agents import get_agent_manager  # noqa: E402
        from core.container.service_container_impl import ProductionServiceContainer  # noqa: E402

        _finish_step(step_config)
    except Exception as e:
        _fail_step(step_config, e)
        logger.error(f"Startup self-check failed: {e}")
        _record_awareness("error", "startup_failed_config_load", {"error": str(e)})
        if STRICT_PRODUCTION_STARTUP:
            raise
        return

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
            logger.warning(f"Service bootstrap failed: {e}")
        _finish_step(step_di)

        step_agents = _start_step("module_initialization")
        manager = get_agent_manager()
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
        missing = [agent for agent in required if agent not in available]

        memory_ready = False
        try:
            from mem_db.memory.unified_memory_manager import UnifiedMemoryManager  # noqa: E402

            mm = await services.get_service(UnifiedMemoryManager)
            memory_ready = mm is not None
        except Exception:
            memory_ready = False

        app.state.agent_startup = {
            "strict": STRICT_PRODUCTION_STARTUP,
            "required": required,
            "available": sorted(available),
            "missing": missing,
            "memory_required": True,
            "memory_ready": memory_ready,
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
            if STRICT_PRODUCTION_STARTUP:
                raise RuntimeError(msg)
            logger.warning(msg)
        else:
            logger.info("Production agent startup check passed")
        _finish_step(step_agents)

        step_plugins = _start_step("plugin_loading")
        failed_routers = [r for r in app.state.router_load_report if not r.get("ok")]
        if failed_routers and STRICT_PRODUCTION_STARTUP:
            raise RuntimeError(f"Router/plugin load failures: {failed_routers}")
        _finish_step(step_plugins, status="Complete" if not failed_routers else "Failed", error=str(failed_routers) if failed_routers else None)

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
            if STRICT_PRODUCTION_STARTUP:
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
            if STRICT_PRODUCTION_STARTUP:
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
        if STRICT_PRODUCTION_STARTUP:
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
    import uvicorn  # noqa: E402

    logger.info("Starting the application...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
