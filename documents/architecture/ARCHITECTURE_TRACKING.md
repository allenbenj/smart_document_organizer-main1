# Architecture Tracking Board

**Last Updated:** 2026-02-09  
**Source Inputs:** `ARCHITECTURE_REVIEW.md`, `ARCHITECTURAL_RECOMMENDATIONS_AND_PLAN.md`

## Status Legend
- `todo`
- `in_progress`
- `blocked`
- `done`

## Governance
| ID | Task | Status | Owner | Target |
|---|---|---|---|---|
| GOV-1 | Keep this tracker as source-of-truth for architecture work items | todo | unassigned | TBD |
| GOV-2 | Add phase acceptance criteria gates (Phase 1/2/3/4/5) and sign-off checklist | todo | unassigned | TBD |
| GOV-3 | Enforce architecture rule: no direct manager/service construction in routes/gui | todo | unassigned | TBD |

## P0 Runtime Correctness & Security
| ID | Task | Status | Owner | Target |
|---|---|---|---|---|
| P0-1 | Fix `X_text` -> `Xtext` in `agents/extractors/quality_classifier.py` | done | codex | 2026-02-09 |
| P0-2 | Add missing `dataclass, field` imports in `agents/extractors/hybrid_extractor.py` | done | codex | 2026-02-09 |
| P0-3 | Wire `verify_api_key` via FastAPI `Depends` on secured routers | done | codex | 2026-02-09 |
| P0-4 | Remove duplicate inline health endpoints from `Start.py` and keep canonical health routes in `routes/health.py` | done | codex | 2026-02-09 |
| P0-5 | Replace module-level DB singleton access in routes with DI dependencies | done | codex | 2026-02-10 |
| P0-6 | Add regression tests for P0 fixes (auth, health route ownership, classifier/hybrid imports) | done | codex | 2026-02-10 |

## Interface Boundaries
| ID | Task | Status | Owner | Target |
|---|---|---|---|---|
| IF-1 | Remove private attribute access from routes (e.g., `_networkx_graph`, `_stats`) | todo | unassigned | TBD |
| IF-2 | Add public manager methods for route-required state/metrics | todo | unassigned | TBD |
| IF-3 | Move in-route business logic (document processing, proposal shaping) into service layer | todo | unassigned | TBD |

## Service Layer (SOA within modular monolith)
| ID | Task | Status | Owner | Target |
|---|---|---|---|---|
| SVC-1 | Create `services/` package scaffold | done | Copilot | 2026-02-08 |
| SVC-2 | Implement `services/document_service.py` and migrate document orchestration logic from routes | done | Copilot | 2026-02-08 |
| SVC-3 | Implement `services/agent_service.py` and centralize agent dispatch | done | Copilot | 2026-02-09 |
| SVC-4 | Implement `services/search_service.py` to unify keyword/vector/knowledge search | done | Copilot | 2026-02-09 |
| SVC-5 | Implement `services/knowledge_service.py` for graph operations | done | Copilot | 2026-02-09 |
| SVC-6 | Refactor `routes/documents.py` and `routes/agents.py` first (highest logic density) to use services | in_progress | Copilot | 2026-02-08 |
If you want, I can next do a strict sweep of all *.py to enforce one consistent DI pattern and produce a short compliance table for every route module.

## Agent Architecture Unification
| ID | Task | Status | Owner | Target |
|---|---|---|---|---|
| AG-1 | Define canonical `AgentType` in `agents/core/models.py` and migrate all managers | done | codex | 2026-02-09 |
| AG-2 | Unify `AgentResult` contracts into one shared model | done | codex | 2026-02-09 |
| AG-3 | Define `AgentManager` interface/protocol and enforce across managers | done | codex | 2026-02-09 |
| AG-4 | Remove `SimpleAgentManager` (deprecate/remove, no adapter path) | done | codex | 2026-02-09 |
| AG-5 | Merge/remove `GUIAgentManager`; GUI must use shared production manager via DI/facade | done | codex | 2026-02-09 |
| AG-6 | Resolve `MemoryEnabledMixin` naming collision (`LegalMemoryMixin` rename path) | done | codex | 2026-02-09 |

## Logging Consolidation
| ID | Task | Status | Owner | Target |
|---|---|---|---|---|
| LOG-1 | Consolidate all logging implementations into `utils/logging.py` | done | codex | 2026-02-09 |
| LOG-2 | Migrate imports from `agents/core/detailed_logging.py`, `config/core/enhanced_detailed_logging.py`, `utils/detailed_logging.py` | done | codex | 2026-02-09 |
| LOG-3 | Remove legacy logging modules after migration | done | codex | 2026-02-09 |

## Data Access & Storage
| ID | Task | Status | Owner | Target |
|---|---|---|---|---|
| DB-1 | Split `mem_db/database.py` into repositories under `mem_db/repositories/` | todo | unassigned | TBD |
| DB-2 | Implement `DocumentRepository` | todo | unassigned | TBD |
| DB-3 | Implement `TagRepository` | todo | unassigned | TBD |
| DB-4 | Implement `AnalyticsRepository` | todo | unassigned | TBD |
| DB-5 | Consolidate SQLite silos into a unified DB plan and migration path | todo | unassigned | TBD |
| DB-6 | Centralize DB path/config in configuration manager | todo | unassigned | TBD |

## Deduplication & Package Hygiene
| ID | Task | Status | Owner | Target |
|---|---|---|---|---|
| DEDUP-1 | Remove duplicate embedding module copy and keep one canonical implementation | todo | unassigned | TBD |
| DEDUP-2 | Merge/retire duplicate hybrid extractor implementations | todo | unassigned | TBD |
| DEDUP-3 | Remove `agents/config/` proxy shim package after import migration is complete | todo | unassigned | TBD |
| DEDUP-4 | Remove duplicate health route implementations (single owner route module) | todo | unassigned | TBD |

## God Module Decomposition
| ID | Task | Status | Owner | Target |
|---|---|---|---|---|
| GOD-1 | Decompose `gui/gui_dashboard.py` into `gui/tabs/*` and keep dashboard shell thin | done | Copilot | 2026-02-08 |
| GOD-2 | Decompose `mem_db/memory/chroma_memory/unified_memory_manager_canonical.py` into focused modules | done | Copilot | 2026-02-09 |
| GOD-3 | Decompose `routes/agents.py` into subrouters (`management`, `analysis`, `memory`) | done | Copilot | 2026-02-09 |
| GOD-4 | Decompose `agents/production_agent_manager.py` (init/routing/health separation) | done | Copilot | 2026-02-09 |

## DI & Infrastructure Modernization
| ID | Task | Status | Owner | Target |
|---|---|---|---|---|
| DI-1 | Fully implement `ProductionServiceContainer` (remove placeholder behavior) | done | codex | 2026-02-09 |
| DI-2 | Register all app services centrally in container startup | done | codex | 2026-02-09 |
| DI-3 | Add startup/shutdown lifecycle order and service health checks | todo | unassigned | TBD |
| DI-4 | Ensure routes and GUI resolve dependencies through container/facades only | done | codex | 2026-02-09 |

## Module Relocation / Cohesion
| ID | Task | Status | Owner | Target |
|---|---|---|---|---|
| MOD-1 | Move dev refactoring workflow modules from `core/` to `tools/` boundary | todo | unassigned | TBD |
| MOD-2 | Relocate non-extractor classifiers from `agents/extractors/` to analysis/classifier domains | todo | unassigned | TBD |
| MOD-3 | Remove vendored binaries and non-runtime artifacts from app package paths | todo | unassigned | TBD |

## Concurrency & Import Standardization
| ID | Task | Status | Owner | Target |
|---|---|---|---|---|
| CI-1 | Standardize async-first agent/service execution model | todo | unassigned | TBD |
| CI-2 | Isolate blocking calls behind thread executors where needed | todo | unassigned | TBD |
| CI-3 | Standardize absolute imports and remove fragile relative patterns | todo | unassigned | TBD |
| CI-4 | Remove `sys.path` bootstrap hacks once import graph is normalized | todo | unassigned | TBD |

## Phase Acceptance Criteria
### Phase 1 (Critical Fixes)
- All P0 tasks complete
- No known runtime import/type errors in critical path
- Auth dependency is enforced where required

### Phase 2 (Dedup + Logging)
- Duplicate modules removed or deprecated with no active references
- Single logging module adopted across codebase

### Phase 3 (Service Layer)
- `routes/documents.py` and `routes/agents.py` thin adapters to services
- Core business rules moved to `services/`

### Phase 4 (Decomposition)
- Top god modules split into maintainable components
- Coverage added for new module boundaries

### Phase 5 (Infra Modernization)
- DI container is authoritative dependency source
- Data access routed through repositories
- Startup and shutdown service lifecycle is deterministic
