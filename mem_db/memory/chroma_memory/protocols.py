"""
Protocols and Interfaces for Unified Memory Manager
===================================================

Defines the core protocols and interfaces used throughout the memory system.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class MemoryBackend(Protocol):
    """Protocol defining the memory backend interface."""

    async def store(
        self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a value with optional metadata."""
        ...

    async def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve a value by key."""
        ...

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for values matching the query."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete a value by key."""
        ...

    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the backend."""
        ...


@runtime_checkable
class ReviewSystem(Protocol):
    """Protocol for review system implementations."""

    async def submit_for_review(self, entry_id: str, review_type: str) -> str:
        """Submit an entry for review."""
        ...

    async def approve_entry(self, entry_id: str, reviewer: str, notes: str) -> bool:
        """Approve a reviewed entry."""
        ...

    async def reject_entry(self, entry_id: str, reviewer: str, notes: str) -> bool:
        """Reject a reviewed entry."""
        ...


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector store implementations."""

    async def add_vector(
        self, vector_id: str, content: str, embedding: Optional[Any] = None
    ) -> bool:
        """Add a vector to the store."""
        ...

    async def search_similar(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        ...