# Holistic Remediation Task List

_Last updated: 2026-02-13 18:46 CST_

## Objective
Ship a stable, production-safe backend by addressing critical architecture and runtime risks in a phased, auditable way.

## Context note (single-user desktop)
This project is being evaluated primarily as a **single-user desktop tool**. Priority and severity are adjusted accordingly:
- Concurrency/abuse risks are still important, but lower than internet-exposed multi-tenant services.
- Data durability, migration safety, and file-system safety remain top priorities.
- Security controls should be pragmatic-by-default (safe defaults without over-complicating local use).

---

## A) SQLite Concurrency & Reliability

### B1. Locking under concurrent load — 🔴 Critical
- [x] Enable `PRAGMA journal_mode=WAL`
- [x] Enable `PRAGMA synchronous=NORMAL`
- [x] Enable `PRAGMA busy_timeout=5000`
- [x] Replace per-call connect/close with thread-local persistent connections
- [x] Add explicit `close()` on `DatabaseManager`
- [x] Add bounded retry wrapper for transient `database is locked` writes
- [x] Add contention stress test scenario (API + scheduler parallel writes)

### B2. Transaction discipline — 🟠 High
- [x] Audit long-running write transactions in services
- [x] Split large write batches into shorter commits where safe
- [x] Ensure scheduler jobs avoid prolonged write locks

---

## C) DatabaseManager Decomposition (God-class breakup)

## C0. Design target
`DatabaseManager` becomes a thin façade/orchestrator; domain SQL lives in repositories.

### C1. Repository scaffold — ✅ Done
- [x] `mem_db/repositories/base.py`
- [x] repository package init

### C2. Extracted domains — ✅ Done
- [x] `OrganizationRepository`
- [x] `TaskMasterRepository`
- [x] `KnowledgeRepository`
- [x] `PersonaRepository`
- [x] `FileIndexRepository` (major extraction)

### C3. Delegation completed in `DatabaseManager` — 🟡 In Progress
- [x] Organization methods delegated
- [x] TaskMaster methods delegated (including schedules)
- [x] Knowledge methods delegated
- [x] Persona/skills methods delegated
- [x] File index/chunks/entities/tables/embeddings/duplicates/scan manifest delegated
- [x] Document CRUD/search/tag/analytics methods delegated to `DocumentRepository`
- [x] Watched directory methods delegated to `FileIndexRepository`
- [x] Remove remaining duplicate SQL from `DatabaseManager`

### C4. Final architecture cleanup — 🟡 In Progress
- [x] Add `DocumentRepository`
- [x] Optional split: `WatchRepository` for watched directories + scan manifest
- [x] Prune stale imports from `database.py`
- [x] Add repository-level tests and fixtures

---

## D) Startup/Admin Observability & Control

### D1. Startup diagnostics — ✅ Done
- [x] Startup step timeline (real states + elapsed)
- [x] Service dependency checks with latency
- [x] Environment snapshot
- [x] Awareness endpoint/status
- [x] Admin monitor panels in org console

### D2. Remaining operations controls — 🟡 In Progress
- [x] Log-tail endpoint for admin GUI
- [x] Retry check controls from GUI
- [x] Guarded restart hook (if allowed by runtime policy)
- [x] Diagnostics export improvements (include recent awareness events + config digest)

---

## E) Warning/Error Debt (non-optional for production)

- [x] Remove deprecated string-key DI warnings at startup
- [x] Resolve pipeline router blocker (`message_bus`)
- [x] Reclassify optional dependency noise to INFO
- [ ] Decide policy for optional dependency status (strict vs optional profiles)
- [ ] Pin dependency profiles (`core` vs `extended`) in docs + CI

---

## F) Testing & Governance

- [ ] Add regression tests for all extracted repository adapters
- [x] Add contract tests for routes touching refactored DB methods
- [ ] Add concurrency test for SQLite locked-write behavior
- [ ] Add static analysis in CI for architecture guardrails (max class length / layer boundaries)
- [x] Add migration-safe checklist for future schema changes

---

## G) Schema Migration Architecture (replace ad-hoc ALTERs) — 🟠 High

### Problem
Ad-hoc `ALTER TABLE ...` statements with broad `except: pass` create unknown schema state and hide real failures.

### Target architecture
- [x] Add `schema_migrations` table:
  - `version INTEGER PRIMARY KEY`
  - `name TEXT NOT NULL`
  - `applied_at TIMESTAMP NOT NULL`
  - `checksum TEXT`
  - `success INTEGER NOT NULL`
  - `error TEXT`
- [x] Add migration runner module: `mem_db/migrations/runner.py`
- [x] Add numbered migration scripts folder: `mem_db/migrations/versions/`
  - `0001_baseline.py`
  - `0002_legacy_schema_upgrades.py`
- [x] Startup contract:
  - no silent swallow of DDL errors
  - migration execution is versioned and recorded
- [x] Strict-mode fail-fast integration for migration errors (explicit policy hook)
- [x] Expose migration status in startup diagnostics endpoint
- [x] CLI/admin utility:
  - `python -m mem_db.migrations.runner status`
  - `... migrate`
  - `... current`

### Rollout sequence
1. Snapshot current schema into `0001_initial` baseline marker.
2. Move existing ALTER-block logic into idempotent numbered migrations.
3. Remove swallowed-exception migration block from `database.py`.
4. Add migration status endpoint integration.

---

## H) Knowledge Proposal Durability — 🟠 High

### Problem
Knowledge proposals currently exist in process memory and are lost on restart.

### Target architecture
- [x] Add DB table `knowledge_proposals` (parallel to organization proposals)
- [x] Add proposal persistence methods in `KnowledgeRepository`
- [x] Refactor `services/knowledge_service.py`:
  - remove module globals (`_proposals`, `_proposal_seq`)
  - persist all proposal lifecycle operations to DB
- [x] Keep existing endpoints functional via service-layer compatibility shape
- [ ] Optional: add `knowledge_proposal_feedback` table for audit trail
- [ ] Optional: add `reviewed_by` if/when user identity is introduced

### Rollout sequence
1. ✅ Introduce table + repository persistence.
2. ✅ Switch reads/writes to DB-backed proposal lifecycle.
3. ⏳ Add optional audit enrichment when identity model is defined.

---

## I) Start.py Monolith Reduction — 🟡 Medium

### Problem
`Start.py` mixes router wiring, startup lifecycle, diagnostics, middleware, and inline endpoints.

### Target architecture
- [x] Extract router registration to `app/bootstrap/routers.py`:
  - `register_routers(app, protected_dependencies)`
  - declarative router manifest to avoid repeated try/except blocks
- [x] Extract startup lifecycle to `app/bootstrap/lifecycle.py`:
  - startup steps, service init, shutdown
- [x] Extract diagnostics/reporting to `diagnostics/startup_report.py`
- [ ] Keep `Start.py` as thin composition root (<200 LOC target)

### Rollout sequence
1. Move router registration first (no behavior change).
2. Move diagnostics builders.
3. Move startup/shutdown orchestration.
4. Keep route/API compatibility unchanged.

---

## J) Data Flow Risk Mitigations

### J1. Ingestion pipeline (`FileIndexService.index_roots`) — 🟠 High

#### Current risk
Large nested method mixes traversal, validation, parsing, metadata/tagging, DB writes, and fallback behavior.

#### Target architecture
- [x] Split into pipeline stages/classes:
  - `FileDiscoveryStage`
  - `ValidationStage`
  - `ExtractionStage`
  - `EnrichmentStage`
  - `PersistenceStage`
- [x] Add per-file transactional boundary strategy:
  - stage-level commits with rollback policy for dependent records
  - ensure no orphan chunks/entities/embeddings on partial failure
- [x] Add ingest job result model with explicit stage failure reason

### J2. Organization LLM call path divergence — 🟠 High

#### Current risk
`OrganizationService._llm_suggest` uses direct `httpx` call path outside shared `LLMManager`.

#### Target architecture
- [x] Route all LLM requests through `core.llm_providers.LLMManager`
- [x] Add organization-specific prompt adapter but shared transport/auth/retry
- [x] Add provider/model override policy in one place
- [x] Remove direct xAI HTTP implementation from organization service

---

## Priority calibration from latest review

### P0 (desktop-pragmatic critical)
- [x] WAL + busy timeout
- [x] Rate limiting middleware
- [x] Persist knowledge proposals to DB

### P1 (next major block)
- [x] Complete `DatabaseManager` split (remaining document/watch methods)
- [x] Add schema migration versioning runner
- [x] Sanitize LLM-suggested paths before apply/move
- [x] Consolidate organization LLM calls through `LLMManager`

### P2 (backlog)
- [x] Refactor monolithic `Start.py` into modules
- [ ] Add global structured exception responses
- [ ] Optional: stronger SQLite pooling strategy or DB migration path
- [x] Add circuit breaker for LLM provider outages
- [ ] Improve file scan parallelism
- [ ] Add memory eviction policy
- [ ] Raise test depth/coverage

## Immediate Next Steps (execution order)

1. Extract `DocumentRepository` and delegate document CRUD/search/tag/analytics.
2. Move watched-directory methods to repository layer.
3. Remove duplicate SQL blocks from `DatabaseManager`.
4. Add retry-on-lock helper for write operations.
5. Implement schema migration runner (`schema_migrations` + numbered files).
6. Refactor Start.py into router/lifecycle/diagnostics modules.
7. Unify organization LLM calls behind `LLMManager`.
8. Add tests for limiter + SQLite contention + repository delegation + migrations.

---

## Definition of Done

- `DatabaseManager` is orchestration/façade only (no domain SQL bodies).
- All domains have focused repositories with clear ownership.
- Rate limiting and SQLite contention mitigations are active and tested.
- Migration system is versioned, auditable, and fail-fast (no swallowed DDL errors).
- Knowledge proposals are durable across restarts.
- Start.py is reduced to a thin composition root.
- Organization LLM calls use one shared provider path (`LLMManager`).
- Admin startup/awareness diagnostics remain complete and actionable.
- No critical known issues left open in this plan.
