"""Typed dependency helpers for FastAPI routes and service-layer wiring."""

from __future__ import annotations

from typing import Any, Callable, Optional, Type, TypeVar

from fastapi import Request

from agents import get_agent_manager
from agents.production_agent_manager import ProductionAgentManager
from config.configuration_manager import ConfigurationManager
from mem_db.database import DatabaseManager, get_database_manager
from mem_db.knowledge import get_knowledge_manager
from mem_db.vector_store import get_vector_store
from services.memory_service import MemoryService

try:
    from mem_db.vector_store.unified_vector_store import UnifiedVectorStore
except Exception:  # pragma: no cover
    UnifiedVectorStore = Any  # type: ignore

T = TypeVar("T")


async def resolve_typed_service(
    request: Request,
    service_type: Type[T],
    fallback_factory: Optional[Callable[[], T]] = None,
) -> Optional[T]:
    """Resolve a service by class/type from app.state.services with fallback."""
    services = getattr(request.app.state, "services", None)
    if services is not None and hasattr(services, "get_service"):
        try:
            resolved = await services.get_service(service_type)
            if resolved is not None:
                return resolved
        except Exception:
            pass

    if fallback_factory is not None:
        try:
            return fallback_factory()
        except Exception:
            return None

    return None


async def get_config_manager_dep(request: Request) -> ConfigurationManager:
    svc = await resolve_typed_service(
        request,
        ConfigurationManager,
        fallback_factory=ConfigurationManager,
    )
    return svc or ConfigurationManager()


async def get_database_manager_dep(request: Request) -> Optional[DatabaseManager]:
    """Return database manager from container when available, otherwise None."""
    svc = await resolve_typed_service(request, DatabaseManager)
    return svc


async def get_vector_store_dep(request: Request):
    """Return vector store from container when available, otherwise None."""
    svc = await resolve_typed_service(request, UnifiedVectorStore)  # type: ignore[arg-type]
    return svc


async def get_knowledge_manager_dep(request: Request):
    # Knowledge manager is optional in some environments.
    try:
        from mem_db.knowledge.unified_knowledge_graph_manager import (  # noqa: E402
            UnifiedKnowledgeGraphManager,
        )

        svc = await resolve_typed_service(request, UnifiedKnowledgeGraphManager)
        return svc
    except Exception:
        return None


async def get_memory_service_dep(request: Request) -> Optional[MemoryService]:
    return await resolve_typed_service(request, MemoryService)


async def get_agent_manager_dep(request: Request):
    """Return agent manager from app state or container when available, otherwise None."""
    manager = getattr(request.app.state, "agent_manager", None)
    if manager is not None:
        return manager

    services = getattr(request.app.state, "services", None)
    if services is not None and hasattr(services, "get_service"):
        try:
            resolved = await services.get_service(ProductionAgentManager)
            if resolved is not None:
                return resolved
            return await services.get_service("agent_manager")
        except Exception:
            pass
    return None


# --- Strict container-backed deps (no module-level fallback) ---
async def _strict_service(request: Request, *service_keys):
    services = getattr(request.app.state, "services", None)
    if services is None or not hasattr(services, "get_service"):
        # Controlled compatibility fallback for critical legacy string-key paths.
        lowered = {str(k).lower() for k in service_keys}
        if "database_manager" in lowered or any("databasemanager" in str(k).lower() for k in service_keys):
            try:
                return get_database_manager()
            except Exception:
                pass
        if "agent_manager" in lowered:
            manager = getattr(request.app.state, "agent_manager", None)
            if manager is not None:
                return manager
            try:
                return get_agent_manager()
            except Exception:
                pass

        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Service container unavailable")

    # Try by type first, then string alias
    for key in service_keys:
        try:
            svc = await services.get_service(key)
            if svc is not None:
                return svc
        except Exception:
            pass
    from fastapi import HTTPException

    raise HTTPException(status_code=503, detail=f"Service(s) not registered: {service_keys}")


async def get_database_manager_strict_dep(request: Request):
    from mem_db.database import DatabaseManager

    return await _strict_service(request, DatabaseManager, "database_manager")


async def get_vector_store_strict_dep(request: Request):
    try:
        from mem_db.vector_store.unified_vector_store import UnifiedVectorStore  # noqa: E402
    except Exception:  # pragma: no cover
        UnifiedVectorStore = object

    return await _strict_service(request, UnifiedVectorStore, "vector_store")


async def get_knowledge_manager_strict_dep(request: Request):
    try:
        from mem_db.knowledge.unified_knowledge_graph_manager import (  # noqa: E402
            UnifiedKnowledgeGraphManager,
        )
    except Exception:
        UnifiedKnowledgeGraphManager = object

    return await _strict_service(request, UnifiedKnowledgeGraphManager, "knowledge_manager")


async def get_agent_manager_strict_dep(request: Request):
    return await _strict_service(request, ProductionAgentManager, "agent_manager")
