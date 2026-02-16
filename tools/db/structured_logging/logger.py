"""
Structured logger implementation with comprehensive tracking capabilities.

Extracted and enhanced from the existing Legal AI Platform detailed logging system.
"""

import asyncio
import functools
import json
import sys
import threading
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from pathlib import Path

from ..interfaces.logging import (
    StructuredLogger,
    LogHandler,
    LogRecord,
    LogLevel,
    LogCategory,
    LoggingError
)


class StructuredLoggerImpl(StructuredLogger):
    """
    Concrete implementation of structured logger.
    
    Features:
    - Structured logging with contextual information
    - Thread-safe operation
    - Multiple output handlers
    - Performance tracking
    - Category-based organization
    """
    
    def __init__(self, name: str, level: LogLevel = LogLevel.INFO):
        self.name = name
        self.level = level
        self._handlers: List[LogHandler] = []
        self._context: Dict[str, Any] = {}
        self._lock = threading.RLock()
        
        # Performance tracking
        self._operation_stack: List[Dict[str, Any]] = []
        self._operation_times: Dict[str, List[float]] = {}
    
    def trace(
        self, 
        message: str, 
        category: LogCategory = LogCategory.SYSTEM,
        **kwargs: Any
    ) -> None:
        """Log trace message."""
        self._log(LogLevel.TRACE, message, category, **kwargs)
    
    def debug(
        self, 
        message: str, 
        category: LogCategory = LogCategory.SYSTEM,
        **kwargs: Any
    ) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, category, **kwargs)
    
    def info(
        self, 
        message: str, 
        category: LogCategory = LogCategory.SYSTEM,
        **kwargs: Any
    ) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message, category, **kwargs)
    
    def warning(
        self, 
        message: str, 
        category: LogCategory = LogCategory.SYSTEM,
        **kwargs: Any
    ) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message, category, **kwargs)
    
    def error(
        self, 
        message: str, 
        category: LogCategory = LogCategory.SYSTEM,
        exception: Optional[Exception] = None,
        **kwargs: Any
    ) -> None:
        """Log error message."""
        self._log(LogLevel.ERROR, message, category, exception=exception, **kwargs)
    
    def critical(
        self, 
        message: str, 
        category: LogCategory = LogCategory.SYSTEM,
        exception: Optional[Exception] = None,
        **kwargs: Any
    ) -> None:
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, category, exception=exception, **kwargs)
    
    def log_with_context(
        self, 
        level: LogLevel, 
        message: str, 
        context: Dict[str, Any],
        category: LogCategory = LogCategory.SYSTEM
    ) -> None:
        """Log message with structured context."""
        self._log(level, message, category, **context)
    
    def set_context(self, **kwargs: Any) -> None:
        """Set persistent context for all subsequent log messages."""
        with self._lock:
            self._context.update(kwargs)
    
    def clear_context(self) -> None:
        """Clear persistent context."""
        with self._lock:
            self._context.clear()
    
    def get_child_logger(self, name: str) -> "StructuredLogger":
        """Get child logger with additional name prefix."""
        child_name = f"{self.name}.{name}"
        child = StructuredLoggerImpl(child_name, self.level)
        child._handlers = self._handlers.copy()
        child._context = self._context.copy()
        return child
    
    def add_handler(self, handler: LogHandler) -> None:
        """Add log handler."""
        with self._lock:
            if handler not in self._handlers:
                self._handlers.append(handler)
    
    def remove_handler(self, handler: LogHandler) -> None:
        """Remove log handler."""
        with self._lock:
            if handler in self._handlers:
                self._handlers.remove(handler)
    
    def set_level(self, level: LogLevel) -> None:
        """Set minimum log level."""
        self.level = level
    
    def start_operation(self, operation_name: str, **context: Any) -> str:
        """
        Start tracking an operation for performance monitoring.
        
        Args:
            operation_name: Name of the operation
            **context: Additional context for the operation
            
        Returns:
            Operation ID for ending the operation
        """
        operation_id = f"{operation_name}_{int(time.time() * 1000000)}"
        
        operation_info = {
            "operation_id": operation_id,
            "operation_name": operation_name,
            "start_time": time.time(),
            "context": context
        }
        
        with self._lock:
            self._operation_stack.append(operation_info)
        
        self.debug(
            f"Started operation: {operation_name}",
            category=LogCategory.PERFORMANCE,
            operation_id=operation_id,
            operation_name=operation_name,
            **context
        )
        
        return operation_id
    
    def end_operation(self, operation_id: str, **result_context: Any) -> float:
        """
        End tracking an operation and log performance metrics.
        
        Args:
            operation_id: Operation ID returned by start_operation
            **result_context: Additional context about operation results
            
        Returns:
            Operation duration in seconds
        """
        end_time = time.time()
        
        with self._lock:
            # Find and remove the operation from stack
            operation_info = None
            for i, op in enumerate(self._operation_stack):
                if op["operation_id"] == operation_id:
                    operation_info = self._operation_stack.pop(i)
                    break
        
        if not operation_info:
            self.warning(
                f"Operation not found: {operation_id}",
                category=LogCategory.PERFORMANCE,
                operation_id=operation_id
            )
            return 0.0
        
        duration = end_time - operation_info["start_time"]
        operation_name = operation_info["operation_name"]
        
        # Track operation times for analytics
        with self._lock:
            if operation_name not in self._operation_times:
                self._operation_times[operation_name] = []
            self._operation_times[operation_name].append(duration)
            
            # Keep only last 100 measurements to avoid memory bloat
            if len(self._operation_times[operation_name]) > 100:
                self._operation_times[operation_name] = self._operation_times[operation_name][-100:]
        
        self.info(
            f"Completed operation: {operation_name}",
            category=LogCategory.PERFORMANCE,
            operation_id=operation_id,
            operation_name=operation_name,
            duration_seconds=duration,
            duration_ms=duration * 1000,
            **operation_info["context"],
            **result_context
        )
        
        return duration
    
    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """Get performance statistics for an operation."""
        with self._lock:
            times = self._operation_times.get(operation_name, [])
        
        if not times:
            return {"operation_name": operation_name, "sample_count": 0}
        
        return {
            "operation_name": operation_name,
            "sample_count": len(times),
            "avg_duration_seconds": sum(times) / len(times),
            "min_duration_seconds": min(times),
            "max_duration_seconds": max(times),
            "total_duration_seconds": sum(times)
        }
    
    def _log(
        self, 
        level: LogLevel, 
        message: str, 
        category: LogCategory,
        exception: Optional[Exception] = None,
        **kwargs: Any
    ) -> None:
        """Internal logging method."""
        if level.value < self.level.value:
            return
        
        # Merge persistent context with kwargs
        with self._lock:
            context = self._context.copy()
            context.update(kwargs)
        
        # Add current operation context if available
        if self._operation_stack:
            current_op = self._operation_stack[-1]
            context["current_operation"] = current_op["operation_name"]
            context["operation_id"] = current_op["operation_id"]
        
        # Create log record
        record = LogRecord(
            level=level,
            message=message,
            category=category,
            timestamp=datetime.now(),
            logger_name=self.name,
            context=context,
            exception=exception
        )
        
        # Emit to all handlers
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler.emit):
                    # For async handlers, we'd need to handle this differently
                    # For now, skip async handlers in sync logging
                    continue
                else:
                    handler.emit(record)
            except Exception as e:
                # Prevent logging errors from breaking the application
                print(f"Error in log handler: {e}", file=sys.stderr)


class PerformanceLogger:
    """Specialized logger for performance tracking."""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
    
    def time_function(self, func_name: Optional[str] = None):
        """Decorator to time function execution."""
        def decorator(func):
            nonlocal func_name
            if func_name is None:
                func_name = f"{func.__module__}.{func.__qualname__}"
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                operation_id = self.logger.start_operation(
                    func_name,
                    function=func_name,
                    args_count=len(args),
                    kwargs_keys=list(kwargs.keys())
                )
                
                try:
                    result = func(*args, **kwargs)
                    self.logger.end_operation(
                        operation_id,
                        success=True,
                        result_type=type(result).__name__
                    )
                    return result
                except Exception as e:
                    self.logger.end_operation(
                        operation_id,
                        success=False,
                        error_type=type(e).__name__,
                        error_message=str(e)
                    )
                    raise
            
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                operation_id = self.logger.start_operation(
                    func_name,
                    function=func_name,
                    args_count=len(args),
                    kwargs_keys=list(kwargs.keys()),
                    async_function=True
                )
                
                try:
                    result = await func(*args, **kwargs)
                    self.logger.end_operation(
                        operation_id,
                        success=True,
                        result_type=type(result).__name__
                    )
                    return result
                except Exception as e:
                    self.logger.end_operation(
                        operation_id,
                        success=False,
                        error_type=type(e).__name__,
                        error_message=str(e)
                    )
                    raise
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper
        
        return decorator


# Standard attributes to filter from log records
_STANDARD_LOG_RECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName"
}


def get_logger(name: str, level: Optional[LogLevel] = None) -> StructuredLogger:
    """
    Factory function to create and return a structured logger instance.
    
    Args:
        name: The name of the logger (typically __name__ of the module)
        level: Optional log level, defaults to INFO
        
    Returns:
        StructuredLogger instance
    """
    if level is None:
        level = LogLevel.INFO
    
    return StructuredLoggerImpl(name, level)