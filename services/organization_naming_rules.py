"""Configurable naming rules for organization folder and filename normalization."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


DEFAULT_RULES: Dict[str, Any] = {
    "folder": {
        "replace_underscore_with_dash": True,
        "number_all_segments": True,
        "number_start_at": 1,
        "number_width": 2,
        "number_separator": "-",
    },
    "filename": {
        "replace_underscore_with_dash": True,
    },
}


class OrganizationNamingRules:
    """Loads and applies organization naming rules from config."""

    def __init__(self, rules_path: Optional[str] = None):
        default_path = Path(__file__).resolve().parents[1] / "config" / "organization_rules.json"
        self.rules_path = rules_path or os.getenv("ORGANIZATION_RULES_PATH") or str(default_path)
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, Any]:
        p = Path(self.rules_path)
        if p.exists() and p.is_file():
            try:
                parsed = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return DEFAULT_RULES

    @staticmethod
    def _normalize_existing_segment_number(segment: str, width: int, sep: str) -> Optional[str]:
        m = re.match(r"^\s*(\d{1,3})\s*[-_ ]\s*(.+?)\s*$", segment or "")
        if not m:
            return None
        num = int(m.group(1))
        text = m.group(2).strip()
        return f"{num:0{width}d}{sep}{text}" if text else None

    def _apply_folder_rules(self, folder: str) -> str:
        folder_rules = self.rules.get("folder") if isinstance(self.rules, dict) else {}
        if not isinstance(folder_rules, dict):
            folder_rules = {}

        out = str(folder or "")
        if bool(folder_rules.get("replace_underscore_with_dash", True)):
            out = out.replace("_", "-")

        parts = [p.strip() for p in out.split("/") if p and p.strip()]
        if not parts:
            return out

        if bool(folder_rules.get("number_all_segments", False)):
            start_at = int(folder_rules.get("number_start_at", 1))
            width = max(1, int(folder_rules.get("number_width", 2)))
            sep = str(folder_rules.get("number_separator", "-") or "-")

            normalized_parts = []
            for idx, part in enumerate(parts):
                existing = self._normalize_existing_segment_number(part, width=width, sep=sep)
                if existing:
                    normalized_parts.append(existing)
                    continue
                n = start_at + idx
                normalized_parts.append(f"{n:0{width}d}{sep}{part}")
            parts = normalized_parts

        return "/".join(parts)

    def _apply_filename_rules(self, filename: str) -> str:
        filename_rules = self.rules.get("filename") if isinstance(self.rules, dict) else {}
        if not isinstance(filename_rules, dict):
            filename_rules = {}

        out = str(filename or "")
        if bool(filename_rules.get("replace_underscore_with_dash", True)):
            stem, ext = os.path.splitext(out)
            out = f"{stem.replace('_', '-')}{ext}"
        return out

    def apply(self, folder: str, filename: str) -> Tuple[str, str]:
        """Apply configured folder + filename normalization rules."""
        return self._apply_folder_rules(folder), self._apply_filename_rules(filename)

