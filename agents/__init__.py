"""
Agent Manager Module

Provides a unified interface for accessing agent managers.
Production-only manager access with strict contract checks.
"""

import logging
from typing import List, Optional  # noqa: E402

from .core.manager_interface import ensure_manager_contract  # noqa: E402
from .core.models import AgentType  # noqa: E402

logger = logging.getLogger(__name__)

try:
    from .production_agent_manager import (  # noqa: E402
        ProductionAgentManager as _ProdMgr,
    )
    PRODUCTION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Production agent manager not available: {e}")
    PRODUCTION_AVAILABLE = False
    _ProdMgr = None

_manager_singleton: Optional[_ProdMgr] = None
_use_production = True


def set_use_production(use_production: bool) -> None:
    """Set production mode flag (production-only system)."""
    global _use_production
    if not use_production:
        raise RuntimeError("Fallback/simple agent mode is disabled; production-only.")
    _use_production = use_production
    logger.info("Agent manager mode set to: production")


def get_agent_manager():
    """
    Return an agent manager instance.

    Returns the production manager only.
    """
    if not PRODUCTION_AVAILABLE:
        raise RuntimeError("Production agent manager import failed.")
    if not _use_production:
        raise RuntimeError("Fallback/simple agent mode is disabled.")

    global _manager_singleton
    if _manager_singleton is None:
        _manager_singleton = _ProdMgr()
        ensure_manager_contract(_manager_singleton)
    return _manager_singleton


async def get_initialized_agent_manager():
    """
    Get a fully initialized agent manager.

    This is the preferred way to get an agent manager in async contexts.
    """
    manager = get_agent_manager()
    if hasattr(manager, 'initialize'):
        await manager.initialize()
    return manager


def get_simple_agent_manager(api_base_url: str = "http://localhost:8000/api"):  # noqa: ARG001
    """Simple manager is intentionally disabled in production-only mode."""
    raise RuntimeError("Simple agent manager is disabled; use production manager.")


def list_agent_types() -> List[str]:
    """List supported agent type identifiers."""
    if not PRODUCTION_AVAILABLE:
        raise RuntimeError("Production agent types unavailable.")
    return [t.value for t in AgentType]


def list_simple_agent_types() -> List[str]:
    """Simple agent mode is disabled."""
    raise RuntimeError("Simple agent types are disabled.")


__all__ = [
    "get_agent_manager",
    "get_initialized_agent_manager",
    "get_simple_agent_manager",
    "list_agent_types",
    "list_simple_agent_types",
    "set_use_production",
]
