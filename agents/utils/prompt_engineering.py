"""
Lightweight prompt engineering helpers.

This module centralizes prompt assembly for legal analysis tasks to avoid
scattered string-building logic and to enable caching of prompt components.
"""

from __future__ import annotations

from functools import lru_cache  # noqa: E402
from typing import Any, Dict, Tuple  # noqa: E402


def _truncate(text: str, max_chars: int) -> Tuple[str, int]:
    if len(text) <= max_chars:
        return text, len(text)
    return text[: max_chars - 3] + "...", len(text)


@lru_cache(maxsize=256)
def build_legal_reasoning_prompt(
    text_hash: str, analysis_type: str = "comprehensive", max_chars: int = 4000
) -> Dict[str, Any]:
    """Return a compact prompt template given a precomputed text hash.

    Note: Callers should hash the long text before invoking this function to
    keep the cache key small and avoid storing large payloads in memory.
    """
    # Minimal scaffold; real systems would add few-shot exemplars conditionally
    system = (
        "You are a precise legal analyst. Identify issues, map rules, and relate "
        "them to facts clearly. Be concise and cite evidence spans."
    )
    user = f"Perform a {analysis_type} analysis on the provided document."
    return {
        "system": system,
        "user": user,
        "meta": {
            "analysis_type": analysis_type,
            "text_hash": text_hash,
            "max_chars": max_chars,
        },
    }
