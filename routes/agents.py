"""Top-level agents router composed from decomposed subrouters."""

from fastapi import APIRouter

from .agent_routes.analysis import router as analysis_router
from .agent_routes.management import router as management_router
from .agent_routes.memory import router as memory_router

router = APIRouter()
router.include_router(management_router)
router.include_router(analysis_router)
router.include_router(memory_router)

__all__ = ["router"]
