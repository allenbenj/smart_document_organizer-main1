from fastapi.testclient import TestClient


def test_health_details_endpoint():
    from Start import app  # noqa: E402

    client = TestClient(app)
    resp = client.get("/api/health/details")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "healthy"
    assert "components" in data
    assert "api" in data["components"]
