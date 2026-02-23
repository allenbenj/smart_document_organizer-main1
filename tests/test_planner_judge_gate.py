from __future__ import annotations

from services.planner_judge_service import PlannerJudgeService


def test_judge_fail_blocks_persistence_semantics() -> None:
    svc = PlannerJudgeService()
    run = svc.create_plan(
        run_id="p1",
        objective_id="obj-1",
        artifact_row_id=1,
        heuristic_ids=[],
        strategy={"goal": "organize"},
    )

    judged = svc.judge_plan(run.run_id)
    assert judged.verdict == "FAIL"
    assert judged.remediation
