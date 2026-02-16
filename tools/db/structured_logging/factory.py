"""
Logger factory for creating configured loggers.
"""

from pathlib import Path
from typing import Dict, List, Optional

from ..interfaces.logging import StructuredLogger, LogLevel, LogCategory
from ..interfaces.configuration import ConfigurationManager
from .logger import StructuredLoggerImpl
from .handlers import FileLogHandler, ConsoleLogHandler, RemoteLogHandler, MemoryLogHandler
from .formatters import JsonLogFormatter, HumanReadableLogFormatter, CompactLogFormatter


class LoggerFactory:
    """
    Factory for creating configured loggers.
    
    Provides centralized logger creation with configuration-driven setup
    and standardized handler/formatter combinations.
    """
    
    def __init__(self, config_manager: Optional[ConfigurationManager] = None):
        self.config_manager = config_manager
        self._loggers: Dict[str, StructuredLogger] = {}
        self._default_level = LogLevel.INFO
        self._logs_dir = Path("logs")
    
    def get_logger(self, name: str, category: LogCategory = LogCategory.SYSTEM) -> StructuredLogger:
        """
        Get or create a logger with the specified name.
        
        Args:
            name: Logger name (typically module name)
            category: Default category for the logger
            
        Returns:
            Configured structured logger
        """
        if name in self._loggers:
            return self._loggers[name]
        
        # Create new logger
        logger = self._create_logger(name, category)
        self._loggers[name] = logger
        
        return logger
    
    def get_child_logger(self, parent_name: str, child_name: str) -> StructuredLogger:
        """Get child logger from parent."""
        parent_logger = self.get_logger(parent_name)
        return parent_logger.get_child_logger(child_name)
    
    def configure_from_config(self, logs_dir: Optional[Path] = None) -> None:
        """Configure factory from configuration manager."""
        if not self.config_manager:
            return
        
        # Get logging configuration
        logging_config = self.config_manager.get_section("logging")
        
        if logs_dir:
            self._logs_dir = logs_dir
        elif "directory" in logging_config:
            self._logs_dir = Path(logging_config["directory"])
        
        # Set default log level
        level_name = logging_config.get("level", "INFO")
        try:
            self._default_level = LogLevel[level_name.upper()]
        except KeyError:
            self._default_level = LogLevel.INFO
        
        # Ensure logs directory exists
        self._logs_dir.mkdir(parents=True, exist_ok=True)
    
    def create_file_logger(
        self, 
        name: str, 
        filename: str, 
        level: Optional[LogLevel] = None,
        use_json: bool = True
    ) -> StructuredLogger:
        """Create logger with file output."""
        logger = StructuredLoggerImpl(name, level or self._default_level)
        
        # Create file handler
        file_path = self._logs_dir / filename
        file_handler = FileLogHandler(str(file_path))
        
        # Set formatter
        if use_json:
            formatter = JsonLogFormatter(indent=2)
        else:
            formatter = HumanReadableLogFormatter()
        
        file_handler.set_formatter(formatter)
        logger.add_handler(file_handler)
        
        return logger
    
    def create_console_logger(
        self, 
        name: str, 
        level: Optional[LogLevel] = None,
        use_colors: bool = True
    ) -> StructuredLogger:
        """Create logger with console output."""
        logger = StructuredLoggerImpl(name, level or self._default_level)
        
        # Create console handler
        console_handler = ConsoleLogHandler(use_colors=use_colors)
        console_handler.set_formatter(HumanReadableLogFormatter())
        
        logger.add_handler(console_handler)
        
        return logger
    
    def create_dual_logger(
        self, 
        name: str, 
        filename: str,
        level: Optional[LogLevel] = None,
        console_level: Optional[LogLevel] = None
    ) -> StructuredLogger:
        """Create logger with both file and console output."""
        logger = StructuredLoggerImpl(name, level or self._default_level)
        
        # File handler with JSON format
        file_path = self._logs_dir / filename
        file_handler = FileLogHandler(str(file_path))
        file_handler.set_formatter(JsonLogFormatter(indent=2))
        logger.add_handler(file_handler)
        
        # Console handler with human-readable format
        console_handler = ConsoleLogHandler(use_colors=True)
        console_handler.set_formatter(HumanReadableLogFormatter())
        logger.add_handler(console_handler)
        
        return logger
    
    def create_remote_logger(
        self, 
        name: str, 
        endpoint: str,
        api_key: Optional[str] = None,
        level: Optional[LogLevel] = None
    ) -> StructuredLogger:
        """Create logger with remote output."""
        logger = StructuredLoggerImpl(name, level or self._default_level)
        
        # Create remote handler
        remote_handler = RemoteLogHandler(endpoint, api_key)
        remote_handler.set_formatter(JsonLogFormatter())
        
        logger.add_handler(remote_handler)
        
        return logger
    
    def create_memory_logger(
        self, 
        name: str, 
        max_records: int = 1000,
        level: Optional[LogLevel] = None
    ) -> StructuredLogger:
        """Create logger with memory storage (for testing)."""
        logger = StructuredLoggerImpl(name, level or self._default_level)
        
        # Create memory handler
        memory_handler = MemoryLogHandler(max_records)
        memory_handler.set_formatter(JsonLogFormatter())
        
        logger.add_handler(memory_handler)
        
        return logger
    
    def _create_logger(self, name: str, category: LogCategory) -> StructuredLogger:
        """Create logger based on configuration."""
        if not self.config_manager:
            # Default configuration: dual logger with reasonable defaults
            return self.create_dual_logger(name, f"{name.replace('.', '_')}.log")
        
        # Get logger-specific configuration
        logger_config = self.config_manager.get_section(f"logging.loggers.{name}")
        
        if not logger_config:
            # Get default logger configuration
            logger_config = self.config_manager.get_section("logging.default")
        
        if not logger_config:
            # Fallback to dual logger
            return self.create_dual_logger(name, f"{name.replace('.', '_')}.log")
        
        # Create logger based on configuration
        handlers = logger_config.get("handlers", ["file", "console"])
        level_name = logger_config.get("level", "INFO")
        
        try:
            level = LogLevel[level_name.upper()]
        except KeyError:
            level = self._default_level
        
        logger = StructuredLoggerImpl(name, level)
        
        # Add configured handlers
        if "file" in handlers:
            filename = logger_config.get("filename", f"{name.replace('.', '_')}.log")
            file_handler = FileLogHandler(str(self._logs_dir / filename))
            
            file_format = logger_config.get("file_format", "json")
            if file_format == "json":
                file_handler.set_formatter(JsonLogFormatter(indent=2))
            else:
                file_handler.set_formatter(HumanReadableLogFormatter())
            
            logger.add_handler(file_handler)
        
        if "console" in handlers:
            console_handler = ConsoleLogHandler(
                use_colors=logger_config.get("console_colors", True)
            )
            
            console_format = logger_config.get("console_format", "human")
            if console_format == "json":
                console_handler.set_formatter(JsonLogFormatter())
            elif console_format == "compact":
                console_handler.set_formatter(CompactLogFormatter())
            else:
                console_handler.set_formatter(HumanReadableLogFormatter())
            
            logger.add_handler(console_handler)
        
        if "remote" in handlers:
            endpoint = logger_config.get("remote_endpoint")
            api_key = logger_config.get("remote_api_key")
            
            if endpoint:
                remote_handler = RemoteLogHandler(endpoint, api_key)
                remote_handler.set_formatter(JsonLogFormatter())
                logger.add_handler(remote_handler)
        
        return logger
    
    def shutdown_all_loggers(self) -> None:
        """Shutdown all loggers and their handlers."""
        for logger in self._loggers.values():
            if hasattr(logger, '_handlers'):
                for handler in logger._handlers:
                    if hasattr(handler, 'close'):
                        try:
                            import asyncio
                            if asyncio.iscoroutinefunction(handler.close):
                                asyncio.create_task(handler.close())
                            else:
                                handler.close()
                        except Exception:
                            pass  # Ignore errors during shutdown
        
        self._loggers.clear()


# Global logger factory instance
_logger_factory: Optional[LoggerFactory] = None


def get_logger_factory() -> LoggerFactory:
    """Get global logger factory instance."""
    global _logger_factory
    if _logger_factory is None:
        _logger_factory = LoggerFactory()
    return _logger_factory


def get_logger(name: str, category: LogCategory = LogCategory.SYSTEM) -> StructuredLogger:
    """Convenience function to get a logger."""
    return get_logger_factory().get_logger(name, category)


def configure_logging(config_manager: ConfigurationManager, logs_dir: Optional[Path] = None) -> None:
    """Configure global logging from configuration manager."""
    global _logger_factory
    _logger_factory = LoggerFactory(config_manager)
    _logger_factory.configure_from_config(logs_dir)