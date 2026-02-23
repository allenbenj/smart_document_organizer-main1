# AEDIS Implementation Dependency Map - 2026-02-21

## Assumptions
- Focus is constrained to modules used by critical-gap sections in the tracker (planner/judge, heuristics, provenance, extraction, learning paths, organization/knowledge/memory gated writes).
- Dependency edges capture runtime flow, not every utility import.

## Route Inventory (Relevant)
- `routes/aedis_runtime.py`
- `routes/extraction.py`
- `routes/knowledge.py`
- `routes/organization.py`
- `routes/agent_routes/memory.py`

## Service Inventory (Relevant)
- `services/planner_judge_service.py`
- `services/planner_persistence_gate_service.py`
- `services/heuristic_governance_service.py`
- `services/provenance_service.py`
- `services/analysis_version_service.py`
- `services/learning_path_service.py`
- `services/knowledge_service.py`
- `services/organization_service.py`
- `services/memory_service.py`

## GUI Caller Inventory (Relevant)
- `gui/services/__init__.py`
- `gui/tabs/heuristic_lifecycle_tab.py`
- `gui/tabs/learning_path_tab.py`
- `gui/tabs/provenance_tab.py`

## Caller -> Route -> Service -> DB Mapping
- Planner/Judge runtime:
  - `gui/services/__init__.py::run_planner_judge`
  - `POST /api/planner-judge/run` (`routes/aedis_runtime.py`)
  - `PlannerJudgeService.create_plan/judge_plan`
  - In-memory runtime store (plus persistence gate flow when used)

- Planner persistence gate:
  - `gui/services/__init__.py::persist_planner_output`
  - `POST /api/planner-judge/persist`
  - `PlannerPersistenceGateService.persist_planner_output` + `ProvenanceService.record_provenance`
  - Tables: `aedis_provenance_records`, `aedis_evidence_spans`, `aedis_artifact_provenance_links`

- Heuristic governance:
  - `gui/tabs/heuristic_lifecycle_tab.py` via API client
  - `/api/heuristics/*` (`routes/aedis_runtime.py`)
  - `HeuristicGovernanceService`
  - Runtime service state + provenance links for promotion

- Learning paths:
  - `gui/tabs/learning_path_tab.py`
  - `/api/learning-paths/*` (`routes/aedis_runtime.py`)
  - `LearningPathService`
  - In-memory service state (persistence migration still open in tracker 11.3)

- Knowledge curated writes:
  - Knowledge manager UI/API callers
  - `/api/knowledge/proposals/approve`, `/api/knowledge/manager/items/{id}/verify`, `/api/knowledge/manager/items/{id}`
  - `routes/knowledge.py` + `KnowledgeService` + DB manager methods
  - Tables: `knowledge_proposals`, `manager_knowledge` + provenance link tables

- Organization proposal generation:
  - Organization UI/API callers
  - `/api/organization/proposals/generate` (`routes/organization.py`)
  - `OrganizationService.generate_proposals`
  - Tables: `organization_proposals`, `organization_feedback`, `organization_actions` + provenance link tables

- Memory claim-grade proposal path:
  - `/api/agents/memory/proposals` (`routes/agent_routes/memory.py`)
  - `MemoryService.create_proposal`
  - Tables: `memory_proposals` (via `proposals_db`) + provenance link tables

- Extraction runtime:
  - extraction UI/API callers
  - `/api/extraction/run` (`routes/extraction.py`)
  - extractor services under `agents/extractors/*`
  - writes to indexed entities/knowledge through DB manager paths
