"""
Base Agent Framework
====================

Core base agent implementation with enterprise-grade features:
- Service container integration for dependency injection
- Memory mixin for collective intelligence
- Circuit breaker patterns for resilience
- Structured logging and monitoring
- Async processing with proper error handling
"""

from agents.core.models import AgentResult
from .base_agent import BaseAgent, AgentStatus, TaskPriority
from .agent_mixins import LegalDomainMixin, LegalMemoryMixin, MemoryEnabledMixin  # noqa: E402
from .pattern_extraction_mixin import PatternExtractionMixin, PatternExtractionResult  # noqa: E402

__all__ = [
    "BaseAgent",
    "AgentResult",
    "AgentStatus",
    "TaskPriority",
    "LegalMemoryMixin",
    "MemoryEnabledMixin",
    "LegalDomainMixin",
    "PatternExtractionMixin",
    "PatternExtractionResult",
]
