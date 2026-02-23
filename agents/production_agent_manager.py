"""Thin production agent manager entry point."""

import asyncio
import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from agents.core.manager_interface import AgentManagerProtocol

from .production_manager import (
    HealthLifecycleMixin,
    InitializationMixin,
    OperationsMixin,
    PRODUCTION_AGENTS_AVAILABLE,
)

logger = logging.getLogger(__name__)


class ProductionAgentManager(
    InitializationMixin,
    OperationsMixin,
    HealthLifecycleMixin,
    AgentManagerProtocol,
):
    """Production-only manager orchestrating agent initialization and operations."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.service_container = None
        self.agent_factory = None
        self.agents = {}
        self.is_initialized = False

        self._cache: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
        ttl = int(os.getenv("AGENTS_CACHE_TTL_SECONDS", "300"))
        self._cache_ttl = timedelta(seconds=max(1, ttl))

        try:
            self._default_timeout = float(os.getenv("AGENTS_DEFAULT_TIMEOUT_SECONDS", "6"))
        except Exception:
            self._default_timeout = 6.0

        self._flags = {
            k: (os.getenv(k, "1").strip() not in ("0", "false", "False"))
            for k in [
                "AGENTS_ENABLE_LEGAL_REASONING",
                "AGENTS_ENABLE_ENTITY_EXTRACTOR",
                "AGENTS_ENABLE_IRAC",
                "AGENTS_ENABLE_TOULMIN",
                "AGENTS_ENABLE_SEMANTIC",
                "AGENTS_ENABLE_KG",
            ]
        }

        self._feedback_path = Path("logs/feedback.jsonl")
        self._precedent_analyzer = None
        self._contract_analyzer = None
        self._compliance_checker = None
        self._initialization_started = False

        self._init_lock = threading.Lock()
        self._async_init_lock: Optional[asyncio.Lock] = None
        self._initialization_task: Optional[asyncio.Task[None]] = None

        if PRODUCTION_AGENTS_AVAILABLE:
            self.logger.info("ProductionAgentManager created. Call initialize() to start.")
        else:
            self.logger.error("Production agents are not available; manager disabled")

    async def initialize(self) -> bool:
        """Initialize the production agent system exactly once (supporting background boot)."""
        if self.is_initialized:
            return True

        with self._init_lock:
            if not self._initialization_started:
                self._initialization_started = True

        if self._async_init_lock is None:
            self._async_init_lock = asyncio.Lock()

        async with self._async_init_lock:
            if self.is_initialized:
                return True

            if PRODUCTION_AGENTS_AVAILABLE:
                # Trigger background initialization once; callers can poll is_initialized.
                if self._initialization_task is None or self._initialization_task.done():
                    self._initialization_task = asyncio.create_task(
                        self._initialize_production_system(),
                    )
                return True # Report success to let API start

            self.logger.error("Production agents not available")
            return False

    def is_ready(self) -> bool:
        return self.is_initialized

    async def __aenter__(self) -> "ProductionAgentManager":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()
        return None


_production_agent_manager = None


def get_production_agent_manager() -> ProductionAgentManager:
    """Get the global production agent manager instance."""
    global _production_agent_manager
    if _production_agent_manager is None:
        _production_agent_manager = ProductionAgentManager()
    return _production_agent_manager
