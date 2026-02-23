from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import data_explorer


def test_data_explorer_integrity_report_route(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(data_explorer.router, prefix="/api/data-explorer")

    expected = {
        "status": "issues_detected",
        "total_checks": 1,
        "total_issues": 1,
        "highest_severity": "warning",
        "issues": [
            {
                "check_name": "dummy_check",
                "issue_count": 1,
                "severity": "warning",
                "details": "dummy details",
                "recommended_action": "dummy action",
            }
        ],
        "actions": ["dummy action"],
    }
    monkeypatch.setattr(
        data_explorer.data_integrity_service,
        "generate_report",
        lambda: expected,
    )

    client = TestClient(app)
    response = client.get("/api/data-explorer/integrity-report")
    assert response.status_code == 200
    assert response.json() == expected
