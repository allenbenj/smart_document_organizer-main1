"""Logging interfaces and shared types for structured logging."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, Enum
import json
import logging
import uuid
from typing import Any, Dict, Optional


class LogLevel(IntEnum):
    """Log severity levels in ascending verbosity order."""

    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class LogCategory(str, Enum):
    """Top-level log event categories."""

    SYSTEM = "system"
    PERFORMANCE = "performance"
    DATABASE = "database"
    API = "api"
    SECURITY = "security"
    BUSINESS = "business"


class LoggingError(Exception):
    """Base logging error."""


class LogFormatterError(Exception):
    """Formatter failed to transform a record."""


class LogHandlerError(Exception):
    """Handler failed to emit a record."""


@dataclass
class LogRecord:
    """Normalized structured log record."""

    level: LogLevel
    message: str
    category: LogCategory
    timestamp: datetime
    logger_name: str
    context: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[Exception] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class LogFormatter(ABC):
    """Formatter contract for log handlers."""

    @abstractmethod
    def format(self, record: LogRecord) -> str:
        raise NotImplementedError


class LogHandler(ABC):
    """Handler contract for log outputs."""

    @abstractmethod
    async def emit(self, record: LogRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_formatter(self, formatter: LogFormatter) -> None:
        raise NotImplementedError


class StructuredLogger(ABC):
    """Application-facing structured logger contract."""

    @abstractmethod
    def trace(
        self,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def debug(
        self,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def info(
        self,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def warning(
        self,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def error(
        self,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        exception: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def critical(
        self,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        exception: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_child_logger(self, name: str) -> "StructuredLogger":
        raise NotImplementedError


TRACE_LEVEL_NUM = LogLevel.TRACE.value
logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")


def generate_correlation_id() -> str:
    """Generate a new correlation identifier for request tracing."""

    return uuid.uuid4().hex


def _make_payload(
    message: str,
    category: LogCategory,
    correlation_id: Optional[str],
    **kwargs: Any,
) -> str:
    payload = {
        "message": message,
        "category": category.value if isinstance(category, LogCategory) else str(category),
        "correlation_id": correlation_id,
        "context": kwargs,
    }
    try:
        return json.dumps(payload, default=str)
    except Exception:
        return f"{message} | category={category} correlation_id={correlation_id} ctx={kwargs}"


class StandardStructuredLogger(StructuredLogger):
    """Simple StructuredLogger backed by the stdlib logging module."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self._logger = logger or logging.getLogger(__name__)

    def trace(
        self,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self._logger.log(TRACE_LEVEL_NUM, _make_payload(message, category, correlation_id, **kwargs))

    def debug(
        self,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self._logger.debug(_make_payload(message, category, correlation_id, **kwargs))

    def info(
        self,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self._logger.info(_make_payload(message, category, correlation_id, **kwargs))

    def warning(
        self,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self._logger.warning(_make_payload(message, category, correlation_id, **kwargs))

    def error(
        self,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        exception: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        if exception:
            kwargs = {**kwargs, "exception": str(exception)}
        self._logger.error(_make_payload(message, category, correlation_id, **kwargs))

    def critical(
        self,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        exception: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        if exception:
            kwargs = {**kwargs, "exception": str(exception)}
        self._logger.critical(_make_payload(message, category, correlation_id, **kwargs))

    def get_child_logger(self, name: str) -> "StructuredLogger":
        return StandardStructuredLogger(self._logger.getChild(name))
