# Tools Directory

Developer utilities and diagnostic tools for the Smart Document Organizer.

## Import Analysis
- `import_map_detailed.json`: canonical detailed map with module edges and metadata.

**Usage:**
- Use this file to tighten imports, detect cycles, and block imports from `_backup/`.
- Pair with CI to prevent accidental imports from backup or missing optional deps.

## Diagnostic Utilities (Added Feb 16, 2026)
- **`analyzer.py`** - Dependency analyzer (analyzes imports and dependencies)
- **`database.py`** - Database management utilities
- **`metadata.py`** - Metadata extraction tools  
- **`check_state.py`** - Application state checker

**Usage:**
```bash
python tools/analyzer.py
python tools/check_state.py
python tools/database.py
python tools/metadata.py
```

These are developer utilities, not part of the main application runtime.
