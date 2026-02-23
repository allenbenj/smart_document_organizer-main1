from __future__ import annotations

import pytest

from services.contracts.aedis_models import OntologyRecord
from services.ontology_registry_service import OntologyRegistryService


@pytest.fixture()
def tmp_registry_service() -> OntologyRegistryService:
    # Fresh in-memory registry per test to preserve baseline isolation.
    return OntologyRegistryService()


def test_ontology_isolation_and_contracts(
    tmp_registry_service: OntologyRegistryService,
) -> None:
    svc = tmp_registry_service

    svc.create_version(ontology_type="objective", description="objective-v2")
    svc.create_version(ontology_type="heuristic", description="heuristic-v2")

    activated_objective = svc.activate_version(ontology_type="objective", version=2)
    objective_record = OntologyRecord.model_validate(
        {
            "ontology_type": "objective",
            **activated_objective,
        }
    )

    assert objective_record.status == "active"
    assert objective_record.version == 2

    objective_active = svc.get_active_version(ontology_type="objective")
    heuristic_active = svc.get_active_version(ontology_type="heuristic")

    assert objective_active is not None
    assert objective_active["version"] == 2
    # Independence proof: activating objective does not alter heuristic active version.
    assert heuristic_active is not None
    assert heuristic_active["version"] == 1
    assert heuristic_active["status"] == "active"


def test_invalid_activation_is_rejected(tmp_registry_service: OntologyRegistryService) -> None:
    with pytest.raises(KeyError):
        tmp_registry_service.activate_version(ontology_type="domain", version=999)
