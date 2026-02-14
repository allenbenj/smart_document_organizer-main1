"""
Models Module
=============

Data models for legal document processing and entity extraction.
"""

import uuid
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from enum import Enum  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, Optional  # noqa: E402


class EntityType(Enum):
    """Types of legal entities that can be extracted."""

    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    DATE = "date"
    MONEY = "money"
    CONTRACT = "contract"
    STATUTE = "statute"
    CASE = "case"
    COURT = "court"
    OBLIGATION = "obligation"
    RIGHT = "right"
    DOCUMENT = "document"
    UNKNOWN = "unknown"


@dataclass
class ExtractedEntity:
    """Represents an extracted entity from a legal document.

    Attributes:
        text: The text that was identified as an entity
        entity_type: The type of entity
        confidence: Confidence score (0.0 to 1.0)
        start_pos: Start position in source text
        end_pos: End position in source text
        source: Source method that extracted this entity
        attributes: Additional attributes
        id: Unique identifier
    """

    text: str
    entity_type: EntityType
    confidence: float = 0.0
    start_pos: int = 0
    end_pos: int = 0
    source: str = "unknown"
    attributes: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "entity_type": self.entity_type.value,
            "confidence": self.confidence,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "source": self.source,
            "attributes": self.attributes,
        }


@dataclass
class ExtractedRelationship:
    """Represents a relationship between two entities.

    Attributes:
        source_entity_id: ID of the source entity
        target_entity_id: ID of the target entity
        relationship_type: Type of relationship
        confidence: Confidence score (0.0 to 1.0)
        properties: Additional properties
        id: Unique identifier
    """

    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    confidence: float = 0.0
    properties: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "relationship_type": self.relationship_type,
            "confidence": self.confidence,
            "properties": self.properties,
        }


@dataclass
class LegalDocument:
    """Represents a legal document for processing.

    Attributes:
        id: Unique document identifier
        filename: Original filename
        content: Document text content
        file_path: Path to the document file
        metadata: Additional metadata
        created_at: When the document was created/ingested
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = ""
    content: Optional[str] = None
    file_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "filename": self.filename,
            "content": self.content,
            "file_path": str(self.file_path) if self.file_path else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


class AgentType(Enum):
    """Canonical agent type identifiers used across managers/routes."""

    DOCUMENT_PROCESSOR = "document_processor"
    ENTITY_EXTRACTOR = "entity_extractor"
    LEGAL_REASONING = "legal_reasoning"
    IRAC_ANALYZER = "irac_analyzer"
    TOULMIN_ANALYZER = "toulmin_analyzer"
    SEMANTIC_ANALYZER = "semantic_analyzer"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    PRECEDENT_ANALYZER = "precedent_analyzer"
    CLASSIFIER = "classifier"
    EMBEDDER = "embedder"
    CONTRADICTION_DETECTOR = "contradiction_detector"
    VIOLATION_REVIEW = "violation_review"
    ORCHESTRATOR = "orchestrator"


@dataclass
class AgentResult:
    """Canonical manager-level agent result contract."""

    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    processing_time: float = 0.0
    agent_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "processing_time": self.processing_time,
            "agent_type": self.agent_type,
            "metadata": self.metadata,
        }


__all__ = [
    "EntityType",
    "ExtractedEntity",
    "ExtractedRelationship",
    "LegalDocument",
    "AgentType",
    "AgentResult",
]
