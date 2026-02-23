"""Compatibility shim for production imports.

Maps legacy `agents.extractors.entity_extractor` imports to the current
`legal_entity_extractor` implementation.

This module is intentionally resilient: if the heavy extractor has an import
or syntax issue, other production agents (e.g., document processor) should
still initialize and serve requests.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from .legal_entity_extractor import (  # noqa: F401
        EntityExtractionConfig,
        ExtractedEntity,
        LegalEntityExtractor,
        create_legal_entity_extractor,
    )
except Exception as exc:  # pragma: no cover - defensive runtime guard
    err_msg = str(exc)
    logger.warning("Entity extractor unavailable: %s", err_msg)
    EntityExtractionConfig = Any  # type: ignore[assignment]
    ExtractedEntity = Any  # type: ignore[assignment]
    LegalEntityExtractor = None  # type: ignore[assignment]

    async def create_legal_entity_extractor(*args: Any, **kwargs: Any):
        raise RuntimeError(f"entity_extractor_unavailable: {err_msg}")
