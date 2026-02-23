from __future__ import annotations

from pathlib import Path


def test_dashboard_wires_phase_tabs() -> None:
    src = Path("gui/gui_dashboard.py").read_text(encoding="utf-8")

    assert "CanonicalArtifactsTab" in src
    assert "OntologyRegistryTab" in src
    assert '("Ontology Registry", lambda: OntologyRegistryTab())' in src
    assert '("Canonical Artifacts", lambda: CanonicalArtifactsTab())' in src


def test_api_client_exposes_aedis_gui_endpoints() -> None:
    src = Path("gui/services/__init__.py").read_text(encoding="utf-8")

    assert "def list_ontology_registry(" in src
    assert "def create_ontology_registry_version(" in src
    assert "def activate_ontology_registry_version(" in src
    assert "def deprecate_ontology_registry_version(" in src
    assert "def ingest_canonical_artifact(" in src
    assert "def append_canonical_lineage_event(" in src
    assert "def get_canonical_lineage(" in src
