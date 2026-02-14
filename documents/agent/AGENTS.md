# Repository Guidelines

This file is the authoritative project-level instruction set for Kilo Code
and compatible AI tooling. It defines **non-negotiable constraints**, workflow
discipline, and truth standards.

---

## 0. Mission & Operating Philosophy

**Primary objective**
- Produce correct, reviewable, testable outputs grounded in source material.

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
- `agents/`: Agent managers and integration helpers for the backend.
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