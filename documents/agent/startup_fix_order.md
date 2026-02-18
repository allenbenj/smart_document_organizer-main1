# Startup Fix Order (Developer Action Plan)

This plan is based on startup captures in `logs/startup_trace/`:
- `startpy_live_20260218_130635.log`
- `summary_backend_20260218_130843.json`
- `python_verbose_backend_20260218_130948.log`
- `repo_files_from_verbose_import_20260218_130948_clean.txt`

## 1) Make backend-first mode the safe default in headless/WSL

Problem:
- Running `python Start.py` triggers GUI launch, which fails in headless/WSL with Qt plugin errors.

Evidence:
- `startpy_live_20260218_130635.log` contains Qt `wayland/xcb` load failures.

Fix:
- In `Start.py`, detect headless/WSL and default to backend mode (same behavior as `--backend`).
- Add explicit `--gui` flag for interactive desktop usage.

Why first:
- This blocks standard startup reliability in non-GUI environments.

Acceptance:
- `python Start.py` starts API without Qt errors in headless/WSL.
- GUI still launches when `--gui` is passed on supported desktops.

## 2) Remove startup race between GUI parent and backend child

Problem:
- Parent process warns "Backend did not become healthy before GUI launch" even when child backend soon reports startup complete.

Evidence:
- `startpy_live_20260218_130635.log` shows warning before backend health settles.

Fix:
- Increase wait robustness in `_wait_for_backend`:
  - extend timeout and backoff;
  - accept startup report endpoint as readiness signal;
  - block GUI launch until readiness succeeds (or fail fast with clear message).

Why second:
- Prevents false-negative startup status and unstable launch sequence.

Acceptance:
- No false health warning during normal startup.
- GUI launch proceeds only after backend readiness.

## 3) Gate heavy ML model initialization behind lazy loading

Problem:
- Startup eagerly imports/initializes large ML stacks and model plumbing.
- This increases boot time and increases failure surface.

Evidence:
- `summary_backend_20260218_130843.json` shows high import/compile/open event volume.
- `python_verbose_backend_20260218_130948.log` and extracted 287 repo paths show broad module fan-in at boot.

Fix:
- Move heavyweight agent/model loads to first-request or explicit warmup.
- Keep critical health/dependency checks lightweight.
- Cache initialized models/services after first load.

Why third:
- Largest impact on startup latency and operational reliability.

Acceptance:
- Cold startup time decreases materially.
- API health endpoint available before optional model warmup completes.

## 4) Prevent runtime network dependency during startup

Problem:
- Startup attempts model/resource resolution that can fail on DNS/network issues.

Evidence:
- `startpy_live_20260218_130635.log` shows GLiNER load warning with name resolution failure.

Fix:
- Enforce offline-safe startup:
  - do not download models at boot;
  - use pre-provisioned model cache paths;
  - downgrade missing optional model loads to deferred warnings.

Why fourth:
- Avoids fragile boot behavior in restricted or air-gapped environments.

Acceptance:
- Startup succeeds consistently with no outbound network required.

## 5) Separate optional frontend static mount from backend startup status

Problem:
- Missing `frontend/dist` marks plugin loading as failed even though backend API is healthy.

Evidence:
- `startpy_live_20260218_130635.log` has `Web GUI dist not found: frontend/dist`.

Fix:
- Classify missing web dist as optional feature-unavailable state, not startup failure.
- Report it distinctly in startup report and health details.

Why fifth:
- Improves operational signal quality and reduces noise.

Acceptance:
- Startup report clearly distinguishes critical failures from optional feature absence.

## 6) Add explicit startup profile flags

Problem:
- A single startup path currently tries to satisfy GUI + backend + agent initialization.

Fix:
- Add profile switches:
  - `STARTUP_PROFILE=api|minimal|full|gui`
  - `AGENTS_LAZY_INIT=true|false`
- Default production/server profile to `api` + lazy agents.

Why sixth:
- Makes behavior predictable per environment without code edits.

Acceptance:
- Startup behavior is deterministic from env/profile only.

## 7) Improve startup observability with per-phase timing budgets

Problem:
- Current logs are verbose but hard to convert into phase-level SLOs.

Fix:
- Emit structured startup phases with timing thresholds and pass/fail budget labels:
  - router include;
  - DI/bootstrap;
  - agent manager init;
  - optional integrations.

Why seventh:
- Enables actionable regression detection.

Acceptance:
- Startup report includes phase timings and threshold outcomes.

## 8) Add regression tests for launch modes

Problem:
- No guardrails for CLI mode behavior changes.

Fix:
- Add tests covering:
  - backend-only mode;
  - headless default mode;
  - GUI mode guard behavior;
  - readiness wait logic.

Why eighth:
- Locks in fixes and prevents recurrence.

Acceptance:
- CI includes mode-specific startup tests and passes.

---

## Recommended implementation sequence (short)

1. `Start.py` mode selection and headless default.
2. Readiness wait hardening.
3. Lazy model/agent initialization.
4. Offline-safe model loading policy.
5. Optional web dist status semantics.
6. Startup profile flags.
7. Structured startup timing/reporting.
8. Tests for all launch paths.
