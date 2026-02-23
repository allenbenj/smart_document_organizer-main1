# Repository Guidelines

This file is the authoritative project-level instruction set for Kilo Code
and compatible AI tooling. It defines **non-negotiable constraints**, workflow
discipline, and truth standards.

---

> **Assessment:** The contents of this guideline fully support the
> application intent.  It articulates mission, safety rules, structure,
> and agent APIs.  The description of the `agents/` directory has been
> expanded to note the reasoning/extraction/registry modules invoked by
> `/api/agents/*` endpoints.  No contradictory or missing guidance has
> been identified; the document can continue serving as the canonical
> contributor handbook.


## 0. Mission & Operating Philosophy

**Primary objective**
- Produce correct, reviewable, testable outputs grounded in source material.

**Required behavior**
- Always adhere to instructions provided by the system or reviewers.
- If a requirement is unclear or seems contradictory, stop and **ask
  questions**; do not proceed with guessing.
- Ignoring or circumventing directives is prohibited and leads to
  incorrect or potentially unsafe responses.

**Secondary objectives**
- Minimize churn and scope creep.
- Preserve developer intent and architectural clarity.
- Prefer explicit uncertainty over false precision.

**Core maxim**
> Structure is truth; content is evidence; inference must be labeled.

---
## 1. Non-Negotiables (Truth & Safety)

- Do **not** fabricate:
  - APIs, routes, config flags, environment variables
  - File contents, logs, stack traces, or test results
  - Case law, statutes, citations, or quotations
- If information is missing, explicitly state what is required to verify it.
- Never silently assume versions, defaults, or implicit behavior.

**Uncertainty rule**
- Facts → must be cited to files, routes, tests, or records.
- Inferences → must be labeled as such.
- Arguments → must be logically derived from stated facts/inferences.

---

## Project Structure & Module Organization
- `Start.py`: FastAPI app (and GUI launcher). Defines `app` and health routes.
- `routes/`: API routers (e.g., `documents.py`, `search.py`, `tags.py`). Each exposes a FastAPI `router`.
- `agents/`: Agent managers and integration helpers for the backend.  This folder holds the core reasoning/extraction/registry modules used by the FastAPI app and invoked via `/api/agents/*` endpoints (e.g. memory manager, legal reasoning agents, entity extractor, IRAC/Toulmin logic).
- `core/`, `utils/`, `diagnostics/`: Shared logic, utilities, and debug tooling.
- `mem_db/`: Lightweight, file-based DB helpers used by routers.
- `gui/`: Optional PySide6 dashboard entry points.
- `tests/`: Pytest suite (`test_*.py`, `conftest.py`).
- `tools/`, `logs/`, `watch/`, `documents/`: Dev utilities, runtime logs, watchers, and docs.

## Build, Test, and Development Commands
- Run API (dev): `python Start.py`
- Run with reload: `uvicorn Start:app --reload --host 0.0.0.0 --port 8000`
- Health check: `GET http://127.0.0.1:8000/api/health`
- Run tests: `pytest -q`
- Run a single test: `pytest tests/test_health.py -q`

## Coding Style & Naming Conventions

- Indentation: 4 spaces; follow PEP 8.
- Types: Prefer type hints for public functions.
- Naming:
  - `snake_case` → modules/functions
  - `CamelCase` → classes
  - `UPPER_SNAKE` → constants
- Routers:
  - One resource per file under `routes/`
  - Must expose `router = APIRouter()`
- Formatting:
  - Prefer `black` (line length 88)
  - Prefer `isort` when available
  
  ##  Change Control & Edit Discipline

- Keep diffs **minimal and scoped**.
- Do not refactor unrelated code “for cleanliness.”
- Do not rename files, symbols, or routes unless explicitly requested.
- For multi-file or architectural changes:
  - Produce a short plan **before** implementing.
  - Identify rollback and verification steps.


## Testing Guidelines
- Framework: `pytest` with `fastapi.testclient.TestClient` (see `tests/conftest.py`).
- Structure: Place tests under `tests/` mirroring module names; name files `test_*.py` and functions `test_*`.
- Coverage: No enforced threshold; aim for ≥80% on touched code.
- Examples: Add API tests like `tests/test_health.py` for endpoints.

## Commit & Pull Request Guidelines
- History: No Git history detected; use Conventional Commits (e.g., `feat:`, `fix:`, `docs:`).
- Commits: Small, focused, imperative mood (e.g., `fix: handle empty uploads`).
- PRs: Include a clear description, linked issues, before/after notes, and screenshots for GUI changes. Ensure tests pass and include new tests for new behavior.

## Architecture Notes & Tips
- Backend: FastAPI app in `Start.py` includes routers from `routes/`.
- Data: Routers default to `mem_db` managers; tests can swap to temp DB via fixtures.
- Ports: Default dev port `8000`. Update hard-coded paths only if necessary and prefer config where possible.

## Configuration & Env Vars

These environment variables configure agents and runtime behavior. Values may be set in your shell or a `.env` file in the project root.

- `ENV`: deployment environment (default `development`).
- `API_KEY`: if set, API requests must include header `X-API-Key: <value>`.
- `AGENTS_ENABLE_REGISTRY`: `1/true` to initialize the Agent Registry on startup.
- `AGENTS_ENABLE_LEGAL_REASONING`: enable legal reasoning agents.
- `AGENTS_ENABLE_ENTITY_EXTRACTOR`: enable entity extraction agents.
- `AGENTS_ENABLE_IRAC`: enable IRAC reasoning components.
- `AGENTS_ENABLE_TOULMIN`: enable Toulmin reasoning components.
- `AGENTS_CACHE_TTL_SECONDS`: TTL for agent caches (default `300`).
- `VECTOR_DIMENSION`: vector embedding dimension used by the vector store (default `384`).
- `MEMORY_APPROVAL_THRESHOLD`: confidence threshold in [0,1] for auto-approval of memory proposals (default `0.7`).

Runtime checks:
- Health details: `GET /api/health/details` shows `auth` status, `vector_store` readiness, and `agents` (registry) status.
- Metrics: `GET /api/metrics` returns simple per-path and per-method counters.

## Memory Governance Rules (Critical)

**Approval ≠ Truth**

- Auto-approval is a *confidence heuristic*, not correctness.
- Approved memory may still be:
  - incomplete
  - context-dependent
  - later contradicted

**Memory hygiene**
- Memory entries must:
  - identify their source (document, route, transcript, test, etc.)
  - separate fact from interpretation
- High-impact or sensitive entries should be flagged even if approved.
- Conflicting memories must be reconciled or annotated, never silently overwritten.

---

## Memory Review API

Endpoints (under `/api/agents`):
- `POST /agents/memory/proposals`: propose a memory entry for review (fields: `namespace`, `key`, `content`, `memory_type`, `agent_id?`, `document_id?`, `metadata?`, `confidence_score`, `importance_score`). Auto-approval if `confidence_score >= MEMORY_APPROVAL_THRESHOLD`.
- `GET /agents/memory/proposals`: list proposals (SQLite-backed) with `status` and `flags`.
- `POST /agents/memory/proposals/approve`: approve and store proposal (optional `corrections`).
- `POST /agents/memory/proposals/reject`: reject proposal.
- `POST /agents/memory/correct`: correct a stored record (content/metadata/scores).
- `POST /agents/memory/delete`: delete a stored record.
- `GET /agents/memory/flags`: flagged proposals and counts by flag type (`low_confidence`, `high_impact`, `sensitive`, `conflict`).
- `GET /agents/memory/stats`: totals, by status, flag counts, and approved index size.

## 2. Key System Capabilities

The Smart Document Organizer includes several advanced subsystems that
implement its legal‑AI intent.  These capabilities are all exercised via
tagged agent endpoints (`/api/agents/<name>`) and are supported by
corresponding modules under `agents/`.

### Legal Reasoning Engine

- Located in `agents/legal_reasoning.py` (and related helpers).  Exposed via
  `POST /api/agents/legal_reasoning` and `/status`.
- Implements IRAC/Toulmin‑style reasoning pipelines, supporting multiple
  personas and chain‑of‑thought prompts.  Outputs structured arguments,
  risk assessments, and recommended actions.
- The GUI tabs `legal_reasoning_tab.py` and `planner_judge_tab.py` are
  front‑ends to this engine.
- **Role/flow:** this engine consumes extracted fact sets or entire
  documents produced by the hybrid extractor, applies issue tree logic
  and the truth judge, then writes its conclusions back into the memory
  manager or returns them directly for export.  It is typically invoked
  after entity extraction and semantic analysis, feeding into
  contradiction/violation checks and pipeline stages.

### Shadow‑Mode Hybrid Legal Extractor

- Core extraction logic lives in `agents/extractors/hybrid_extractor.py`.
- Runs in "shadow mode" when `AGENTS_ENABLE_ENTITY_EXTRACTOR=1`; it
  processes documents but does not immediately write results to memory
  unless approved.
- Combines keyword heuristics, GLiNER zero‑shot models, and LLM
  fallbacks.  Behaves like a hybrid system that audits itself by running
  multiple extractors in parallel and flagging discrepancies.
- GUI interaction via `/api/agents/extract/proposals` and the
  `EntityExtractionTab`, with audit layout in `gui/tabs/heuristic_lifecycle_tab.py`.
- **Sequence:** documents arrive via the Document Processing Tab or API
  upload, are handed to the extractor.  The extractor returns a set of
  entity proposals that feed the memory manager (as proposals) and also
  provide input for the reasoning engine.  A separate audit thread
  evaluates extractor agreement and flags low‑confidence items; these
  are reviewed in the heuristic lifecycle tab.

### Reasoning Framework & Cognitive Reasoning Service

- Provided by `agents/reasoning_service.py` and the `core/reasoning` package.
- Supports a Perspective Switcher that alters the agent's viewpoint (e.g.
  plaintiff vs. defendant) via configurable context templates.
- Implements Toulmin model for argument structure, with `claims`,
  `grounds`, `warrants`, and `backing` represented in JSON payloads.
- Includes a dynamic **Truth Judge** component (`agents/truth_judge.py`) that
  evaluates tentative assertions against issue trees and a strategic map
  (stored in `agents/issue_tree.py`) before allowing them into memory.
- The service is callable at `/api/agents/cognitive_reasoning` and
  is used by higher‑level APIs (e.g. legal reasoning engine, planner/judge).
- **Data flow:** this service sits between extraction and final output.
  It receives candidate facts/entities from the extractor, consults the
  strategic map to determine relevant legal issues, applies perspective
  rewriting, and then either returns structured reasoning or writes
  vetted claims to the memory manager.  Other subsystems (e.g.
  vector search) may also query its results when constructing evidence
  chains.

### Perspective Switcher & Strategic Map

- The Perspective Switcher is a small middleware (`agents/perspective.py`) that
  rewrites prompts based on `env.PERSPECTIVE` or runtime argument; used by
  both extraction and reasoning agents.
- The Strategic Map subsystem (`agents/strategic_map.py`) maintains a
  directed graph of goals, subgoals, and dependencies.  It is editable via
  `/api/agents/strategy` endpoints and visualized in the GUI's
  `provenance_highlighting` and `planner_judge` tabs.

### Shadow Mode Audit Layout

- When the system runs in `ENV=production` with `STRICT_PRODUCTION_STARTUP`,
  the extractors and reasoners operate in shadow mode by default: they log
  results to `logs/shadow/` and expose them through `/api/agents/shadow/*`
  endpoints without modifying memory.
- Audit reports are generated by `agents/audit.py` and the GUI layer uses
  `heuristic_lifecycle_tab.py` to present them alongside status markers.

### Digital Jurist Blueprint & Thinking Layer

- The "Digital Jurist" is the umbrella term for the stack described
  above.  Its **thinking layer** consists of the Cognitive Reasoning
  Service plus supporting rule engines in `agents/rule_engine.py` and
  `core/heuristics.py`.
- These modules provide evaluation of issue trees, heuristic rules, and
  truth judgments; they are heavily instrumented by `diagnostics/` for
  auditability.

### Data Management & Proposal Tables

- All transient decisions (extraction proposals, memory proposals,
  reasoning drafts, heuristic candidates) are stored in SQLite tables under
  `mem_db/` (e.g. `memory_proposals`, `organization_proposals`).
- Access is abstracted by `agents/memory_manager.py` and
  `agents/proposal_store.py`; these provide CRUD APIs used by `/api/agents`.
- Tables include metadata columns (`source_file`, `confidence_score`,
  `flags`) to support governance rules.

### Agent Memory Manager

- Implemented in `agents/memory_manager.py` and its submodules.
- Manages the lifecycle of memory entries, including auto‑approval
  heuristics, conflict detection, and provenance indexing.
- Exposes REST endpoints under `/api/agents/memory/*` (see earlier section).
- GUI front‑ends: `memory_review_tab.py`, `memory_analytics_tab.py`, and
  `gui/open_memory_review.py`.

### System Workflow Overview

The system operates as a loosely‑coupled pipeline:

1. **Ingestion & Processing** – files arrive via upload or filesystem
   watchers; `DocumentProcessingTab` (or API) extracts text/metadata and
   stores the normalized document in `mem_db`.
2. **Extraction** – the Hybrid Legal Extractor analyses the text, producing
   entity proposals. These proposals are sent to the memory manager as
   pending entries and also forwarded to the reasoning framework as
   candidate facts.
3. **Semantic Analysis** – optionally, semantic analysis runs to cluster
   themes or summaries; results may seed the strategic map or vector
   search indices.
4. **Reasoning** – the Cognitive Reasoning Service takes candidate facts,
   applies perspective switching, consults the issue tree/strategic map,
   and invokes the Truth Judge. Approved claims are routed back into
   memory; full reasoning outputs are returned for GUI export or as
   input to contradictions/violations agents.
5. **Legal Reasoning & Planning** – specialized reasoning engines perform
   IRAC/Toulmin analysis or Planner‑Judge cycles on the vetted data.
6. **Governance & Audit** – heuristic lifecycle and shadow‑mode audits
   monitor the extractor and reasoning modules. Discrepancies trigger
   UI review workflows; audit logs persist under `logs/shadow/`.
7. **Memory & Vector Stores** – approved memory entries are indexed and
   made available for retrieval via `/api/agents/memory/search` and the
   vector search subsystem. Downstream components (e.g., knowledge graph,
   contradictions, legal reasoning) query these stores when needed.

Every step emits diagnostic events captured by the `diagnostics/` tools,
allowing post‑hoc investigation and ensuring the entire flow is
traceable from raw document through final decision.

---

This section augments the guidelines with a blueprint of the system’s
unique AI capabilities and their implementation loci.  Contributors should
refer back here when extending or auditing those features.
Review UI:
- Memory Review Tab in the main dashboard (GUI) lists proposals and supports Approve/Reject.
- Standalone: `python -m gui.open_memory_review`.

## Pipeline Orchestration (DAG + Conditions)

- Pipelines execute as a dependency-aware DAG.
- Steps may run in parallel when dependencies are satisfied.
- `when` expressions must be:
  - side-effect free
  - safe boolean expressions
  - evaluated against shared context only

**Rule**
- A step must not assume another step’s output unless declared in `depends_on`.

---

## Mode Expectations (Architect / Code / Debug / Ask)

**Architect**
- Plans only. No code edits unless explicitly authorized.
- Must identify risks and acceptance criteria.

**Code**
- Implements approved plans step-by-step.
- No architectural improvisation.

**Debug**
- Follow scientific method:
  1. Reproduce
  2. Isolate
  3. Fix
  4. Regression test

**Ask / Review**
- Read-only.
- Cite file paths, routes, or records.
- No speculative edits.

---

## Legal & Analytical Writing Discipline (When Enabled)

- Separate:
  1. Facts (with record support)
  2. Inferences
  3. Arguments
- No unstated assumptions.
- No uncited authority.
- Use calibrated language: *appears*, *suggests*, *consistent with*.
- Prefer plain English and active voice.

---

## Final Rule

When rules conflict:
**Mode rules > project rules (this file) > global rules > personal preferences**

When in doubt:
- Stop
- State the uncertainty
- Ask for the missing input