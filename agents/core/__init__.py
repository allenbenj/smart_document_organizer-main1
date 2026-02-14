"""
Agents Core Module
==================

Core utilities and base classes for the agents subsystem.
"""

from .base_agent import BaseAgent
from utils.logging import (  # noqa: E402
    LogCategory,
    detailed_log_function,
    get_detailed_logger,
)
from .models import (  # noqa: E402
    AgentResult,
    AgentType,
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    LegalDocument,
)
from .manager_interface import AgentManagerProtocol  # noqa: E402
from .unified_exceptions import AgentError  # noqa: E402

__all__ = [
    # Base agent
    "BaseAgent",
    "AgentResult",
    "AgentType",
    "AgentManagerProtocol",
    # Logging
    "LogCategory",
    "detailed_log_function",
    "get_detailed_logger",
    # Models
    "EntityType",
    "ExtractedEntity",
    "ExtractedRelationship",
    "LegalDocument",
    # Exceptions
    "AgentError",
]
