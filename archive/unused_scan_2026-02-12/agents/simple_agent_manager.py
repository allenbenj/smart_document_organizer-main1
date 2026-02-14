"""SimpleAgentManager removed.

This project is production-agent-only. Importing or using SimpleAgentManager
must fail fast to prevent partial/non-production execution paths.
"""

from typing import Any


class SimpleAgentManager:  # pragma: no cover
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError(
            "SimpleAgentManager has been removed. Use agents.get_agent_manager() "
            "for production mode."
        )


def get_agent_manager() -> SimpleAgentManager:  # pragma: no cover
    raise RuntimeError(
        "SimpleAgentManager has been removed. Use agents.get_agent_manager()."
    )


__all__ = ["SimpleAgentManager", "get_agent_manager"]
