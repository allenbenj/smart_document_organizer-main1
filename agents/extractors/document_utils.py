"""Document extraction helper interfaces and default classifier."""
import logging
import re
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Keyword-based classification rules: (document_type, keywords, filename_patterns)
_CLASSIFICATION_RULES: List[tuple] = [
    ("contract", ["agreement", "contract", "hereby", "parties", "obligations", "clause", "terms and conditions", "executed"], [r"contract", r"agreement"]),
    ("legal_brief", ["plaintiff", "defendant", "court", "motion", "brief", "jurisdiction", "petition", "respondent"], [r"brief", r"motion"]),
    ("case_law", ["opinion", "court of appeals", "supreme court", "affirmed", "reversed", "dissent", "holding", "precedent"], [r"case", r"opinion"]),
    ("statute", ["section", "subsection", "enacted", "legislature", "effective date", "chapter", "title", "code"], [r"statute", r"code"]),
    ("memo", ["memorandum", "memo", "to:", "from:", "subject:", "re:"], [r"memo"]),
    ("pleading", ["complaint", "answer", "counterclaim", "cross-claim", "demurrer"], [r"complaint", r"pleading"]),
    ("correspondence", ["dear", "sincerely", "regards", "cc:", "enclosed"], [r"letter", r"correspondence"]),
    ("report", ["report", "findings", "analysis", "summary", "conclusion", "recommendation"], [r"report"]),
]


class LegalDocumentClassifier:
    """Rule-based legal document classifier with keyword heuristics.

    Provides a fallback classification that never raises. Returns the best
    matching document type with a confidence score. When no rules match,
    returns type='unknown' with confidence 0.1.
    """

    def classify(self, text: str, filename: Optional[str] = None) -> Dict[str, Any]:
        """Classify a document using keyword and filename heuristics.

        Args:
            text: Document text content.
            filename: Optional filename for additional signal.

        Returns:
            Dict with keys: type, confidence, matched_keywords, method.
        """
        if not text and not filename:
            return {
                "type": "unknown",
                "confidence": 0.0,
                "matched_keywords": [],
                "method": "rule_based",
            }

        text_lower = (text or "").lower()
        filename_lower = (filename or "").lower()

        best_type = "unknown"
        best_score = 0.0
        best_keywords: List[str] = []

        for doc_type, keywords, fname_patterns in _CLASSIFICATION_RULES:
            matched = [kw for kw in keywords if kw in text_lower]
            text_score = len(matched) / len(keywords) if keywords else 0.0

            fname_score = 0.0
            if filename_lower:
                for pat in fname_patterns:
                    if re.search(pat, filename_lower):
                        fname_score = 0.2
                        break

            combined = min(text_score + fname_score, 1.0)

            if combined > best_score:
                best_score = combined
                best_type = doc_type
                best_keywords = matched

        # Scale to a reasonable confidence range (0.1 – 0.85 for heuristics)
        confidence = round(max(0.1, min(best_score * 0.85, 0.85)), 2)
        if best_type == "unknown":
            confidence = 0.1

        return {
            "type": best_type,
            "confidence": confidence,
            "matched_keywords": best_keywords,
            "method": "rule_based",
        }


def extract_document_text(content: bytes) -> str:
    """Decode document bytes as UTF-8."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Document bytes are not valid UTF-8") from exc
