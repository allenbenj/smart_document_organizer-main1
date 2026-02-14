"""Memory Management Interfaces
============================

Defines the core interfaces and data structures for the unified memory system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime  # noqa: E402
from enum import Enum  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402


class MemoryType(Enum):
    """Types of memory records."""

    AGENT = "agent"
    DOCUMENT = "document"
    ENTITY = "entity"
    ANALYSIS = "analysis"
    CASE_LAW = "case_law"
    PRECEDENT = "precedent"
    CONTEXT = "context"


@dataclass
class MemoryRecord:
    """Represents a single memory record in the unified system."""

    record_id: str
    namespace: str
    key: str
    content: str
    memory_type: MemoryType
    agent_id: Optional[str] = None
    document_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance_score: float = 1.0
    confidence_score: float = 1.0
    access_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def update_access(self) -> None:
        """Update access statistics when record is retrieved."""
        self.access_count += 1
        self.updated_at = datetime.now()


@dataclass
class SearchResult:
    """Represents a search result from memory queries."""

    record: MemoryRecord
    similarity_score: float
    relevance_score: float
    match_type: str  # "semantic", "keyword", "exact"

    @property
    def combined_score(self) -> float:
        """Combined score considering similarity, relevance, and importance."""
        return (
            self.similarity_score * 0.4
            + self.relevance_score * 0.4
            + self.record.importance_score * 0.2
        )


class MemoryProvider(ABC):
    """Abstract interface for memory storage providers."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the memory provider."""

    @abstractmethod
    async def store(self, record: MemoryRecord) -> str:
        """Store a memory record and return its ID."""

    @abstractmethod
    async def retrieve(self, record_id: str) -> Optional[MemoryRecord]:
        """Retrieve a memory record by ID."""

    @abstractmethod
    async def search(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        namespace: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.6,
    ) -> List[SearchResult]:
        """Search memory records."""

    @abstractmethod
    async def update(self, record: MemoryRecord) -> bool:
        """Update an existing memory record."""

    @abstractmethod
    async def delete(self, record_id: str) -> bool:
        """Delete a memory record."""

    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory usage statistics."""

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Clean up expired memory records."""

    @abstractmethod
    async def get_all_records(
        self,
        memory_type: Optional[MemoryType] = None,
        namespace: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[MemoryRecord]:
        """Retrieve all memory records matching criteria."""

    @abstractmethod
    async def batch_store(self, records: List[MemoryRecord]) -> List[str]:
        """Store multiple memory records efficiently."""

    @abstractmethod
    async def batch_delete(self, record_ids: List[str]) -> int:
        """Delete multiple memory records efficiently."""

    @abstractmethod
    async def export_data(self, format: str = "json") -> bytes:
        """Export all memory data in specified format."""

    @abstractmethod
    async def import_data(self, data: bytes, format: str = "json") -> int:
        """Import memory data from specified format."""


@dataclass
class MemoryQuery:
    """Structured query for memory searches."""

    query_text: str
    memory_types: Optional[List[MemoryType]] = None
    namespaces: Optional[List[str]] = None
    agent_ids: Optional[List[str]] = None
    document_ids: Optional[List[str]] = None
    date_range: Optional[tuple[datetime, datetime]] = None
    min_importance: float = 0.0
    min_confidence: float = 0.0
    limit: int = 10
    min_similarity: float = 0.6
    include_metadata: bool = True


@dataclass
class MemoryStats:
    """Memory system statistics."""

    total_records: int
    records_by_type: Dict[MemoryType, int]
    records_by_agent: Dict[str, int]
    total_size_mb: float
    average_importance: float
    most_accessed_records: List[MemoryRecord]
    recent_activity: List[Dict[str, Any]]
    storage_health: Dict[str, Any]


class UnifiedMemoryInterface:
    """Unified interface for all memory operations."""

    def __init__(self, provider: MemoryProvider):
        self.provider = provider

    async def initialize(self) -> bool:
        """Initialize the memory system."""
        return await self.provider.initialize()

    async def store(self, record: MemoryRecord) -> str:
        """Store a memory record."""
        return await self.provider.store(record)

    async def retrieve(self, record_id: str) -> Optional[MemoryRecord]:
        """Retrieve a memory record."""
        return await self.provider.retrieve(record_id)

    async def search(self, query: MemoryQuery) -> List[SearchResult]:
        """Search memory records with structured query."""
        return await self.provider.search(
            query.query_text,
            memory_type=None if query.memory_types is None else query.memory_types[0],
            namespace=None if query.namespaces is None else query.namespaces[0],
            agent_id=None if query.agent_ids is None else query.agent_ids[0],
            limit=query.limit,
            min_similarity=query.min_similarity,
        )

    async def update(self, record: MemoryRecord) -> bool:
        """Update a memory record."""
        return await self.provider.update(record)

    async def delete(self, record_id: str) -> bool:
        """Delete a memory record."""
        return await self.provider.delete(record_id)

    async def get_all_records(
        self,
        memory_type: Optional[MemoryType] = None,
        namespace: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[MemoryRecord]:
        """Retrieve all memory records matching criteria."""
        return await self.provider.get_all_records(
            memory_type=memory_type, namespace=namespace, agent_id=agent_id, limit=limit
        )

    async def batch_store(self, records: List[MemoryRecord]) -> List[str]:
        """Store multiple memory records efficiently."""
        return await self.provider.batch_store(records)

    async def batch_delete(self, record_ids: List[str]) -> int:
        """Delete multiple memory records efficiently."""
        return await self.provider.batch_delete(record_ids)

    async def export_data(self, format: str = "json") -> bytes:
        """Export all memory data in specified format."""
        return await self.provider.export_data(format)

    async def import_data(self, data: bytes, format: str = "json") -> int:
        """Import memory data from specified format."""
        return await self.provider.import_data(data, format)

    async def get_statistics(self) -> MemoryStats:
        """Get comprehensive memory statistics."""
        stats = await self.provider.get_statistics()
        return MemoryStats(
            total_records=stats.get("total_records", 0),
            records_by_type=stats.get("records_by_type", {}),
            records_by_agent=stats.get("records_by_agent", {}),
            total_size_mb=stats.get("total_size_mb", 0.0),
            average_importance=stats.get("average_importance", 0.0),
            most_accessed_records=stats.get("most_accessed_records", []),
            recent_activity=stats.get("recent_activity", []),
            storage_health=stats.get("storage_health", {}),
        )

    async def cleanup_expired(self) -> int:
        """Clean up expired memory records."""
        return await self.provider.cleanup_expired()

    async def get_all_records(  # noqa: F811
        self,
        memory_type: Optional[MemoryType] = None,
        namespace: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[MemoryRecord]:
        """Retrieve all memory records matching criteria."""
        return await self.provider.get_all_records(
            memory_type=memory_type, namespace=namespace, agent_id=agent_id, limit=limit
        )

    async def cleanup_expired(self) -> int:  # noqa: F811
        """Clean up expired memory records."""
        return await self.provider.cleanup_expired()
