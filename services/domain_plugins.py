"""Domain plugin templates for scanner enrichment.

MVP intent: provide a stable template contract for domain-specific parsers
(e.g., lab reports) without coupling scanner core to one domain.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional, Protocol


class DomainPlugin(Protocol):
    name: str
    domain: str

    def supports(self, *, ext: str, mime_type: Optional[str] = None) -> bool:
        ...

    def extract(self, path: Path, *, text: str) -> Dict[str, Any]:
        ...


class DomainPluginTemplate:
    name = "template"
    domain = "generic"

    def supports(self, *, ext: str, mime_type: Optional[str] = None) -> bool:
        return ext in {".txt", ".md", ".pdf"}

    def extract(self, path: Path, *, text: str) -> Dict[str, Any]:
        return {
            "plugin": self.name,
            "domain": self.domain,
            "signals": [],
            "entities": [],
            "notes": f"Template extraction for {path.name}",
        }


class LabReportPluginTemplate(DomainPluginTemplate):
    name = "lab-report-template"
    domain = "lab_report"

    _pattern_map = {
        "compound_thc": r"\bTHC\b",
        "compound_cbd": r"\bCBD\b",
        "compound_hhc": r"\bHHC\b",
        "label_lab_report": r"\blab\s+report\b",
    }

    def extract(self, path: Path, *, text: str) -> Dict[str, Any]:
        signals = []
        for tag, pattern in self._pattern_map.items():
            if re.search(pattern, text or "", flags=re.IGNORECASE):
                signals.append({"tag": tag, "confidence": 0.7, "source": "regex"})
        return {
            "plugin": self.name,
            "domain": self.domain,
            "signals": signals,
            "entities": [],
            "notes": f"Detected {len(signals)} lab-report signals",
        }


class DomainPluginRegistry:
    def __init__(self):
        self._plugins: list[DomainPlugin] = []

    def register(self, plugin: DomainPlugin) -> None:
        self._plugins.append(plugin)

    def resolve(self, *, ext: str, mime_type: Optional[str] = None) -> Optional[DomainPlugin]:
        for plugin in self._plugins:
            if plugin.supports(ext=ext, mime_type=mime_type):
                return plugin
        return None


def build_default_domain_plugin_registry() -> DomainPluginRegistry:
    reg = DomainPluginRegistry()
    reg.register(LabReportPluginTemplate())
    return reg
