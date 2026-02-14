# ARCHITECTURE SPEC V2 — Memory-First Web Workflow
**Date:** 2026-02-14
**Status:** Phase C quality pass complete (v2 rebuild in progress)
**Primary UI:** React + TypeScript web app (`frontend/`)
**Backend:** Existing FastAPI service (non-breaking extension)

## 1) Scope and Intent
This specification defines the v2 memory-first orchestration workflow as a guided, stateful web experience backed by explicit workflow contracts.

- Preserve existing backend behavior and routes.
- Add additive v2 workflow endpoints/contracts.
- Keep legacy PySide GUI available during migration (**legacy / maintenance mode**).

## 2) Legacy + Transition Policy
- Existing GUI under `gui/` remains intact and runnable.
- New workflow is implemented in `frontend/` and exposed through additive backend routes.
- Legacy GUI is marked as fallback only; no destructive removal in this phase.

## 3) Memory-First Stepper Workflow
Persistent left-rail stepper (always visible):
1. **Sources** — define source roots + inclusion/exclusion profile.
2. **Index + Extract** — indexing and structured extraction run.
3. **Summarize** — memory-relevant summarization and confidence markers.
4. **Proposals** — bulk proposal generation for organization/actions.
5. **Review** — approve/reject/edit proposals with ontology-level adjustments.
6. **Apply** — dry-run then committed apply.
7. **Analytics** — run outcomes, action counts, rollback groups, and drift indicators.

Each step has:
- `status`: `not_started | in_progress | blocked | complete | failed`
- `draft_state`: `clean | dirty | saving | failed`
- `updated_at`, `updated_by`, `checkpoint_id`

## 4) Draft-State Indicator
Global draft-state indicator appears in the top strip:
- **Clean**: no local edits pending.
- **Dirty**: pending unsaved edits (proposal text, ontology edits, selection changes).
- **Saving**: optimistic save + server acknowledgement in progress.
- **Failed**: save conflict/network error with retry CTA.

Conflict strategy:
- Per-entity `version` and `etag` in payloads.
- Reject stale write with conflict object + server snapshot.

## 5) Bulk Ops + Granular Ontology Edits
### Bulk operations
- Approve/reject/edit multiple proposals in one action.
- Batch payload includes `idempotency_key` and operation fingerprint.

### Granular ontology edits
- Node-level/class-level/property-level updates.
- Inline patch model (`add/remove/replace`) and optional semantic validation.

## 6) Undo Stack and Audit
- Session-level undo stack for reversible actions (client + server acknowledged).
- Server emits `undo_token` for each mutation-capable operation.
- Undo operation validates token freshness and resource version.
- All changes are written to audit event stream.

## 7) Progress Persistence + Resume
- Workflow progress persisted per `job_id`.
- Step checkpoint includes:
  - active step
  - form selections
  - cursor/page pointers
  - last processed entity offsets
- Resume on refresh/session restart via `GET /api/workflow/jobs/{job_id}/status`.

## 8) Webhook Callback Support
- Optional callback URL per job.
- Delivery events:
  - `step.started`
  - `step.completed`
  - `step.failed`
  - `job.completed`
  - `job.failed`
- Signed callback payload (`X-Workflow-Signature` HMAC).
- Retry policy: exponential backoff + dead-letter record after max attempts.

## 9) Pagination Strategy
List-bearing endpoints use cursor-capable pagination with offset fallback:
- request: `limit`, `offset` and/or `cursor`
- response: `count`, `has_more`, `next_cursor`

Default limits:
- proposals: 100
- events: 200
- results: 100

## 10) Idempotency Key Strategy
Mutation endpoints accept `idempotency_key`:
- key unique per operation intent window.
- server stores key + request hash + response hash.
- duplicate key with same hash -> replay previous response.
- duplicate key with mismatched hash -> `409 idempotency_conflict`.

## 11) UI Shell Requirements (Kickoff)
- Persistent left-rail stepper.
- Run console panel with recent events + job summary.
- System health strip (backend and queue posture snapshot).
- Placeholder views for all 7 workflow steps.

## 12) Non-Goals (This Slice)
- No removal/refactor of legacy PySide tabs.
- No breaking change to existing `/api/taskmaster/*` and `/api/organization/*` behavior.
- No websocket/SSE requirement in kickoff (polling-friendly contracts).

## 13) Phase C Quality Pass (Current)
Completed smoke coverage now validates the v2 workflow surface expected by the web UI:
- Frontend-facing workflow contract path (`create job` -> `status` -> `execute proposals` -> `results`).
- Organization Console static serving and proxy failure envelopes (GET + POST).
- PySide migration safety checks for guarded fallback tabs and legacy-fallback doc guarantees.

This keeps web-first v2 delivery confidence high while PySide remains in maintenance-mode fallback.

