"""
Unified Exceptions Module
=========================

Common exceptions for the agents subsystem.
"""


class AgentError(Exception):
    """Base exception for agent-related errors.

    Attributes:
        message: Error message
        agent_name: Name of the agent that raised the error
        details: Additional error details
    """

    def __init__(self, message: str, agent_name: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.agent_name = agent_name
        self.details = details or {}

    def to_dict(self) -> dict:
        """Convert exception to dictionary."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "agent_name": self.agent_name,
            "details": self.details,
        }


class AgentInitializationError(AgentError):
    """Raised when an agent fails to initialize."""


class AgentProcessingError(AgentError):
    """Raised when agent processing fails."""


class AgentTimeoutError(AgentError):
    """Raised when agent operation times out."""


class AgentConfigurationError(AgentError):
    """Raised when agent configuration is invalid."""


class ExtractionError(AgentError):
    """Raised when entity extraction fails."""


class ReasoningError(AgentError):
    """Raised when legal reasoning fails."""


__all__ = [
    "AgentError",
    "AgentInitializationError",
    "AgentProcessingError",
    "AgentTimeoutError",
    "AgentConfigurationError",
    "ExtractionError",
    "ReasoningError",
]
