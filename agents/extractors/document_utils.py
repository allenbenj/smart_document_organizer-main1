"""Document extraction helper interfaces.

This module intentionally does not provide runtime fallback classifiers.
"""
from typing import Optional, Dict, Any


class LegalDocumentClassifier:
    """Classifier interface placeholder requiring concrete implementation."""

    def classify(self, text: str, filename: Optional[str] = None) -> Dict[str, Any]:
        raise RuntimeError(
            "LegalDocumentClassifier has no runtime fallback implementation. "
            "Register a concrete classifier service."
        )


def extract_document_text(content: bytes) -> str:
    """Decode document bytes as UTF-8."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Document bytes are not valid UTF-8") from exc
