# Database Tools Integration Guide
## For Smart Document Organizer Application

This guide shows how to integrate the production-ready database tools into the main application.

---

## 🎯 Overview

The database tools provide three main systems:
1. **File Index System** - Track and analyze application source files
2. **Configuration System** - Hierarchical configuration management
3. **Structured Logging System** - Production-grade logging

---

## 📦 File Index System Integration

### Use Case: Track Codebase Changes During Development

The File Index System is perfect for:
- Understanding code structure
- Tracking file changes during development
- Finding files by content or metadata
- Generating documentation
- Impact analysis for refactoring

### Basic Integration

```python
from tools.db.file_index_manager import FileIndexManager

# Initialize the file index
manager = FileIndexManager(
    db_path="databases/file_index.db",
    project_root="."
)

# Perform initial scan
stats = manager.scan_files(incremental=False)
print(f"Indexed {stats['added']} files")

# Get statistics
overall_stats = manager.get_statistics()
print(f"Total files: {overall_stats['total_files']}")
print(f"Total lines: {overall_stats['total_lines_of_code']:,}")

# Search for files
results = manager.search_files("agent")
for file in results:
    print(f"- {file['file_path']} ({file['file_category']})")

# Get files by category
python_files = manager.get_files_by_category("core")
for file in python_files:
    print(f"- {file['file_path']}")
```

### Incremental Scanning

```python
# After initial scan, use incremental=True for faster updates
stats = manager.scan_files(incremental=True)
print(f"Updated: {stats['updated']}")
print(f"Added: {stats['added']}")
print(f"Removed: {stats['removed']}")
```

### Using the Inspector Tool

```python
from tools.db.file_index_inspector import FileIndexInspector

inspector = FileIndexInspector()

# Show overview
inspector.show_overview()

# Show file types distribution
inspector.show_file_types()

# Show recent changes
inspector.show_recent_changes(limit=20)

# Search files
inspector.search_files("database", limit=10)

# Export to JSON
inspector.export_to_json("file_index.json")
```

### Command-Line Usage

```bash
# Initialize the index (one-time setup)
python tools/db/init_file_index.py

# Quick overview
python tools/db/file_index_inspector.py --overview

# Search for files
python tools/db/file_index_inspector.py --search "keyword"

# Show file types
python tools/db/file_index_inspector.py --types

# Show categories
python tools/db/file_index_inspector.py --categories

# Export to JSON
python tools/db/file_index_inspector.py --export output.json
```

---

## ⚙️ Configuration System Integration

### Use Case: Centralized Application Configuration

The Configuration System provides:
- Multiple configuration sources (files, environment, database)
- Hierarchical configuration
- Type-safe access
- Schema validation
- Change notifications

### Basic Integration

```python
from tools.db.configuration import ConfigurationManagerImpl, FileConfigurationProvider
from tools.db.configuration import EnvironmentConfigurationProvider
from pathlib import Path

# Create configuration manager
config_manager = ConfigurationManagerImpl()

# Add configuration providers
await config_manager.add_provider(
    FileConfigurationProvider(
        file_path=Path("config/app.json"),
        format="json"
    )
)

await config_manager.add_provider(
    EnvironmentConfigurationProvider(prefix="APP_")
)

# Initialize
await config_manager.initialize([])

# Get configuration values
db_path = config_manager.get("database.path", default="databases/app.db")
api_key = config_manager.get("api.key")
debug_mode = config_manager.get_typed("app.debug", bool, default=False)

# Get entire section
db_config = config_manager.get_section("database")
print(f"Database config: {db_config}")

# Listen for configuration changes
def on_config_change(old_value, new_value):
    print(f"Configuration changed: {old_value} -> {new_value}")

config_manager.add_change_listener("api.key", on_config_change)

# Set configuration value
config_manager.set("app.feature_enabled", True)
```

### Schema Validation

```python
from tools.db.configuration import ConfigurationSchema, SchemaType

# Create schema
schema = ConfigurationSchema()

schema.add_field(
    "database.path",
    SchemaType.STRING,
    required=True,
    description="Database file path"
)

schema.add_field(
    "api.timeout",
    SchemaType.INTEGER,
    required=False,
    default=30,
    min_value=1,
    max_value=300,
    description="API timeout in seconds"
)

schema.add_field(
    "app.log_level",
    SchemaType.STRING,
    required=False,
    default="INFO",
    choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    description="Logging level"
)

# Validate configuration
config_data = {
    "database": {"path": "databases/app.db"},
    "api": {"timeout": 60},
    "app": {"log_level": "DEBUG"}
}

try:
    is_valid = schema.validate(config_data)
    print("Configuration is valid!")
except ValidationError as e:
    print(f"Validation error: {e.message}")
```

---

## 📝 Structured Logging System Integration

### Use Case: Production-Grade Application Logging

The Structured Logging System provides:
- Structured logs with context
- Multiple output handlers (file, console, remote)
- Different formatters (JSON, human-readable)
- Performance tracking
- Thread-safe operation

### Basic Integration

```python
from tools.db.structured_logging import get_logger, LogLevel, LogCategory

# Get a logger instance
logger = get_logger(
    name="my_application",
    category=LogCategory.APPLICATION
)

# Basic logging
logger.info("Application started")
logger.debug("Debug information", {"user_id": 123})
logger.warning("Warning message", {"threshold": 90})
logger.error("Error occurred", {"error_code": "ERR001"})

# Log with context
logger.log(
    level=LogLevel.INFO,
    message="User logged in",
    category=LogCategory.SECURITY,
    correlation_id="abc123",
    user_id=456,
    ip_address="192.168.1.1"
)

# Performance tracking
with logger.track_performance("database_query"):
    # Your code here
    result = database.query("SELECT * FROM users")

# Track async operations
async def fetch_data():
    async with logger.track_async_performance("api_call"):
        # Your async code here
        data = await api.fetch()
    return data
```

### Advanced Configuration

```python
from tools.db.structured_logging import LoggerFactory, LogLevel
from tools.db.structured_logging import FileLogHandler, ConsoleLogHandler
from tools.db.structured_logging import JsonLogFormatter, HumanReadableLogFormatter
from pathlib import Path

# Get logger factory
factory = LoggerFactory()

# Configure file handler with JSON formatter
file_handler = FileLogHandler(
    log_dir=Path("logs"),
    formatter=JsonLogFormatter()
)
factory.add_handler("file", file_handler)

# Configure console handler with human-readable formatter
console_handler = ConsoleLogHandler(
    formatter=HumanReadableLogFormatter()
)
factory.add_handler("console", console_handler)

# Set log level
factory.set_log_level(LogLevel.INFO)

# Create logger
logger = factory.create_logger(
    name="my_app",
    category=LogCategory.APPLICATION
)
```

### Integration with Configuration System

```python
from tools.db.structured_logging import configure_logging
from tools.db.configuration import ConfigurationManagerImpl
from pathlib import Path

# Assume config_manager is already initialized
logs_dir = Path(config_manager.get("logging.directory", default="logs"))

# Configure logging from configuration
configure_logging(config_manager, logs_dir)

# Now all loggers will use the configured settings
logger = get_logger("my_app")
logger.info("Logging configured from settings")
```

---

## 🔗 Combined Integration Example

### Complete Application Setup

```python
import asyncio
from pathlib import Path
from tools.db.file_index_manager import FileIndexManager
from tools.db.configuration import ConfigurationManagerImpl, FileConfigurationProvider
from tools.db.structured_logging import configure_logging, get_logger, LogCategory

async def initialize_application():
    """Initialize all database tools for the application."""
    
    # 1. Setup Configuration
    config_manager = ConfigurationManagerImpl()
    await config_manager.add_provider(
        FileConfigurationProvider(
            file_path=Path("config/app.json"),
            format="json"
        )
    )
    await config_manager.initialize([])
    
    # 2. Setup Logging
    logs_dir = Path(config_manager.get("logging.directory", default="logs"))
    configure_logging(config_manager, logs_dir)
    logger = get_logger("app_init", LogCategory.SYSTEM)
    
    logger.info("Initializing application...")
    
    # 3. Setup File Index (optional, for development)
    if config_manager.get("development.enable_file_index", default=False):
        logger.info("Initializing file index...")
        file_index = FileIndexManager(
            db_path=config_manager.get("file_index.db_path", default="databases/file_index.db"),
            project_root="."
        )
        stats = file_index.scan_files(incremental=True)
        logger.info(f"File index updated: {stats['added']} added, {stats['updated']} updated")
    
    logger.info("Application initialized successfully")
    
    return {
        "config": config_manager,
        "logger": logger,
        "file_index": file_index if config_manager.get("development.enable_file_index") else None
    }

# Run initialization
if __name__ == "__main__":
    app_context = asyncio.run(initialize_application())
    
    # Use the initialized components
    logger = app_context["logger"]
    config = app_context["config"]
    
    logger.info("Application running", {
        "version": config.get("app.version", default="1.0.0")
    })
```

---

## 🚀 Best Practices

### File Index System
1. **Run initial scan once** - Use `incremental=False` for first scan
2. **Use incremental scans** - Set `incremental=True` for subsequent scans
3. **Schedule regular scans** - Run daily or after major changes
4. **Export for analysis** - Use inspector to export data for offline analysis

### Configuration System
1. **Use schema validation** - Define schemas for critical configuration
2. **Layer configurations** - Use multiple providers for flexibility
3. **Monitor changes** - Add listeners for critical configuration keys
4. **Document defaults** - Always provide sensible defaults

### Structured Logging
1. **Use appropriate levels** - DEBUG for development, INFO for production
2. **Add context** - Include correlation IDs, user IDs, etc.
3. **Rotate logs** - Configure log rotation to manage disk space
4. **Use categories** - Categorize logs for easier filtering

---

## 📊 Performance Considerations

- **File Index**: Initial scan may take time for large codebases (1,155 files ~1 minute)
- **Configuration**: Configuration loading is fast, cache when possible
- **Logging**: Async logging is recommended for high-throughput applications

---

## 🐛 Troubleshooting

### File Index Issues

**Problem**: "database is locked" error
**Solution**: Ensure no other process is accessing the database

**Problem**: Files not being indexed
**Solution**: Check exclude patterns in `file_index_manager.py`

### Configuration Issues

**Problem**: Configuration not loading
**Solution**: Check file paths and permissions

**Problem**: Environment variables not loading
**Solution**: Ensure environment variables have correct prefix

### Logging Issues

**Problem**: Logs not appearing
**Solution**: Check log level and handler configuration

**Problem**: Permission denied on log files
**Solution**: Ensure log directory is writable

---

## 📚 Additional Resources

- **Full API Reference**: See source code docstrings
- **Production Status**: See `PRODUCTION_STATUS_REPORT.md`
- **Examples**: See `tools/db/README.md`
- **Archive**: See `archive/tools_db_reference_20260216/README.md`

---

## ✅ Checklist for Integration

- [ ] Initialize File Index System (if needed for development)
- [ ] Configure Configuration System with appropriate providers
- [ ] Setup Structured Logging with proper handlers
- [ ] Test all integrations in development environment
- [ ] Document configuration requirements
- [ ] Setup log rotation for production
- [ ] Monitor performance and adjust as needed

---

**Last Updated**: February 16, 2026
**Status**: All tools production-ready and tested
