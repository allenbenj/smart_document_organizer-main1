# TaskMaster UI Refactor Change Log
Last updated: 2026-02-21

Purpose: Running list of items discovered during implementation that should be changed, added, or removed.

## Added
- Added `gui/core/path_config.py` for centralized GUI path portability:
  - Repo root resolution
  - WSL project path resolution
  - Dialog directory candidate generation
  - Environment-driven local model path resolution

## Changed
- `gui/tabs/default_paths.py`
  - Replaced legacy hardcoded Windows defaults with centralized portable candidates from `gui/core/path_config.py`.
- `gui/gui_dashboard.py`
  - Replaced hardcoded fallback `WSL_PROJECT_PATH` with dynamic resolver (`default_wsl_project_path`).
- `gui/tabs/workers.py`
  - Replaced hardcoded LED model path with env/repo-aware resolver.
  - Replaced one silent fallback (`except Exception: pass`) with warning logging during semantic manager bootstrap.
- `gui/tabs/workers.py`
  - Replaced duplicated local helper logic with wrappers over shared `gui/utils.py` helpers (`read_text_file_if_supported`, `collect_folder_content`, `extract_content_from_response`).
- `gui/professional_manager.py`
  - Replaced multiple silent `except NameError: pass` tab initializations with explicit optional-tab loader, placeholders, and logging.
  - Replaced additional silent catch paths in WSL startup/health lifecycle with explicit logging or status emissions.
- `gui/db_monitor.py`
  - Replaced host-specific log path defaults with env/project-relative resolution (`SMART_DOC_MONITOR_LOG_PATH` or `logs/bulk_analysis_monitor.log`).
- `gui/tabs/organization_tab.py`
  - Replaced Windows-centric root-folder placeholder text with neutral, portable guidance.
- `gui/core/path_config.py`
  - Removed legacy hardcoded project path constant no longer needed.
- `gui/tabs/workers.py`
  - Removed legacy hardcoded Windows LED model fallback path and cleaned path-specific comments.

## Remove Candidates
- Remove duplicated hardcoded style blocks in `gui/professional_manager.py` once `.qss` resources are introduced.
- Remove duplicate dashboard startup logic between `gui/gui_dashboard.py` and `gui/professional_manager.py` after unified entry point is implemented.
- Remove stale legacy path assumptions remaining in comments/placeholders where no longer needed.

## Additional Findings (Pending)
- `gui/memory_review_tab.py` still includes broad `except Exception: pass` blocks that should be hardened in a dedicated pass.
- `gui/professional_manager.py` still embeds a large inline stylesheet; migration to `gui/resources/styles/*.qss` remains pending.

## Next Candidate Tasks
1. Introduce `BaseTab` in `gui/core/` and migrate high-churn tabs.
2. Extract duplicated response utility functions into `gui/utils/response_utils.py`.
3. Externalize `professional_manager` stylesheet into `.qss` assets.
