from fastapi.testclient import TestClient


def test_auth_optional_access_without_api_key():
    from Start import app  # noqa: E402

    client = TestClient(app)
    # No API_KEY in environment should allow access
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "healthy"
