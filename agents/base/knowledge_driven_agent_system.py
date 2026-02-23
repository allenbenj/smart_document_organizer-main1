"""Knowledge-driven agent system integration module."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


class KnowledgeDrivenAgentSystem:
    """Coordinates knowledge-backed behaviors for agent subsystems."""

    def __init__(self, service_container: Any, knowledge_base_path: Path) -> None:
        self.service_container = service_container
        self.knowledge_base_path = Path(knowledge_base_path)
        self.initialized = False

    async def initialize(self) -> None:
        if not self.knowledge_base_path.exists():
            raise RuntimeError(
                f"Knowledge base path does not exist: {self.knowledge_base_path}"
            )
        self.initialized = True

    async def health_check(self) -> Dict[str, Any]:
        return {
            "initialized": self.initialized,
            "knowledge_base_path": str(self.knowledge_base_path),
            "knowledge_base_exists": self.knowledge_base_path.exists(),
        }

    async def shutdown(self) -> None:
        self.initialized = False
