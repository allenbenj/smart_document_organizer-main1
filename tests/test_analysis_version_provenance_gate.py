from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.analysis_version_service import AnalysisVersionService
from services.contracts.aedis_models import AnalysisVersion, EvidenceSpan, ProvenanceRecord
from services.provenance_service import ProvenanceGateError


class _FakeDB:
    def __init__(self) -> None:
        self.add_calls = 0
        self.last_payload = None

    def add_analysis_version(self, analysis_version_data):
        self.add_calls += 1
        self.last_payload = analysis_version_data
        return 1

    def get_analysis_version(self, analysis_id: str):
        return {
            "analysis_id": analysis_id,
            "artifact_row_id": 42,
            "version": 1,
            "parent_version": None,
            "status": "draft",
            "payload": {"result": "ok", "provenance_id": 909},
            "audit_deltas": [],
            "created_at": datetime.now(timezone.utc),
            "provenance": {
                "source_artifact_row_id": 42,
                "source_sha256": "a" * 64,
                "captured_at": datetime.now(timezone.utc),
                "extractor": "pytest-analysis",
                "spans": [
                    {
                        "artifact_row_id": 42,
                        "start_char": 0,
                        "end_char": 10,
                        "quote": "test quote",
                    }
                ],
                "notes": "test",
            },
        }


class _FakeProvenanceService:
    def __init__(self) -> None:
        self.validate_calls = 0
        self.record_calls = 0

    def validate_write_gate(self, record, target_type: str, target_id: str) -> None:
        self.validate_calls += 1
        if not record.spans:
            raise ProvenanceGateError("Provenance Write-Gate Failure: at least one EvidenceSpan is required")

    def record_provenance(self, record, target_type: str, target_id: str) -> int:
        self.record_calls += 1
        return 909


def _analysis_version(spans: list[EvidenceSpan]) -> AnalysisVersion:
    return AnalysisVersion(
        analysis_id="analysis-1",
        artifact_row_id=42,
        version=1,
        parent_version=None,
        status="draft",
        payload={"result": "ok"},
        provenance=ProvenanceRecord(
            source_artifact_row_id=42,
            source_sha256="a" * 64,
            captured_at=datetime.now(timezone.utc),
            extractor="pytest-analysis",
            spans=spans,
            notes="test",
        ),
        audit_deltas=[],
        created_at=datetime.now(timezone.utc),
    )


def test_analysis_version_create_fails_without_evidence_spans() -> None:
    db = _FakeDB()
    prov = _FakeProvenanceService()
    svc = AnalysisVersionService(db_manager=db, provenance_service=prov)

    with pytest.raises(ProvenanceGateError):
        svc.create_analysis_version(_analysis_version(spans=[]))

    assert db.add_calls == 0
    assert prov.validate_calls == 1
    assert prov.record_calls == 0


def test_analysis_version_create_records_provenance_before_persist() -> None:
    db = _FakeDB()
    prov = _FakeProvenanceService()
    svc = AnalysisVersionService(db_manager=db, provenance_service=prov)

    out = svc.create_analysis_version(
        _analysis_version(
            spans=[
                EvidenceSpan(
                    artifact_row_id=42,
                    start_char=0,
                    end_char=12,
                    quote="sample quote",
                )
            ]
        )
    )

    assert out.analysis_id == "analysis-1"
    assert db.add_calls == 1
    assert prov.validate_calls == 1
    assert prov.record_calls == 1
