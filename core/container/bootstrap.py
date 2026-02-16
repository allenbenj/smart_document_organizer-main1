import logging
import os
from typing import Any

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
        logger.debug(f"Optional ConfigurationManager unavailable: {e}")

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
        logger.debug(f"Optional DatabaseManager unavailable: {e}")

    # Vector store (optional, dummy if missing)
    try:
        vs = get_vector_store()
        dummy = False
        if vs is None:
            dummy = True
            class DummyVectorStore:
                def __init__(self):
                    self.doc_count = 0

                async def initialize(self) -> None:
                    pass

                async def add_document(self, *args, **kwargs) -> str:
                    self.doc_count += 1
                    return f"dummy_doc_{self.doc_count}"

                async def search(self, *args, **kwargs) -> list:
                    return []

                async def search_similar(self, *args, **kwargs) -> list:
                    return []

                async def health_check(self) -> dict:
                    return {"healthy": True, "mode": "dummy"}

                async def close(self) -> None:
                    pass

                async def get_statistics(self) -> dict:
                    return {"total_documents": self.doc_count}

                def get_system_status(self) -> dict:
                    return {"status": "dummy", "available": False}

            vs = DummyVectorStore()
        vs_type = type(vs)
        await services.register_instance(
            vs_type,
            vs,
            aliases=[
                "vector_store",
                "enhanced_vector_store",
                "unified_vector_store",
                "chroma_memory",
                "faiss_vector_store",
            ],
        )
        mode = "dummy" if dummy else "real"
        logger.info(f"Registered VectorStore ({mode})")
    except Exception as e:
        logger.debug(f"Vector store registration failed (optional): {e}")

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
        logger.debug(f"Optional KnowledgeManager unavailable: {e}")

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

        # Enhanced Persistence Manager (optional)
        try:
            from agents.base.core_integration import EnhancedPersistenceManager, create_enhanced_persistence_manager
            epm = create_enhanced_persistence_manager()
            await epm.initialize()
            await services.register_instance(
                EnhancedPersistenceManager,
                epm,
                aliases=["enhanced_persistence_manager", "persistence_manager"],
            )
            logger.info("Registered EnhancedPersistenceManager")
        except Exception as e:
            logger.debug(f"EnhancedPersistenceManager unavailable (optional): {e}")
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
        logger.debug(f"Optional LLMManager skipped: {e}")

    logger.debug("Service container bootstrap finished")
