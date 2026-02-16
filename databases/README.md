# Database Storage

## Purpose
This folder contains the **primary production databases** for the Smart Document Organizer application.

## Active Databases

### 1. file_index.db (1.2 MB)
**Purpose**: File indexing and tracking system  
**Used by**: `tools/db/file_index_manager.py`  
**Status**: ✅ Production-ready  
**Records**: 1,155 files indexed  
**Description**: Central registry of all files processed by the application, including metadata, paths, and indexing status.

### 2. unified_memory.db
**Purpose**: Unified memory management system  
**Used by**:
- `mem_db/memory/unified_memory_manager.py`
- `mem_db/memory/chroma_memory/unified_memory_manager_canonical.py`
- `gui/db_monitor.py`

**Status**: ✅ Production-ready  
**Description**: Stores agent memory, conversation history, and cross-agent knowledge sharing data.

### 3. todo.db
**Purpose**: Task tracking and management  
**Used by**: `gui/db_monitor.py`  
**Status**: ✅ Active  
**Description**: Tracks application tasks, todos, and workflow progress.

### 4. vector_memory/ (subfolder)
**Purpose**: Chroma vector database storage  
**Contains**:
- `chroma.sqlite3` - Chroma metadata database
- `277a6ef6-4049-4f8c-b3cb-9f6becce3af0/` - Chroma data storage (UUID folder)

**Used by**: Vector search and semantic similarity operations  
**Status**: ✅ Production-ready  
**Description**: Stores document embeddings for semantic search and retrieval.

## Other Database Locations

### Why are some databases elsewhere?
Some databases are intentionally kept in their module folders to maintain **module encapsulation** and **architectural boundaries**.

### mem_db/data/ (3 databases) ✅
**Module-specific databases** - Part of the mem_db module architecture:
1. **documents.db** - Document memory storage (20+ active references)
2. **memory_proposals.db** - Memory proposal system
3. **vector_store/metadata.db** - Vector store metadata

**Recommendation**: ✅ Keep in mem_db/data/ (proper module architecture)

### ~~mem_db/memory/chroma_memory/chroma_db/~~ ✅ ARCHIVED
**Former legacy memory system**:
- Contained separate Chroma instance (not used by production)
- **Archived**: 2026-02-16 → archive/databases_backup_20260216/chroma_db_legacy
- **Note**: Seed documents (90+ agent prompts) remain in mem_db/memory/chroma_memory/seed_documents/

### Archived Databases
- `archive/databases_backup_20260216/organizer.db` - Orphaned legal organizer database (archived 2026-02-16)
- `archive/Review_Backup_20260216/*.db` - Previous memory system backups

## Database Management

### Monitoring
Use the GUI database monitor:
```python
from gui.db_monitor import DatabaseMonitor
```

### Backup Strategy
- Regular backups recommended for production databases
- Archived databases moved to `archive/databases_backup_YYYYMMDD/`
- Never delete databases without archiving first

### Adding New Databases
When creating new databases:
1. Place in `databases/` if shared across modules
2. Place in module folder (e.g., `mem_db/data/`) if module-specific
3. Document in this README
4. Add to database monitor

## Architecture Notes

**Primary Location**: `databases/` folder  
**Module-Specific**: Keep in respective module folders (e.g., `mem_db/data/`)  
**Archived**: Move to `archive/databases_backup_YYYYMMDD/`

---
**Last Updated**: 2026-02-16  
**Status**: All databases active and production-ready ✅  
**Total Active Databases**: 7 (.db files) + 2 (.sqlite3 files)
