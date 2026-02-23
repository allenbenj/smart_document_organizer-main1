from __future__ import annotations

import os
from typing import Any


class JurisdictionService:
    """Centralized jurisdiction resolution for write paths."""

    def __init__(self, default_jurisdiction: str | None = None) -> None:
        self.default_jurisdiction = (
            default_jurisdiction
            or os.getenv("AEDIS_DEFAULT_JURISDICTION")
            or os.getenv("DEFAULT_JURISDICTION")
            or ""
        ).strip()

    def resolve(
        self,
        jurisdiction: str | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        direct = str(jurisdiction or "").strip()
        if direct:
            return direct

        md = metadata if isinstance(metadata, dict) else {}
        candidate = str(md.get("jurisdiction") or "").strip()
        if candidate:
            return candidate

        return self.default_jurisdiction or None


jurisdiction_service = JurisdictionService()
