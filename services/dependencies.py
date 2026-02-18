"""Typed dependency helpers for FastAPI routes and service-layer wiring."""

from __future__ import annotations

from typing import Any, Optional, Type, TypeVar

from fastapi import HTTPException, Request

from agents.production_agent_manager import ProductionAgentManager
from config.configuration_manager import ConfigurationManager
from mem_db.database import DatabaseManager
from services.memory_service import MemoryService

try:
    from mem_db.vector_store.unified_vector_store import UnifiedVectorStore
except Exception:  # pragma: no cover
    UnifiedVectorStore = Any  # type: ignore

T = TypeVar("T")


async def resolve_typed_service(
    request: Request,
    service_type: Type[T],
) -> Optional[T]:
    """Resolve a service by class/type from app.state.services."""
    services = getattr(request.app.state, "services", None)
    if services is not None and hasattr(services, "get_service"):
        try:
            resolved = await services.get_service(service_type)
            if resolved is not None:
                return resolved
        except Exception:
            pass

    return None


async def get_config_manager_dep(request: Request) -> ConfigurationManager:
    return await _strict_service(
        request,
        ConfigurationManager,
        "config_manager",
        "configuration_manager",
        "config",
    )


async def get_database_manager_dep(request: Request) -> Optional[DatabaseManager]:
    """Return database manager from container."""
    return await _strict_service(request, DatabaseManager, "database_manager")


async def get_vector_store_dep(request: Request):
    """Return vector store from container."""
    return await _strict_service(request, UnifiedVectorStore, "vector_store")  # type: ignore[arg-type]


async def get_knowledge_manager_dep(request: Request):
    from mem_db.knowledge.unified_knowledge_graph_manager import (  # noqa: E402
        UnifiedKnowledgeGraphManager,
    )
    return await _strict_service(
        request,
        UnifiedKnowledgeGraphManager,
        "knowledge_manager",
    )


async def get_memory_service_dep(request: Request) -> Optional[MemoryService]:
    return await _strict_service(request, MemoryService, "memory_service")


async def get_agent_manager_dep(request: Request):
    """Return agent manager from app/container."""
    return await _strict_service(request, ProductionAgentManager, "agent_manager")


# --- Strict container-backed deps (no module-level fallback) ---
async def _strict_service(request: Request, *service_keys):
    services = getattr(request.app.state, "services", None)
    if services is None or not hasattr(services, "get_service"):
        raise HTTPException(status_code=503, detail="Service container unavailable")

    # Try by type first, then string alias
    for key in service_keys:
        try:
            svc = await services.get_service(key)
            if svc is not None:
                return svc
        except Exception:
            pass
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
