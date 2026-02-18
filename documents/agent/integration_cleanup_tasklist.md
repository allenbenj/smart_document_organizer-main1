# Integration Cleanup Task List (Fail-Fast, No Mock/Fallback)

Last updated: 2026-02-18
Owner: Codex
Tracking source: `documents/assessments/analysis_routes_agent_services_assessment.md`

## Rules (non-negotiable)
- No mock data
- No fake/stub responses in runtime routes
- No fallback execution paths
- Single mode only: service works or fails explicitly
- No mock data
- No fake/stub responses in runtime routes
- No fallback execution paths
- Single mode only: service works or fails explicitly
- No mock data
- No fake/stub responses in runtime routes
- No fallback execution paths
- Single mode only: service works or fails explicitly
- No mock data
- No fake/stub responses in runtime routes
- No fallback execution paths
- Single mode only: service works or fails explicitly
- No mock data
- No fake/stub responses in runtime routes
- No fallback execution paths
- Single mode only: service works or fails explicitly
- No mock data
- No fake/stub responses in runtime routes
- No fallback execution paths
- Single mode only: service works or fails explicitly
- No mock data
- No fake/stub responses in runtime routes
- No fallback execution paths
- Single mode only: service works or fails explicitly
All paths must be complete and working
All paths must be complete and working

All paths must be complete and working
All paths must be complete and working

All paths must be complete and working
All paths must be complete and working

All paths must be complete and working
All paths must be complete and working

All paths must be complete and working
All paths must be complete and working
All paths must be complete and working

All paths must be complete and working
All paths must be complete and working
All paths must be complete and working
All paths must be complete and working
All paths must be complete and working

## Completed
- [x] Replace placeholder route implementations with `AgentService` dispatch:
  - `routes/analysis.py`
  - `routes/extraction.py`
  - `routes/reasoning.py`
  - `routes/classification.py`
  - `routes/embedding.py`
- [x] Remove fake entity return from `GET /api/extraction/{doc_id}/entities` (now explicit `501` with clear message)
- [x] Add missing schema wrapper `_v(...)` for:
  - `POST /api/agents/feedback`
  - `POST /api/agents/contradictions`
  - `POST /api/agents/violations`
- [x] Remove relaxed agent dependency path usage in analysis routes
- [x] Enforce single-mode schema validation (no strict/loose toggle)
- [x] Scope root filtering wired backend+UI for organization proposals (no “show all” fallback)
- [x] Remove runtime fallback branches in `agents/production_manager/operations.py`
  - Acceptance met: no regex/keyword fallback return payloads; explicit failures on unavailable dependencies
- [x] Remove mock/placeholder logic in `agents/legal/legal_reasoning_engine.py`
  - Acceptance met: extractor wired to real hybrid path; fabricated entity/relationship/evidence placeholders removed

## In Progress
- [ ] Clean fallback terminology + behavior in vector/search paths:
  - `routes/vector_store.py`
  - `services/file_parsers.py`
  - Acceptance: messages and behavior reflect explicit dependency requirements, no fallback semantics

## Pending (High Priority)
- [x] Remove fallback processing path in `agents/processors/document_processor.py`
  - Acceptance met: unsupported/unavailable parser now fails explicitly; fallback text synthesis removed
- [x] Remove fallback/heuristic entity typing in `agents/extractors/legal_entity_extractor.py`
  - Acceptance met: unsupported entity types are rejected with no default substitution branch
- [x] Remove fallback helper behavior in `agents/extractors/document_utils.py`
  - Acceptance met: runtime fallback classifier removed; explicit error for missing concrete classifier
- [x] Remove/replace fallback paths in `agents/legal/precedent_analyzer.py`
  - Acceptance met: similarity scoring now requires embedding backend; no heuristic procedural/text-overlap fallback paths
- [x] Remove fallback behavior in `agents/embedding/unified_embedding_agent.py` and `mem_db/embedding/unified_embedding_agent.py`
  - Acceptance met: missing vector/memgraph/numpy dependencies now raise explicit runtime errors
- [x] Remove fallback handling in `core/service_integration.py`, `agents/base/core_integration.py`, `agents/base/enhanced_agent_factory.py`
  - Acceptance met: missing required services/modules now raise explicit errors; placeholder fallback branches removed

## Pending (Medium Priority)
- [ ] Replace placeholder extraction status usage where runtime-facing:
  - `services/semantic_file_service.py`
  - `mem_db/repositories/file_index_repository.py`
  - Acceptance: status reflects real extraction state only
- [ ] Remove heuristic toggles from knowledge endpoints/UI if still runtime-enabled:
  - `routes/knowledge.py`
  - `services/knowledge_service.py`
  - `gui/tabs/knowledge_graph_tab.py`

## Startup Reliability Tasks
- [ ] Remove startup heavy model initialization from blocking path
  - Acceptance: `/api/health` ready quickly; heavy models initialized on first use or explicit warmup
- [ ] Ensure startup does not attempt remote model downloads by default
  - Acceptance: no HuggingFace/xAI network calls during startup unless explicitly requested
- [ ] Keep fail-fast checks runtime-real (dependency/registration), not text-pattern scans
  - Acceptance: startup fails only for actual runtime blockers

## Verification Tasks
- [ ] `python3 -m compileall -q Start.py routes agents services core gui mem_db`
- [ ] Start backend and verify health:
  - `python3 Start.py --backend`
  - `GET /api/health` returns 200 quickly
  - `GET /api/agents/health` returns initialized required agents
- [ ] Validate all primary analysis routes return schema-compliant payloads
- [ ] Validate organization flow on changed root:
  - index -> generate -> review scoped proposals -> approve -> apply

## Progress Counters
- Completed tasks: 16
- In progress: 1
- Remaining tasks: 8

## Change Log
- 2026-02-18: Initial tracked cleanup list created from assessment + live runtime scan.
- 2026-02-18: Marked `agents/production_manager/operations.py` and `agents/legal/legal_reasoning_engine.py` complete after code update + verification scan.
- 2026-02-18: Marked `agents/processors/document_processor.py` complete after removing runtime fallback processing paths and verifying compile/lint.
- 2026-02-18: Marked `agents/extractors/legal_entity_extractor.py` complete after removing default fallback entity typing.
- 2026-02-18: Marked `agents/extractors/document_utils.py` complete after removing runtime fallback classifier behavior.
- 2026-02-18: Marked `agents/legal/precedent_analyzer.py` complete after replacing heuristic similarity fallback paths with required embedding-based similarity.
- 2026-02-18: Marked both `agents/embedding/unified_embedding_agent.py` and `mem_db/embedding/unified_embedding_agent.py` complete after converting dependency gaps to explicit failures.
- 2026-02-18: Marked `core/service_integration.py`, `agents/base/core_integration.py`, and `agents/base/enhanced_agent_factory.py` complete after fail-fast conversion for missing services/modules.
