"""GUI facade for production agent manager.

Legacy GUI-specific manager has been retired. GUI code should use this module,
which delegates to the shared production manager used by the API layer.
"""

from typing import Any

from agents import get_agent_manager as _get_production_manager


def get_agent_manager() -> Any:
    """Return the shared production manager singleton."""
    return _get_production_manager()


__all__ = ["get_agent_manager"]
