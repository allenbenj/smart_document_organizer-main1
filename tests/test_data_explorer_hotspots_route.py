from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import data_explorer


def test_data_explorer_hotspots_route(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(data_explorer.router, prefix="/api/data-explorer")

    expected = [
        {
            "file_path": "src/high.py",
            "change_events": 12,
            "issue_weight": 8,
            "complexity_score": 8.5,
            "hotspot_score": 83.0,
            "risk_level": "critical",
            "recommended_action": "do things",
        }
    ]
    monkeypatch.setattr(
        data_explorer.code_hotspot_service,
        "get_hotspots",
        lambda limit=50: expected,
    )

    client = TestClient(app)
    response = client.get("/api/data-explorer/hotspots", params={"limit": 10})
    assert response.status_code == 200
    assert response.json() == expected
