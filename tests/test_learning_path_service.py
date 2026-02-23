from __future__ import annotations

from services.learning_path_service import LearningPathService


def test_learning_path_service_generates_deterministic_step_count() -> None:
    svc = LearningPathService()

    path = svc.generate_path(
        path_id="lp-svc-1",
        user_id="user-a",
        objective_id="OBJECTIVE.LEARN",
        heuristic_ids=["h-1", "h-2", "h-3"],
        evidence_spans=[
            {
                "artifact_row_id": 1,
                "start_char": 0,
                "end_char": 8,
                "quote": "evidence",
            }
        ],
    )

    assert len(path.steps) == 3
    assert path.steps[0].heuristic_ids == ["h-1"]


def test_learning_path_service_completion_updates_status() -> None:
    svc = LearningPathService()

    path = svc.generate_path(
        path_id="lp-svc-2",
        user_id="user-a",
        objective_id="OBJECTIVE.LEARN",
        heuristic_ids=["h-1"],
        evidence_spans=[
            {
                "artifact_row_id": 1,
                "start_char": 0,
                "end_char": 8,
                "quote": "evidence",
            }
        ],
    )

    step_id = path.steps[0].step_id
    updated = svc.update_step_completion(path_id="lp-svc-2", step_id=step_id, completed=True)

    assert updated.status == "completed"
    assert updated.steps[0].completed is True
