"""Runtime imports and availability flags for production agent manager."""

import logging

logger = logging.getLogger(__name__)

try:
    from agents.base.enhanced_agent_factory import EnhancedAgentFactory  # noqa: E402
    from agents.extractors.entity_extractor import (  # noqa: E402
        create_legal_entity_extractor,
    )
    from agents.legal.irac_analyzer import create_irac_analyzer  # noqa: E402
    from agents.legal.legal_reasoning_engine import (  # noqa: E402
        create_legal_reasoning_engine,
    )
    from agents.processors.document_processor import (  # noqa: E402
        create_document_processor,
    )

    try:
        from agents.legal.precedent_analyzer import (  # type: ignore  # noqa: E402, F401
            LegalPrecedentAnalyzer,
            create_legal_precedent_analyzer,
        )

        PRECEDENT_ANALYZER_AVAILABLE = True
    except Exception:
        LegalPrecedentAnalyzer = None  # type: ignore
        create_legal_precedent_analyzer = None  # type: ignore
        PRECEDENT_ANALYZER_AVAILABLE = False

    from core.container.service_container_impl import ProductionServiceContainer  # noqa: E402
    from agents.legal.toulmin_analyzer import ToulminAnalyzer  # noqa: E402

    PRODUCTION_AGENTS_AVAILABLE = True
except Exception as e:
    logger.warning(f"Production agents not available: {e}")
    EnhancedAgentFactory = None  # type: ignore
    create_legal_entity_extractor = None  # type: ignore
    create_irac_analyzer = None  # type: ignore
    create_legal_reasoning_engine = None  # type: ignore
    create_document_processor = None  # type: ignore
    ProductionServiceContainer = None  # type: ignore
    ToulminAnalyzer = None  # type: ignore
    PRECEDENT_ANALYZER_AVAILABLE = False
    PRODUCTION_AGENTS_AVAILABLE = False
