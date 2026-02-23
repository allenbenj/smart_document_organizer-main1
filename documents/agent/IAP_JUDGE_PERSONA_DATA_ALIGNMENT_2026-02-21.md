# IAP Judge Persona - Data Element Alignment

Date: 2026-02-21  
Scope: Align the Integrated Adversarial Protocol (IAP) with concrete system data elements, references, and implementation touchpoints.

## 1. Authoritative References

## 1.1 Jurisprudential References (for persona behavior)
- Oliver Wendell Holmes Jr., *The Common Law* (1881) - experience-grounded legal reasoning.
- Louis D. Brandeis, judicial method emphasizing factual record depth and practical consequences.
- Hugo Black, textual fidelity and rule-constrained interpretation.
- Earl Warren, procedural fairness and equal administration.
- William J. Brennan Jr., adaptive constitutional/application reasoning to lived realities.
- Thurgood Marshall, due process and equal protection rigor in adversarial procedure.

## 1.2 System References (for implementation)
- AEDIS contracts: `services/contracts/aedis_models.py`
- Knowledge payload contract: `routes/knowledge.py`
- Runtime judge/planner/provenance/learning routes: `routes/aedis_runtime.py`
- Provenance gate service: `services/provenance_service.py`
- Heuristic lifecycle service: `services/heuristic_governance_service.py`
- Learning path service: `services/learning_path_service.py`
- Memory proposal lifecycle: `services/memory_service.py`, `routes/agent_routes/memory.py`
- Canonical/knowledge persistence tables: `mem_db/database.py`
- Provenance tables: `mem_db/migrations/phases/p3_up.sql`

## 2. Persona Operating Constraints

- Jurisdiction must be parameterized, not hardcoded.  
- Default runtime jurisdiction for this deployment: `North Carolina`.
- Every substantive claim used by Judge scoring should carry provenance spans (or fail closed where enforced).
- Planner output persistence must be blocked on Judge `FAIL`.
- Heuristic promotion should include provenance lineage payload.

## 3. Required Data Elements (Minimum Viable IAP Persona)

## 3.1 Core Identity and Context
- `persona_id`
- `jurisdiction` (default: `North Carolina`)
- `forum_level` (trial/appellate/admin)
- `case_type` (criminal/civil/regulatory)
- `stance` (prosecution/defense)

## 3.2 Issue-Tree and IRAC Structure
- `root_issue`
- `branches[]` with:
  - `branch_id`
  - `branch_type` (`elements`, `defenses`, `evidence`, `procedure`)
  - `priority_score` (weighted)
  - `irac.issue`
  - `irac.rule`
  - `irac.application`
  - `irac.conclusion`

## 3.3 Toulmin Argument Structure
- `claim`
- `data[]`
- `warrant`
- `backing[]`
- `qualifiers[]`
- `rebuttals[]`

## 3.4 Critical Scrutiny Layer
- `assumptions[]`
- `fallacy_flags[]`
- `inconsistency_flags[]`
- `bias_flags[]`
- `alternative_hypotheses[]`
- `weakness_severity_score`

## 3.5 Strategic Layer
- `causal_chain[]`
- `abductive_ranked_explanations[]`
- `cost_benefit_matrix[]`
- `swot` (`strengths`, `weaknesses`, `opportunities`, `threats`)
- `recommended_actions[]`

## 3.6 Provenance and Auditability
- `source_artifact_row_id`
- `source_sha256`
- `extractor`
- `spans[]` (start/end offsets + quote)
- `target_type`
- `target_id`
- `confidence`

Mapped contracts:
- `EvidenceSpan`, `ProvenanceRecord`, `AnalysisVersion`, `PlannerRun`, `JudgeRun`, `LearningStep`, `LearningPath` in `services/contracts/aedis_models.py`.

## 4. IAP Phase -> System Mapping

| IAP Phase | Required Data | Current System Path |
|---|---|---|
| Phase 1 Fact Extraction + Issue Tree | entities, evidence spans, branch map | `routes/extraction.py`, `agents/extractors/hybrid_extractor.py` |
| Phase 2 Legal Research + Principle ID | rule catalog, jurisdictional authority refs | `routes/knowledge.py`, `services/knowledge_service.py` |
| Phase 3 IRAC Dissection | issue/rule/application/conclusion objects | `routes/agent_routes/analysis.py`, `services/contracts/aedis_models.py` |
| Phase 4 Toulmin Construction | claim/data/warrant/backing/rebuttal fields | `routes/knowledge.py` (`KnowledgeItemPayload`) |
| Phase 5 Critical Scrutiny | flags, inconsistencies, alternative hypotheses | analysis/legal reasoning + memory proposals |
| Phase 6 Supplementary Reasoning | abductive/causal/cost-benefit outputs | analysis layer + knowledge payload extensions |
| Phase 7 Strategic Calculus (SWOT) | SWOT matrix + recommendations | knowledge/analysis outputs |
| Phase 8 Uncertainty + Transparency | provenance completeness + confidence qualifiers | `services/provenance_service.py`, `routes/aedis_runtime.py` |
| Phase 9 Synthesis + Action Output | judged result + persisted output + learning path | `routes/aedis_runtime.py` (`planner-judge`, `persist`, `learning-paths`) |

## 5. Judge Scoring Criteria (Drafted from IAP)

Use deterministic dimensions (0-1 scale each):
- `schema_compliance`
- `objective_success`
- `heuristic_fidelity`
- `provenance_completeness`
- `risk_disclosure`

Gate rule:
- If any required key missing or provenance invalid -> `FAIL`.
- Persistence allowed only on `PASS` (already enforced in runtime path).

References:
- `services/planner_judge_service.py`
- `services/planner_persistence_gate_service.py`
- `routes/aedis_runtime.py`

## 6. Canonical Payload Template for IAP Judge Persona

```json
{
  "persona_id": "IAP_JUDGE_V1",
  "jurisdiction": "North Carolina",
  "case_type": "criminal",
  "stance": "defense",
  "root_issue": "Did the search violate constitutional constraints?",
  "branches": [
    {
      "branch_id": "evidence_admissibility",
      "branch_type": "evidence",
      "priority_score": 0.86,
      "irac": {
        "issue": "Was seizure lawful under governing standards?",
        "rule": "Applicable constitutional and evidentiary standards",
        "application": "Fact-to-rule mapping with causal chain and exceptions",
        "conclusion": "Suppression risk is substantial"
      },
      "toulmin": {
        "claim": "Evidence is vulnerable to suppression",
        "data": ["timeline gap", "custody gap"],
        "warrant": "authentication/custody requirements",
        "backing": ["controlling precedent"],
        "qualifiers": ["if timeline gap remains unrebutted"],
        "rebuttals": ["state may assert good-faith exception"]
      }
    }
  ],
  "provenance": {
    "source_artifact_row_id": 1,
    "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "extractor": "iap_judge_runtime",
    "spans": [
      {"artifact_row_id": 1, "start_char": 0, "end_char": 120, "quote": "evidence excerpt"}
    ]
  }
}
```

## 7. Immediate Implementation Hooks

- Judge + persistence: `POST /api/planner-judge/run`, `POST /api/planner-judge/persist`.
- Heuristic lifecycle with provenance payload: `POST /api/heuristics/candidates/{candidate_id}/promote`.
- Provenance readback: `GET /api/provenance/{target_type}/{target_id}`.
- Learning rollout: `POST /api/learning-paths/generate` and follow-up endpoints.

## 8. Remaining Alignment Work

1. Enforce provenance gate in organization proposal and knowledge-approval promotion paths (fail-closed where required).
2. Ensure all analysis-version writes are provenance-gated by service/route entrypoints.
3. Extend knowledge payload normalization for full IAP fields (critical scrutiny + SWOT + cost-benefit) where absent.
4. Add end-to-end regression asserting persona output can traverse extraction -> judge -> persistence -> learning path with full traceability.

---

This document is stored in-project for immediate use by both implementation agents and can serve as the reference contract for the IAP Judge persona rollout.
