# AEDIS Authority & Execution Ledger (AEL)

Last Updated: 2026-02-19  
Owner: Codex  
Status: ACTIVE  
Governance Mode: FAIL-FAST / ZERO-STUB / VERIFICATION-DRIVEN  
Reference Roadmap: `documents/agent/AEDIS_GAP_CLOSURE_ROADMAP.md`  
Whitepaper Alignment: Full traceability to §7.1 Progressive Formalization

---

## Core Mandates (Applied to ALL Horizons)
- Zero-Stub Policy: No mock data, fake responses, or placeholder implementations in runtime routes/services.
- Fail-Fast: Services must succeed or raise explicit, logged exceptions; no silent fallbacks.
- Verification-Driven: No task is done until gate command output and required artifacts are present.
- GUI-Integrated: Every backend capability must expose a functional GUI workflow.
- Migration-Safe: Schema changes require forward migration, rollback, redo, and backfill validation.

## Status Legend
- `[ ]` PENDING
- `[/]` IN-FLIGHT (branch/PR exists, not gate-verified)
- `[x]` VERIFIED (gate command run + artifacts captured + tests passed)

---

## Dependency Lock (Hard Ordering)
- Horizon 1 exit gate must pass before any Horizon 2 phase is marked `VERIFIED`.
- Phase 0 gate must pass before Phase 1 starts.
- Phase 1 gate + migration gate must pass before Phase 2 starts.
- Phase 2 gate + migration gate must pass before Phase 3 starts.
- Phase 3 gate + migration gate must pass before Phase 4 starts.
- Phase 4 gate must pass before Phase 5 and Phase 6 start.
- Phase 5 gate must pass before Phase 7 starts.
- Phase 6 gate must pass before Phase 8 starts.
- Phase 7 gate must pass before program closure.
- Phase 8 gate is final program acceptance gate.

---

## 🟢 Horizon 1: Tactical Stabilization (Health: 0/19)
Focus: Eliminate technical debt and ensure baseline platform integrity before AEDIS layering.

| ID | Task Description | Scope | Status |
| :--- | :--- | :--- | :--- |
| STAB-H1-API-01 | Replace all placeholders with `AgentService` dispatch | API | [ ] |
| STAB-H1-API-02 | Add `_v(...)` schema wrappers to every agent-facing POST route | API | [ ] |
| STAB-H1-CORE-03 | Enforce strict dependency fail-fast paths (no relaxed imports) | CORE | [ ] |
| STAB-H1-CORE-04 | Remove fabricated entities/evidence in legal reasoning engine | CORE | [ ] |
| STAB-H1-GUI-05 | Resolve `ProcessingJob` NameError in document processing tab | GUI | [ ] |
| STAB-H1-GUI-06 | Wire `Enable OCR` toggle GUI -> worker -> backend | GUI/API | [ ] |
| STAB-H1-CORE-07 | Enable startup offline-safe mode + lazy agent init | CORE | [ ] |
| STAB-H1-VERI-08 | Validate full org flow (index -> generate -> approve -> apply) | INTEG | [ ] |
| STAB-H1-LEG-09 | Remove legacy legal placeholder artifacts/remnants | CORE | [ ] |
| STAB-H1-ORG-10 | Enforce organization scope/root filtering + changed-root behavior | INTEG | [ ] |
| STAB-H1-SCH-11 | Enforce single schema mode (no strict/loose toggle drift) | CORE | [ ] |
| STAB-H1-VEC-12 | Remove vector/search fallback terminology and fallback logic | CORE | [ ] |
| STAB-H1-EXT-13 | Replace placeholder extraction status logic | CORE | [ ] |
| STAB-H1-KNO-14 | Remove knowledge heuristic-toggle remnants | GUI/API | [ ] |
| STAB-H1-FLB-15 | Remove fallback paths in `document_processor.py` | CORE | [ ] |
| STAB-H1-FLB-16 | Remove fallback paths in `legal_entity_extractor.py` | CORE | [ ] |
| STAB-H1-FLB-17 | Remove fallback paths in remaining listed runtime files | CORE | [ ] |
| STAB-H1-ENV-18 | Add forbidden module scan for runtime (`mock`, `unittest.mock`) | CI/CORE | [ ] |
| STAB-H1-PERF-19 | Enforce startup performance budget (`total_startup_ms < 15000`) with gate artifact | CORE/CI | [ ] |

### Verification Gate (H1 Exit)
| Command | Expected Artifact |
| :--- | :--- |
| `python3 Start.py --check-integrity --output logs/integrity_h1.json` | `logs/integrity_h1.json` exists with `{"status":"pass","fallback_count":0,"placeholder_count":0}` |
| `python3 scripts/quality/forbidden_runtime_scan.py --paths agents services routes --output logs/forbidden_runtime_scan_h1.json` | `logs/forbidden_runtime_scan_h1.json` exists with `{"violations":0}` |
| `python3 Start.py --check-integrity --layer h1 --output logs/integrity_h1_perf.json` | `logs/integrity_h1_perf.json` plus startup diagnostics show `total_startup_ms < 15000` |
| `pytest tests/test_document_processing.py -q --junitxml=logs/junit_h1_doc_processing.xml` | `logs/junit_h1_doc_processing.xml` indicates pass |
| `pytest tests/test_organization_integration.py -q --junitxml=logs/junit_h1_org_integration.xml` | `logs/junit_h1_org_integration.xml` indicates index->generate->approve->apply pass |
| `pytest tests/test_organization_route_contracts.py -q --junitxml=logs/junit_h1_org_contracts.xml` | `logs/junit_h1_org_contracts.xml` indicates schema contract pass |

H1 Exit Rule: All 19 H1 tasks must be `[x]` and all H1 gate artifacts must exist.

---

## 🔵 Horizon 2: AEDIS Strategic Transition (Health: 0/40)
Focus: Build immutable truth, ontological governance, deterministic Planner-Judge gating, tacit promotion, and measured operation.

## Phase 0: Foundations & Contracts (Health: 0/3)
Blocked Until: H1 gate pass.

| ID | Task Description | Scope | Status |
| :--- | :--- | :--- | :--- |
| AEDIS-P0-DTO-01 | Implement DTOs in `services/contracts/aedis_models.py`: `CanonicalArtifact`, `AnalysisVersion`, `ProvenanceRecord`, `HeuristicEntry`, `PlannerRun`, `JudgeRun`, `EvidenceSpan`, `AuditDelta` | API/CORE | [ ] |
| AEDIS-P0-GUI-02 | Implement `gui/services/aedis_contract_adapters.py` (API <-> GUI adapters) | GUI | [ ] |
| AEDIS-P0-TEST-03 | Add CI gate `tests/quality/test_no_runtime_stubs.py` for all AEDIS modules | CI | [ ] |

### Verification Gate 0
| Command | Expected Artifact |
| :--- | :--- |
| `pytest tests/quality/test_no_runtime_stubs.py -q --junitxml=logs/junit_p0_no_stubs.xml` | `logs/junit_p0_no_stubs.xml` pass |
| `pytest tests/contracts/test_aedis_models.py -q --junitxml=logs/junit_p0_contracts.xml` | `logs/junit_p0_contracts.xml` pass with `EvidenceSpan`/`AuditDelta` validation |
| `pytest tests/test_gui_api_contract_alignment.py -q --junitxml=logs/junit_p0_gui_alignment.xml` | `logs/junit_p0_gui_alignment.xml` pass |

## Phase 1: Immutable Canonical Layer (Health: 0/4)
Blocked Until: Phase 0 gate pass.

| ID | Task Description | Scope | Status |
| :--- | :--- | :--- | :--- |
| AEDIS-P1-DB-01 | Create append-only `canonical_artifacts` and `canonical_artifact_blobs` tables with SHA-256 anchoring | DB | [ ] |
| AEDIS-P1-SVC-02 | Implement `CanonicalArtifactService` with immutable mutation guard | CORE | [ ] |
| AEDIS-P1-API-03 | Implement `POST /api/canonical/ingest` and read/lineage routes | API | [ ] |
| AEDIS-P1-GUI-04 | Add `CanonicalArtifactsTab` ingest + lineage + audit viewer | GUI | [ ] |

### Verification Gate 1
| Command | Expected Artifact |
| :--- | :--- |
| `python3 Start.py --check-integrity --layer canonical --output logs/integrity_p1_canonical.json` | `logs/integrity_p1_canonical.json` shows canonical layer active |
| `pytest tests/test_canonical_immutability.py -q --junitxml=logs/junit_p1_immutability.xml` | `logs/junit_p1_immutability.xml` pass |
| `pytest tests/test_canonical_lineage_integrity.py -q --junitxml=logs/junit_p1_lineage.xml` | `logs/junit_p1_lineage.xml` pass |
| `pytest tests/test_gui_canonical_workflow.py -q --junitxml=logs/junit_p1_gui.xml` | `logs/junit_p1_gui.xml` pass |

### Migration Gate 1-M
| Command | Expected Artifact |
| :--- | :--- |
| `python3 scripts/migrate.py up --phase p1 --report logs/migrate_p1_up.json` | `logs/migrate_p1_up.json` pass |
| `python3 scripts/migrate.py down --phase p1 --report logs/migrate_p1_down.json` | `logs/migrate_p1_down.json` pass |
| `python3 scripts/migrate.py redo --phase p1 --verify-data-integrity --report logs/migrate_p1_redo_verify.json` | `logs/migrate_p1_redo_verify.json` pass with no hash-anchor drift |
| `pytest tests/migrations/test_phase1_backfill.py -q --junitxml=logs/junit_p1_backfill.xml` | `logs/junit_p1_backfill.xml` pass |

## Phase 2: Six-Ontology Registry (Health: 0/3)
Blocked Until: Phase 1 gate + migration gate pass.

| ID | Task Description | Scope | Status |
| :--- | :--- | :--- | :--- |
| AEDIS-P2-SVC-01 | Implement unified `OntologyRegistryService` for all 6 ontologies | CORE | [ ] |
| AEDIS-P2-API-02 | Add activation/deprecation/version APIs with validation | API | [ ] |
| AEDIS-P2-GUI-03 | Add ontology version selector + promotion controls in GUI tabs | GUI | [ ] |

### Verification Gate 2
| Command | Expected Artifact |
| :--- | :--- |
| `python3 Start.py --check-integrity --layer ontology --output logs/integrity_p2_ontology.json` | `logs/integrity_p2_ontology.json` shows all six classes active |
| `pytest tests/test_ontology_registry_versions.py -q --junitxml=logs/junit_p2_versions.xml` | `logs/junit_p2_versions.xml` pass |
| `pytest tests/test_ontology_registry_activation.py -q --junitxml=logs/junit_p2_activation.xml` | `logs/junit_p2_activation.xml` pass |
| `pytest tests/test_gui_ontology_registry_workflow.py -q --junitxml=logs/junit_p2_gui.xml` | `logs/junit_p2_gui.xml` pass |

### Migration Gate 2-M
| Command | Expected Artifact |
| :--- | :--- |
| `python3 scripts/migrate.py up --phase p2 --report logs/migrate_p2_up.json` | `logs/migrate_p2_up.json` pass |
| `python3 scripts/migrate.py down --phase p2 --report logs/migrate_p2_down.json` | `logs/migrate_p2_down.json` pass |
| `python3 scripts/migrate.py redo --phase p2 --verify-data-integrity --report logs/migrate_p2_redo_verify.json` | `logs/migrate_p2_redo_verify.json` pass |
| `pytest tests/migrations/test_phase2_backfill.py -q --junitxml=logs/junit_p2_backfill.xml` | `logs/junit_p2_backfill.xml` pass |

## Phase 3: Global Provenance Contract (Health: 0/4)
Blocked Until: Phase 2 gate + migration gate pass.

| ID | Task Description | Scope | Status |
| :--- | :--- | :--- | :--- |
| AEDIS-P3-SVC-01 | Enforce `ProvenanceRecord` on all write paths | CORE | [ ] |
| AEDIS-P3-SVC-02 | Implement provenance query + reconstruction service | CORE | [ ] |
| AEDIS-P3-GUI-03 | Add provenance panels across output workflows | GUI | [ ] |
| AEDIS-P3-GUI-04 | Add character-level provenance highlighting via `EvidenceSpan` | GUI | [ ] |

### Verification Gate 3
| Command | Expected Artifact |
| :--- | :--- |
| `python3 Start.py --check-integrity --layer provenance --output logs/integrity_p3_provenance.json` | `logs/integrity_p3_provenance.json` shows write-gate enforcement enabled |
| `pytest tests/test_provenance_required_fields.py -q --junitxml=logs/junit_p3_required_fields.xml` | `logs/junit_p3_required_fields.xml` pass |
| `pytest tests/test_provenance_trace_reconstruction.py -q --junitxml=logs/junit_p3_trace.xml` | `logs/junit_p3_trace.xml` pass |
| `pytest tests/test_gui_provenance_highlighting.py -q --junitxml=logs/junit_p3_gui_highlight.xml` | `logs/junit_p3_gui_highlight.xml` pass |

### Migration Gate 3-M
| Command | Expected Artifact |
| :--- | :--- |
| `python3 scripts/migrate.py up --phase p3 --report logs/migrate_p3_up.json` | `logs/migrate_p3_up.json` pass |
| `python3 scripts/migrate.py down --phase p3 --report logs/migrate_p3_down.json` | `logs/migrate_p3_down.json` pass |
| `python3 scripts/migrate.py redo --phase p3 --verify-data-integrity --report logs/migrate_p3_redo_verify.json` | `logs/migrate_p3_redo_verify.json` pass |

## Phase 4: Planner-Judge Deterministic Core (Health: 0/5)
Blocked Until: Phase 3 gate + migration gate pass.

| ID | Task Description | Scope | Status |
| :--- | :--- | :--- | :--- |
| AEDIS-P4-SVC-01 | Implement Planner strategy composition service | CORE | [ ] |
| AEDIS-P4-SVC-02 | Implement deterministic Judge scoring + rejection modes | CORE | [ ] |
| AEDIS-P4-SVC-03 | Enforce hard gate: no persistence on Judge FAIL | CORE | [ ] |
| AEDIS-P4-GUI-04 | Add Planner/Judge run workflow + failure inspector in GUI | GUI | [ ] |
| AEDIS-P4-RULE-05 | Implement versioned Judge ruleset (Judge DSL/schema persisted in DB) | CORE/DB | [ ] |

### Verification Gate 4
| Command | Expected Artifact |
| :--- | :--- |
| `python3 Start.py --check-integrity --layer planner_judge --output logs/integrity_p4_planner_judge.json` | `logs/integrity_p4_planner_judge.json` shows deterministic gate active |
| `pytest tests/test_planner_judge_gate.py -q --junitxml=logs/junit_p4_gate.xml` | `logs/junit_p4_gate.xml` pass |
| `pytest tests/test_judge_determinism.py -q --junitxml=logs/junit_p4_determinism.xml` | `logs/junit_p4_determinism.xml` pass |
| `pytest tests/test_judge_ruleset_versioning.py -q --junitxml=logs/junit_p4_ruleset.xml` | `logs/junit_p4_ruleset.xml` pass |
| `pytest tests/test_gui_planner_judge_workflow.py -q --junitxml=logs/junit_p4_gui.xml` | `logs/junit_p4_gui.xml` pass |

## Phase 5: Tacit Knowledge Promotion Lifecycle (Health: 0/4)
Blocked Until: Phase 4 gate pass.

| ID | Task Description | Scope | Status |
| :--- | :--- | :--- | :--- |
| AEDIS-P5-SVC-01 | Implement Candidate -> Qualified -> Promoted -> Active lifecycle | CORE | [ ] |
| AEDIS-P5-SVC-02 | Add promotion thresholds, lineage, and rollback | CORE | [ ] |
| AEDIS-P5-GUI-03 | Add GUI governance workflow for promotion/deprecation | GUI | [ ] |
| AEDIS-P5-CONFLICT-04 | Implement heuristic collision/dissent tracking for competing expert rules | CORE | [ ] |

### Verification Gate 5
| Command | Expected Artifact |
| :--- | :--- |
| `python3 Start.py --check-integrity --layer heuristics --output logs/integrity_p5_heuristics.json` | `logs/integrity_p5_heuristics.json` shows lifecycle + dissent tracking active |
| `pytest tests/test_heuristic_promotion_thresholds.py -q --junitxml=logs/junit_p5_thresholds.xml` | `logs/junit_p5_thresholds.xml` pass |
| `pytest tests/test_heuristic_collision_detection.py -q --junitxml=logs/junit_p5_collision.xml` | `logs/junit_p5_collision.xml` pass |
| `pytest tests/test_gui_heuristic_governance.py -q --junitxml=logs/junit_p5_gui.xml` | `logs/junit_p5_gui.xml` pass |

## Phase 6: Generative + Instructional Activation (Health: 0/3)
Blocked Until: Phase 4 gate pass.

| ID | Task Description | Scope | Status |
| :--- | :--- | :--- | :--- |
| AEDIS-P6-SVC-01 | Implement `GenerativeDraftService` (Judge-gated generation only) | CORE | [ ] |
| AEDIS-P6-SVC-02 | Implement `LearningPathService` with trace-backed steps | CORE | [ ] |
| AEDIS-P6-GUI-03 | Add GUI drafting + learning-mode workflows | GUI | [ ] |

### Verification Gate 6
| Command | Expected Artifact |
| :--- | :--- |
| `python3 Start.py --check-integrity --layer generative_instructional --output logs/integrity_p6_gen_instr.json` | `logs/integrity_p6_gen_instr.json` shows Judge-gated generation + trace-learning active |
| `pytest tests/test_generation_requires_judge_pass.py -q --junitxml=logs/junit_p6_gen_gate.xml` | `logs/junit_p6_gen_gate.xml` pass |
| `pytest tests/test_learning_path_traceability.py -q --junitxml=logs/junit_p6_learning_trace.xml` | `logs/junit_p6_learning_trace.xml` pass |
| `pytest tests/test_gui_learning_mode.py -q --junitxml=logs/junit_p6_gui.xml` | `logs/junit_p6_gui.xml` pass |

## Phase 7: Global Ontology Enforcement (Health: 0/3)
Blocked Until: Phase 5 gate pass.

| ID | Task Description | Scope | Status |
| :--- | :--- | :--- | :--- |
| AEDIS-P7-SVC-01 | Enforce ontology mapping on all entity producers/consumers | CORE | [ ] |
| AEDIS-P7-SVC-02 | Require explicit extension registration for non-core entity types | CORE | [ ] |
| AEDIS-P7-GUI-03 | Enforce GUI labels aligned to active ontology registry | GUI | [ ] |

### Verification Gate 7
| Command | Expected Artifact |
| :--- | :--- |
| `python3 Start.py --check-integrity --layer ontology_enforcement --output logs/integrity_p7_ontology_enforcement.json` | `logs/integrity_p7_ontology_enforcement.json` shows global enforcement active |
| `pytest tests/test_entity_ontology_enforcement_global.py -q --junitxml=logs/junit_p7_enforcement.xml` | `logs/junit_p7_enforcement.xml` pass |
| `pytest tests/test_entity_type_extension_registration.py -q --junitxml=logs/junit_p7_extensions.xml` | `logs/junit_p7_extensions.xml` pass |
| `pytest tests/test_gui_entity_ontology_alignment.py -q --junitxml=logs/junit_p7_gui.xml` | `logs/junit_p7_gui.xml` pass |

## Phase 8: Measurement Harness (Whitepaper §8) (Health: 0/3)
Blocked Until: Phase 6 gate pass and Phase 7 gate pass.

| ID | Task Description | Scope | Status |
| :--- | :--- | :--- | :--- |
| AEDIS-P8-SVC-01 | Implement quality/speed/retention/safety KPI pipeline | CORE | [ ] |
| AEDIS-P8-SVC-02 | Add hold-out set evaluation + Judge calibration workflow | CORE | [ ] |
| AEDIS-P8-GUI-03 | Add GUI KPI dashboard with drill-down to traces/failures | GUI | [ ] |

### Verification Gate 8
| Command | Expected Artifact |
| :--- | :--- |
| `python3 Start.py --check-integrity --layer measurement --output logs/integrity_p8_measurement.json` | `logs/integrity_p8_measurement.json` shows KPI harness active |
| `pytest tests/test_evaluation_metrics_pipeline.py -q --junitxml=logs/junit_p8_metrics.xml` | `logs/junit_p8_metrics.xml` pass |
| `pytest tests/test_holdout_guardrails.py -q --junitxml=logs/junit_p8_holdout.xml` | `logs/junit_p8_holdout.xml` pass |
| `pytest tests/test_gui_kpi_dashboard.py -q --junitxml=logs/junit_p8_gui.xml` | `logs/junit_p8_gui.xml` pass |

---

## Program Counters (Conservative Reset)
- Total Tasks: 58
- Verified: 0
- In-Flight: 0
- Pending: 58

## Measurement Plan (Whitepaper §8)
- Document Quality: Judge fidelity score, senior-review delta, downstream rework rate.
- Speed: Time-to-first-draft, approval cycle count, time-to-competency for new staff.
- Retention: Percent of promoted heuristics traceable to departed experts still active.
- Safety: False-positive/false-negative rates for inconsistency detection and heuristic fidelity.

## Change Log
- 2026-02-19.010: Removed duplicated/overlapping tasks and normalized task IDs.
- 2026-02-19.010: Added explicit dependency locks between phases (hard gate ordering).
- 2026-02-19.010: Upgraded Verification Gates 4/5/6/7/8 to concrete command + artifact-path format.
- 2026-02-19.010: Added `EvidenceSpan` and `AuditDelta` to Phase 0 DTOs.
- 2026-02-19.010: Added Phase 3 character-level provenance highlighting task.
- 2026-02-19.010: Added Phase 4 Judge DSL/versioned ruleset task.
- 2026-02-19.010: Added Phase 5 dissent/collision tracking task.
- 2026-02-19.010: Added H1 forbidden runtime module scan task.
