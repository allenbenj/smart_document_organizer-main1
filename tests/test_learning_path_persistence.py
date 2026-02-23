from __future__ import annotations

from mem_db.database import DatabaseManager
from services.learning_path_service import LearningPathService


def _spans() -> list[dict]:
    return [
        {
            "artifact_row_id": 1,
            "start_char": 0,
            "end_char": 12,
            "quote": "sample quote",
        }
    ]


def test_learning_path_persists_across_service_instances(tmp_path) -> None:
    db_path = tmp_path / "learning_paths.db"
    db = DatabaseManager(str(db_path))

    svc_a = LearningPathService(db)
    created = svc_a.generate_path(
        path_id="path-persist-1",
        user_id="user-1",
        objective_id="OBJ-1",
        heuristic_ids=["h1", "h2"],
        evidence_spans=_spans(),
    )
    assert created.path_id == "path-persist-1"

    svc_b = LearningPathService(db)
    loaded = svc_b.get_path("path-persist-1")
    assert loaded.path_id == "path-persist-1"
    assert len(loaded.steps) == 2


def test_learning_path_step_updates_persist_in_db(tmp_path) -> None:
    db_path = tmp_path / "learning_paths_updates.db"
    db = DatabaseManager(str(db_path))

    svc = LearningPathService(db)
    created = svc.generate_path(
        path_id="path-persist-2",
        user_id="user-2",
        objective_id="OBJ-2",
        heuristic_ids=["h1"],
        evidence_spans=_spans(),
    )

    step_id = created.steps[0].step_id
    updated = svc.update_step_completion(
        path_id="path-persist-2",
        step_id=step_id,
        completed=True,
    )
    assert updated.status == "completed"

    svc_reload = LearningPathService(db)
    loaded = svc_reload.get_path("path-persist-2")
    assert loaded.status == "completed"
    assert loaded.steps[0].completed is True
