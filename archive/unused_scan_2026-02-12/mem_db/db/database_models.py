from dataclasses import dataclass
from datetime import datetime  # noqa: E402
from typing import Optional  # noqa: E402


@dataclass
class DatabaseConfig:
    name: str
    type: str
    url: str


@dataclass
class ViolationRecord:
    id: str
    document_id: str
    violation_type: str
    severity: str
    status: str
    description: str
    confidence: float
    detected_time: datetime
    reviewed_by: Optional[str] = None
    review_time: Optional[datetime] = None
    comments: Optional[str] = None


@dataclass
class MemoryRecord:
    id: str
    memory_type: str
    content: str
    confidence: float
    source_document: str
    created_time: datetime
    last_accessed: datetime
    access_count: int
    tags: Optional[str] = None
    metadata: Optional[str] = None


@dataclass
class GraphNode:
    id: str
    label: str
    node_type: str
    properties: str
    created_time: datetime
    updated_time: datetime


@dataclass
class GraphEdge:
    id: str
    from_node: str
    to_node: str
    relationship_type: str
    weight: float
    properties: str
    created_time: datetime


@dataclass
class DatabaseMetrics:
    connection_count: int = 0
    active_queries: int = 0
    avg_response_time: float = 0.0
    error_rate: float = 0.0
    last_backup: Optional[datetime] = None
    disk_usage_mb: float = 0.0
    health_status: str = "unknown"
    last_health_check: Optional[datetime] = None
