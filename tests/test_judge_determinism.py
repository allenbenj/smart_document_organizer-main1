from __future__ import annotations

from services.planner_judge_service import PlannerJudgeService


def test_judge_score_is_deterministic_for_same_strategy() -> None:
    svc = PlannerJudgeService()
    strategy = {"goal": "organize", "steps": ["scan", "classify"]}

    first = svc.create_plan(
        run_id="d1",
        objective_id="obj",
        artifact_row_id=2,
        heuristic_ids=["h1"],
        strategy=strategy,
    )
    second = svc.create_plan(
        run_id="d2",
        objective_id="obj",
        artifact_row_id=2,
        heuristic_ids=["h1"],
        strategy=strategy,
    )

    j1 = svc.judge_plan(first.run_id)
    j2 = svc.judge_plan(second.run_id)

    assert j1.verdict == "PASS"
    assert j2.verdict == "PASS"
    assert j1.score == j2.score
