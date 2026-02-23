from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.core.models import AgentResult
from routes import aedis_runtime
from routes.extraction import router as extraction_router
from services.dependencies import get_agent_manager_strict_dep
from services.heuristic_governance_service import HeuristicGovernanceService
from services.learning_path_service import LearningPathService
from services.planner_judge_service import PlannerJudgeService
from services.planner_persistence_gate_service import PlannerPersistenceGateService


class _FakeExtractionManager:
    async def extract_entities(self, text: str, **kwargs):
        entities = [
            {
                "id": "loc-1",
                "text": "downstairs",
                "entity_type": "location",
                "confidence": 0.98,
                "start_pos": 39,
                "end_pos": 49,
                "source": kwargs.get("extraction_type", "ner"),
                "attributes": {"canonical_value": "downstairs"},
            }
        ]
        return AgentResult(
            success=True,
            data={
                "extraction_result": {
                    "entities": entities,
                    "relationships": [
                        {
                            "source_id": "loc-1",
                            "target_id": "evt-1",
                            "relation_type": "CONTAINS_EVIDENCE",
                        }
                    ],
                    "extraction_stats": {"entity_count": 1, "relationship_count": 1},
                }
            },
            agent_type="entity_extractor",
        )


class _FakeProvenanceService:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], dict] = {}
        self._next_id = 1

    def record_provenance(self, record, target_type: str, target_id: str) -> int:
        record_id = self._next_id
        self._next_id += 1
        self._records[(target_type, target_id)] = record.model_dump(mode="json")
        return record_id

    def get_provenance_for_artifact(self, target_type: str, target_id: str):
        payload = self._records.get((target_type, target_id))
        if not payload:
            return None
        return _ProvenanceEnvelope(payload)


class _ProvenanceEnvelope:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def model_dump(self, mode: str = "json") -> dict:
        _ = mode
        return self._payload


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(extraction_router, prefix="/api/extraction")
    app.include_router(aedis_runtime.router, prefix="/api")

    async def _override_dep():
        return _FakeExtractionManager()

    app.dependency_overrides[get_agent_manager_strict_dep] = _override_dep
    return TestClient(app)


def _reset_runtime_services() -> None:
    provenance_service = _FakeProvenanceService()
    aedis_runtime.planner_judge_service = PlannerJudgeService()
    aedis_runtime.heuristic_governance_service = HeuristicGovernanceService()
    aedis_runtime.planner_persistence_gate_service = PlannerPersistenceGateService()
    aedis_runtime.learning_path_service = LearningPathService()
    aedis_runtime.get_provenance_service = lambda: provenance_service


def _provenance_payload(artifact_row_id: int) -> dict:
    return {
        "source_artifact_row_id": artifact_row_id,
        "source_sha256": "b" * 64,
        "captured_at": "2026-02-22T00:00:00+00:00",
        "extractor": "iap_judge_pipeline_test",
        "spans": [
            {
                "artifact_row_id": artifact_row_id,
                "start_char": 39,
                "end_char": 49,
                "quote": "downstairs",
            }
        ],
        "notes": "judge persona end-to-end validation",
    }


def _full_iap_strategy() -> dict:
    return {
        "goal": "Run IAP Judge persona across all operational phases",
        "steps": [
            "phase_1_fact_extraction_and_issue_tree",
            "phase_2_legal_research_and_principles",
            "phase_3_irac_dissection",
            "phase_4_toulmin_argument_construction",
            "phase_5_critical_scrutiny",
            "phase_6_supplementary_reasoning",
            "phase_7_strategic_calculus",
            "phase_8_uncertainty_and_transparency",
            "phase_9_synthesis_and_action_output",
        ],
        "phase_1": {"root_issue": "suppression risk", "branches": ["evidence", "procedure"]},
        "phase_2": {"jurisdiction": "North Carolina", "rule_set": ["KRE901-analog", "NC suppressions"]},
        "phase_3": {"irac": {"issue": "lawful seizure", "rule": "authentication required"}},
        "phase_4": {"toulmin": {"claim": "suppression risk", "warrant": "custody/authentication"}},
        "phase_5": {"critical_scrutiny": {"fallacy_flags": [], "inconsistency_flags": []}},
        "phase_6": {"reasoning": {"abductive": ["chain-break"], "causal_chain": ["entry", "seizure"]}},
        "phase_7": {"swot": {"strengths": ["timeline"], "threats": ["missing logs"]}},
        "phase_8": {"risk_disclosure": ["camera gap"], "confidence": 0.86},
        "phase_9": {"output_target": "motion_to_suppress_outline"},
    }


def test_judge_persona_runs_full_pipeline_steps_end_to_end() -> None:
    _reset_runtime_services()
    client = _build_client()

    extraction = client.post(
        "/api/extraction/run",
        json={
            "text": "Officer proceeded downstairs and located disputed evidence.",
            "extraction_type": "llm",
            "options": {"jurisdiction": "North Carolina"},
        },
    )
    assert extraction.status_code == 200
    extraction_body = extraction.json()
    assert extraction_body["success"] is True
    assert extraction_body["data"]["entities"][0]["text"] == "downstairs"

    heuristic_id = "iap.judge.chain_of_custody"
    register = client.post(
        "/api/heuristics/register",
        json={
            "heuristic_id": heuristic_id,
            "rule_text": "Prefer corroborated chain-of-custody with timeline anchors.",
            "owner": "iap_judge_persona",
        },
    )
    assert register.status_code == 200

    evidence = client.post(
        f"/api/heuristics/{heuristic_id}/evidence",
        json={"evidence_count": 24, "success_rate": 0.93},
    )
    assert evidence.status_code == 200

    promote = client.post(
        f"/api/heuristics/candidates/{heuristic_id}/promote",
        json={
            "metadata": {"phase": "persona_bootstrap"},
            "provenance": _provenance_payload(501),
        },
    )
    assert promote.status_code == 200
    assert promote.json()["item"]["stage"] == "active"

    run = client.post(
        "/api/planner-judge/run",
        json={
            "run_id": "planner::iap-judge::full-flow",
            "objective_id": "OBJECTIVE.IAP.JUDGE.FULL",
            "artifact_row_id": 501,
            "strategy": _full_iap_strategy(),
            "heuristic_ids": [heuristic_id],
        },
    )
    assert run.status_code == 200
    run_body = run.json()
    assert run_body["success"] is True
    assert run_body["judge_run"]["verdict"] == "PASS"
    planner_run_id = run_body["planner_run"]["run_id"]

    judge_failures = client.get(f"/api/judge/failures/{planner_run_id}")
    assert judge_failures.status_code == 200
    assert judge_failures.json()["failed"] is False

    persist = client.post(
        "/api/planner-judge/persist",
        json={
            "planner_run_id": planner_run_id,
            "output": {
                "jurisdiction": "North Carolina",
                "canonical_value": "downstairs",
                "status": "verified",
                "relations_json": extraction_body["data"]["relationships"],
            },
            "provenance": _provenance_payload(501),
        },
    )
    assert persist.status_code == 200
    persist_body = persist.json()
    assert persist_body["success"] is True

    persisted = client.get(f"/api/planner-judge/persisted/{planner_run_id}")
    assert persisted.status_code == 200
    assert persisted.json()["item"]["output"]["canonical_value"] == "downstairs"

    provenance = client.get(f"/api/provenance/planner_persisted_output/{planner_run_id}")
    assert provenance.status_code == 200
    assert provenance.json()["item"]["extractor"] == "iap_judge_pipeline_test"

    learning_path = client.post(
        "/api/learning-paths/generate",
        json={
            "path_id": "lp-iap-judge-full",
            "user_id": "judge-persona-user",
            "objective_id": "OBJECTIVE.IAP.JUDGE.FULL",
            "heuristic_ids": [heuristic_id],
            "evidence_spans": _provenance_payload(501)["spans"],
        },
    )
    assert learning_path.status_code == 200
    lp_body = learning_path.json()
    assert lp_body["success"] is True
    assert len(lp_body["item"]["steps"]) == 1

    step_id = lp_body["item"]["steps"][0]["step_id"]
    complete = client.post(
        f"/api/learning-paths/lp-iap-judge-full/steps/{step_id}",
        json={"completed": True},
    )
    assert complete.status_code == 200
    assert complete.json()["item"]["steps"][0]["completed"] is True
