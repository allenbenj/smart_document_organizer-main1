from fastapi import HTTPException
from fastapi.routing import APIRoute


def test_verify_api_key_enforced_when_configured(monkeypatch):
    import Start

    monkeypatch.setattr(Start, "API_KEY_ENV", "unit-test-key")

    # Correct key should pass
    Start.verify_api_key("unit-test-key")

    # Missing/incorrect key should fail
    try:
        Start.verify_api_key(None)
        assert False, "Expected HTTPException for missing key"
    except HTTPException as e:
        assert e.status_code == 401

    try:
        Start.verify_api_key("wrong")
        assert False, "Expected HTTPException for wrong key"
    except HTTPException as e:
        assert e.status_code == 401


def test_auth_dependency_wired_on_protected_routes_not_health():
    import Start

    protected_paths = {"/api/documents/", "/api/agents"}

    for path in protected_paths:
        route = next(
            r for r in Start.app.routes if isinstance(r, APIRoute) and r.path == path
        )
        dep_names = {
            getattr(dep.dependency, "__name__", str(dep.dependency))
            for dep in route.dependencies
        }
        assert "verify_api_key" in dep_names

    for path in ("/api/health", "/api/health/details"):
        route = next(
            r for r in Start.app.routes if isinstance(r, APIRoute) and r.path == path
        )
        dep_names = {
            getattr(dep.dependency, "__name__", str(dep.dependency))
            for dep in route.dependencies
        }
        assert "verify_api_key" not in dep_names
