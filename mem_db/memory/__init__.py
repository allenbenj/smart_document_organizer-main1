"""
Memory Management Module for Legal AI Platform
===============================================

This module provides a unified memory management system that enables the key
differentiator of this Legal AI platform: shared memory between agents that
makes them collectively smarter through knowledge sharing.

Key Features:
- Unified memory management across all agents
- Vector-based semantic search capabilities
- SQLite persistence with ChromaDB integration
- Cross-agent memory sharing and knowledge accumulation
- Document memory, entity memory, and analysis result storage
- Memory-based learning and case law knowledge building

The shared memory system is what transforms individual agents into a
collectively intelligent legal AI platform.
"""

from .unified_memory_manager import UnifiedMemoryManager, create_unified_memory_manager
from .memory_interfaces import (  # noqa: E402
    MemoryProvider,
    MemoryRecord,
    SearchResult,
    MemoryQuery,
    MemoryStats,
    MemoryType,
)
from .memory_mixin import MemoryMixin  # noqa: E402
from .memory_service import (  # noqa: E402
    MemoryService,
    memory_service_factory,
    register_memory_service,
    memory_service_context,
    memory_manager_context,
)
from .service_integration import (  # noqa: E402
    register_memory_services,
    register_wrapped_memory_services,
    create_memory_container,
    MemoryServiceProxy,
    get_memory_proxy,
    ensure_memory_services,
    MemoryServiceWrapper,
)

__all__ = [
    # Core memory management
    "UnifiedMemoryManager",
    "create_unified_memory_manager",
    # Interfaces and data structures
    "MemoryProvider",
    "MemoryRecord",
    "SearchResult",
    "MemoryQuery",
    "MemoryStats",
    "MemoryType",
    # Agent integration
    "MemoryMixin",
    # Service layer
    "MemoryService",
    "memory_service_factory",
    "register_memory_service",
    "memory_service_context",
    "memory_manager_context",
    # Service container integration
    "register_memory_services",
    "register_wrapped_memory_services",
    "create_memory_container",
    "MemoryServiceProxy",
    "get_memory_proxy",
    "ensure_memory_services",
    "MemoryServiceWrapper",
]
