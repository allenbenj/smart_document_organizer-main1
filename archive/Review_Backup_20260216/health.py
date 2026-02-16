from fastapi import APIRouter, Request
import time
import os
import logging
from typing import Any, Dict

from mem_db.vector_store import get_vector_store
from mem_db.database import get_database_manager
from config.configuration_manager import ConfigurationManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health/details")
async def health_details(request: Request) -> Dict[str, Any]:
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
        store = get_vector_store()
        if store is None:
            components["vector_store"] = {"available": False, "initialized": False, "latency_ms": int((time.perf_counter()-t0)*1000)}
        else:
            try:
                ok = await store.initialize()
            except Exception:
                ok = False
            state = getattr(store, "_state", None)
            stats = getattr(store, "_stats", {})
            components["vector_store"] = {
                "available": True,
                "initialized": bool(ok),
                "state": str(state) if state is not None else None,
                "stats": stats,
                "latency_ms": int((time.perf_counter()-t0)*1000),
            }
    except Exception as e:
        logger.error(f"Health vector store check failed: {e}")
        components["vector_store"] = {"available": False, "error": "check_failed"}

    # Agent registry status
    try:
        services = getattr(request.app.state, "services", None)
        registry = None
        if services is not None and hasattr(services, "get_service"):
            try:
                registry = await services.get_service("agent_registry")
            except Exception:
                registry = None
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
        from agents import get_agent_manager  # type: ignore
        mgr = get_agent_manager()
        sys_health = await mgr.get_system_health()
        components["advanced"] = {
            "ready": bool(sys_health.get("system_initialized")) and bool(sys_health.get("production_agents_available")),
            "production_agents_available": bool(sys_health.get("production_agents_available")),
            "initialized": bool(sys_health.get("system_initialized")),
            "timestamp": sys_health.get("timestamp"),
        }
    except Exception as e:
        components["advanced"] = {"ready": False, "error": str(e)}

    # Database status (timed)
    try:
        t0 = time.perf_counter()
        db = get_database_manager()
        ok = False
        try:
            with db.get_connection() as conn:  # type: ignore[attr-defined]
                conn.execute("SELECT 1")
                ok = True
        except Exception:
            ok = False
        components["database"] = {"ok": ok, "latency_ms": int((time.perf_counter()-t0)*1000)}
    except Exception as e:
        logger.error(f"Health database check failed: {e}")
        components["database"] = {"ok": False, "error": "check_failed"}

    # Config surface (env + selected flags)
    try:
        services = getattr(request.app.state, "services", None)
        cfg: ConfigurationManager = None  # type: ignore
        if services is not None and hasattr(services, "get_service"):
            try:
                cfg = await services.get_service("config_manager")
            except Exception:
                cfg = None  # type: ignore
        if cfg:
            components["config"] = {
                "env": cfg.get_str("env", "development"),
                "agents": {
                    "enable_registry": cfg.get_bool("agents.enable_registry", False),
                    "enable_legal_reasoning": cfg.get_bool("agents.enable_legal_reasoning", False),
                    "enable_entity_extractor": cfg.get_bool("agents.enable_entity_extractor", False),
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

    return {"status": "healthy", "components": components, "uptime_ms": uptime_ms}


@router.get("/metrics")
async def metrics(request: Request) -> Dict[str, Any]:
    """Return simple in-memory API metrics collected by middleware."""
    metrics = getattr(request.app.state, "metrics", None)
    if not isinstance(metrics, dict):
        return {"enabled": False}
    return {"enabled": True, **metrics}
