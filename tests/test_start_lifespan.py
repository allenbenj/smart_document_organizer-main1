from pathlib import Path

import pytest

import Start


def test_start_file_no_on_event_decorators() -> None:
    text = Path("Start.py").read_text(encoding="utf-8")
    assert "@app.on_event(" not in text


@pytest.mark.asyncio
async def test_lifespan_invokes_startup_and_shutdown(monkeypatch) -> None:
    calls = []

    async def fake_startup() -> None:
        calls.append("startup")

    async def fake_shutdown() -> None:
        calls.append("shutdown")

    monkeypatch.setattr(Start, "_startup_services", fake_startup)
    monkeypatch.setattr(Start, "_shutdown_services", fake_shutdown)

    async with Start.app.router.lifespan_context(Start.app):
        assert calls == ["startup"]

    assert calls == ["startup", "shutdown"]


@pytest.mark.asyncio
async def test_lifespan_propagates_startup_errors(monkeypatch) -> None:
    async def failing_startup() -> None:
        raise RuntimeError("startup failure")

    monkeypatch.setattr(Start, "_startup_services", failing_startup)

    with pytest.raises(RuntimeError, match="startup failure"):
        async with Start.app.router.lifespan_context(Start.app):
            pass
