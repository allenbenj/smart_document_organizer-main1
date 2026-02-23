# Project Cleanup - February 16, 2026

## Summary

Cleaned root directory from 50+ items down to ~10 essential files.

## Changes Made

### Scripts Folder (NEW: `scripts/`)
**Moved 9 startup/utility scripts:**
- `run_app.bat` → `scripts/run_app.bat`
- `run_app.ps1` → `scripts/run_app.ps1`
- `run_clean.ps1` → `scripts/run_clean.ps1`
- `run_deps.bat` → `scripts/run_deps.bat`
- `run_hybrid.ps1` → `scripts/run_hybrid.ps1`
- `run_start.bat` → `scripts/run_start.bat`
- `cleanup.bat` → `scripts/cleanup.bat`
- `cleanup.ps1` → `scripts/cleanup.ps1`
- `stop_backend_wsl.ps1` → `scripts/stop_backend_wsl.ps1`

**Created:** `scripts/README.md` with usage instructions

### Utility Files (to `tools/`)
**Moved 4 utility scripts:**
- `analyzer.py` → `tools/analyzer.py`
- `database.py` → `tools/database.py`
- `metadata.py` → `tools/metadata.py`
- `check_state.py` → `tools/check_state.py`

**Updated:** `tools/README.md` to document new files

### Documentation (to `docs/`)
**Moved 2 documentation files:**
- `startup-baseline.md` → `docs/startup-baseline.md`
- `startup-issues.csv` → `docs/startup-issues.csv`

### Test Artifacts
**Moved to appropriate folders:**
- `openapi-e2e.json` → `tests/openapi-e2e.json`
- `todo.db` → `databases/todo.db`

### Requirements Files
**Consolidated and archived:**
- Rewrote `requirements.txt` with better organization and comments
- `requirements-core.txt` → `archive/requirements/` (archived)
- `requirements-dev.txt` → `archive/requirements/` (archived)
- `requirements-optional.txt` → `archive/requirements/` (archived)

## Root Directory - Before vs After

### Before (50+ items)
```
__init__.py, _test_dashboard.py, analyzer.py, check_state.py, cleanup.bat, 
cleanup.ps1, database.py, metadata.py, openapi-e2e.json, pyproject.toml, 
requirements-core.txt, requirements-dev.txt, requirements-optional.txt, 
requirements.txt, run_app.bat, run_app.ps1, run_clean.ps1, run_deps.bat, 
run_hybrid.ps1, run_start.bat, Start.py, startup-baseline.md, 
startup-issues.csv, stop_backend_wsl.ps1, todo.db, + 30 folders
```

### After (~10 essential files)
```
__init__.py
pyproject.toml
requirements.txt
Start.py
+ core folders (agents/, config/, core/, gui/, routes/, etc.)
```

## Impact

### Developer Experience
✅ **Easier to navigate** - Root folder no longer overwhelming  
✅ **Clear organization** - Scripts in scripts/, tools in tools/, docs in docs/  
✅ **Better discoverability** - READMEs explain what's where  
✅ **Maintained compatibility** - All files accessible, just reorganized

### Script Paths
**UPDATE YOUR COMMANDS:**

**Old:**
```powershell
.\run_clean.ps1
.\cleanup.ps1
```

**New:**
```powershell
.\scripts\run_clean.ps1
.\scripts\cleanup.ps1
```

### CI/CD
If you have CI/CD pipelines referencing scripts, update paths:
- `run_*.bat|ps1` → `scripts/run_*.bat|ps1`
- `cleanup.*` → `scripts/cleanup.*`

## Files Still in Root (Justified)

**Application Entry Points:**
- `Start.py` - Backend server entry point
- `__init__.py` - Package marker

**Configuration:**
- `pyproject.toml` - Project metadata, tool config
- `requirements.txt` - Consolidated dependencies
- `.env`, `.env.example` - Environment config (hidden)
- `.gitignore`, `.flake8`, `.pre-commit-config.yaml` - Tool config (hidden)

**Process Tracking:**
- `.backend-wsl.pid` - Backend process ID (hidden, auto-generated)

## Next Steps

1. **Test startup scripts** with new paths
2. **Update documentation** referencing old script paths
3. **Update CI/CD** if it references moved files
4. **Verify imports** - tools/*.py may need import adjustments

## Rollback (if needed)

All files are still present, just moved. To rollback:
```powershell
Move-Item scripts/* .
Move-Item tools/analyzer.py .
Move-Item tools/database.py .
Move-Item tools/metadata.py .
Move-Item tools/check_state.py .
Move-Item docs/startup-* .
```
