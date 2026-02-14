from fastapi.testclient import TestClient


def test_vector_status_endpoint():
    from Start import app  # noqa: E402

    client = TestClient(app)
    r = client.get("/api/vector")
    assert r.status_code == 200
    data = r.json()
    assert "available" in data
