"""
Data Models for Unified Memory Manager
=======================================

Contains all enums, dataclasses, and data structures used in the memory system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MemoryType(Enum):
    """Types of memory storage in the system."""

    AGENT = "agent"
    CLAUDE = "claude"
    CONTEXT = "context"
    DOCUMENT = "document"
    ENTITY = "entity"
    FACT = "fact"
    RELATIONSHIP = "relationship"
    INFERENCE = "inference"
    DOCUMENT_ANALYSIS = "document_analysis"
    LEGAL_PRECEDENT = "legal_precedent"
    WORKFLOW_RESULT = "workflow_result"
    USER_ANNOTATION = "user_annotation"
    DECISION = "decision"
    MISCONDUCT_PATTERN = "misconduct_pattern"


class ReviewStatus(Enum):
    """Review status for memory entries."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"
    UNDER_REVIEW = "under_review"
    ESCALATED = "escalated"
    CONSOLIDATED = "consolidated"


class ConfidenceLevel(Enum):
    """Confidence levels for memory entries."""

    VERY_LOW = 0.1
    LOW = 0.3
    MEDIUM = 0.5
    HIGH = 0.7
    VERY_HIGH = 0.9
    CERTAIN = 1.0


@dataclass
class MemoryEntry:
    """Enhanced memory entry with review capabilities."""

    id: str
    memory_type: MemoryType
    content: Dict[str, Any]
    confidence: float
    source: str
    created_at: datetime
    updated_at: datetime
    review_status: ReviewStatus
    metadata: Dict[str, Any]
    tags: List[str]
    version: int
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)

    # Legacy compatibility fields
    key: Optional[str] = None
    value: Optional[Any] = None


@dataclass
class ReviewRequest:
    """Represents a review request for memory entries."""

    id: str
    memory_entry_id: str
    requested_by: str
    requested_at: datetime
    priority: str  # low, medium, high, urgent
    review_type: str  # accuracy, relevance, completeness, quality
    notes: str
    deadline: Optional[datetime] = None
    assigned_reviewer: Optional[str] = None
    status: str = "pending"


@dataclass
class ReviewDecision:
    """Represents a review decision."""

    review_request_id: str
    reviewer: str
    decision: ReviewStatus
    confidence_adjustment: Optional[float]
    notes: str
    reviewed_at: datetime
    suggested_changes: Optional[Dict[str, Any]] = None


@dataclass
class DecisionEntry:
    """Agent decision logging entry."""

    id: str
    agent_name: str
    input_summary: str
    decision: str
    context_snapshot: Dict[str, Any]
    timestamp: datetime
    tag: str = "decision"
    confidence_score: Optional[float] = None
    session_id: Optional[str] = None


@dataclass
class MisconductPattern:
    """Misconduct pattern tracking entry."""

    id: str
    actor_name: str
    violation_type: str
    case_id: str
    reference_id: str
    timestamp: datetime
    severity: str = "medium"
    verified: bool = False


@dataclass
class MemoryRecord:
    """Enhanced memory record with vector embedding capabilities."""

    id: str
    namespace: str
    key: str
    content: str
    embedding: Optional[Any] = None  # numpy array when available
    metadata: Dict[str, Any] = field(default_factory=dict)
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    importance_score: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None


@dataclass
class SemanticSearchResult:
    """Search result with similarity score."""

    record: MemoryRecord
    similarity_score: float
    distance: float