from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import aedis_runtime
from services.learning_path_service import LearningPathService


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(aedis_runtime.router, prefix="/api")
    return TestClient(app)


def _reset_service() -> None:
    aedis_runtime.learning_path_service = LearningPathService()


def test_learning_path_generate_get_update_recommendations() -> None:
    _reset_service()
    client = _build_client()

    generated = client.post(
        "/api/learning-paths/generate",
        json={
            "path_id": "lp-1",
            "user_id": "user-1",
            "objective_id": "OBJECTIVE.LEARN",
            "heuristic_ids": ["h-1", "h-2"],
            "evidence_spans": [
                {
                    "artifact_row_id": 1,
                    "start_char": 0,
                    "end_char": 12,
                    "quote": "sample quote",
                }
            ],
        },
    )
    assert generated.status_code == 200
    body = generated.json()
    assert body["success"] is True
    assert len(body["item"]["steps"]) == 2

    fetched = client.get("/api/learning-paths/lp-1")
    assert fetched.status_code == 200
    step_id = fetched.json()["item"]["steps"][0]["step_id"]

    recs_before = client.get("/api/learning-paths/lp-1/recommendations")
    assert recs_before.status_code == 200
    assert recs_before.json()["count"] == 2

    updated = client.post(
        f"/api/learning-paths/lp-1/steps/{step_id}",
        json={"completed": True},
    )
    assert updated.status_code == 200

    recs_after = client.get("/api/learning-paths/lp-1/recommendations")
    assert recs_after.status_code == 200
    assert recs_after.json()["count"] == 1
