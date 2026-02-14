from fastapi.testclient import TestClient


def test_health_details_includes_config_section():
    from Start import app  # noqa: E402

    client = TestClient(app)
    r = client.get("/api/health/details")
    assert r.status_code == 200
    data = r.json()
    comps = data.get("components", {})
    cfg = comps.get("config")
    assert isinstance(cfg, dict)
    assert "env" in cfg
    assert "agents" in cfg
    assert "vector" in cfg
