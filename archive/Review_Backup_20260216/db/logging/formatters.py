"""
Log formatters for different output formats.
"""

import json
from datetime import datetime
from typing import Any, Dict

from ..interfaces.logging import (
    LogFormatter,
    LogRecord,
    LogLevel,
    LogCategory,
    LogFormatterError
)


class JsonLogFormatter(LogFormatter):
    """JSON log formatter for structured logging."""
    
    def __init__(
        self, 
        include_timestamp: bool = True, 
        include_level: bool = True,
        include_category: bool = True,
        include_logger_name: bool = True,
        indent: int = None
    ):
        self.include_timestamp = include_timestamp
        self.include_level = include_level
        self.include_category = include_category
        self.include_logger_name = include_logger_name
        self.indent = indent
    
    def format(self, record: LogRecord) -> str:
        """Format log record as JSON."""
        try:
            log_data = {
                "message": record.message
            }
            
            if self.include_timestamp:
                log_data["timestamp"] = record.timestamp.isoformat()
            
            if self.include_level:
                log_data["level"] = record.level.name
                log_data["level_number"] = record.level.value
            
            if self.include_category:
                log_data["category"] = record.category.value
            
            if self.include_logger_name:
                log_data["logger"] = record.logger_name
            
            # Add context data
            if record.context:
                log_data["context"] = record.context
            
            # Add exception information if present
            if record.exception:
                log_data["exception"] = {
                    "type": type(record.exception).__name__,
                    "message": str(record.exception),
                    "traceback": self._format_exception(record.exception)
                }
            
            # Add extra fields
            if record.extra:
                log_data["extra"] = record.extra
            
            return json.dumps(log_data, indent=self.indent, default=self._json_serializer)
            
        except Exception as e:
            raise LogFormatterError(f"Failed to format log record as JSON: {e}")
    
    def _format_exception(self, exception: Exception) -> str:
        """Format exception traceback."""
        import traceback
        return ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    
    def _json_serializer(self, obj: Any) -> Any:
        """JSON serializer for non-standard types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)


class HumanReadableLogFormatter(LogFormatter):
    """Human-readable log formatter."""
    
    def __init__(
        self, 
        include_timestamp: bool = True, 
        include_category: bool = True,
        include_logger_name: bool = True,
        timestamp_format: str = "%Y-%m-%d %H:%M:%S.%f",
        show_context: bool = True,
        context_indent: int = 2
    ):
        self.include_timestamp = include_timestamp
        self.include_category = include_category
        self.include_logger_name = include_logger_name
        self.timestamp_format = timestamp_format
        self.show_context = show_context
        self.context_indent = context_indent
    
    def format(self, record: LogRecord) -> str:
        """Format log record as human-readable text."""
        try:
            parts = []
            
            # Timestamp
            if self.include_timestamp:
                if self.timestamp_format.endswith('.%f'):
                    # Truncate microseconds to 3 digits (milliseconds)
                    timestamp_str = record.timestamp.strftime(self.timestamp_format)[:-3]
                else:
                    timestamp_str = record.timestamp.strftime(self.timestamp_format)
                parts.append(timestamp_str)
            
            # Log level
            level_str = f"[{record.level.name:>8}]"
            parts.append(level_str)
            
            # Category
            if self.include_category:
                category_str = f"[{record.category.value}]"
                parts.append(category_str)
            
            # Logger name
            if self.include_logger_name:
                logger_str = f"{record.logger_name}:"
                parts.append(logger_str)
            
            # Main message
            parts.append(record.message)
            
            # Combine main parts
            main_line = " ".join(parts)
            
            lines = [main_line]
            
            # Add context information
            if self.show_context and record.context:
                context_lines = self._format_context(record.context)
                lines.extend(context_lines)
            
            # Add exception information
            if record.exception:
                exception_lines = self._format_exception(record.exception)
                lines.extend(exception_lines)
            
            # Add extra fields
            if record.extra:
                extra_lines = self._format_extra(record.extra)
                lines.extend(extra_lines)
            
            return '\n'.join(lines)
            
        except Exception as e:
            raise LogFormatterError(f"Failed to format log record: {e}")
    
    def _format_context(self, context: Dict[str, Any]) -> list[str]:
        """Format context data as indented lines."""
        lines = []
        if context:
            lines.append(f"{' ' * self.context_indent}Context:")
            for key, value in context.items():
                if isinstance(value, dict):
                    lines.append(f"{' ' * (self.context_indent + 2)}{key}:")
                    for sub_key, sub_value in value.items():
                        lines.append(f"{' ' * (self.context_indent + 4)}{sub_key}: {sub_value}")
                else:
                    lines.append(f"{' ' * (self.context_indent + 2)}{key}: {value}")
        return lines
    
    def _format_exception(self, exception: Exception) -> list[str]:
        """Format exception information."""
        lines = []
        lines.append(f"{' ' * self.context_indent}Exception:")
        lines.append(f"{' ' * (self.context_indent + 2)}{type(exception).__name__}: {exception}")
        
        # Add traceback
        import traceback
        tb_lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
        for tb_line in tb_lines:
            for line in tb_line.rstrip().split('\n'):
                if line:
                    lines.append(f"{' ' * (self.context_indent + 2)}{line}")
        
        return lines
    
    def _format_extra(self, extra: Dict[str, Any]) -> list[str]:
        """Format extra fields."""
        lines = []
        if extra:
            lines.append(f"{' ' * self.context_indent}Extra:")
            for key, value in extra.items():
                lines.append(f"{' ' * (self.context_indent + 2)}{key}: {value}")
        return lines


class CompactLogFormatter(LogFormatter):
    """Compact log formatter for high-volume logging."""
    
    def __init__(self, include_timestamp: bool = True):
        self.include_timestamp = include_timestamp
    
    def format(self, record: LogRecord) -> str:
        """Format log record in compact format."""
        try:
            parts = []
            
            if self.include_timestamp:
                # Use compact timestamp format
                timestamp_str = record.timestamp.strftime("%H:%M:%S.%f")[:-3]
                parts.append(timestamp_str)
            
            # Single character log level
            level_char = record.level.name[0]
            parts.append(level_char)
            
            # Category abbreviation
            category_abbrev = record.category.value[:3].upper()
            parts.append(category_abbrev)
            
            # Logger name (last component only)
            logger_name = record.logger_name.split('.')[-1]
            parts.append(logger_name)
            
            # Message
            parts.append(record.message)
            
            # Key context fields only
            if record.context:
                key_fields = []
                for key in ['operation_id', 'duration_ms', 'error_type']:
                    if key in record.context:
                        key_fields.append(f"{key}={record.context[key]}")
                
                if key_fields:
                    parts.append(f"[{','.join(key_fields)}]")
            
            return " ".join(parts)
            
        except Exception as e:
            raise LogFormatterError(f"Failed to format log record in compact format: {e}")


class StructuredTextFormatter(LogFormatter):
    """Structured text formatter with key-value pairs."""
    
    def __init__(self, field_separator: str = " | ", kv_separator: str = "="):
        self.field_separator = field_separator
        self.kv_separator = kv_separator
    
    def format(self, record: LogRecord) -> str:
        """Format log record as structured key-value text."""
        try:
            fields = []
            
            # Core fields
            fields.append(f"timestamp{self.kv_separator}{record.timestamp.isoformat()}")
            fields.append(f"level{self.kv_separator}{record.level.name}")
            fields.append(f"category{self.kv_separator}{record.category.value}")
            fields.append(f"logger{self.kv_separator}{record.logger_name}")
            fields.append(f"message{self.kv_separator}{record.message}")
            
            # Context fields
            if record.context:
                for key, value in record.context.items():
                    # Escape special characters in values
                    escaped_value = str(value).replace(self.field_separator, "\\|").replace(self.kv_separator, "\\=")
                    fields.append(f"{key}{self.kv_separator}{escaped_value}")
            
            # Exception information
            if record.exception:
                fields.append(f"exception_type{self.kv_separator}{type(record.exception).__name__}")
                fields.append(f"exception_message{self.kv_separator}{str(record.exception)}")
            
            return self.field_separator.join(fields)
            
        except Exception as e:
            raise LogFormatterError(f"Failed to format log record as structured text: {e}")


class DebugLogFormatter(LogFormatter):
    """Debug log formatter with maximum detail."""
    
    def format(self, record: LogRecord) -> str:
        """Format log record with maximum debug information."""
        try:
            lines = []
            
            # Header line
            header = f"=== LOG RECORD [{record.level.name}] [{record.category.value}] ==="
            lines.append(header)
            
            # Basic information
            lines.append(f"Timestamp: {record.timestamp.isoformat()}")
            lines.append(f"Logger: {record.logger_name}")
            lines.append(f"Level: {record.level.name} ({record.level.value})")
            lines.append(f"Category: {record.category.value}")
            lines.append(f"Message: {record.message}")
            
            # Context information
            if record.context:
                lines.append("Context:")
                for key, value in record.context.items():
                    lines.append(f"  {key}: {repr(value)}")
            
            # Extra information
            if record.extra:
                lines.append("Extra:")
                for key, value in record.extra.items():
                    lines.append(f"  {key}: {repr(value)}")
            
            # Exception information
            if record.exception:
                lines.append("Exception:")
                lines.append(f"  Type: {type(record.exception).__name__}")
                lines.append(f"  Message: {str(record.exception)}")
                lines.append("  Traceback:")
                
                import traceback
                tb_lines = traceback.format_exception(
                    type(record.exception), 
                    record.exception, 
                    record.exception.__traceback__
                )
                for tb_line in tb_lines:
                    for line in tb_line.rstrip().split('\n'):
                        if line:
                            lines.append(f"    {line}")
            
            lines.append("=" * len(header))
            
            return '\n'.join(lines)
            
        except Exception as e:
            raise LogFormatterError(f"Failed to format debug log record: {e}")