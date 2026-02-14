"""Shared helpers for agent route submodules."""

import os
from typing import Any, List, Optional

from fastapi import HTTPException, Request

from services.agent_service import AgentService
from services.dependencies import get_memory_service_dep

DEFAULT_REQUIRED_PRODUCTION_AGENTS = [
    "document_processor",
    "entity_extractor",
    "legal_reasoning",
    "irac_analyzer",
]


def required_production_agents() -> List[str]:
    raw = os.getenv(
        "REQUIRED_PRODUCTION_AGENTS",
        ",".join(DEFAULT_REQUIRED_PRODUCTION_AGENTS),
    )
    vals = [v.strip().lower() for v in raw.split(",") if v.strip()]
    out: List[str] = []
    seen = set()
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


async def get_strict_production_manager(request: Request):
    startup = getattr(request.app.state, "agent_startup", None) or {}
    if startup.get("strict", True) and startup.get("missing"):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "production_startup_guard_failed",
                "missing": startup.get("missing", []),
                "required": startup.get("required", []),
                "available": startup.get("available", []),
            },
        )

    from services.dependencies import get_agent_manager_strict_dep  # noqa: E402

    manager = await get_agent_manager_strict_dep(request)
    if hasattr(manager, "initialize"):
        ok = await manager.initialize()
        if not ok:
            raise HTTPException(
                status_code=503,
                detail={"error": "production_manager_initialize_failed"},
            )

    required = required_production_agents()
    available = {
        getattr(key, "value", str(key)).strip().lower()
        for key in getattr(manager, "agents", {}).keys()
    }
    missing = [a for a in required if a not in available]

    request.app.state.agent_startup = {
        "strict": True,
        "required": required,
        "available": sorted(available),
        "missing": missing,
    }
    if missing:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "required_production_agents_missing",
                "missing": missing,
                "required": required,
                "available": sorted(available),
            },
        )

    return manager


async def get_memory_service(request: Request) -> Optional[Any]:
    return await get_memory_service_dep(request)


async def get_agent_service(request: Request) -> AgentService:
    """Get the AgentService instance."""
    manager = await get_strict_production_manager(request)
    return AgentService(manager)
