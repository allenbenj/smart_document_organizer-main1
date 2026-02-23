from __future__ import annotations

import pytest

from services.ontology_registry_service import OntologyRegistryService


def test_activation_switches_active_version() -> None:
    svc = OntologyRegistryService()
    svc.create_version(ontology_type="heuristic", description="new policy")
    activated = svc.activate_version(ontology_type="heuristic", version=2)

    assert activated["status"] == "active"
    entry = svc.get_registry_entry("heuristic")
    assert entry["active_version"] == 2


def test_cannot_deprecate_active_version() -> None:
    svc = OntologyRegistryService()
    with pytest.raises(ValueError):
        svc.deprecate_version(ontology_type="tool", version=1)
