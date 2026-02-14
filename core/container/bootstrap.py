import logging
import os
from typing import Any, Optional

from config.configuration_manager import create_configuration_manager, ConfigurationManager
from mem_db.database import get_database_manager, DatabaseManager
from mem_db.vector_store import get_vector_store
from mem_db.knowledge import get_knowledge_manager
from mem_db.memory.unified_memory_manager import (
    UnifiedMemoryManager,
    create_unified_memory_manager,
)
from services.memory_service import MemoryService

logger = logging.getLogger(__name__)


async def configure(services: Any, app: Any) -> None:
    """Centralize runtime service registration.

    Registers commonly-used services and aliases in the `ProductionServiceContainer` so
    routes/services only depend on the container as the single source of truth.
    """

    # Configuration manager
    try:
        cfg: ConfigurationManager = create_configuration_manager()
        await services.register_instance(
            ConfigurationManager,
            cfg,
            aliases=["config_manager", "configuration_manager", "config"],
        )
        logger.info("Registered ConfigurationManager")
    except Exception as e:
        logger.warning(f"ConfigurationManager registration failed: {e}")

    # Database manager
    try:
        db = get_database_manager()
        if db is not None:
            await services.register_instance(
                DatabaseManager,
                db,
                aliases=["database_manager", "db_manager", "db"],
            )
            logger.info("Registered DatabaseManager")
    except Exception as e:
        logger.warning(f"DatabaseManager registration failed: {e}")

    # Vector store (optional)
    try:
        vs = get_vector_store()
        if vs is not None:
            await services.register_instance(
                type(vs),
                vs,
                aliases=[
                    "vector_store",
                    "enhanced_vector_store",
                    "unified_vector_store",
                    "chroma_memory",
                    "faiss_vector_store",
                ],
            )
            logger.info("Registered VectorStore (if available)")
    except Exception as e:
        logger.warning(f"Vector store registration failed: {e}")

    # Knowledge manager (optional)
    try:
        kg = get_knowledge_manager()
        if kg is not None:
            await services.register_instance(
                type(kg),
                kg,
                aliases=["knowledge_manager", "unified_knowledge_manager", "knowledge_graph_manager"],
            )
            logger.info("Registered KnowledgeManager (if available)")
    except Exception as e:
        logger.warning(f"Knowledge manager registration failed: {e}")

    # Memory manager (required for memory features)
    try:
        memory_manager = await create_unified_memory_manager()
        await services.register_instance(
            UnifiedMemoryManager,
            memory_manager,
            aliases=["memory_manager", "unified_memory_manager", "memory"],
        )
        memory_service = MemoryService(memory_manager=memory_manager, config_manager=cfg if 'cfg' in locals() else None)
        await services.register_instance(
            MemoryService,
            memory_service,
            aliases=["memory_service", "memory_service_manager"],
        )
        logger.info("Registered UnifiedMemoryManager + MemoryService")
    except Exception as e:
        logger.warning(f"Memory manager registration failed (no fallback): {e}")

    # LLM manager (optional, configured via env vars)
    try:
        from core.llm_providers import LLMManager  # noqa: E402

        llm_manager = LLMManager(
            api_key=os.getenv("XAI_API_KEY", "").strip() or None,
            provider=os.getenv("LLM_PROVIDER", "xai"),
            default_model=os.getenv("LLM_MODEL", "grok-4-fast-reasoning"),
            base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
        )
        await services.register_instance(
            LLMManager,
            llm_manager,
            aliases=["llm_manager", "llm", "language_model"],
        )
        logger.info("Registered LLMManager (if available)")
    except Exception as e:
        logger.warning(f"LLMManager registration skipped: {e}")

    logger.debug("Service container bootstrap finished")
