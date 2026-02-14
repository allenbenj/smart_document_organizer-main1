from pathlib import Path

from fastapi.routing import APIRoute


def test_start_has_no_inline_health_endpoints():
    """Regression: health endpoints are owned by routes/health.py, not Start.py."""
    content = Path("Start.py").read_text(encoding="utf-8")
    assert '@app.get("/health")' not in content
    assert '@app.get("/health/details")' not in content


def test_health_routes_exist_under_api_prefix():
    from Start import app

    paths = {
        r.path
        for r in app.routes
        if isinstance(r, APIRoute) and "GET" in (getattr(r, "methods", set()) or set())
    }
    assert "/api/health" in paths
    assert "/api/health/details" in paths


def test_no_direct_singleton_calls_in_health_and_vector_routes():
    """Regression for P0-5: route handlers should rely on dependencies, not singleton calls."""
    health = Path("routes/health.py").read_text(encoding="utf-8")
    vector = Path("routes/vector_store.py").read_text(encoding="utf-8")

    assert "store = get_vector_store()" not in health
    assert "db = get_database_manager()" not in health
    assert "mgr = get_agent_manager()" not in health

    assert "store = get_vector_store()" not in vector
