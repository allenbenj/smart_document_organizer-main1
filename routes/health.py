import logging
import os  # noqa: E402
import time  # noqa: E402
from typing import Any, Dict  # noqa: E402

from fastapi import APIRouter, Depends, Request  # noqa: E402

from agents.base.agent_registry import AgentRegistry  # noqa: E402
from config.configuration_manager import ConfigurationManager  # noqa: E402
from mem_db.memory.unified_memory_manager import UnifiedMemoryManager  # noqa: E402
from services.dependencies import (  # noqa: E402
    get_agent_manager_dep,
    get_database_manager_dep,
    get_vector_store_dep,
    resolve_typed_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> Dict[str, Any]:
    """Canonical lightweight health endpoint."""
    startup = getattr(request.app.state, "agent_startup", None) or {}
    memory_ready = bool(startup.get("memory_ready", False))
    missing_required = startup.get("missing") or []
    deferred_required = startup.get("deferred_required") or []
    agents_ready = memory_ready and not missing_required and not deferred_required
    status = "healthy" if agents_ready else "degraded"
    return {
        "status": status,
        "message": "Smart Document Organizer API is running",
        "memory": {"required": True, "ready": memory_ready},
        "agents": {
            "ready": agents_ready,
            "missing_required": missing_required,
            "deferred_required": deferred_required,
        },
        "agent_startup": startup,
    }


@router.get("/health/details")
async def health_details(
    request: Request,
    vector_store=Depends(get_vector_store_dep),
    agent_manager=Depends(get_agent_manager_dep),
    db_manager=Depends(get_database_manager_dep),
) -> Dict[str, Any]:  # noqa: C901
    started = time.time()
    # Basic process health; extend with checks to DB, vector store, agents
    uptime_ms = 0
    try:
        # Placeholder for a real uptime mechanism
        uptime_ms = int((time.time() - started) * 1000)
    except Exception:
        pass
    components: Dict[str, Any] = {"api": {"ok": True}}

    # Auth status
    components["auth"] = {"enabled": bool(os.getenv("API_KEY", ""))}

    # Vector store status (timed)
    try:
        t0 = time.perf_counter()
        store = vector_store
        if store is None:
            components["vector_store"] = {
                "available": False,
                "initialized": False,
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            }
        else:
            try:
                ok = await store.initialize()
            except Exception:
                ok = False
            health = await store.health_check()
            stats = await store.get_statistics()
            components["vector_store"] = {
                "available": True,
                "initialized": bool(ok),
                "state": health.get("state"),
                "healthy": bool(health.get("healthy", False)),
                "stats": stats,
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            }
    except Exception as e:
        logger.error(f"Health vector store check failed: {e}")
        components["vector_store"] = {"available": False, "error": "check_failed"}

    # Agent registry status
    try:
        registry = await resolve_typed_service(request, AgentRegistry)
        if registry is None:
            components["agents"] = {"enabled": False}
        else:
            stats = getattr(registry, "registry_stats", {}) or {}
            components["agents"] = {
                "enabled": True,
                "registered": len(getattr(registry, "registered_agents", {})),
                "active_instances": len(getattr(registry, "active_instances", {})),
                "stats": stats,
            }
    except Exception as e:
        logger.error(f"Health agent registry check failed: {e}")
        components["agents"] = {"enabled": False, "error": "check_failed"}

    # Advanced readiness via production agent manager
    try:
        sys_health = await agent_manager.get_system_health()
        components["advanced"] = {
            "ready": bool(sys_health.get("system_initialized"))
            and bool(sys_health.get("production_agents_available")),
            "production_agents_available": bool(
                sys_health.get("production_agents_available")
            ),
            "initialized": bool(sys_health.get("system_initialized")),
            "timestamp": sys_health.get("timestamp"),
        }
    except Exception as e:
        components["advanced"] = {"ready": False, "error": str(e)}

    # Database status (timed)
    try:
        t0 = time.perf_counter()
        db = db_manager
        ok = False
        try:
            with db.get_connection() as conn:  # type: ignore[attr-defined]
                conn.execute("SELECT 1")
                ok = True
        except Exception:
            ok = False
        components["database"] = {
            "ok": ok,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }
    except Exception as e:
        logger.error(f"Health database check failed: {e}")
        components["database"] = {"ok": False, "error": "check_failed"}

    # Memory status (required)
    try:
        services = getattr(request.app.state, "services", None)
        mm = None
        if services is not None:
            mm = await services.get_service(UnifiedMemoryManager)
            if mm is None:
                mm = await services.get_service("memory_manager")
        components["memory"] = {
            "required": True,
            "ready": mm is not None,
            "type": type(mm).__name__ if mm is not None else None,
        }
    except Exception as e:
        components["memory"] = {"required": True, "ready": False, "error": str(e)}

    # Config surface (env + selected flags)
    try:
        cfg: ConfigurationManager = await resolve_typed_service(
            request, ConfigurationManager
        )
        if cfg:
            components["config"] = {
                "env": cfg.get_str("env", "development"),
                "agents": {
                    "enable_registry": cfg.get_bool("agents.enable_registry", False),
                    "enable_legal_reasoning": cfg.get_bool(
                        "agents.enable_legal_reasoning", False
                    ),
                    "enable_entity_extractor": cfg.get_bool(
                        "agents.enable_entity_extractor", False
                    ),
                    "enable_irac": cfg.get_bool("agents.enable_irac", False),
                    "enable_toulmin": cfg.get_bool("agents.enable_toulmin", False),
                    "cache_ttl_seconds": cfg.get_int("agents.cache_ttl_seconds", 300),
                },
                "vector": {
                    "dimension": cfg.get_int("vector.dimension", 384),
                },
            }
    except Exception:
        pass

    startup = getattr(request.app.state, "agent_startup", None) or {}
    has_missing = bool(startup.get("missing"))
    has_deferred = bool(startup.get("deferred_required"))
    memory_ready = bool(components.get("memory", {}).get("ready"))
    overall = "healthy" if (memory_ready and not has_missing and not has_deferred) else "degraded"
    return {
        "status": overall,
        "components": components,
        "uptime_ms": uptime_ms,
        "agent_startup": startup,
    }


@router.get("/metrics")
async def metrics(request: Request) -> Dict[str, Any]:
    """Return simple in-memory API metrics collected by middleware."""
    metrics = getattr(request.app.state, "metrics", None)
    if not isinstance(metrics, dict):
        return {"enabled": False}
    return {"enabled": True, **metrics}
