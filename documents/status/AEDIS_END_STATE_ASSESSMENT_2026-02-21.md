# AEDIS End-State Assessment (Current Application)

Date: 2026-02-21  
Scope: Code-level assessment of whether the current application meets the AEDIS elements provided in your specification.

## Assessment Method
- Evidence source: direct repository inspection of routes, services, contracts, GUI tabs, and extractor modules.
- Verdict scale: `Meets`, `Partial`, `Missing`.
- Constraint: this is a static implementation assessment; no full end-to-end runtime validation was executed in this pass.

## Executive Verdict
The application is **not yet fully at the AEDIS desired end state**.  
It is **strongly scaffolded** for AEDIS (contracts, canonical layer services, ontology registry, provenance service, planner/judge and heuristic governance services, and GUI surfaces), but several core capabilities remain **partial or not wired end-to-end**.

## Requirement Matrix

| AEDIS Element | Verdict | Evidence | Notes |
|---|---|---|---|
| Immutable canonical truth anchors | Partial | `services/canonical_artifact_service.py:9`, `services/canonical_artifact_service.py:58`, `routes/ontology.py:182` | Immutability enforcement exists in service (`PermissionError` on update/delete) and ingest/lineage routes exist, but broader system-wide usage as the universal truth anchor is not fully enforced. |
| Mutable/versioned analytical abstractions | Partial | `services/contracts/aedis_models.py:62`, `services/contracts/aedis_models.py:71` | `AnalysisVersion` contract exists (with lineage fields), but full persistence + universal runtime adoption across all analysis flows is not demonstrated in this pass. |
| Six ontology separation (Domain/Cognitive/Tool/Objective/Heuristic/Generative) | Partial | `services/ontology_registry_service.py:8`, `services/ontology_registry_service.py:13`, `services/ontology_registry_service.py:14` | Six-type registry exists and versions can be created/activated/deprecated; enforcement across all extraction/reasoning outputs appears incomplete. |
| Non-negotiable provenance for claims/heuristics/generated output | Partial | `services/contracts/aedis_models.py:40`, `services/provenance_service.py:28`, `services/provenance_service.py:21` | Write-gate exists and requires evidence spans, but provenance is not yet verified as mandatory across every write path and every output type. |
| Planner-Judge loop with deterministic verification | Partial | `services/planner_judge_service.py:11`, `services/planner_judge_service.py:75`, `gui/tabs/planner_judge_tab.py:165` | Core service exists and is deterministic; GUI exists. However, corresponding API routes used by GUI are not present in `routes/` (see gap below). |
| Planner FAIL blocks persistence | Missing (end-to-end) | `services/planner_judge_service.py:75`, `services/planner_judge_service.py:93` | Judge verdict logic exists, but no verified end-to-end persistence gate route/workflow was found enforcing "no write on FAIL" globally. |
| Tacit knowledge promotion lifecycle (Candidate->...->Deprecated) | Partial | `services/heuristic_governance_service.py:12`, `services/heuristic_governance_service.py:46`, `services/heuristic_governance_service.py:116` | Lifecycle and thresholds exist in service with collision detection, but route-layer wiring is missing for GUI calls. |
| Dissent/conflict handling among experts | Partial | `services/heuristic_governance_service.py:67`, `services/heuristic_governance_service.py:79` | Collision detection implemented in service; operational API path not found in current routes. |
| Extraction pipeline available | Partial | `routes/extraction.py:19`, `routes/extraction.py:29`, `agents/extractors/hybrid_extractor.py:179`, `agents/extractors/hybrid_extractor.py:186` | Extraction endpoint exists, but `HybridLegalExtractor` NER and LLM backends are explicitly unimplemented. |
| Knowledge creation + proposal workflow | Meets (for proposal lifecycle) | `routes/agent_routes/memory.py:53`, `routes/agent_routes/memory.py:63`, `routes/agent_routes/memory.py:75` | Proposal creation/review/approval/rejection/update/delete routes are present. |
| Generative drafting assistance with explanatory traces | Partial | `services/contracts/aedis_models.py:40`, `routes/agent_routes/analysis.py:112` | Reasoning/generation-adjacent flows exist, but explicit mature "community-calibrated drafting + trace" workflow is not fully evidenced as a closed loop. |
| Personalized learning pathways | Missing | `documents/agent/AEDIS_GAP_CLOSURE_ROADMAP.md:58` | Current roadmap itself marks this as missing; no production learning-path service/routes were identified in this scan. |

## Critical End-to-End Gaps

1. Planner/Judge API wiring gap
- GUI client calls these paths: `gui/services/__init__.py:872`, `gui/services/__init__.py:894`, `gui/services/__init__.py:898`.
- No matching backend routes were found under `routes/` for planner/judge/heuristics endpoints (`rg` search returned none).

2. Extraction completeness gap
- `HybridLegalExtractor` currently raises runtime errors for both NER and LLM backends (`agents/extractors/hybrid_extractor.py:179`, `agents/extractors/hybrid_extractor.py:186`).
- This prevents a fully functional "hybrid" extraction path as described in the target state.

3. Universal provenance enforcement gap
- Provenance write-gate exists (`services/provenance_service.py:28`), but not all write paths are demonstrably blocked without provenance in this inspection.

4. Learning-path capability gap
- Personalized/trace-based instructional layer remains unimplemented in the production path (also recorded in roadmap).

## Net Conclusion
The application currently **implements important AEDIS foundations** but **does not yet fully meet** the full AEDIS end-state requirements.  
Most foundational layers are present as contracts/services/UI scaffolding, while key outcomes require final end-to-end route wiring, mandatory enforcement integration, and completion of missing extraction/learning-path components.

## Confidence
Assessment confidence: **High** for structural findings (present/missing routes, implemented/unimplemented methods), **Medium** for behavioral guarantees (because full integration runtime tests were not executed in this pass).

## Post-Implementation Update (2026-02-21)
- Closed since initial assessment: heuristic lifecycle semantics alignment, extraction architecture decision, cross-service provenance validation suite, structured knowledge payload normalization, endpoint alias/contract cleanup, and learning-path persistent storage migration.
- Remaining blockers: repo-wide static lint debt (`ruff check .`) outside current gap-closure scope, and interactive manual GUI E2E verification in a desktop session.
- Current state: critical service/runtime flows are functional and regression-tested; readiness closure now depends primarily on environment-level quality gates and final manual GUI validation.
