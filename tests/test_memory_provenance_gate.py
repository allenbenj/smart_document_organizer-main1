from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.contracts.aedis_models import EvidenceSpan, ProvenanceRecord
from services.memory_service import MemoryService
from services.provenance_service import ProvenanceGateError


class _FakeProvenanceService:
    def __init__(self) -> None:
        self.validate_calls: list[tuple[str, str]] = []
        self.record_calls: list[tuple[str, str]] = []

    def validate_write_gate(self, record: ProvenanceRecord, target_type: str, target_id: str) -> None:
        self.validate_calls.append((target_type, target_id))
        if not record.spans:
            raise ProvenanceGateError("missing spans")

    def record_provenance(self, record: ProvenanceRecord, target_type: str, target_id: str) -> int:
        self.record_calls.append((target_type, target_id))
        return 505


def _proposal_data(memory_type: str = "analysis") -> dict:
    return {
        "namespace": "case",
        "key": "fact-1",
        "content": "downstairs",
        "memory_type": memory_type,
        "metadata": {"claim_grade": True},
        "confidence_score": 0.9,
        "importance_score": 0.9,
    }


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(
        source_artifact_row_id=7,
        source_sha256="a" * 64,
        captured_at=datetime.now(timezone.utc),
        extractor="pytest-memory",
        spans=[
            EvidenceSpan(
                artifact_row_id=7,
                start_char=0,
                end_char=10,
                quote="downstairs",
            )
        ],
        notes="test",
    )


@pytest.mark.asyncio
async def test_memory_claim_grade_proposal_requires_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    add_calls: list[dict] = []

    def _add_proposal(proposal: dict) -> int:
        add_calls.append(proposal)
        return 1

    monkeypatch.setattr("services.memory_service.proposals_db.add_proposal", _add_proposal)
    monkeypatch.setattr("services.memory_service.proposals_db.update_proposal", lambda *_args, **_kwargs: True)
    monkeypatch.setattr("services.memory_service.proposals_db.delete_proposal", lambda *_args, **_kwargs: True)

    svc = MemoryService(memory_manager=None, config_manager=None, provenance_service=_FakeProvenanceService())

    with pytest.raises(ProvenanceGateError, match="memory_claim_grade_provenance_required"):
        await svc.create_proposal(_proposal_data(), provenance_record=None)

    assert add_calls == []


@pytest.mark.asyncio
async def test_memory_claim_grade_proposal_records_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    add_calls: list[dict] = []
    update_calls: list[tuple] = []

    def _add_proposal(proposal: dict) -> int:
        add_calls.append(proposal)
        return 2

    def _update_proposal(proposal_id: int, content=None, metadata=None):
        update_calls.append((proposal_id, metadata))
        return True

    monkeypatch.setattr("services.memory_service.proposals_db.add_proposal", _add_proposal)
    monkeypatch.setattr("services.memory_service.proposals_db.update_proposal", _update_proposal)
    monkeypatch.setattr("services.memory_service.proposals_db.delete_proposal", lambda *_args, **_kwargs: True)

    prov = _FakeProvenanceService()
    svc = MemoryService(memory_manager=None, config_manager=None, provenance_service=prov)

    out = await svc.create_proposal(_proposal_data(), provenance_record=_provenance())

    assert out["id"] == 2
    assert add_calls
    assert prov.validate_calls == [("memory_proposal", "pending"), ("memory_proposal", "2")]
    assert prov.record_calls == [("memory_proposal", "2")]
    assert update_calls
    assert update_calls[0][1]["provenance_id"] == 505
