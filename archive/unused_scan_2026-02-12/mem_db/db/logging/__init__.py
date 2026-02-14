"""
Structured logging implementation for the Legal AI Platform.

Provides comprehensive logging with structured data, contextual information,
and configurable outputs extracted from the existing detailed logging system.
"""

from .logger import StructuredLoggerImpl
from .handlers import FileLogHandler, ConsoleLogHandler, RemoteLogHandler  # noqa: E402
from .formatters import JsonLogFormatter, HumanReadableLogFormatter  # noqa: E402
from .factory import LoggerFactory  # noqa: E402

__all__ = [
    "StructuredLoggerImpl",
    "FileLogHandler",
    "ConsoleLogHandler",
    "RemoteLogHandler",
    "JsonLogFormatter",
    "HumanReadableLogFormatter",
    "LoggerFactory",
]
