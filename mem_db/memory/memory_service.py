"""
Memory Service Integration
==========================

Service container integration for the unified memory system.
Provides proper dependency injection, health monitoring, and lifecycle management
following the established service container patterns in the Legal AI platform.
"""

import logging
from contextlib import asynccontextmanager  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, AsyncGenerator, Dict, Optional  # noqa: E402

from core.container.service_container_impl import ProductionServiceContainer  # noqa: E402

from .unified_memory_manager import UnifiedMemoryManager, create_unified_memory_manager  # noqa: E402

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Service wrapper for the UnifiedMemoryManager that integrates with the
    service container architecture and provides health monitoring.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        chroma_path: Optional[Path] = None,
        enable_vector_search: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.db_path = db_path
        self.chroma_path = chroma_path
        self.enable_vector_search = enable_vector_search
        self.config = config or {}

        self._memory_manager: Optional[UnifiedMemoryManager] = None
        self._initialized = False
        self._health_status = {
            "healthy": False,
            "initialization_status": "pending",
            "error": None,
        }

        logger.debug("MemoryService initialized with configuration")

    async def initialize(self) -> bool:
        """Initialize the memory service."""
        if self._initialized:
            return True

        try:
            logger.info("Initializing MemoryService...")

            # Create and initialize the unified memory manager
            self._memory_manager = await create_unified_memory_manager(
                db_path=self.db_path,
                vector_store_path=self.chroma_path,
                vector_backend=self.config.get("vector_backend", "chromadb"),
            )

            self._initialized = True
            self._health_status.update(
                {"healthy": True, "initialization_status": "completed", "error": None}
            )

            logger.info("MemoryService successfully initialized")
            return True

        except Exception as e:
            error_msg = f"Failed to initialize MemoryService: {e}"
            logger.error(error_msg)

            self._health_status.update(
                {
                    "healthy": False,
                    "initialization_status": "failed",
                    "error": error_msg,
                }
            )
            return False

    def get_memory_manager(self) -> Optional[UnifiedMemoryManager]:
        """Get the unified memory manager instance."""
        return self._memory_manager

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the memory service."""
        if not self._initialized or not self._memory_manager:
            return {
                "healthy": False,
                "service": "MemoryService",
                "status": "not_initialized",
                **self._health_status,
            }

        try:
            # Get memory manager statistics for health assessment
            stats = await self._memory_manager.get_statistics()

            # Assess health based on statistics
            healthy = (
                stats.get("total_records", 0) >= 0
                and self._memory_manager._initialized
                and self._health_status["healthy"]
            )

            return {
                "healthy": healthy,
                "service": "MemoryService",
                "status": "running" if healthy else "degraded",
                "statistics": stats,
                "memory_manager_initialized": self._memory_manager._initialized,
                "vector_search_enabled": self._memory_manager.enable_vector_search,
                **self._health_status,
            }

        except Exception as e:
            error_msg = f"Health check failed: {e}"
            logger.error(error_msg)

            return {
                "healthy": False,
                "service": "MemoryService",
                "status": "error",
                "error": error_msg,
                **self._health_status,
            }

    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory service statistics."""
        if not self._memory_manager:
            return {"status": "not_initialized"}

        try:
            stats = await self._memory_manager.get_statistics()
            return {
                "service": "MemoryService",
                "initialized": self._initialized,
                "memory_manager_stats": stats,
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {"status": "error", "message": str(e)}

    async def close(self) -> None:
        """Close the memory service and clean up resources."""
        logger.info("Closing MemoryService...")

        if self._memory_manager:
            await self._memory_manager.close()
            self._memory_manager = None

        self._initialized = False
        self._health_status.update(
            {"healthy": False, "initialization_status": "closed", "error": None}
        )

        logger.info("MemoryService closed")


def register_memory_service(
    container: ProductionServiceContainer,
    db_path: Optional[Path] = None,
    chroma_path: Optional[Path] = None,
    enable_vector_search: bool = True,
    config: Optional[Dict[str, Any]] = None,
) -> MemoryService:
    """
    Register the memory service with the service container.

    Args:
        container: Service container instance
        db_path: Path to SQLite database
        chroma_path: Path to ChromaDB storage
        enable_vector_search: Whether to enable vector search
        config: Additional configuration

    Returns:
        MemoryService instance
    """

    # Create the memory service
    memory_service = MemoryService(
        db_path=db_path,
        chroma_path=chroma_path,
        enable_vector_search=enable_vector_search,
        config=config,
    )

    # Register with container using established patterns
    container.register_singleton(MemoryService, memory_service)
    container.register_alias("memory_service", MemoryService)

    container.register_singleton(
        UnifiedMemoryManager, lambda: memory_service.get_memory_manager()
    )
    container.register_alias("memory_manager", UnifiedMemoryManager)
    container.register_alias("unified_memory_manager", UnifiedMemoryManager)

    logger.info("Memory service registered with service container")
    return memory_service


@asynccontextmanager
async def memory_service_context(
    db_path: Optional[Path] = None,
    chroma_path: Optional[Path] = None,
    enable_vector_search: bool = True,
    config: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[MemoryService, None]:
    """
    Context manager for memory service lifecycle management.

    This provides a convenient way to initialize and cleanup the memory service
    following the patterns established in the codebase.
    """
    service = MemoryService(db_path, chroma_path, enable_vector_search, config)

    try:
        if await service.initialize():
            yield service
        else:
            raise RuntimeError("Failed to initialize MemoryService")
    finally:
        await service.close()


@asynccontextmanager
async def memory_manager_context(
    db_path: Optional[Path] = None,
    chroma_path: Optional[Path] = None,
    enable_vector_search: bool = True,
) -> AsyncGenerator[UnifiedMemoryManager, None]:
    """
    Context manager that yields an initialized UnifiedMemoryManager instance.

    This follows the pattern established in the existing codebase for direct
    memory manager access.
    """
    async with memory_service_context(
        db_path, chroma_path, enable_vector_search
    ) as service:
        manager = service.get_memory_manager()
        if manager:
            yield manager
        else:
            raise RuntimeError("Failed to get memory manager from service")


# Factory function for service container integration
def memory_service_factory(
    db_path: Optional[str] = None,
    chroma_path: Optional[str] = None,
    enable_vector_search: bool = True,
    **config,
) -> MemoryService:
    """
    Factory function for creating MemoryService instances.

    This follows the factory pattern used throughout the service container
    architecture for proper dependency injection.
    """
    return MemoryService(
        db_path=Path(db_path) if db_path else None,
        chroma_path=Path(chroma_path) if chroma_path else None,
        enable_vector_search=enable_vector_search,
        config=config,
    )
