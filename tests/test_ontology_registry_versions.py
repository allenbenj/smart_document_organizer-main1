from __future__ import annotations

from services.ontology_registry_service import OntologyRegistryService, OntologyType


def test_all_six_ontology_types_registered_with_default_versions() -> None:
    svc = OntologyRegistryService()
    items = svc.list_registry()
    assert len(items) == 6
    seen = {item["ontology_type"] for item in items}
    assert seen == {otype.value for otype in OntologyType}
    assert all(item["active_version"] == 1 for item in items)


def test_create_new_version_increments_monotonically() -> None:
    svc = OntologyRegistryService()
    created = svc.create_version(ontology_type="domain", description="v2")
    assert created["version"] == 2
    assert created["status"] == "inactive"
