from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

_RESERVED_CATEGORY_KEYS = {
    "framework": "framework",
    "system_issue": "system_issue",
    "entity": "entity",
}


def _lookup_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _tokenize(value: str) -> list[str]:
    parts = re.split(r"[^A-Za-z0-9]+", value or "")
    return [p for p in parts if p]


@lru_cache(maxsize=1)
def _ontology_label_map() -> dict[str, str]:
    """Build permissive lookup keys that resolve to canonical ontology labels."""
    out: dict[str, str] = {}
    try:
        from agents.extractors.ontology import LegalEntityType

        for item in LegalEntityType:
            label = str(item.value.label or "").strip()
            enum_name = str(item.name or "").strip()
            if not label:
                continue

            for candidate in (
                label,
                enum_name,
                "_".join(_tokenize(label)),
                "_".join(_tokenize(enum_name)),
                "".join(_tokenize(label)),
                "".join(_tokenize(enum_name)),
            ):
                key = _lookup_key(candidate)
                if key:
                    out[key] = label
    except Exception:
        # Graceful fallback when ontology definitions are unavailable.
        return {}
    return out


def normalize_ontology_entity_id(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    mapped = _ontology_label_map().get(_lookup_key(raw))
    return mapped or raw


def normalize_category(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None

    low = raw.lower()
    if low in _RESERVED_CATEGORY_KEYS:
        return _RESERVED_CATEGORY_KEYS[low]

    mapped = normalize_ontology_entity_id(raw)
    return mapped or raw

