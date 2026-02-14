"""
Production Base Agent for Legal AI Platform
============================================

Provides a robust foundation for all AI agents with integrated monitoring,
error handling, and service container support. This is migrated from the
production system with full preservation of enterprise-grade features.
"""

import asyncio
import time  # noqa: E402
import uuid  # noqa: E402
from abc import ABC, abstractmethod  # noqa: E402
from datetime import datetime  # noqa: E402
from enum import Enum  # noqa: E402
from typing import Any, Dict, Optional, cast  # noqa: E402

structlog = None
try:
    import structlog  # type: ignore[reportMissingImports,import-not-found]  # noqa: E402

    logger = structlog.get_logger()
    STRUCTLOG_AVAILABLE = True
except ImportError:
    import logging  # noqa: E402

    logger = logging.getLogger(__name__)
    STRUCTLOG_AVAILABLE = False

from core.container.service_container_impl import ProductionServiceContainer  # noqa: E402
from mem_db.memory.memory_mixin import MemoryMixin  # noqa: E402
from agents.core.models import AgentResult  # noqa: E402


class _CompatLogger:
    """Wrap stdlib logger to accept structlog-style keyword context."""

    def __init__(self, base_logger):
        self._base = base_logger

    def info(self, message: str, **kwargs: Any) -> None:
        if kwargs:
            self._base.info(message, extra={"context": kwargs})
        else:
            self._base.info(message)

    def warning(self, message: str, **kwargs: Any) -> None:
        if kwargs:
            self._base.warning(message, extra={"context": kwargs})
        else:
            self._base.warning(message)

    def error(self, message: str, **kwargs: Any) -> None:
        if kwargs:
            self._base.error(message, extra={"context": kwargs})
        else:
            self._base.error(message)

    def debug(self, message: str, **kwargs: Any) -> None:
        if kwargs:
            self._base.debug(message, extra={"context": kwargs})
        else:
            self._base.debug(message)

    def bind(self, **kwargs: Any) -> "_CompatLogger":
        return self


class AgentStatus(Enum):
    """Agent execution status"""

    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class TaskPriority(Enum):
    """Task priority levels"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class BaseAgent(ABC, MemoryMixin):
    """
    Production base agent class with comprehensive features:
    - Service container integration
    - Memory capabilities through mixin
    - Monitoring and metrics
    - Error handling and resilience
    - Structured logging
    - Health monitoring
    """

    def __init__(
        self,
        services: ProductionServiceContainer,
        agent_name: str,
        agent_type: str = "base",
        timeout_seconds: float = 300.0,
    ):
        # Initialize base agent
        self.services = services
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.timeout_seconds = timeout_seconds

        # Initialize memory mixin
        MemoryMixin.__init__(self)

        # State management
        self.status = AgentStatus.IDLE
        self.current_task_id: Optional[str] = None
        self.start_time: Optional[datetime] = None

        # Setup logging with agent context
        if STRUCTLOG_AVAILABLE:
            self.logger = structlog.get_logger(f"agent.{agent_name}")
        else:
            self.logger = _CompatLogger(logger.getChild(agent_name))

        # Get monitoring if available
        self.monitoring = None
        try:
            if hasattr(services, "get_service") and not asyncio.iscoroutinefunction(
                services.get_service
            ):
                self.monitoring = services.get_service("monitoring_manager")
        except Exception:
            pass

        self.logger.info(
            "Agent initialized", agent_type=agent_type, timeout_seconds=timeout_seconds
        )

    def set_shared_memory(self, memory_manager: Any) -> None:
        """Attach an external/shared memory manager to this agent."""
        self._memory_manager = memory_manager

    @abstractmethod
    async def _process_task(self, task_data: Any, metadata: Dict[str, Any]) -> Any:
        """
        Abstract method for task processing.
        Must be implemented by concrete agent classes.

        Args:
            task_data: The data to process
            metadata: Additional metadata about the task

        Returns:
            Processed result

        Raises:
            Exception: If processing fails
        """

    async def execute(
        self,
        task_data: Any,
        priority: TaskPriority = TaskPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> AgentResult:
        """
        Execute a task with comprehensive monitoring and error handling

        Args:
            task_data: Data to process
            priority: Task priority
            metadata: Additional metadata
            correlation_id: Correlation ID for tracing

        Returns:
            AgentResult with execution details
        """

        # Generate correlation ID if not provided
        correlation_id = correlation_id or str(uuid.uuid4())

        # Generate task ID
        task_id = str(uuid.uuid4())

        # Update metadata
        execution_metadata = {
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "task_id": task_id,
            "correlation_id": correlation_id,
            "priority": priority.name,
            **(metadata or {}),
        }

        # Setup logging context
        if STRUCTLOG_AVAILABLE:
            task_logger = self.logger.bind(
                task_id=task_id, correlation_id=correlation_id, priority=priority.name
            )
        else:
            task_logger = self.logger

        # Initialize result
        start_time = time.time()
        self.status = AgentStatus.PROCESSING
        self.current_task_id = task_id
        self.start_time = datetime.now()

        try:
            task_logger.info(
                "Starting task execution", task_data_type=type(task_data).__name__
            )

            # Execute with timeout
            try:
                result_data = await asyncio.wait_for(
                    self._process_task(task_data, execution_metadata),
                    timeout=self.timeout_seconds,
                )

                execution_time = time.time() - start_time
                self.status = AgentStatus.COMPLETED

                task_logger.info(
                    "Task execution completed successfully",
                    execution_time=execution_time,
                    result_type=type(result_data).__name__,
                )

                return AgentResult(
                    success=True,
                    data=result_data,
                    processing_time=execution_time,
                    agent_type=self.agent_type,
                    metadata=execution_metadata,
                )

            except asyncio.TimeoutError:
                execution_time = time.time() - start_time
                self.status = AgentStatus.TIMEOUT
                error_msg = (
                    f"Task execution timed out after {self.timeout_seconds} seconds"
                )

                task_logger.error(
                    "Task execution timed out", execution_time=execution_time
                )

                return AgentResult(
                    success=False,
                    error=error_msg,
                    processing_time=execution_time,
                    agent_type=self.agent_type,
                    metadata=execution_metadata,
                )

        except Exception as e:
            execution_time = time.time() - start_time
            self.status = AgentStatus.FAILED
            error_msg = str(e)

            task_logger.error(
                "Task execution failed",
                error=error_msg,
                execution_time=execution_time,
                error_type=type(e).__name__,
            )

            return AgentResult(
                success=False,
                error=error_msg,
                processing_time=execution_time,
                agent_type=self.agent_type,
                metadata=execution_metadata,
            )

        finally:
            self.current_task_id = None
            self.start_time = None

    async def health_check(self) -> Dict[str, Any]:  # noqa: C901
        """
        Perform health check for this agent

        Returns:
            Health check result
        """
        try:
            # Basic health indicators
            health_data = {
                "healthy": True,
                "agent_name": self.agent_name,
                "agent_type": self.agent_type,
                "status": self.status.value,
                "current_task_id": self.current_task_id,
                "timeout_seconds": self.timeout_seconds,
            }

            # Add execution time if currently processing
            if self.start_time and self.status == AgentStatus.PROCESSING:
                current_duration = (datetime.now() - self.start_time).total_seconds()
                health_data["current_execution_duration"] = current_duration

                # Mark unhealthy if taking too long
                if current_duration > self.timeout_seconds * 0.9:
                    health_data["healthy"] = False
                    health_data["warning"] = "Execution approaching timeout"

            # Check service dependencies
            try:
                if hasattr(self, "_check_dependencies"):
                    dependency_status = await self._check_dependencies()
                    health_data["dependencies"] = dependency_status

                    # Mark unhealthy if critical dependencies are down
                    if any(
                        not dep.get("healthy", True)
                        for dep in dependency_status.values()
                    ):
                        health_data["healthy"] = False
                        health_data["warning"] = "Critical dependencies unhealthy"

            except Exception as e:
                health_data["dependency_check_error"] = str(e)

            # Check memory system health if available
            if self._is_memory_available():
                try:
                    memory_stats = await self.get_memory_statistics()
                    health_data["memory_system"] = {
                        "available": True,
                        "status": memory_stats.get("status", "unknown"),
                    }
                except Exception as e:
                    health_data["memory_system"] = {"available": False, "error": str(e)}
            else:
                health_data["memory_system"] = {"available": False}

            return health_data

        except Exception as e:
            return {"healthy": False, "error": str(e), "agent_name": self.agent_name}

    async def _check_dependencies(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health of service dependencies.
        Override in subclasses to add specific dependency checks.

        Returns:
            Dictionary of dependency health statuses
        """
        dependencies = {}

        # Check service container
        try:
            get_service_info = getattr(self.services, "get_service_info", None)
            if callable(get_service_info):
                service_info = cast(Dict[str, Any], get_service_info())
                dependencies["service_container"] = {
                    "healthy": True,
                    "registered_services": len(
                        service_info.get("registered_services", [])
                    ),
                }
            else:
                dependencies["service_container"] = {
                    "healthy": True,
                    "note": "Basic service container",
                }
        except Exception as e:
            dependencies["service_container"] = {"healthy": False, "error": str(e)}

        return dependencies

    async def _cleanup_resources(self) -> None:
        """Hook for subclasses to release external resources."""
        return None

    async def shutdown(self):
        """Graceful shutdown of the agent"""
        self.logger.info("Shutting down agent")

        # Cancel current task if running
        if self.status == AgentStatus.PROCESSING:
            self.logger.warning("Shutting down while task is processing")
            self.status = AgentStatus.FAILED

        # Cleanup resources
        if hasattr(self, "_cleanup_resources"):
            try:
                await cast(Any, self)._cleanup_resources()
            except Exception as e:
                self.logger.error("Error during resource cleanup", error=str(e))

        self.status = AgentStatus.IDLE
        self.logger.info("Agent shutdown completed")

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "current_task_id": self.current_task_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "timeout_seconds": self.timeout_seconds,
            "memory_available": self._is_memory_available(),
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.agent_name}, type={self.agent_type}, status={self.status.value})>"
