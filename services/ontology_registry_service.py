from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any


class OntologyType(str, Enum):
    DOMAIN = "domain"
    COGNITIVE = "cognitive"
    TOOL = "tool"
    OBJECTIVE = "objective"
    HEURISTIC = "heuristic"
    GENERATIVE = "generative"


class OntologyRegistryService:
    """In-memory ontology registry with versioning and activation/deprecation controls."""

    def __init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._store: dict[str, dict[str, Any]] = {
            otype.value: {
                "ontology_type": otype.value,
                "active_version": 1,
                "versions": {
                    "1": {
                        "version": 1,
                        "status": "active",
                        "description": f"default {otype.value} ontology",
                        "created_at": now,
                    }
                },
            }
            for otype in OntologyType
        }

    def list_registry(self) -> list[dict[str, Any]]:
        return [self.get_registry_entry(otype.value) for otype in OntologyType]

    def get_registry_entry(self, ontology_type: str) -> dict[str, Any]:
        key = ontology_type.strip().lower()
        if key not in self._store:
            raise KeyError(f"Unknown ontology type: {ontology_type}")
        entry = self._store[key]
        return {
            "ontology_type": entry["ontology_type"],
            "active_version": entry["active_version"],
            "versions": [
                entry["versions"][v]
                for v in sorted(entry["versions"].keys(), key=lambda x: int(x))
            ],
        }

    def create_version(
        self,
        *,
        ontology_type: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        key = ontology_type.strip().lower()
        if key not in self._store:
            raise KeyError(f"Unknown ontology type: {ontology_type}")
        entry = self._store[key]
        next_version = max(int(v) for v in entry["versions"].keys()) + 1
        record = {
            "version": next_version,
            "status": "inactive",
            "description": description or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        entry["versions"][str(next_version)] = record
        return record

    def activate_version(self, *, ontology_type: str, version: int) -> dict[str, Any]:
        key = ontology_type.strip().lower()
        if key not in self._store:
            raise KeyError(f"Unknown ontology type: {ontology_type}")
        if version < 1:
            raise ValueError("version must be >= 1")
        entry = self._store[key]
        if str(version) not in entry["versions"]:
            raise KeyError(f"Unknown version {version} for ontology type {ontology_type}")

        for rec in entry["versions"].values():
            if rec["status"] == "active":
                rec["status"] = "inactive"
        entry["versions"][str(version)]["status"] = "active"
        entry["active_version"] = version
        return entry["versions"][str(version)]

    def deprecate_version(self, *, ontology_type: str, version: int) -> dict[str, Any]:
        key = ontology_type.strip().lower()
        if key not in self._store:
            raise KeyError(f"Unknown ontology type: {ontology_type}")
        entry = self._store[key]
        if str(version) not in entry["versions"]:
            raise KeyError(f"Unknown version {version} for ontology type {ontology_type}")
        if entry["active_version"] == version:
            raise ValueError("cannot deprecate currently active version")
        entry["versions"][str(version)]["status"] = "deprecated"
        return entry["versions"][str(version)]

    def get_active_version(self, *, ontology_type: str) -> dict[str, Any] | None:
        key = ontology_type.strip().lower()
        if key not in self._store:
            raise KeyError(f"Unknown ontology type: {ontology_type}")
        entry = self._store[key]
        active_version = int(entry["active_version"])
        rec = entry["versions"].get(str(active_version))
        if not isinstance(rec, dict):
            return None
        if rec.get("status") != "active":
            return None
        return rec
