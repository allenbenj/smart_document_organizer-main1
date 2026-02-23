from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import aedis_runtime
from services.heuristic_governance_service import HeuristicGovernanceService
from services.planner_judge_service import PlannerJudgeService


def _provenance_payload(artifact_row_id: int) -> dict:
    return {
        "source_artifact_row_id": artifact_row_id,
        "source_sha256": "a" * 64,
        "captured_at": "2026-02-21T00:00:00+00:00",
        "extractor": "pytest-runtime",
        "spans": [
            {
                "artifact_row_id": artifact_row_id,
                "start_char": 0,
                "end_char": 10,
                "quote": "test quote",
            }
        ],
        "notes": "test provenance",
    }


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(aedis_runtime.router, prefix="/api")
    return TestClient(app)


def _reset_services() -> None:
    aedis_runtime.planner_judge_service = PlannerJudgeService()
    aedis_runtime.heuristic_governance_service = HeuristicGovernanceService()


def test_planner_judge_run_and_lookup_endpoints() -> None:
    _reset_services()
    client = _build_client()

    run_resp = client.post(
        "/api/planner-judge/run",
        json={
            "objective_id": "OBJECTIVE.TEST",
            "artifact_row_id": 101,
            "strategy": {"goal": "test", "steps": []},
            "heuristic_ids": [],
        },
    )
    assert run_resp.status_code == 200
    body = run_resp.json()
    assert body["success"] is True
    planner_run = body["planner_run"]
    judge_run = body["judge_run"]
    assert judge_run["verdict"] == "PASS"

    planner_get = client.get(f"/api/planner/run/{planner_run['run_id']}")
    assert planner_get.status_code == 200
    assert planner_get.json()["item"]["objective_id"] == "OBJECTIVE.TEST"

    failures_get = client.get(f"/api/judge/failures/{planner_run['run_id']}")
    assert failures_get.status_code == 200
    assert failures_get.json()["failed"] is False


def test_planner_judge_fails_when_required_keys_missing() -> None:
    _reset_services()
    client = _build_client()

    run_resp = client.post(
        "/api/planner-judge/run",
        json={
            "objective_id": "OBJECTIVE.TEST",
            "artifact_row_id": 102,
            "strategy": {"goal": "missing steps"},
            "heuristic_ids": [],
        },
    )
    assert run_resp.status_code == 200
    body = run_resp.json()
    assert body["judge_run"]["verdict"] == "FAIL"
    assert any("missing required key" in r for r in body["judge_run"]["reasons"])


def test_judge_failures_missing_run_returns_404() -> None:
    _reset_services()
    client = _build_client()

    resp = client.get("/api/judge/failures/unknown-run")
    assert resp.status_code == 404


def test_heuristic_governance_endpoints() -> None:
    _reset_services()
    client = _build_client()

    register = client.post(
        "/api/heuristics/register",
        json={
            "heuristic_id": "h1",
            "rule_text": "Prefer corroborated claims with timeline anchors",
            "owner": "expert_a",
        },
    )
    assert register.status_code == 200

    evidence = client.post(
        "/api/heuristics/h1/evidence",
        json={"evidence_count": 22, "success_rate": 0.95},
    )
    assert evidence.status_code == 200

    candidates = client.get("/api/heuristics/candidates")
    assert candidates.status_code == 200
    assert candidates.json()["count"] >= 1

    promote = client.post(
        "/api/heuristics/candidates/h1/promote",
        json={"metadata": {}, "provenance": _provenance_payload(1)},
    )
    assert promote.status_code == 200
    assert promote.json()["item"]["stage"] == "active"

    governance = client.get("/api/heuristics/governance")
    assert governance.status_code == 200
    assert "items" in governance.json()

    collisions = client.get("/api/heuristics/h1/collisions")
    assert collisions.status_code == 200

    deprecate = client.post("/api/heuristics/h1/deprecate")
    assert deprecate.status_code == 200
    assert deprecate.json()["item"]["stage"] == "deprecated"


def test_heuristic_promotion_rejects_missing_provenance() -> None:
    _reset_services()
    client = _build_client()

    register = client.post(
        "/api/heuristics/register",
        json={
            "heuristic_id": "h-prov",
            "rule_text": "Prefer chain-of-custody corroboration",
            "owner": "expert_a",
        },
    )
    assert register.status_code == 200

    evidence = client.post(
        "/api/heuristics/h-prov/evidence",
        json={"evidence_count": 25, "success_rate": 0.95},
    )
    assert evidence.status_code == 200

    promote = client.post("/api/heuristics/candidates/h-prov/promote", json={"metadata": {}})
    assert promote.status_code == 400


def test_planner_persist_pass_allows_persistence() -> None:
    _reset_services()
    client = _build_client()

    run_resp = client.post(
        "/api/planner-judge/run",
        json={
            "objective_id": "OBJECTIVE.PERSIST",
            "artifact_row_id": 301,
            "strategy": {"goal": "persist", "steps": ["a"]},
            "heuristic_ids": [],
        },
    )
    assert run_resp.status_code == 200
    planner_run_id = run_resp.json()["planner_run"]["run_id"]

    persist = client.post(
        "/api/planner-judge/persist",
        json={
            "planner_run_id": planner_run_id,
            "output": {"result": "accepted"},
            "provenance": _provenance_payload(301),
        },
    )
    assert persist.status_code == 200
    assert persist.json()["success"] is True
    assert "provenance_status" in persist.json()["item"]

    persisted = client.get(f"/api/planner-judge/persisted/{planner_run_id}")
    assert persisted.status_code == 200
    assert persisted.json()["item"]["output"]["result"] == "accepted"


def test_planner_persist_fail_blocks_persistence_and_emits_failure_artifact() -> None:
    _reset_services()
    client = _build_client()

    run_resp = client.post(
        "/api/planner-judge/run",
        json={
            "objective_id": "OBJECTIVE.PERSIST.FAIL",
            "artifact_row_id": 302,
            "strategy": {"goal": "missing required steps key"},
            "heuristic_ids": [],
        },
    )
    assert run_resp.status_code == 200
    planner_run_id = run_resp.json()["planner_run"]["run_id"]
    assert run_resp.json()["judge_run"]["verdict"] == "FAIL"

    persist = client.post(
        "/api/planner-judge/persist",
        json={
            "planner_run_id": planner_run_id,
            "output": {"result": "reject-me"},
            "provenance": _provenance_payload(302),
        },
    )
    assert persist.status_code == 200
    body = persist.json()
    assert body["success"] is False
    assert body["blocked"] is True
    assert "failure_artifact" in body
    assert body["failure_artifact"]["planner_run_id"] == planner_run_id

    persisted = client.get(f"/api/planner-judge/persisted/{planner_run_id}")
    assert persisted.status_code == 404


def test_planner_persist_rejects_missing_provenance() -> None:
    _reset_services()
    client = _build_client()

    run_resp = client.post(
        "/api/planner-judge/run",
        json={
            "objective_id": "OBJECTIVE.PERSIST.PROV",
            "artifact_row_id": 303,
            "strategy": {"goal": "persist", "steps": ["x"]},
            "heuristic_ids": [],
        },
    )
    assert run_resp.status_code == 200
    planner_run_id = run_resp.json()["planner_run"]["run_id"]

    persist = client.post(
        "/api/planner-judge/persist",
        json={"planner_run_id": planner_run_id, "output": {"result": "accepted"}},
    )
    assert persist.status_code == 400


def test_provenance_readback_route_uses_service_contract(monkeypatch) -> None:
    _reset_services()
    client = _build_client()

    class _FakeProvenanceService:
        def get_provenance_for_artifact(self, target_type: str, target_id: str):
            from datetime import datetime, timezone
            from services.contracts.aedis_models import EvidenceSpan, ProvenanceRecord

            if target_id == "missing":
                return None
            return ProvenanceRecord(
                source_artifact_row_id=1,
                source_sha256="a" * 64,
                captured_at=datetime.now(timezone.utc),
                extractor="test",
                spans=[EvidenceSpan(artifact_row_id=1, start_char=0, end_char=4, quote="test")],
            )

    monkeypatch.setattr(aedis_runtime, "get_provenance_service", lambda: _FakeProvenanceService())

    ok = client.get("/api/provenance/planner_persisted_output/run-1")
    assert ok.status_code == 200
    assert ok.json()["success"] is True

    missing = client.get("/api/provenance/planner_persisted_output/missing")
    assert missing.status_code == 404
