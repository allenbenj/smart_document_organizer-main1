"""Canonical structured logging utilities for the application."""

from __future__ import annotations

import functools
import inspect
import logging
from enum import Enum
from typing import Any, Callable, Dict


class LogCategory(str, Enum):
    AGENT = "agent"
    DATABASE = "database"
    API = "api"
    SYSTEM = "system"
    EXTRACTION = "extraction"
    REASONING = "reasoning"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    PIPELINE = "pipeline"
    PERFORMANCE = "performance"
    SECURITY = "security"
    DATA = "data"
    ML = "ml"
    OPTIMIZATION = "optimization"
    WORKFLOW = "workflow"


class DetailedLogger:
    """Compatibility logger accepting legacy keyword arguments safely."""

    def __init__(self, name: str, category: LogCategory = LogCategory.SYSTEM):
        self._logger = logging.getLogger(name)
        self._category = category
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)

    def _format(self, message: str, **kwargs: Any) -> str:
        parts = [f"[{self._category.value}] {message}"]
        payload: Dict[str, Any] = {}
        if "parameters" in kwargs and kwargs["parameters"] is not None:
            payload["parameters"] = kwargs["parameters"]
        if "result" in kwargs and kwargs["result"] is not None:
            payload["result"] = kwargs["result"]
        if "extra" in kwargs and kwargs["extra"] is not None:
            payload["extra"] = kwargs["extra"]
        if "exception" in kwargs and kwargs["exception"] is not None:
            payload["exception"] = str(kwargs["exception"])

        ignore = {"parameters", "result", "extra", "exception", "exc_info", "stack_info"}
        for k, v in kwargs.items():
            if k not in ignore and v is not None:
                payload[k] = v

        if payload:
            parts.append(f"| {payload}")
        return " ".join(parts)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._logger.debug(self._format(message, **kwargs))

    def info(self, message: str, **kwargs: Any) -> None:
        self._logger.info(self._format(message, **kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        self._logger.warning(self._format(message, **kwargs))

    def error(self, message: str, **kwargs: Any) -> None:
        self._logger.error(self._format(message, **kwargs))

    def critical(self, message: str, **kwargs: Any) -> None:
        self._logger.critical(self._format(message, **kwargs))

    def exception(self, message: str, **kwargs: Any) -> None:
        exc = kwargs.get("exception")
        if exc is not None:
            self._logger.exception(self._format(f"{message}: {exc}", **kwargs))
            return
        self._logger.exception(self._format(message, **kwargs))


def get_detailed_logger(
    name: str, category: LogCategory = LogCategory.SYSTEM
) -> DetailedLogger:
    return DetailedLogger(name, category)


def detailed_log_function(category: LogCategory = LogCategory.SYSTEM) -> Callable:
    """Decorator that logs entry/exit/errors for sync or async functions."""

    def decorator(func: Callable) -> Callable:
        logger = get_detailed_logger(func.__module__, category)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any):
            logger.debug(
                f"Entering {func.__name__}",
                parameters={"args": len(args), "kwargs": list(kwargs.keys())},
            )
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Exiting {func.__name__}")
                return result
            except Exception as exc:
                logger.error(f"Exception in {func.__name__}", exception=exc)
                raise

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any):
            logger.debug(
                f"Entering {func.__name__}",
                parameters={"args": len(args), "kwargs": list(kwargs.keys())},
            )
            try:
                result = await func(*args, **kwargs)
                logger.debug(f"Exiting {func.__name__}")
                return result
            except Exception as exc:
                logger.error(f"Exception in {func.__name__}", exception=exc)
                raise

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


__all__ = [
    "LogCategory",
    "DetailedLogger",
    "get_detailed_logger",
    "detailed_log_function",
]

