from __future__ import annotations

from types import SimpleNamespace

import pytest
from routes.agent_routes import common
from services.agent_service import AgentService


@pytest.mark.asyncio
async def test_get_agent_service_relaxed_skips_startup_guard(monkeypatch) -> None:
    fake_manager = object()

    async def fake_dep(_request):
        return fake_manager

    monkeypatch.setattr(common, "get_agent_manager_dep", fake_dep)

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                agent_startup={"strict": True, "missing": ["document_processor"]},
            )
        )
    )

    svc = await common.get_agent_service_relaxed(request)
    assert isinstance(svc, AgentService)
    assert svc.agent_manager is fake_manager


@pytest.mark.asyncio
async def test_get_strict_production_manager_initializes_and_does_not_guard(
    monkeypatch,
) -> None:
    class FakeManager:
        def __init__(self) -> None:
            self.agents = {}

        async def initialize(self) -> bool:
            return True

    fake_manager = FakeManager()

    async def fake_dep(_request):
        return fake_manager

    import services.dependencies as deps

    monkeypatch.setattr(deps, "get_agent_manager_strict_dep", fake_dep)

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                agent_startup={
                    "strict": True,
                    "missing": ["document_processor"],
                    "required": ["document_processor"],
                    "available": [],
                }
            )
        )
    )

    out = await common.get_strict_production_manager(request)

    assert out is fake_manager
    assert request.app.state.agent_startup.get("strict") is False
