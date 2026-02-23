# AEDIS Test Harness Targets - 2026-02-21

## Assumptions
- This plan is for critical-gap closure verification, not full CI replacement.
- Commands use `-s` due intermittent capture errors in this environment.

## Existing Suites Mapped to Critical Gaps
- Planner/Judge + heuristics routes: `tests/test_aedis_runtime_routes.py`
- Planner persistence semantics: `tests/test_planner_persistence_gate_service.py`, `tests/test_planner_judge_gate.py`
- Extraction runtime/backends: `tests/test_extraction_route_runtime.py`, `tests/test_hybrid_extractor_backends.py`
- Provenance contract/service: `tests/test_provenance_required_fields.py`, `tests/test_provenance_trace_reconstruction.py`
- Learning path runtime/service: `tests/test_learning_path_runtime_routes.py`, `tests/test_learning_path_service.py`
- GUI wiring/contract smoke: `tests/test_gui_*`

## New Suites Added for Critical Gap Completion
- `tests/test_organization_provenance_gate.py`
- `tests/test_knowledge_provenance_gate.py`
- `tests/test_memory_provenance_gate.py`
- `tests/test_analysis_version_provenance_gate.py`
- `tests/test_provenance_matrix_conformance.py`

## Minimum Acceptance Command Set by Phase
- Phase A (runtime routes):
  - `pytest -q -s tests/test_aedis_runtime_routes.py`
- Phase B (extraction):
  - `pytest -q -s tests/test_extraction_route_runtime.py tests/test_hybrid_extractor_backends.py`
- Phase C (provenance core):
  - `pytest -q -s tests/test_provenance_required_fields.py tests/test_provenance_trace_reconstruction.py`
- Phase D (learning paths):
  - `pytest -q -s tests/test_learning_path_runtime_routes.py tests/test_learning_path_service.py`
- Phase E (cross-service provenance enforcement):
  - `pytest -q -s tests/test_organization_provenance_gate.py tests/test_knowledge_provenance_gate.py tests/test_memory_provenance_gate.py tests/test_analysis_version_provenance_gate.py tests/test_provenance_matrix_conformance.py`

## GUI-Backed API Smoke Commands
- `pytest -q -s tests/test_gui_planner_judge_workflow.py`
- `pytest -q -s tests/test_gui_heuristic_governance.py`
- `pytest -q -s tests/test_gui_learning_path_tab_wiring.py`
- `pytest -q -s tests/test_gui_api_contract_alignment.py`
