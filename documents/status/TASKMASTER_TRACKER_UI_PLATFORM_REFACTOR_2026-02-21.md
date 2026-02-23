# UI Platform Refactor Plan & Tracker - 2026-02-21

**Objective:** Consolidate the GUI platform, reduce code duplication, improve maintainability, and enhance portability based on the code review of 2026-02-21.

---

## 1. Redundancy & Maintenance

### 1.1 Merge Duplicate Dashboards

-   **Status:** `[x] Done`
-   **Description:** The `gui_dashboard.py` and `professional_manager.py` files serve nearly identical functions, leading to duplicated effort and potential for code drift. The goal is to merge them into a single, canonical dashboard entry point.
-   **Affected Files:**
    -   `gui/gui_dashboard.py` (Source of WSL logic)
    -   `gui/professional_manager.py` (Target for merge, will become the primary dashboard)
-   **Action Plan:**
    1.  `[x]` Identify unique, valuable features from each dashboard. (`gui_dashboard` has advanced WSL backend management; `professional_manager` has a superior UI/theme).
    2.  `[x]` Copy the `WslBackendThread` class and its related startup logic from `gui_dashboard.py` into `professional_manager.py`.
    3.  `[x]` Integrate the WSL thread's signals (`status_update`, `healthy`, `failed`) with the `ProfessionalManager` UI to provide startup feedback.
    4.  `[x]` Ensure all tabs previously loaded by `gui_dashboard` are correctly loaded by the new unified dashboard.
    5.  `[x]` Mark `gui_dashboard.py` for deprecation by adding a warning and changing it to launch `professional_manager.py`.
-   **Research Needed:** None.

### 1.2 Introduce a `BaseTab` Class

-   **Status:** `[x] In Progress`
-   **Description:** Many tab widgets (`gui/tabs/*.py`) repeat boilerplate code for UI setup, signal connections, worker management, and status updates. A common base class would significantly reduce this duplication.
-   **Affected Files:**
    -   `gui/core/base_tab.py` (New file created)
    -   All files in `gui/tabs/`
-   **Action Plan:**
    1.  `[x]` Create `gui/core/base_tab.py` with a `BaseTab` class inheriting from `QWidget`.
    2.  `[x]` Abstract common patterns into `BaseTab`:
        -   A standardized `setup_ui()` structure.
        -   A `status_presenter` instance.
        -   Generic worker start/stop/cleanup methods.
        -   A placeholder `on_backend_ready()` method.
    3.  `[x]` Refactor a pilot tab (e.g., `DocumentProcessingTab`) to inherit from `BaseTab` and remove redundant code. (Also `classification_tab.py`, `diagnostics_tab.py`, `entity_extraction_tab.py`, `embedding_operations_tab.py`, `expert_prompts_tab.py`, `heuristic_lifecycle_tab.py`, `knowledge_graph_tab.py`, `legal_reasoning_tab.py`, `ontology_registry_tab.py`, `organization_tab.py`, `pipelines_tab.py`, `semantic_analysis_tab.py`, `vector_search_tab.py`, `canonical_artifacts_tab.py`, `planner_judge_tab.py`)
    4.  `[x]` Roll out the change to all other tabs.
-   **Research Needed:** None.

---

## 2. Configuration & Portability

### 2.1 Centralize UI Styles

-   **Status:** `[x] Done`
-   **Description:** UI styling (CSS/QSS) is currently hardcoded as strings within Python files (e.g., `professional_manager.py`), making themes difficult to manage or change.
-   **Affected Files:**
    -   `gui/professional_manager.py`
    -   Various tab and UI widget files.
-   **Action Plan:**
    1.  `[x]` Create a `gui/assets/` directory if it doesn't exist.
    2.  `[x]` Create `gui/assets/dark_theme.qss` and move the stylesheet from `professional_manager.py` into it.
    3.  `[x]` Implement a theme loader utility that reads the `.qss` file and applies it to the `QApplication` instance.
    4.  `[ ]` Remove hardcoded styles from all other components. (This is a broader ongoing task but the main stylesheet is handled)
-   **Research Needed:** None.

### 2.2 Remove Hardcoded File Paths

-   **Status:** `[ ] Not Started`
-   **Description:** Some workers contain hardcoded, OS-specific file paths (e.g., `E:\...`), which breaks portability and contradicts the project's WSL/Linux setup.
-   **Affected Files:**
    -   `gui/tabs/workers.py` (Specifically in `SemanticAnalysisWorker`)
    -   Other files may be affected.
-   **Action Plan:**
    1.  `[ ]` Perform a codebase search for hardcoded paths (e.g., `E:\`, `C:\`).
    2.  `[ ]` Replace hardcoded paths with a configuration-driven approach. Introduce a `config.py` or similar to resolve paths from environment variables or a config file.
    3.  `[ ]` Ensure paths are constructed using `os.path.join` for cross-platform compatibility.
-   **Research Needed:** `[ ]` Grep search across the `gui/` directory for `E:\`, `D:\`, `C:\` to identify all affected files.

---

## 3. Code Quality

### 3.1 Refactor Silent Error Handling

-   **Status:** `[x] Done`
-   **Description:** Generic `except Exception: pass` or `except NameError: pass` blocks are used, which can hide bugs.
-   **Affected Files:**
    -   `professional_manager.py` (loading tabs)
    -   `gui_dashboard.py`
-   **Action Plan:**
    1.  `[x]` Replace overly broad exceptions with more specific ones (e.g., `ImportError`, `FileNotFoundError) where practical in startup/control paths.
    2.  `[x]` Add logging (`logger.warning(...)` or `logger.error(...)`) inside except blocks to ensure that even if the program continues, the failure is recorded.
-   **Research Needed:** None.

### 3.2 Create a Shared Utilities Module

-   **Status:** `[x] Done`
-   **Description:** Helper functions like `extract_content_from_response` are defined inside worker modules, leading to duplication if needed elsewhere.
-   **Affected Files:**
    -   `gui/tabs/workers.py`
-   **Action Plan:**
    1.  `[x]` Create a new `gui/utils.py` file.
    2.  `[x]` Move `extract_content_from_response` and other potential shared functions into this file.
    3.  `[x]` Update all files that used the old function to import from the new `gui.utils` module.
-   **Research Needed:** None.
