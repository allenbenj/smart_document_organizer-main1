# AEDIS Gap Closure Roadmap (Paper -> Production System)

Last updated: 2026-02-19  
Owner: Engineering  
Source paper: `documents/Adaptive Epistemic Document Intelligence System.docx`  
Status: **AUTHORITATIVE STRATEGY**

## 1) Objective

Close the full capability gap between the AEDIS paper and the current Smart Document Organizer implementation, with zero placeholder/stub tracks and explicit acceptance gates per phase.

This roadmap is intentionally implementation-level, with:
- concrete schema changes
- concrete service/route/module changes
- concrete test suites
- hard exit criteria
- explicit anti-stub rules

## 1.1 Unified Production Specification (Authoritative Summary)

Strategic goal: transform institutional tacit knowledge into versioned, inheritable capital.

Epistemic core:
- **Immutable canonical layer**: original artifacts are content-hash anchored and append-only.
- **Mutable analytical layer**: all analysis artifacts are versioned and lineage-linked.
- **Mandatory provenance**: no extraction/generation artifact is accepted without full provenance envelope (line-level precision).

Six-ontology registry (independently versioned):
- Domain, Cognitive, Tool, Objective, Heuristic, Generative/Instructional.

Planner-Judge loop:
- Planner composes strategy from objectives, tools, and active heuristics.
- Judge deterministically validates schema, objective success, heuristic fidelity, provenance completeness, and risk flags.
- **No Persistence on FAIL**: Failures produce rejection artifacts with remediation guidance.

Tacit knowledge promotion lifecycle:
- Candidate -> Qualified -> Promoted -> Active -> Deprecated.
- **Dissent Tracking**: System must handle conflicting expert heuristics without overwriting.

## 2) Non-Negotiable Delivery Rules

1. **Zero-Stub Policy**: No runtime stubs, placeholders, or fake success payloads.
2. **Contract-First**: Every new route/service path must have contract and integration tests.
3. **Integrity Gates**: Every phase must ship a migration plan with destructive recovery verification.
4. **Line-Level Provenance**: Every claim must be traceable to a specific character-level evidence span.
5. **GUI-Integrated**: No backend feature is complete without a functional GUI workflow.

## 3) Delta Matrix (Paper vs Current vs Target)

| AEDIS Capability (Paper) | Current State | Gap | Target State |
|---|---|---|---|
| Immutable canonical truth anchors | Indexed records exist | No content-hash lineage | Immutable artifacts with SHA-256 anchors |
| Analytical mutable layer | Fragmented records | No unified version graph | Unified analysis model with parent lineage |
| Six separate ontologies | Basic Domain structure | Missing registry/governance | Registry with 6 versioned namespaces |
| Mandatory line-level provenance | File-level in parts | No universal character offsets | Enforced `EvidenceSpan` at write-time |
| Planner-Judge deterministic gate | Workflow workers | No hard persistence gate | Planner output persists ONLY on Judge PASS |
| Tacit knowledge promotion | Organization audit logs | No formal promotion lifecycle | Heuristic lifecycle with collision detection |
| Personalized learning pathways | Missing | No instructional layer | Generated, traceable learning paths |
| Measurement plan (KPIs) | Basic events | No AEDIS KPI model | KPI dashboard (Quality, Speed, Retention) |

## 4) Target Architecture (Concrete)

```
Canonical Artifact Store (Immutable SHA-256 Anchored)
  -> Analysis Layer (Mutable, Parent-Linked, Versioned)
    -> Ontology Registry (6 versioned classes)
      -> Planner Service (Strategy Composition)
        -> Judge Service (Deterministic DSL-based Rules)
          -> PASS: Persisted Output + Trace Graph
          -> FAIL: Rejection Artifact + Remediation Hints
Learning Path Service
  <- consumes heuristics + traces + objective outcomes
```

## 5) Phase Plan (No-Stub Gates)

## Phase 0 - Foundations & Contracts (1 week)

### Deliverables
- **RFC: Canonical Data Contracts**:
  - `CanonicalArtifact`, `AnalysisVersion`, `OntologyRecord`, `HeuristicRecord`, `PlannerRun`, `JudgeRun`, `LearningPath`.
  - **New**: `EvidenceSpan` (char-level offsets) and `AuditDelta` (expert trace diffs).
- **System Integrity Flag**: Implementation of `Start.py --check-integrity` to verify AEDIS service availability.

### Code Changes
- Add `services/contracts/aedis_models.py`.
- Add `gui/services/aedis_contract_adapters.py`.
- Add CI guard: `tests/quality/test_no_runtime_stubs.py`.

### Exit Criteria
- Contracts merged. CI fails on placeholder returns. 
- `--check-integrity` command successfully detects missing vs. active AEDIS layers.

---

## Phase 1 - Immutable Canonical Layer (2 weeks)

### Deliverables
- First-class immutable canonical artifact store.
- **Destructive Recovery Verification**: Migration tests that prove hash-anchors survive rollback/redo.

### DB/Migrations
- Tables: `canonical_artifacts`, `canonical_artifact_blobs`, `canonical_artifact_events` (append-only).
- Uniqueness: `UNIQUE(artifact_id, sha256)`.

### Service Changes
- `services/canonical_artifact_service.py` (strict no-mutation logic).

### Exit Criteria
- Any mutation attempt returns `403 Forbidden`.
- **Integrity Test**: `python scripts/migrate.py redo --verify-data-integrity` passes.

---

## Phase 2 - Six-Ontology Registry (2 weeks)

### Deliverables
- Unified registry for: Domain, Cognitive, Tool, Objective, Heuristic, Generative.
- Registry-backed activation/deprecation logic.

### Exit Criteria
- All ontology lookups flow through registry service.
- GUI version selector operational.

---

## Phase 3 - Global Line-Level Provenance (2 weeks)

### Deliverables
- Mandatory `ProvenanceRecord` envelope for all artifacts.
- **GUI Feature**: Character-level provenance highlighting (click generation to see source span).

### Exit Criteria
- Writes without character-level `EvidenceSpan` are rejected.
- GUI can visualize full provenance chain from generation to truth anchor.

---

## Phase 4 - Planner-Judge Deterministic Core (3 weeks)

### Deliverables
- Planner strategy composition service.
- **Judge DSL/Registry**: Versioned, deterministic rules for scoring (Schema, Success, Fidelity, Provenance).

### Exit Criteria
- Proof that Judge `FAIL` blocks DB persistence.
- Operator can inspect remediations in `gui/tabs/planner_judge_tab.py`.

---

## Phase 5 - Tacit Knowledge Promotion (3 weeks)

### Deliverables
- Candidate -> Qualified -> Promoted -> Active lifecycle.
- **Heuristic Collision Detection**: Handle multi-expert dissent/conflict.

### Exit Criteria
- All active heuristics have version + lineage + promotion record.
- Conflict resolver UI available for governance.

---

## Phase 6 - Instructional/Learning Activation (3 weeks)

### Deliverables
- Trace-backed LearningPath generation.
- **Traceable Mastery**: Each step links to a concrete expert trace or promoted heuristic.

### Exit Criteria
- Learning paths are trackable and verified in GUI.

---

## Phase 7 - Global Ontology Enforcement (2 weeks)

### Deliverables
- Universal ontology mapping for GLiNER/BERT and all agent outputs.

### Exit Criteria
- No entity output bypasses the registry contract.

---

## Phase 8 - Measurement Harness (2 weeks)

### Deliverables
- KPI dashboards: Quality (Judge Score), Speed, Retention (Expert heuristic reuse), Safety.
- **Automatic Holdout calibration**: Block regressions via holdout set validation.

### Exit Criteria
- KPIs automatically computed from production traces and visible in GUI.

---

## 6) Cross-Cutting Engineering Requirements

- **Migration Discipline**: Every phase requires `up`, `down`, `backfill`, and `integrity_check`.
- **Dissent Tracking**: Heuristics must capture who said what and when experts disagree.
- **Observability**: Span IDs must link API requests to specific Judge evaluations and DB writes.

## 7) Definition of Done (Program Level)

The AEDIS implementation is complete only when:
1. Every layer exists in production code and data model.
2. **Planner output cannot bypass deterministic Judge acceptance.**
3. All six ontology classes are versioned and govern runtime behavior.
4. **Heuristic promotion is active**, turning expert judgment into versioned capital.
5. Learning paths provide junior users with **Traceable Mastery** of institutional moves.
6. CI enforces the **Zero-Stub** mandate across the entire codebase.
