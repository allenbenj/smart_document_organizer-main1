from __future__ import annotations

import asyncio
import logging

import pytest

from agents.production_manager.operations import OperationsMixin


class _DummyManager(OperationsMixin):
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.is_initialized = False
        self._initialization_task = None
        self.agents = {}

    async def initialize(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_ensure_initialized_waits_for_background_task() -> None:
    manager = _DummyManager()

    async def _finish_init() -> None:
        await asyncio.sleep(0.01)
        manager.is_initialized = True

    manager._initialization_task = asyncio.create_task(_finish_init())
    ok = await manager._ensure_initialized(timeout_seconds=1.0)

    assert ok is True
    assert manager.is_initialized is True


@pytest.mark.asyncio
async def test_process_document_returns_init_error_when_not_ready() -> None:
    manager = _DummyManager()
    result = await manager.process_document("nonexistent.txt", init_wait_seconds=0.05)

    assert result.success is False
    assert result.error == "Production system not initialized"
