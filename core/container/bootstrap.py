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

    cfg: ConfigurationManager = create_configuration_manager()
    await services.register_instance(
        ConfigurationManager,
        cfg,
        aliases=["config_manager", "configuration_manager", "config"],
    )
    logger.info("Registered ConfigurationManager")

    db = get_database_manager()
    if db is None:
        raise RuntimeError("DatabaseManager unavailable")
    await services.register_instance(
        DatabaseManager,
        db,
        aliases=["database_manager", "db_manager", "db"],
    )
    logger.info("Registered DatabaseManager")

    vs = get_vector_store()
    if vs is None:
        raise RuntimeError("Vector store unavailable")
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
    logger.info("Registered VectorStore")

    kg = get_knowledge_manager()
    if kg is None:
        raise RuntimeError("KnowledgeManager unavailable")
    await services.register_instance(
        type(kg),
        kg,
        aliases=["knowledge_manager", "unified_knowledge_manager", "knowledge_graph_manager"],
    )
    logger.info("Registered KnowledgeManager")

    memory_manager = await create_unified_memory_manager()
    await services.register_instance(
        UnifiedMemoryManager,
        memory_manager,
        aliases=["memory_manager", "unified_memory_manager", "memory"],
    )
    memory_service = MemoryService(memory_manager=memory_manager, config_manager=cfg)
    await services.register_instance(
        MemoryService,
        memory_service,
        aliases=["memory_service", "memory_service_manager"],
    )
    logger.info("Registered UnifiedMemoryManager + MemoryService")

    from agents.base.core_integration import (
        EnhancedPersistenceManager,
        create_enhanced_persistence_manager,
    )

    epm = create_enhanced_persistence_manager()
    await epm.initialize()
    await services.register_instance(
        EnhancedPersistenceManager,
        epm,
        aliases=["enhanced_persistence_manager", "persistence_manager"],
    )
    logger.info("Registered EnhancedPersistenceManager")

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
    logger.info("Registered LLMManager")

    logger.debug("Service container bootstrap finished")
