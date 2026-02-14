"""
Memory Service Integration with Production Service Container
============================================================

Integrates the unified memory system with the production service container
following the established patterns for lazy loading, health monitoring,
and dependency injection.
"""

import logging
from pathlib import Path  # noqa: E402
from typing import Any, Dict, Optional  # noqa: E402

from ..mem_db.memory.production_memory.memory_service import (  # noqa: E402
    MemoryService,
    memory_service_factory,
)
from ..mem_db.memory.unified_memory_manager import UnifiedMemoryManager  # noqa: E402
from ..mem_db.service_integration import register_mem_db_service  # noqa: E402
from .container.service_container_impl import ProductionServiceContainer  # noqa: E402

logger = logging.getLogger(__name__)


async def register_memory_services(
    container: ProductionServiceContainer,
    db_path: Optional[Path] = None,
    chroma_path: Optional[Path] = None,
    enable_vector_search: bool = True,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Register memory services with the production service container.

    This follows the established patterns for service registration with:
    - Proper dependency injection
    - Health monitoring integration
    - Circuit breaker protection
    - Singleton lifecycle management
    """

    # Create memory service factory with configuration
    def create_memory_service() -> MemoryService:
        return memory_service_factory(
            db_path=str(db_path) if db_path else None,
            chroma_path=str(chroma_path) if chroma_path else None,
            enable_vector_search=enable_vector_search,
            **(config or {}),
        )

    # Factory for memory manager (delegated to service)
    def create_memory_manager():
        memory_service = container._instances.get(MemoryService)
        if memory_service:
            return memory_service.get_memory_manager()
        else:
            # This should not happen in production, but provides fallback
            logger.warning("MemoryService not found when creating memory manager")
            return None

    # Register MemoryService as singleton with no dependencies
    await container.register_service(
        interface=MemoryService,
        implementation=lambda: create_memory_service(),
        singleton=True,
        dependencies=[],
    )

    # Register UnifiedMemoryManager as singleton dependent on MemoryService
    await container.register_service(
        interface=UnifiedMemoryManager,
        implementation=lambda: create_memory_manager(),
        singleton=True,
        dependencies=[MemoryService],
    )

    # Initialize MemoryService to start background health monitoring
    memory_service = await container.get_service(MemoryService)
    if not await memory_service.initialize():
        raise RuntimeError("Failed to initialize MemoryService")

    logger.info("Memory services registered with production service container")


class MemoryServiceWrapper:
    """
    Wrapper that adapts MemoryService to the service container interface.

    This provides the health_check and lifecycle methods expected by
    the production service container.
    """

    def __init__(self, memory_service: MemoryService):
        self._memory_service = memory_service
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the memory service."""
        if not self._initialized:
            success = await self._memory_service.initialize()
            if not success:
                raise RuntimeError("Failed to initialize MemoryService")
            self._initialized = True

    async def health_check(self) -> Dict[str, Any]:
        """Health check compatible with service container."""
        return await self._memory_service.health_check()

    async def shutdown(self) -> None:
        """Shutdown the memory service."""
        await self._memory_service.close()
        self._initialized = False

    def get_memory_manager(self) -> Optional[UnifiedMemoryManager]:
        """Get the unified memory manager."""
        return self._memory_service.get_memory_manager()

    async def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics."""
        return await self._memory_service.get_statistics()


async def register_wrapped_memory_services(
    container: ProductionServiceContainer,
    db_path: Optional[Path] = None,
    chroma_path: Optional[Path] = None,
    enable_vector_search: bool = True,
    config: Optional[Dict[str, Any]] = None,
) -> MemoryServiceWrapper:
    """
    Register memory services with wrapper for full service container integration.

    This version provides complete integration with health monitoring,
    lifecycle management, and metrics collection.
    """

    # Create memory service
    memory_service = memory_service_factory(
        db_path=str(db_path) if db_path else None,
        chroma_path=str(chroma_path) if chroma_path else None,
        enable_vector_search=enable_vector_search,
        **(config or {}),
    )

    # Wrap for service container integration
    wrapper = MemoryServiceWrapper(memory_service)

    # Register wrapper as instance (already created)
    await container.register_instance(MemoryServiceWrapper, wrapper)

    # Create factory for UnifiedMemoryManager
    def memory_manager_factory() -> Optional[UnifiedMemoryManager]:
        wrapper_instance = container._instances.get(MemoryServiceWrapper)
        if wrapper_instance:
            return wrapper_instance.get_memory_manager()
        return None

    # Register memory manager with dependency on wrapper
    await container.register_service(
        interface=UnifiedMemoryManager,
        implementation=memory_manager_factory,
        singleton=True,
        dependencies=[MemoryServiceWrapper],
    )

    # Initialize the wrapper
    await wrapper.initialize()

    logger.info("Wrapped memory services registered with full container integration")
    return wrapper


async def create_memory_container(
    db_path: Optional[Path] = None,
    chroma_path: Optional[Path] = None,
    enable_vector_search: bool = True,
    config: Optional[Dict[str, Any]] = None,
    parent_container: Optional[ProductionServiceContainer] = None,
) -> ProductionServiceContainer:
    """
    Create a service container with memory services registered.

    This is a convenience function for creating a container specifically
    configured for memory management operations.
    """

    # Create container (with optional parent)
    container = ProductionServiceContainer(parent=parent_container)

    # Register memory services
    await register_wrapped_memory_services(
        container=container,
        db_path=db_path,
        chroma_path=chroma_path,
        enable_vector_search=enable_vector_search,
        config=config,
    )

    # Register mem_db service
    await register_mem_db_service(
        container=container, db_path="mem_db.sqlite", config=config
    )

    logger.info("Memory-enabled service container created")
    return container


class MemoryServiceProxy:
    """
    Proxy for accessing memory services through the service container.

    This provides a convenient interface for agents and other components
    to access memory functionality without directly coupling to the
    service container implementation.
    """

    def __init__(self, container: ProductionServiceContainer):
        self._container = container
        self._memory_manager: Optional[UnifiedMemoryManager] = None
        self._service_wrapper: Optional[MemoryServiceWrapper] = None

    async def get_memory_manager(self) -> UnifiedMemoryManager:
        """Get the unified memory manager through the service container."""
        if not self._memory_manager:
            self._memory_manager = await self._container.get_service(
                UnifiedMemoryManager
            )

            if not self._memory_manager:
                raise RuntimeError(
                    "UnifiedMemoryManager not available from service container"
                )

        return self._memory_manager

    async def get_service_wrapper(self) -> MemoryServiceWrapper:
        """Get the memory service wrapper."""
        if not self._service_wrapper:
            self._service_wrapper = await self._container.get_service(
                MemoryServiceWrapper
            )

            if not self._service_wrapper:
                raise RuntimeError(
                    "MemoryServiceWrapper not available from service container"
                )

        return self._service_wrapper

    async def health_check(self) -> Dict[str, Any]:
        """Get memory service health status."""
        wrapper = await self.get_service_wrapper()
        return await wrapper.health_check()

    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory service statistics."""
        wrapper = await self.get_service_wrapper()
        return await wrapper.get_statistics()

    def is_available(self) -> bool:
        """Check if memory services are available."""
        return (
            self._container._instances.get(MemoryServiceWrapper) is not None
            or self._container._instances.get(UnifiedMemoryManager) is not None
        )


# Convenience function for agent integration
def get_memory_proxy(container: ProductionServiceContainer) -> MemoryServiceProxy:
    """
    Get a memory service proxy for the given container.

    This is the recommended way for agents to access memory services
    through the service container.
    """
    return MemoryServiceProxy(container)


# Service registration helper for agents
async def ensure_memory_services(
    container: ProductionServiceContainer, **memory_config
) -> bool:
    """
    Ensure memory services are registered and available in the container.

    This checks if memory services are already available and registers
    them if not. Returns True if services are available after this call.
    """

    # Check if already available
    has_wrapper = await container.has_service(MemoryServiceWrapper)
    has_manager = await container.has_service(UnifiedMemoryManager)

    if has_wrapper and has_manager:
        return True

    try:
        # Register services with provided configuration
        await register_wrapped_memory_services(container, **memory_config)
        return True

    except Exception as e:
        logger.error(f"Failed to ensure memory services: {e}")
        return False
