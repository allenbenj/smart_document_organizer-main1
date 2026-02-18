from __future__ import annotations

from types import SimpleNamespace

import Start
from diagnostics.startup_report import build_startup_report


def test_resolve_launch_mode_prefers_explicit_backend() -> None:
    mode = Start._resolve_launch_mode(
        backend_requested=True,
        gui_requested=False,
        startup_profile="full",
        headless=False,
    )
    assert mode == "backend"


def test_resolve_launch_mode_prefers_explicit_gui() -> None:
    mode = Start._resolve_launch_mode(
        backend_requested=False,
        gui_requested=True,
        startup_profile="api",
        headless=True,
    )
    assert mode == "gui"


def test_resolve_launch_mode_uses_profile_and_headless_defaults() -> None:
    assert (
        Start._resolve_launch_mode(
            backend_requested=False,
            gui_requested=False,
            startup_profile="api",
            headless=False,
        )
        == "backend"
    )
    assert (
        Start._resolve_launch_mode(
            backend_requested=False,
            gui_requested=False,
            startup_profile="full",
            headless=True,
        )
        == "backend"
    )


def test_backend_readiness_urls_include_primary_endpoints() -> None:
    urls = Start._backend_readiness_urls(port=8011)
    assert urls[0].endswith("/api/health")
    assert any(url.endswith("/api/startup/report") for url in urls)
    assert any(url.endswith("/api/health/details") for url in urls)


def test_startup_report_separates_optional_router_failures() -> None:
    app = SimpleNamespace(
        state=SimpleNamespace(
            agent_startup={},
            router_load_report=[
                {"name": "core_router", "prefix": "/api", "ok": False, "optional": False},
                {"name": "web_gui", "prefix": "/web", "ok": False, "optional": True},
                {"name": "health", "prefix": "/api", "ok": True, "optional": False},
            ],
            startup_steps=[{"name": "plugin_loading", "status": "CompleteWithWarnings"}],
            startup_profile="api",
            agents_lazy_init=True,
            startup_offline_safe=True,
        )
    )

    report = build_startup_report(
        app=app,
        strict_startup=False,
        required_production_agents=[],
        api_key_enabled=False,
        rate_limit_requests_per_minute=60,
    )

    assert len(report["routers"]["failed"]) == 1
    assert report["routers"]["failed"][0]["name"] == "core_router"
    assert len(report["routers"]["failed_optional"]) == 1
    assert report["routers"]["failed_optional"][0]["name"] == "web_gui"
    assert report["runtime"]["startup_profile"] == "api"
    assert report["runtime"]["agents_lazy_init"] is True
