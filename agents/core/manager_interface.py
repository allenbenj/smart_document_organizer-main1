"""Shared agent manager contract for production manager integrations."""

from typing import Any, Dict, List, Protocol, runtime_checkable

from agents.core.models import AgentResult, AgentType


@runtime_checkable
class AgentManagerProtocol(Protocol):
    async def initialize(self) -> bool: ...
    async def get_agent_status(self, agent_type: AgentType) -> Dict[str, Any]: ...
    async def get_system_health(self) -> Dict[str, Any]: ...
    def get_available_agents(self) -> List[str]: ...

    async def process_document(self, file_path: str, **kwargs: Any) -> AgentResult: ...
    async def extract_entities(self, text: str, **kwargs: Any) -> AgentResult: ...
    async def analyze_legal_reasoning(
        self, document_content: str, **kwargs: Any
    ) -> AgentResult: ...
    async def analyze_irac(self, document_text: str, **kwargs: Any) -> AgentResult: ...
    async def analyze_toulmin(
        self, document_content: str, **kwargs: Any
    ) -> AgentResult: ...


def ensure_manager_contract(manager: Any) -> None:
    """Fail fast if manager does not satisfy the minimum runtime contract."""
    required = [
        "initialize",
        "get_agent_status",
        "get_system_health",
        "get_available_agents",
        "process_document",
        "extract_entities",
        "analyze_legal_reasoning",
        "analyze_irac",
        "analyze_toulmin",
    ]
    missing = [name for name in required if not hasattr(manager, name)]
    if missing:
        raise RuntimeError(f"Agent manager contract violation; missing: {missing}")

