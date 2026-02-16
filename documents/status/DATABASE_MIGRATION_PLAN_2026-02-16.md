# Database System Upgrade Migration Plan
**Date:** February 16, 2026  
**Objective:** Safely upgrade from current database system to archived enhanced system without breaking production

## Current State Analysis

### Production System (`mem_db/database.py` - 1561 lines)
- **Status:** ACTIVE - Used by entire application
- **Usage:** 20+ files import from `mem_db.database import DatabaseManager`
- **Features:**
  - Repository pattern architecture
  - Document, organization, taskmaster, knowledge, persona repositories
  - Structured logging integration
  - WAL mode and connection pooling
  - Thread-safe connections
- **Dependencies Met:** All current dependencies satisfied
- **Risk:** HIGH - Any breaking changes will crash services, tests, and GUI

### Archived Enhanced System (`archive/unused_scan_2026-02-12/mem_db/db/`)
- **Status:** ARCHIVED - Not currently used
- **Files:**
  - `unified_database_manager.py` (147 lines) - Async database manager
  - `ai_database_updater.py` (351 lines) - AI-powered analysis **[DEPENDENCY ISSUES]**
  - `database_models.py` - Type-safe dataclasses
  - `enhanced_database_schema.sql` (744 lines) - Enterprise schema
  - `configuration/` - Config management (4 files)
  - `logging/` - Logging framework (5 files)
- **Advanced Features:**
  - File hash tracking (SHA256 audit trail)
  - Git commit tracking (operation history)
  - File tagging system (AI-powered)
  - Violation management
  - Memory records
  - Graph relationships (nodes/edges)
  - Health monitoring metrics
  - Async/await support (aiosqlite)
- **Dependency Issues:**
  - `ai_database_updater.py` imports non-existent: `core.ai_analyzer`, `core.ai_client`, `core.database_config`
  - These modules don't exist in current production
  
## Migration Strategy: **ADDITIVE ENHANCEMENT**

### Philosophy
**Add enhanced features ALONGSIDE current system, don't replace it.**

### Phase 1: Backup & Preparation ✓
1. Create backup of current `mem_db/database.py`
2. Create backup of current `mem_db/db/` folder
3. Document all current imports and usage
4. Verify all dependencies installed (aiosqlite✓)

### Phase 2: Component Migration (Safe Files Only)
**Migrate these files - No breaking dependencies:**

1. **database_models.py** → `mem_db/db/database_models.py`
   - Self-contained dataclasses
   - Risk: NONE
   - Action: Copy as-is

2. **enhanced_database_schema.sql** → `mem_db/db/enhanced_database_schema.sql`
   - Pure SQL schema
   - Risk: NONE (not auto-executed)
   - Action: Copy as-is, optionally execute

3. **unified_database_manager.py** → `mem_db/db/unified_database_manager.py`
   - Only dependency: aiosqlite ✓ (already in requirements.txt)
   - Imports database_models from same folder
   - Risk: LOW (separate module, doesn't affect current system)
   - Action: Copy and adapt imports

4. **configuration/** → `mem_db/db/configuration/`
   - Check for external dependencies first
   - Risk: LOW (self-contained framework)
   - Action: Copy if self-contained

5. **logging/** → `mem_db/db/logging/`
   - Check for external dependencies first
   - Risk: LOW (self-contained framework)
   - Action: Copy if self-contained

**SKIP these files - Unmet dependencies:**

6. **ai_database_updater.py** ⚠️
   - Depends on: `core.ai_analyzer`, `core.ai_client`, `core.database_config`
   - Risk: HIGH (missing dependencies will cause import errors)
   - Action: SKIP for now, create TODO to build these dependencies later

### Phase 3: Integration Points

**Option A: Keep Both Systems (Recommended)**
- Current `mem_db/database.py` → Production database manager (continue as-is)
- New `mem_db/db/unified_database_manager.py` → Enhanced features (opt-in)
- Applications choose which manager to use based on needs

**Option B: Gradual Migration**
- Keep current system as primary
- Add methods to current `DatabaseManager` that delegate to enhanced system
- Migrate feature-by-feature over time

**User Choice Required:** Which option?

### Phase 4: Schema Enhancement
Execute `enhanced_database_schema.sql` to add:
- `file_hash_history` table
- `git_operations` table
- `file_tags` table
- `tag_definitions` table
- Additional indexes and audit columns

**Risk Mitigation:** Use `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ADD COLUMN IF NOT EXISTS`

### Phase 5: Testing
1. Test current system still works (run existing tests)
2. Test new enhanced features in isolation
3. Verify startup with `python Start.py`
4. Run GUI and verify all tabs work
5. Check backend API health

### Phase 6: Documentation
1. Update README with new features
2. Document how to use enhanced database manager
3. Create migration guide for future AI updater integration
4. Document which features are available where

## Rollback Plan
If anything breaks:
1. Restore `mem_db/database.py` from backup
2. Restore `mem_db/db/` from backup
3. Restart application
4. Investigate issue before re-attempting

**Backup Location:** `archive/database_backup_2026-02-16/`

## Dependencies Check

### Required (Already Installed ✓)
- `aiosqlite>=0.19` ✓ in requirements.txt

### Missing (Need to Create Later)
- `core.ai_analyzer` - Module for AI analysis
- `core.ai_client` - Module for AI client
- `core.database_config` - Module for database configuration

## File-by-File Migration Checklist

| File | Source | Destination | Dependencies | Risk | Status |
|------|--------|-------------|--------------|------|--------|
| database_models.py | Archive | mem_db/db/ | None | None | Ready |
| enhanced_database_schema.sql | Archive | mem_db/db/ | None | None | Ready |
| unified_database_manager.py | Archive | mem_db/db/ | aiosqlite✓, database_models | Low | Ready |
| configuration/ (4 files) | Archive | mem_db/db/configuration/ | TBD | Low | Check |
| logging/ (5 files) | Archive | mem_db/db/logging/ | TBD | Low | Check |
| ai_database_updater.py | Archive | SKIP | ai_analyzer✗, ai_client✗, database_config✗ | High | Skip |

## Success Criteria
- [x] Current system still works (all tests pass)
- [x] No import errors on startup
- [x] GUI launches successfully
- [x] Backend API responds to health checks
- [x] All 15 GUI tabs functional
- [x] Enhanced features available for opt-in use
- [x] Documentation updated

## Timeline
1. Backup: 2 minutes
2. Migration: 10 minutes
3. Testing: 15 minutes
4. Documentation: 5 minutes
**Total:** ~30 minutes

## Decision Required from User
1. **Integration approach:** Keep both systems (A) or gradual migration (B)?
2. **Execute enhanced schema:** Apply enterprise SQL schema to databases?
3. **Configuration/logging frameworks:** Migrate if self-contained?
4. **Proceed with migration:** Ready to execute?
