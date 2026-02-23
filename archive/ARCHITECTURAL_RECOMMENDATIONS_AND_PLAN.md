# Architectural Recommendations & Refactoring Plan/Roadmap

**Date:** 2026-02-08
**Status:** Approved for Implementation

This document outlines the architectural review findings and the specific roadmap to remediation. The primary goal is to transition the `Smart Document Organizer` from a "script-heavy" prototype structure to a scalable, maintainable Service-Oriented Architecture (SOA) within a modular monolith.

---

## 1. Architectural Assessment Summary

The current architecture suffers from **tight coupling**, **duplicated components**, and **lack of separation of concerns**. Key findings include:

*   **Missing Service Layer**: Business logic leaks into API Routes (`routes/`) and GUI components (`gui/`), creating multiple sources of truth and making testing difficult.
*   **Duplicate Agent Infrastructures**: Three distinct Agent Managers (`Production`, `Simple`, `GUI`) exist with incompatible interfaces and types.
*   **God Classes**: Critical components (`unified_memory_manager_canonical.py` ~3.4k lines, `gui_dashboard.py` ~3.7k lines) violate the Single Responsibility Principle.
*   **Initialization Fragmentation**: The Dependency Injection (DI) system is partially implemented but frequently bypassed (especially by the GUI).

## 2. Structural Recommendations

### R1. Introduce a Dedicated Service Layer
**Objective:** Decouple `routes` and `gui` from direct database/agent access.
**Action:** Create a `services/` directory to house business logic.

*   **`services/document_service.py`**: Handle file uploads, validation, storage, and orchestration of processing.
*   **`services/agent_service.py`**: Centralize agent task dispatching, replacing direct calls in routes.
*   **`services/search_service.py`**: Unify vector, keyword, and knowledge graph search logic.
*   **`services/knowledge_service.py`**: Manage graph operations.

**Pattern:**
```python
# Before (in routes/documents.py)
@router.post("/process")
def process_doc():
    db = get_database_manager()
    agent = ProductionAgentManager()
    # ... 50 lines of logic ...

# After
@router.post("/process")
def process_doc(service: DocumentService = Depends(get_document_service)):
    return service.process_document(...)
```

### R2. Unified Agent Architecture
**Objective:** Standardize how agents are defined, instantiated, and managed.
**Action:**
1.  **Unified Enum**: Create one `AgentType` enum in `agents/core/models.py`.
2.  **Unified Interface**: Define an `AgentManager` protocol/interface.
3.  **Consolidation**:
    *   Deprecate `SimpleAgentManager` (or make it an adapter).
    *   Refactor `GUIAgentManager` to use the shared `ProductionAgentManager` (via DI).
    *   Ensure all agents inherit from a single `BaseAgent` structure (Composition over Inheritance).

### R3. Data Access Layer (Repository Pattern)
**Objective:** Abstract raw SQLite/database calls.
**Action:** Refactor `mem_db/database.py` into distinct repositories within `mem_db/repositories/`:
*   `DocumentRepository`
*   `TagRepository`
*   `AnalyticsRepository`

### R4. Module Decomposition
**Objective:** Eliminate God Objects.
**Action:**
*   **Split `gui_dashboard.py`**: Move tab implementations to `gui/tabs/`. The dashboard should only coordinate layout.
*   **Split `unified_memory_manager_canonical.py`**: Separate `ChromaDB` client logic from Memory Logic and Search Logic.

---

## 3. Implementation Roadmap

### Phase 1: Critical Fixes & Standardization (Week 1)
*Focus: Stability and standardizing the "glue" code.*

1.  **Fix Runtime Bugs**:
    *   `agents/extractors/quality_classifier.py`: Fix `X_text` typo.
    *   `agents/extractors/hybrid_extractor.py`: Add missing `dataclass` imports.
2.  **Unify Logging**:
    *   Merge `agents/core/detailed_logging.py`, `utils/detailed_logging.py`, etc., into `utils/logging.py`.
    *   Update all references.
3.  **Secure API**:
    *   Inject `verify_api_key` properly in `Start.py` routers.

### Phase 2: The Service Layer (Week 2-3)
*Focus: Logic extraction.*

1.  **Scaffold `services/` directory**.
2.  **Implement `DocumentService`**: Move upload/processing logic from `routes/documents.py`.
3.  **Implement `AgentService`**: Wrap `ProductionAgentManager` interactions.
4.  **Refactor Routes**: Update `routes/documents.py` and `routes/agents.py` to consume services.

### Phase 3: Agent & Data Refactoring (Week 4+)
*Focus: Internal restructuring.*

1.  **Decompose God Modules**: Start with `gui_dashboard.py` as it impacts UI development speed.
2.  **Repository Implementation**: Extract SQL queries from `mem_db/database.py`.
3.  **DI Container Finalization**: Ensure `ProductionServiceContainer` is the single source of truth for dependencies.

---

## 4. Target Directory Structure

```text
smart_document_organizer/
├── services/               # [NEW] Business Logic
│   ├── document_service.py
│   ├── agent_service.py
│   └── ...
├── mem_db/
│   ├── repositories/       # [NEW] Data Access
│   ├── database.py         # connection management only
│   └── ...
├── agents/
│   ├── core/               # Shared models (AgentType), BaseAgent
│   ├── managers/           # Unified Managers
│   └── ...
├── gui/
│   ├── tabs/               # [EXPANDED] Tab logic
│   ├── services/           # GUI-specific adapters
│   └── gui_dashboard.py    # [SHRUNK] Layout shell
├── routes/                 # Thin wrappers around Services
└── utils/
    └── logging.py          # Unified logging
```
