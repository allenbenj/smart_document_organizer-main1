# AEDIS Manual E2E Run Log - 2026-02-21

## Scope
Operational validation of core AEDIS flows using runtime route tests and direct API-equivalent invocations in this environment.

## Executed Flow Coverage

1. Extraction API with known sample text
- Evidence: `tests/test_extraction_route_runtime.py` passing.
- Result: PASS.

2. Promote memory/heuristic and validate provenance links
- Evidence: `tests/test_memory_provenance_gate.py`, `tests/test_knowledge_provenance_gate.py`, `tests/test_aedis_runtime_routes.py` (heuristic promotion path).
- Result: PASS.

3. Planner/Judge run with PASS and FAIL strategies
- Evidence: `tests/test_aedis_runtime_routes.py` passing.
- Result: PASS.

4. Verify FAIL prevents persistence
- Evidence: `tests/test_aedis_runtime_routes.py::test_planner_persist_fail_blocks_persistence_and_emits_failure_artifact`.
- Result: PASS.

5. Generate and inspect one learning path with trace references
- Evidence: `tests/test_learning_path_runtime_routes.py`, `tests/test_learning_path_persistence.py`.
- Result: PASS.

6. GUI tab flows for planner/judge, heuristics, learning path
- Status: Not executed as interactive manual flow in this headless run context.
- Closest automated evidence: GUI wiring/contract tests (`tests/test_gui_*`).

## Overall
- API/service-level E2E criteria are satisfied in this run.
- Remaining manual GUI interaction verification requires an interactive desktop session.
