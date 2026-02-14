"""Simple helpers for document classification/extraction used by extractors/tests

This module provides minimal, safe fallbacks used by the extractors to avoid
import-time failures in test environments where ML libraries are not available.
"""
from typing import Optional, Dict, Any


class LegalDocumentClassifier:
    """Minimal document classifier fallback used when no ML model is available."""

    def classify(self, text: str, filename: Optional[str] = None) -> Dict[str, Any]:
        # Very small heuristic: if 'contract' in text, guess contract, else unknown.
        t = (text or "").lower()
        if "contract" in t:
            return {
                "is_legal_document": True,
                "primary_type": "contract",
                "primary_score": 0.8,
                "filename": filename,
            }
        return {
            "is_legal_document": False,
            "primary_type": "unknown",
            "primary_score": 0.0,
            "filename": filename,
        }


def extract_document_text(content: bytes) -> str:
    # Attempt rudimentary decode; tests only need a consistent output
    try:
        return content.decode("utf-8")
    except Exception:
        return ""
