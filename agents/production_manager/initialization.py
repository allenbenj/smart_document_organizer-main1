"""Initialization behavior for ProductionAgentManager."""

import inspect
from typing import Any

from agents.core.models import AgentType
from core.container import bootstrap
from core.llm_providers import LLMManager

from .runtime import (
    EnhancedAgentFactory,
    PRECEDENT_ANALYZER_AVAILABLE,
    ProductionServiceContainer,
    ToulminAnalyzer,
    create_document_processor,
    create_irac_analyzer,
    create_legal_entity_extractor,
    create_legal_precedent_analyzer,
    create_legal_reasoning_engine,
)


class InitializationMixin:
    async def _initialize_production_system(self):
        """Initialize the production agent system."""
        try:
            self.service_container = ProductionServiceContainer()
            # Register baseline runtime services and legacy aliases.
            try:
                await bootstrap.configure(self.service_container, app=None)
            except Exception as e:
                self.logger.warning(f"Service bootstrap skipped: {e}")

            self.agent_factory = EnhancedAgentFactory(
                service_container=self.service_container
            )

            await self._create_core_agents()

            self.is_initialized = True
            self.logger.info("Production agent system initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize production system: {e}")
            self.is_initialized = False

    async def _create_core_agents(self):  # noqa: C901
        """Create the core agents needed for runtime."""
        try:
            self.agents[AgentType.DOCUMENT_PROCESSOR] = await create_document_processor(
                self.service_container
            )
        except Exception as e:
            self.logger.warning(f"Document processor unavailable: {e}")

        if self._flags.get("AGENTS_ENABLE_ENTITY_EXTRACTOR", True):
            try:
                self.agents[AgentType.ENTITY_EXTRACTOR] = (
                    await create_legal_entity_extractor(self.service_container)
                )
            except Exception as e:
                self.logger.warning(f"Entity extractor unavailable: {e}")

        if self._flags.get("AGENTS_ENABLE_LEGAL_REASONING", True):
            try:
                self.agents[AgentType.LEGAL_REASONING] = create_legal_reasoning_engine(
                    self.service_container
                )
            except Exception as e:
                self.logger.warning(f"Legal reasoning engine unavailable: {e}")

        if self._flags.get("AGENTS_ENABLE_IRAC", True):
            try:
                self.agents[AgentType.IRAC_ANALYZER] = await create_irac_analyzer(
                    self.service_container
                )
            except Exception as e:
                self.logger.warning(f"IRAC analyzer unavailable: {e}")

        if self._flags.get("AGENTS_ENABLE_TOULMIN", True):
            try:
                llm_manager: Any = None
                if self.service_container and hasattr(self.service_container, "get_service"):
                    try:
                        maybe = self.service_container.get_service(LLMManager)
                        llm_manager = await maybe if inspect.isawaitable(maybe) else maybe
                    except Exception:
                        maybe = self.service_container.get_service("llm_manager")
                        llm_manager = await maybe if inspect.isawaitable(maybe) else maybe
                self.agents[AgentType.TOULMIN_ANALYZER] = ToulminAnalyzer(
                    llm_manager=llm_manager,
                    config=None,
                )
            except Exception as e:
                self.logger.warning(f"Toulmin analyzer unavailable: {e}")

        if PRECEDENT_ANALYZER_AVAILABLE:
            try:
                self._precedent_analyzer = await create_legal_precedent_analyzer(self.service_container)  # type: ignore[arg-type]
            except Exception as e:
                self.logger.warning(f"Precedent analyzer unavailable: {e}")

        if not self.agents:
            raise RuntimeError("No production agents could be initialized.")

        self.logger.info(f"Created {len(self.agents)} production agents")
