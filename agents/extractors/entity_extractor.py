"""Compatibility shim for production imports.

Maps legacy `agents.extractors.entity_extractor` imports to the current
`legal_entity_extractor` implementation.
"""

from .legal_entity_extractor import (  # noqa: F401
    EntityExtractionConfig,
    ExtractedEntity,
    LegalEntityExtractor,
    create_legal_entity_extractor,
)

