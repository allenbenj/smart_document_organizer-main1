"""
Structured logging implementation for the Legal AI Platform.

Provides comprehensive logging with structured data, contextual information,
and configurable outputs extracted from the existing detailed logging system.
"""

from .logger import StructuredLoggerImpl
from .handlers import FileLogHandler, ConsoleLogHandler, RemoteLogHandler
from .formatters import JsonLogFormatter, HumanReadableLogFormatter
from .factory import LoggerFactory

__all__ = [
    "StructuredLoggerImpl",
    "FileLogHandler",
    "ConsoleLogHandler", 
    "RemoteLogHandler",
    "JsonLogFormatter",
    "HumanReadableLogFormatter",
    "LoggerFactory",
]