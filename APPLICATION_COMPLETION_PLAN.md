# Application Completion Plan
## Date: March 31, 2026

This plan replaces assumption-based completion claims with an evidence-based path to application readiness.

## Current Assessment

### What is clearly implemented
- The repository has substantial application breadth across backend routes, service layer, persistence, agents, and PySide6 GUI surfaces.
- The main codebase compiles successfully with `python -m compileall Start.py launch.py services routes gui app agents mem_db utils core config`.
- The launcher entry point works at the CLI level via `python launch.py --help`.
- The project includes a large verification surface with 100 test files under `tests/`.

### What is not yet proven complete
- The runtime environment is not provisioned for the declared stack. Imports for `fastapi`, `pydantic`, `PySide6`, `aiosqlite`, NLP libraries, and most other required packages currently fail.
- The backend entry point cannot start in the current environment because `python Start.py --help` fails immediately on missing `fastapi`.
- The automated test suite is not currently runnable in this environment. `pytest` cannot execute project tests because dependencies are missing, and `pytest --collect-only -q` also fails in capture teardown.
- Public documentation is out of sync with the actual application architecture. The README still describes a “Python-only desktop runtime (no web stack)” and tells users to run `python main.py`, while the codebase uses `Start.py`, `launch.py`, and a FastAPI backend.

### Known implementation gaps found in code
- `services/search_service.py` contains a hybrid vector search placeholder and does not merge semantic/vector results yet.
- `config/extraction_patterns.py` is still a placeholder implementation and returns empty entity/relationship results.
- `agents/processors/document_processor.py` advertises `.doc`, `.xls`, and `.ppt` handling in the handler map, but those paths intentionally raise `NotImplementedError` and require conversion.
- There are still UI follow-up TODOs such as settings/dialog routing and preview wiring.

## Completion Definition

The application should only be considered complete when all of the following are true:

1. A clean environment can install dependencies and start the supported runtime entry points.
2. README and launch documentation accurately describe the actual architecture and supported startup flows.
3. Core user-visible workflows are either implemented end-to-end or explicitly documented as unsupported with graceful handling.
4. Automated verification runs in a repeatable way and covers startup, API, persistence, and GUI smoke paths.
5. Release readiness is backed by a reproducible manual scenario and a short known-limitations list.

## Recommended Hardening Sequence

Only one phase should be active at a time.

### Phase 1: Runtime Truth and Bootstrap Hardening
#### Scope
- Align documentation, startup instructions, and dependency expectations with the actual application.
- Make the declared startup paths reproducible in a clean environment.
- Resolve the gap between desktop-only messaging and the real desktop-plus-FastAPI architecture.

#### Non-goals
- New features
- Search improvements
- Extraction model improvements

#### Risks
- New contributors and testers cannot start the app reliably.
- False “production ready” claims create churn and mis-prioritization.
- CI and local verification remain blocked behind environment drift.

#### Implementation plan
- Update `README.md` so it reflects the actual entry points: `Start.py` for backend and `launch.py` for launcher-driven UI flow.
- Document required dependency tiers clearly: minimum runtime, full application runtime, and optional ML extras.
- Add one reproducible bootstrap command sequence for Windows/WSL and one for pure backend verification.
- Audit status documents that currently overstate readiness and either scope them narrowly or mark them historical.

#### Verification requirements
- `pip install -r requirements.txt` succeeds in a clean supported environment.
- `python launch.py --help` succeeds.
- `python Start.py --help` succeeds in the provisioned environment.
- One documented startup path reaches a healthy backend response and one launches the intended GUI mode.

#### Done criteria
- No documentation claims conflict with the actual architecture.
- A new contributor can follow the documented setup without guessing missing steps.
- Startup commands are verified on a clean environment and recorded.

### Phase 2: Verification Baseline Recovery
#### Scope
- Restore reliable automated verification.
- Establish a minimum required test matrix for backend, persistence, and GUI smoke coverage.

#### Non-goals
- Large feature refactors
- Model quality tuning

#### Risks
- Regressions can land unnoticed because the test suite is not operational.
- “Implemented” code remains unverified across launch modes.

#### Implementation plan
- Fix environment and pytest configuration issues so collection works deterministically.
- Define a minimum smoke subset that must pass on every change.
- Separate optional dependency tests from core verification if needed.
- Add a simple CI command set for compile, test, and startup smoke.

#### Verification requirements
- `pytest --collect-only` succeeds.
- Core smoke tests pass for startup, health, and selected service contracts.
- A compile step remains clean.

#### Done criteria
- Test discovery is stable.
- The repo has a documented default verification command.
- At least one backend smoke path and one GUI smoke path run in automation.

### Phase 3: Feature Contract Hardening
#### Scope
- Close or explicitly contract the user-visible gaps that are currently half-implemented.
- Prioritize incomplete paths that can mislead users today.

#### Non-goals
- Brand-new major subsystems
- Broad UX redesign

#### Risks
- Users hit placeholder behavior in search and extraction.
- File formats appear supported but fail late at runtime.

#### Implementation plan
- Either implement hybrid vector merge in `services/search_service.py` or remove the implied capability from exposed contracts.
- Either implement real pattern loading/extraction in `config/extraction_patterns.py` or mark it internal/inactive until complete.
- Make unsupported legacy formats fail early and clearly at the UI/API contract level instead of appearing supported in handler maps.
- Resolve the highest-value GUI TODOs that block expected navigation or preview behavior.

#### Verification requirements
- Contract tests for unsupported-format behavior
- Tests for search behavior matching the documented capability set
- Tests for extraction fallback behavior

#### Done criteria
- No placeholder behavior remains exposed as a finished feature.
- Unsupported paths are explicit, documented, and handled gracefully.

### Phase 4: Release Readiness and Operational Sign-off
#### Scope
- Final readiness pass across docs, startup, verification, and user workflow proof.

#### Non-goals
- Net-new functionality

#### Risks
- The application is still difficult to evaluate externally even if internally improved.

#### Implementation plan
- Create a short release checklist.
- Record one reproducible end-to-end manual scenario.
- Produce a concise known-limitations document.
- Freeze scope and address only release-blocking defects.

#### Verification requirements
- Full required verification suite passes.
- Manual scenario is executed successfully from a clean starting state.
- Known limitations are reviewed and accepted.

#### Done criteria
- The application can be installed, launched, exercised, and verified without undocumented tribal knowledge.
- Completion claims are backed by test evidence and one reproducible workflow.

## Immediate Next Phase

The correct next phase is **Phase 1: Runtime Truth and Bootstrap Hardening**.

Reason:
- It removes the current blocker for every later phase.
- It converts the project from “large but hard to verify” into something we can evaluate consistently.
- It eliminates the current mismatch between documentation, environment assumptions, and actual architecture.

## Evidence Snapshot Used For This Plan

- `README.md` still claims a desktop-only runtime and points to `python main.py`.
- `launch.py` is the current launcher entry point and references backend synchronization behavior.
- `Start.py` is the backend application entry point and currently depends on FastAPI at import time.
- `services/search_service.py` still contains a vector merge placeholder.
- `config/extraction_patterns.py` still contains placeholder extraction behavior.
- `agents/processors/document_processor.py` still maps legacy formats that intentionally raise `NotImplementedError`.
- The repository currently contains 100 test files, but test execution is blocked in this environment by missing dependencies.
