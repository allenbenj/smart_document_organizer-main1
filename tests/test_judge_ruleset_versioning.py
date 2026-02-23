from __future__ import annotations

from services.planner_judge_service import PlannerJudgeService


def test_ruleset_version_activation_changes_requirements() -> None:
    svc = PlannerJudgeService()
    new = svc.create_ruleset(name="strict", required_keys=["goal", "steps", "risk_controls"])
    svc.activate_ruleset(new["version"])

    run = svc.create_plan(
        run_id="rv1",
        objective_id="obj-3",
        artifact_row_id=3,
        heuristic_ids=[],
        strategy={"goal": "organize", "steps": ["index"]},
    )
    judged = svc.judge_plan(run.run_id)

    assert svc.active_ruleset_version == new["version"]
    assert judged.verdict == "FAIL"
    assert any("risk_controls" in reason for reason in judged.reasons)
