"""Rule-based file tagging with configurable keyword/regex rules and provenance spans."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_RULES: List[Dict[str, Any]] = [
    {
        "id": "seed-delta9",
        "tag": "domain:delta9",
        "type": "keyword",
        "pattern": "delta-9",
        "case_sensitive": False,
        "sources": ["name", "path", "content"],
    },
    {
        "id": "seed-hhc",
        "tag": "domain:hhc",
        "type": "keyword",
        "pattern": "hhc",
        "case_sensitive": False,
        "sources": ["name", "path", "content"],
    },
    {
        "id": "seed-cbd",
        "tag": "domain:cbd",
        "type": "keyword",
        "pattern": "cbd",
        "case_sensitive": False,
        "sources": ["name", "path", "content"],
    },
    {
        "id": "seed-thc",
        "tag": "domain:thc",
        "type": "keyword",
        "pattern": "thc",
        "case_sensitive": False,
        "sources": ["name", "path", "content"],
    },
    {
        "id": "seed-lab-report",
        "tag": "document:lab-report",
        "type": "regex",
        "pattern": r"\blab\s+report\b",
        "flags": ["IGNORECASE"],
        "sources": ["name", "path", "content"],
    },
    {
        "id": "seed-case-number",
        "tag": "legal:case-number",
        "type": "regex",
        "pattern": r"\b(?:case\s*(?:no\.?|number)?\s*[:#-]?\s*)?[A-Z]{1,5}-?\d{2,6}(?:-\d{1,6})?\b",
        "flags": ["IGNORECASE"],
        "sources": ["name", "path", "content"],
    },
    {
        "id": "seed-date",
        "tag": "entity:date",
        "type": "regex",
        "pattern": r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b",
        "sources": ["name", "path", "content"],
    },
    {
        "id": "seed-person-name",
        "tag": "entity:possible-name",
        "type": "regex",
        "pattern": r"\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b",
        "sources": ["name", "content"],
    },
]

_FLAG_MAP = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
}


class RuleTagger:
    """Applies tagging rules to scanner text sources and returns span provenance."""

    def __init__(self, *, rules: Optional[List[Dict[str, Any]]] = None, rules_path: Optional[str] = None):
        default_path = Path(__file__).resolve().parents[1] / "config" / "file_tagging_rules.json"
        self.rules_path = rules_path or os.getenv("FILE_TAG_RULES_PATH") or str(default_path)
        self.rules = self._load_rules(rules=rules)

    def _load_rules(self, *, rules: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        if rules is not None:
            return rules

        if self.rules_path:
            p = Path(self.rules_path)
            if p.exists() and p.is_file():
                try:
                    parsed = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(parsed, list):
                        return parsed
                    if isinstance(parsed, dict) and isinstance(parsed.get("rules"), list):
                        return parsed["rules"]
                except Exception:
                    pass
        return DEFAULT_RULES

    @staticmethod
    def _snippet(text: str, start: int, end: int, window: int = 32) -> str:
        a = max(0, start - window)
        b = min(len(text), end + window)
        return text[a:b]

    @staticmethod
    def _compile_flags(rule: Dict[str, Any]) -> int:
        flags = 0
        for raw in (rule.get("flags") or []):
            flags |= _FLAG_MAP.get(str(raw).upper(), 0)
        if not bool(rule.get("case_sensitive", False)):
            flags |= re.IGNORECASE
        return flags

    def _iter_matches(self, rule: Dict[str, Any], text: str) -> Iterable[re.Match[str]]:
        pattern = str(rule.get("pattern") or "")
        if not pattern:
            return []

        typ = str(rule.get("type") or "keyword").lower()
        flags = self._compile_flags(rule)

        if typ == "keyword":
            expr = re.escape(pattern)
            return re.finditer(expr, text, flags=flags)
        return re.finditer(pattern, text, flags=flags)

    def apply(self, *, sources: Dict[str, str], max_hits: int = 200) -> Dict[str, Any]:
        hits: List[Dict[str, Any]] = []
        for rule in self.rules:
            rule_id = str(rule.get("id") or "rule")
            tag = str(rule.get("tag") or rule_id)
            allowed_sources = {str(s) for s in (rule.get("sources") or ["name", "path", "content"])}
            for source_name, source_text in sources.items():
                if source_name not in allowed_sources:
                    continue
                if not source_text:
                    continue
                try:
                    for m in self._iter_matches(rule, source_text):
                        if len(hits) >= max_hits:
                            break
                        hits.append(
                            {
                                "rule_id": rule_id,
                                "tag": tag,
                                "rule_type": str(rule.get("type") or "keyword"),
                                "source": source_name,
                                "start": int(m.start()),
                                "end": int(m.end()),
                                "match_text": source_text[m.start() : m.end()],
                                "snippet": self._snippet(source_text, m.start(), m.end()),
                            }
                        )
                except Exception:
                    continue

        unique_tags = sorted({h["tag"] for h in hits})
        return {
            "rule_tags": unique_tags,
            "rule_tag_hits": hits,
            "rule_tag_summary": {
                "count": len(hits),
                "tags": unique_tags,
                "rules_path": self.rules_path,
                "rules_count": len(self.rules),
            },
        }
