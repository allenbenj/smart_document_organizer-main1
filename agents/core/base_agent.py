"""
Base Agent Module
=================

Provides the base agent class and result types for the agents subsystem.
"""

from abc import ABC, abstractmethod
from datetime import datetime  # noqa: E402
from typing import Any, Dict, Optional  # noqa: E402

from .models import AgentResult  # noqa: E402


class BaseAgent(ABC):
    """Abstract base class for all agents.

    Provides common interface and utilities for agent implementations.
    """

    def __init__(
        self,
        service_container: Optional[Any] = None,
        name: Optional[str] = None,
        agent_type: str = "base",
    ):
        """Initialize the base agent.

        Args:
            service_container: Optional service container for dependency injection
            name: Human-readable name for the agent
            agent_type: Type identifier for the agent
        """
        self.service_container = service_container
        self.name = name or self.__class__.__name__
        self.agent_type = agent_type
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the agent. Override in subclasses for async setup."""
        self._initialized = True

    def is_initialized(self) -> bool:
        """Check if the agent has been initialized."""
        return self._initialized

    @abstractmethod
    async def _process_task(self, task_data: Any, metadata: Dict[str, Any]) -> Any:
        """Process a task. Must be implemented by subclasses.

        Args:
            task_data: The task data to process
            metadata: Additional metadata for the task

        Returns:
            Processing result
        """

    async def process(
        self, data: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """Process data and return a result.

        Args:
            data: Input data to process
            metadata: Optional metadata for processing

        Returns:
            AgentResult with success/failure and data
        """
        start_time = datetime.now()
        metadata = metadata or {}

        try:
            result_data = await self._process_task(data, metadata)
            execution_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                success=True,
                data=result_data,
                processing_time=execution_time,
                agent_type=self.agent_type,
                metadata=metadata,
            )
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                success=False,
                error=str(e),
                processing_time=execution_time,
                agent_type=self.agent_type,
                metadata=metadata,
            )


__all__ = ["BaseAgent", "AgentResult"]
