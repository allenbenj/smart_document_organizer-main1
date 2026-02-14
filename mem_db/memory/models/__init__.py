"""
Database Models for Legal AI Platform
Provides SQLAlchemy models for all data entities
"""

from .base import Base, BaseModel, TimestampMixin
from .agent_models import Agent, AgentConfig, AgentMemory, AgentMetrics  # noqa: E402
from .document_models import Document, DocumentAnalysis, EntityExtraction  # noqa: E402
from .legal_models import LegalCase, LegalEntity, LegalRelationship, Citation  # noqa: E402
from .knowledge_models import KnowledgeNode, KnowledgeEdge, OntologyEntity  # noqa: E402
from .user_models import User, UserSession, UserPreference  # noqa: E402
from .system_models import SystemConfig, SystemMetrics, HealthCheck  # noqa: E402

__all__ = [
    # Base
    "Base",
    "BaseModel",
    "TimestampMixin",
    # Agent models
    "Agent",
    "AgentConfig",
    "AgentMemory",
    "AgentMetrics",
    # Document models
    "Document",
    "DocumentAnalysis",
    "EntityExtraction",
    # Legal models
    "LegalCase",
    "LegalEntity",
    "LegalRelationship",
    "Citation",
    # Knowledge models
    "KnowledgeNode",
    "KnowledgeEdge",
    "OntologyEntity",
    # User models
    "User",
    "UserSession",
    "UserPreference",
    # System models
    "SystemConfig",
    "SystemMetrics",
    "HealthCheck",
]


def get_database_url() -> str:
    """Get database URL from environment or configuration"""
    import os  # noqa: E402

    # Environment variables
    if db_url := os.getenv("DATABASE_URL"):
        return db_url

    # Development default
    return "sqlite:///database/legal_ai.db"
