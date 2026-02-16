# Database Tools

Comprehensive database management and file indexing tools for the Smart Document Organizer application.

## ✅ Production Status (February 16, 2026)

**All core database tools are PRODUCTION READY and fully tested!**

- ✅ File Index System - Complete and operational (1,155 files indexed)
- ✅ Configuration System - Complete with schema validation
- ✅ Structured Logging System - Complete with multiple handlers
- ✅ Interfaces - Complete and tested

See `PRODUCTION_STATUS_REPORT.md` for detailed test results and statistics.

## 📋 Overview

This directory contains powerful database tools organized into two main systems:

1. **File Index System** - Track and analyze application source files (NEW!)
2. **Configuration & Logging Infrastructure** - Reusable database, config, and logging components

## 🗂️ File Index System (Application File Tracking)

The File Index System is a comprehensive database for tracking and understanding the application's own source files during development. **This is NOT for documents processed by the application** - it's specifically for tracking the codebase itself.

### Core Components

#### 1. `file_index_schema.sql`
Complete SQL schema with:
- File tracking with change detection (hashing)
- AI-powered analysis results storage
- File relationships and dependencies
- Issue tracking and tagging system
- Code entities (classes, functions, methods)
- Knowledge graph for code understanding
- Full-text search capabilities
- Comprehensive views and triggers

#### 2. `file_index_manager.py`
Main file indexing engine:
- **File Discovery**: Automatically scans project directories
- **Change Detection**: Tracks file modifications via content hashing
- **Classification**: Categorizes files by type and purpose
- **Search**: Full-text and metadata search
- **Statistics**: Comprehensive codebase metrics
- **Tagging**: Flexible tagging system for organization

#### 3. `file_index_inspector.py`
Interactive inspection and query tool:
```bash
# Overview of indexed files
python tools/db/file_index_inspector.py --overview

# Search for files
python tools/db/file_index_inspector.py --search "agent"

# Show file details
python tools/db/file_index_inspector.py --file "agents/core/manager.py"

# Show top files by lines of code
python tools/db/file_index_inspector.py --top lines --limit 20

# Export to JSON
python tools/db/file_index_inspector.py --export codebase_index.json
```

#### 4. `init_file_index.py`
One-command initialization:
```bash
python tools/db/init_file_index.py
```

### Quick Start

```bash
# 1. Initialize the file index database
python tools/db/init_file_index.py

# 2. Inspect the results
python tools/db/file_index_inspector.py --overview

# 3. Search for specific files
python tools/db/file_index_inspector.py --search "database"

# 4. View statistics
python tools/db/file_index_inspector.py --types
python tools/db/file_index_inspector.py --categories
```

### Use Cases

- **Code Navigation**: Understand file relationships and dependencies
- **Impact Analysis**: See which files are affected by changes
- **Quality Monitoring**: Track code metrics and issues
- **Documentation**: Generate codebase documentation
- **Refactoring**: Identify candidates for cleanup or optimization
- **Onboarding**: Help new developers understand the codebase
- **Technical Debt**: Track and prioritize technical debt

### Features

✅ **Automatic File Discovery**: Scans entire project with smart filtering  
✅ **Change Detection**: SHA256 hashing for precise change tracking  
✅ **Smart Classification**: Auto-categorizes files by type and purpose  
✅ **Relationship Mapping**: Tracks imports and dependencies  
✅ **Full-Text Search**: Fast content and metadata search  
✅ **Issue Tracking**: Track bugs, security issues, and technical debt  
✅ **Tagging System**: Flexible categorization with auto-tagging  
✅ **Knowledge Graph**: Build relationships between code entities  
✅ **Export**: JSON export for integration with other tools  

## 🔧 Configuration & Logging Infrastructure

Reusable components for database, configuration, and logging management.

### Configuration System

Located in `configuration/`:
- `manager.py` - Configuration manager with hierarchical sources
- `providers.py` - File, environment, and database configuration providers
- `schema.py` - Configuration schema validation

Supports:
- Multiple configuration sources (JSON, YAML, TOML, ENV, Database)
- Hierarchical configuration with priority ordering
- Type-safe configuration access
- Environment variable interpolation
- Schema validation

### Structured Logging System

Located in `structured_logging/`:
- `logger.py` - Structured logger implementation
- `handlers.py` - File, console, and remote log handlers
- `formatters.py` - JSON and human-readable formatters
- `factory.py` - Logger factory for easy setup

Features:
- Structured logging with categories
- Multiple output handlers
- Performance tracking
- Thread-safe operation

### Interfaces

Located in `interfaces/`:
- `configuration.py` - Configuration interfaces and types
- `logging.py` - Logging interfaces and types

## 📚 Legacy/Reference Files

**All legacy reference files have been archived** (February 16, 2026)

Previous reference files that had their functionality incorporated into the main file index system have been moved to:
- `archive/tools_db_reference_20260216/`

These included:
- `ai_database_updater.py` - AI analysis concepts incorporated into file_index_manager.py
- `database_models.py` - Data models incorporated into file_index_manager.py
- `enhanced_database_schema.sql` - Schema concepts incorporated into file_index_schema.sql
- `unified_database_manager.py` - Incomplete implementation superseded by file_index_manager.py

See `archive/tools_db_reference_20260216/README.md` for recovery instructions if needed.

## 🎯 Development Workflow

### Daily Development

```bash
# Update file index after making changes
python tools/db/file_index_manager.py

# Check what changed
python tools/db/file_index_inspector.py --changes 20

# Find files to work on
python tools/db/file_index_inspector.py --search "your_keyword"
```

### Code Review

```bash
# Show files with open issues
python tools/db/file_index_inspector.py --top issues

# Show recent changes
python tools/db/file_index_inspector.py --changes 50

# Export for review
python tools/db/file_index_inspector.py --export review_$(date +%Y%m%d).json
```

### Documentation

```bash
# Show overview
python tools/db/file_index_inspector.py --overview

# Export structure
python tools/db/file_index_inspector.py --export project_structure.json
```

## 📊 Database Schema Overview

The file index database includes:

### Core Tables
- `files` - All indexed files with metadata
- `file_analysis` - AI analysis results
- `file_relationships` - Import and dependency mapping
- `file_change_history` - Complete change history
- `file_tags` - Flexible tagging system
- `file_issues` - Issue and concern tracking
- `code_entities` - Classes, functions, methods
- `file_groups` - Module and component grouping
- `knowledge_nodes` - Knowledge graph nodes
- `knowledge_edges` - Knowledge graph relationships

### System Tables
- `scan_history` - Scan operation history
- `system_config` - System configuration
- `system_logs` - System event logging
- `tag_definitions` - Predefined tag definitions

### Views
- `v_files_complete` - Complete file information
- `v_file_dependencies` - Dependency relationships
- `v_file_stats` - Statistical aggregations
- `v_issue_summary` - Issue summaries

## 🔒 Important Notes

- **This is for DEVELOPMENT use** - Tracks the application's source files, not application data
- **Not for production documents** - Use the main application databases for document processing
- **Git-aware** - Can integrate with Git for commit tracking
- **Incremental updates** - Fast incremental scans after initial indexing
- **Privacy** - All data stays local in SQLite database

## 📖 Additional Documentation

For more details on specific components:
- Production Status: See `PRODUCTION_STATUS_REPORT.md`
- Configuration: See source files in `configuration/`
- Structured Logging: See source files in `structured_logging/`
- File Index: Run `python tools/db/file_index_inspector.py --help`
- Archive: See `archive/tools_db_reference_20260216/README.md`

## 🤝 Contributing

When adding new database tools:
1. Follow the existing patterns in `file_index_manager.py`
2. Add comprehensive docstrings
3. Include example usage
4. Update this README
5. Add appropriate indexes for performance

## 📝 License

Part of the Smart Document Organizer project.
