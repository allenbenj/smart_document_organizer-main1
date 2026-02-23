from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from services.contracts.aedis_models import JudgeRun, PlannerRun
from services.planner_persistence_gate_service import PlannerPersistenceGateService


def _planner(run_id: str) -> PlannerRun:
    return PlannerRun(
        run_id=run_id,
        objective_id="OBJECTIVE.TEST",
        artifact_row_id=1,
        heuristic_ids=[],
        strategy={"goal": "x", "steps": []},
        created_at=datetime.now(UTC),
    )


def _judge(run_id: str, verdict: str) -> JudgeRun:
    return JudgeRun(
        run_id=f"judge::{run_id}",
        planner_run_id=run_id,
        artifact_row_id=1,
        verdict=verdict,
        score=0.9 if verdict == "PASS" else 0.2,
        reasons=[] if verdict == "PASS" else ["missing required key: steps"],
        remediation=[] if verdict == "PASS" else ["add strategy.steps"],
        created_at=datetime.now(UTC),
    )


def test_persist_allows_pass_verdict() -> None:
    svc = PlannerPersistenceGateService()
    record = svc.persist_planner_output(
        planner_run=_planner("run-pass"),
        judge_run=_judge("run-pass", "PASS"),
        output_payload={"ok": True},
    )

    assert record["planner_run_id"] == "run-pass"
    assert svc.get_persisted("run-pass")["output"]["ok"] is True


def test_persist_blocks_fail_verdict() -> None:
    svc = PlannerPersistenceGateService()

    with pytest.raises(PermissionError):
        svc.persist_planner_output(
            planner_run=_planner("run-fail"),
            judge_run=_judge("run-fail", "FAIL"),
            output_payload={"ok": False},
        )

    assert svc.get_blocked("run-fail") is not None
    with pytest.raises(KeyError):
        svc.get_persisted("run-fail")


def test_malformed_judge_shape_cannot_bypass_gate() -> None:
    svc = PlannerPersistenceGateService()
    malformed_judge = SimpleNamespace(
        verdict="BROKEN",
        run_id="judge::broken",
        reasons=["corrupt verdict"],
        remediation=["re-run judge"],
    )

    with pytest.raises(PermissionError):
        svc.persist_planner_output(
            planner_run=_planner("run-malformed"),
            judge_run=malformed_judge,  # type: ignore[arg-type]
            output_payload={"ok": "no"},
        )

    with pytest.raises(KeyError):
        svc.get_persisted("run-malformed")
