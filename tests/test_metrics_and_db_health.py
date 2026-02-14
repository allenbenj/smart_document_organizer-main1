from fastapi.testclient import TestClient


def test_metrics_endpoint_enabled():
    from Start import app  # noqa: E402

    client = TestClient(app)
    r = client.get("/api/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data.get("enabled") is True
    assert "requests_total" in data
    assert "per_path" in data
    assert "per_method" in data


def test_health_details_database():
    from Start import app  # noqa: E402

    client = TestClient(app)
    r = client.get("/api/health/details")
    assert r.status_code == 200
    data = r.json()
    assert "components" in data
    db = data["components"].get("database")
    assert isinstance(db, dict)
    assert "ok" in db
