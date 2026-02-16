"""NLP based document classifier with optional ML model."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .document_utils import LegalDocumentClassifier


class NLPDocumentClassifier:
    """Classify documents using a transformer model if available."""

    def __init__(
        self,
        labels: Optional[List[str]] = None,
        model_name: str = "typeform/distilbert-base-uncased-mnli",
    ) -> None:
        self.labels = labels or ["contract", "court_filing", "statute"]
        self._pipeline = None
        try:
            from transformers import pipeline  # type: ignore

            self._pipeline = pipeline(
                "zero-shot-classification", model=model_name
            )
        except Exception:
            # Any import or model loading error falls back to keyword approach
            self._pipeline = None
        self._fallback = LegalDocumentClassifier()

    def classify(self, text: str, filename: Optional[str] = None) -> Dict[str, Any]:
        """Return document classification details."""
        if self._pipeline is not None:
            try:
                result = self._pipeline(text, self.labels)
                best_label = result["labels"][0]
                best_score = float(result["scores"][0])
                return {
                    "is_legal_document": best_score > 0.5,
                    "primary_type": best_label,
                    "primary_score": best_score,
                    "filename": filename,
                    "used_ml_model": True,
                }
            except Exception:
                # Fall back if inference fails
                pass
        fallback = self._fallback.classify(text, filename)
        fallback["used_ml_model"] = False
        return fallback


__all__ = ["NLPDocumentClassifier"]
