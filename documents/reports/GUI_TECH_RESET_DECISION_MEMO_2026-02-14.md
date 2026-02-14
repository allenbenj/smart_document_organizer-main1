# GUI Technology Reset Decision Memo
**Date:** 2026-02-14  
**Repo:** `smart_document_organizer-main`  
**Scope:** Replace unstable/fragmented GUI while preserving memory-first organization workflow.

---

## Executive Summary

### Recommendation
Adopt **(B) Web-first React + TypeScript frontend with existing FastAPI backend** as the target stack.

### Why
- The backend is already the system of record and is rich in workflow endpoints (`/api/taskmaster/*`, `/api/organization/*`, `/api/startup/*`, `/api/health/*`).
- Current PySide6 desktop layer shows known lifecycle/thread fragility:
  - `QThread: Destroyed while thread '' is still running` (`gui-launch-error.log`)
  - shutdown coroutine warnings (`HealthLifecycleMixin.shutdown was never awaited`) in `gui-crash.log`
- Current GUI implementation is tab-heavy and duplicated in behavior (multiple `QThread` workers making direct HTTP calls in `gui/tabs/workers.py`, plus parallel structures in `gui/workers/*`), causing fragmented UX and hard-to-test flows.
- A web UI aligns directly with observability goals: easier instrumentation, deterministic state management, better testing automation, cleaner long-running job UX.

### Transitional Note
Do **not** hard-cut. Run a phased migration where PySide remains available as a fallback shell while the new web workflow becomes primary.

---

## Current-State Findings (Grounded in Repo)

## 1) Architecture already backend-first
- `Start.py` hosts FastAPI with explicit startup lifecycle, health, diagnostics, rate-limit middleware, and route modularization.
- Router bootstrap (`app/bootstrap/routers.py`) already includes organization, taskmaster, files, knowledge, health, etc.
- Organization pipeline is service-ized (`services/organization_service.py`) and exposed (`routes/organization.py`).
- Task orchestration and long-running event model already exists (`services/taskmaster_service.py`, `routes/taskmaster.py`).

## 2) UI instability indicators are real
- `gui-launch-error.log`: `QThread destroyed while thread ... still running`.
- `gui-crash.log`: coroutine not awaited during shutdown.
- GUI shutdown code in `gui/gui_dashboard.py` performs best-effort thread cleanup; this confirms known complexity around worker lifecycle.

## 3) Workflow fragmentation
- Main dashboard builds many independent tabs (`Semantic`, `Entity`, `Legal`, `Embedding`, `KG`, `Vector`, `Classification`, `Document Organization`, `Pipelines`, `Memory`...).
- Each tab tends to own request orchestration, status, and worker wiring, creating duplicated logic and inconsistent state handling.
- Worker file (`gui/tabs/workers.py`) contains many near-duplicate request patterns and timeout assumptions, which increases drift risk.

## 4) Observability is strongest at API layer, weakest in GUI layer
- Backend has `/api/startup/report`, `/api/startup/steps`, `/api/startup/services`, `/api/startup/awareness` and structured run/event tables.
- GUI has limited cross-tab event timeline and no robust global run-trace view.
- Existing `tools/org_console/app.py` already demonstrates a practical web workflow for organization + startup diagnostics, validating the web direction.

---

## Option Comparison

Scoring: 1 (poor) to 5 (strong)

| Criterion | (A) Keep PySide6 + Refactor | (B) Web-first React/TS + FastAPI | (C) Hybrid Shell (Tauri/Electron + Web UI) |
|---|---:|---:|---:|
| Architecture fit with existing backend | 3 | **5** | 4 |
| Stability risk (thread/lifecycle) | 2 | **4** | 3 |
| Dev velocity (next 3 months) | 3 | **5** | 2 |
| Testability (unit/integration/e2e) | 2 | **5** | 3 |
| Long-running job UX | 3 | **5** | 4 |
| Offline/local operation | **5** | 4 | **5** |
| Packaging complexity | 3 | **4** | 2 |
| Observability coherence | 2 | **5** | 4 |
| Workflow coherence (memory-first) | 3 | **5** | 4 |

### A) Keep PySide6 + Refactor
**Pros**
- Lowest immediate stack change.
- Native desktop/offline is already present.

**Cons**
- Existing failure mode is exactly in this layer (QThread + shutdown lifecycle).
- High refactor effort to centralize workers, eliminate duplicated tab logic, and make robust.
- GUI automated testing remains comparatively weak/slow.

### B) Web-first React/TypeScript + FastAPI (Recommended)
**Pros**
- Reuses current backend contracts directly.
- Enables unified state machine for runs/events/proposals.
- Stronger observability UI and testability (Playwright + component tests).
- Faster incremental delivery (route by route).

**Cons**
- Introduces Node toolchain.
- Requires auth/session and API client conventions if expanded beyond localhost.

### C) Hybrid Shell (Tauri/Electron)
**Pros**
- Good if strict desktop distribution is required.
- Can still use web UI architecture.

**Cons**
- Adds packaging/build complexity too early.
- Not necessary to solve current robustness problems; can be deferred until web app stabilizes.

---

## Recommended Target Stack

## Target
**FastAPI backend + React/TypeScript SPA frontend** (web-first, local-first), with optional desktop shell later.

## Principles
1. **Backend remains source of truth** for runs, events, proposals, actions.
2. **Memory-first workflow** represented as one guided pipeline, not scattered tabs.
3. **Observability-first UI**: startup health, run timeline, queue depth, and action audit always visible.
4. **Long-running-safe UX**: optimistic UI + polling/event stream + resumable views.

---

## Phased Migration Plan (Start Immediately)

## Phase 0 (Now, 1–2 days): Stabilize and freeze API contracts
- Keep current FastAPI routes as contract base.
- Define explicit UI-facing response schemas for:
  - `GET /api/taskmaster/runs`, `GET /api/taskmaster/runs/{id}/events`
  - `POST /api/taskmaster/runs/file-pipeline`
  - `GET/POST /api/organization/*`
  - `GET /api/startup/*`
- Add a single compatibility note in docs: old PySide tabs are in maintenance mode.

## Phase 1 (Week 1): New Web App skeleton + first coherent workflow
Build a minimal but complete **Memory-First Organization Console v1**:
- Left rail: Startup/Health + queue snapshot.
- Main stepper:
  1. Index/Refresh (TaskMaster run)
  2. Analyze Indexed (optional)
  3. Generate Proposals
  4. Review/Approve/Edit
  5. Apply (dry-run then real)
- Right rail: Live run event feed (polling every 2–5s from `/api/taskmaster/runs/{id}/events`).

## Phase 2 (Week 2–3): Migrate high-value tabs into workflows
- Replace isolated tabs with workflow pages:
  - Ingestion & Indexing
  - Analysis & Knowledge
  - Organization & Execution
  - Memory Review/Flags
- Keep PySide launcher but add “Open Web Console” as default action.

## Phase 3 (Week 4+): Decommission PySide risk surface
- Remove most QThread-based orchestration from PySide.
- Keep only minimal desktop bootstrap if needed.
- Decide later on packaging target:
  - pure local web app (preferred early), or
  - Tauri wrapper if desktop distribution requirements remain.

---

## Concrete First Implementation Slice (Can Start Today)

**Slice goal:** Deliver one production-usable page that runs memory-first organization end-to-end.

### Scope
1. Launch `organize_indexed` pipeline run.
2. Show run status + live events.
3. Generate and list proposals (scoped root optional).
4. Approve/edit/reject proposals.
5. Dry-run apply + real apply.
6. Show recent actions and rollback group IDs.

### Why this slice
- Touches core user value quickly.
- Uses already-available endpoints; no backend rewrite.
- Proves coherence vs fragmented tab model.

---

## File-Level Starter Plan (in this repo)

### Backend (small additions only)
1. **`routes/organization.py`**
   - Add optional `root_prefix` filter to list endpoint (currently generation/clear support this; list does not).
2. **`services/organization_service.py`**
   - Add filtered list helper and standard response metadata (`count`, `has_more`).
3. **`routes/taskmaster.py`**
   - Add lightweight `GET /taskmaster/runs/{id}/summary` (derived KPIs for UI cards).
4. **`tests/`**
   - `tests/test_organization_routes_web_console.py`
   - `tests/test_taskmaster_run_summary.py`

### New frontend workspace (proposed)
Create: **`frontend/`**

- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/vite.config.ts`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/lib/api.ts` (typed API client)
- `frontend/src/types/api.ts` (route response types)
- `frontend/src/features/startup/StartupHealthPanel.tsx`
- `frontend/src/features/taskmaster/RunLauncher.tsx`
- `frontend/src/features/taskmaster/RunEventsFeed.tsx`
- `frontend/src/features/organization/ProposalTable.tsx`
- `frontend/src/features/organization/ProposalEditorDrawer.tsx`
- `frontend/src/features/organization/ApplyPanel.tsx`
- `frontend/src/features/layout/MemoryFirstStepper.tsx`
- `frontend/src/state/useOrganizationFlowStore.ts` (Zustand/Redux Toolkit)
- `frontend/src/hooks/usePolling.ts`
- `frontend/tests/e2e/organization-flow.spec.ts` (Playwright)

### Integration / launch
- Update `tools/run_app.py` to optionally launch frontend dev server (`--with-web`), while retaining API and current console behavior.
- Add docs:
  - `documents/guides/WEB_GUI_MIGRATION.md`
  - `documents/guides/MEMORY_FIRST_WORKFLOW_UI.md`

---

## Risks and Mitigations

1. **Risk:** API payload inconsistencies across routes.  
   **Mitigation:** Add `src/types/api.ts` + backend response normalization tests.

2. **Risk:** Polling load for event feeds.  
   **Mitigation:** 2–5s adaptive polling; cap events by cursor/limit; later SSE/WebSocket.

3. **Risk:** Dual-UI confusion during migration.  
   **Mitigation:** Mark PySide as maintenance mode and route users to web-first workflow.

4. **Risk:** Packaging uncertainty.  
   **Mitigation:** Defer Electron/Tauri until workflow stabilizes; package decision after Phase 2.

---

## Decision
Proceed with **Option B: Web-first React/TypeScript + FastAPI**, with phased migration and immediate delivery of a memory-first organization workflow page. Keep PySide only as transitional fallback to minimize disruption while removing the dominant stability risk surface.
