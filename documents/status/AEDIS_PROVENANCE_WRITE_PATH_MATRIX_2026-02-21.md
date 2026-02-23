# AEDIS Provenance Write-Path Matrix

Date: 2026-02-21  
Scope: Current implementation write paths mapped to provenance enforcement status.

## Classification Legend
- `Required`: Write path should require provenance gate before persistence.
- `Exempt`: Write path not in AEDIS claim/generation trace scope.
- `Partial`: Some provenance integration exists but is not strict/complete.

## Matrix

| Write Path | Location | Classification | Current Status | Notes |
|---|---|---|---|---|
| Planner generated output persistence | `routes/aedis_runtime.py` (`POST /planner-judge/persist`) | Required | Enforced | Requires `ProvenanceRecord` validation; attempts DB record, degrades to `validated_only` when provenance tables unavailable. |
| Organization proposal generation | `services/organization_service.py` | Required | Enforced | Fail-closed provenance implemented in generate_proposals. |
| Memory proposal creation | `services/memory_service.py` + `routes/agent_routes/memory.py` | Required (for claim-grade memory) | Enforced | Claim-grade proposals now require provenance; create route accepts provenance payload and fails closed when missing/invalid. |
| Knowledge proposal approval -> curated knowledge write | `services/knowledge_service.py` / `routes/knowledge.py` | Required | Enforced | Proposal approval and manager verification/curation writes now require and record provenance. |
| Analysis version creation (AEDIS contracts) | `services/analysis_version_service.py` | Required | Enforced | Provenance gate enforced by AnalysisVersionService.create_analysis_version. |
| Heuristic promotion lifecycle writes | `routes/aedis_runtime.py` + `services/heuristic_governance_service.py` | Required (for promoted institutional heuristics) | Enforced | Provenance gate enforced as per Task 5.3 Action 3. |
| Canonical artifact ingest/lineage events | `routes/ontology.py` + `services/canonical_artifact_service.py` | Exempt from `ProvenanceRecord` gate | N/A | Canonical layer already has immutable lineage event model; not same as claim evidence gate. |
| Generic file indexing/chunk persistence | `services/file_index_service.py` + repos | Exempt / Optional | N/A | Operational indexing metadata includes provenance-like fields but not AEDIS evidence-span gate target. |
| Workflow step persistence | `services/workflow/execution.py` | Exempt / Optional | N/A | Job orchestration persistence, not directly claim-grade knowledge output. |

## Required Follow-On Enforcement Plan

1. Add matrix-conformance regression tests to ensure required paths stay gated. (BLOCKED due to pytest-asyncio configuration issues)
2. Expand memory gating coverage to approval promotion paths where claim-grade records are persisted.
3. Expand analysis-version route/API coverage to guarantee service gate is always used through public entrypoints.

## Owner Notes

- This matrix is intended as the source-of-truth checklist for completing tracker section `5.1` and guiding `5.3` rollout.
- Update this file whenever a write path changes enforcement status.
