"""
Entity Extractors Module for Legal AI Platform
==============================================

Contains entity extraction agents and utilities for legal document analysis.

Key Features:
- Multi-model hybrid entity extraction (spaCy, Legal-BERT, GLiNER)
- Legal-specific pattern matching and ontology validation
- Collective intelligence integration for enhanced accuracy
- Production-grade error handling and performance optimization

All extractors integrate with the shared memory system to enable
collective intelligence across entity extraction tasks.
"""

# Primary entity extractor
try:
    from .legal_entity_extractor import (  # noqa: E402
        LegalEntityExtractor,
        EntityExtractionConfig,
        create_legal_entity_extractor,
    )
except ImportError:
    LegalEntityExtractor = None
    EntityExtractionConfig = None
    create_legal_entity_extractor = None

__all__ = [
    "LegalEntityExtractor",
    "EntityExtractionConfig",
    "create_legal_entity_extractor",
]
