from __future__ import annotations

import pytest

from services.organization_service import OrganizationService


class _FakeDB:
    def __init__(self, *, rows: list[dict], add_return_id: int = 41) -> None:
        self._rows = rows
        self.add_calls = 0
        self.deleted_ids: list[int] = []
        self._next_id = add_return_id

    def list_all_indexed_files(self) -> list[dict]:
        return self._rows

    def organization_add_proposal(self, proposal: dict) -> int:
        self.add_calls += 1
        return self._next_id

    def organization_delete_proposal(self, proposal_id: int) -> bool:
        self.deleted_ids.append(proposal_id)
        return True


class _FakeProvenanceService:
    def __init__(self, provenance_id: int = 9001) -> None:
        self.calls: list[tuple] = []
        self.provenance_id = provenance_id

    def record_provenance(self, record, target_type: str, target_id: str) -> int:
        self.calls.append((record, target_type, target_id))
        return self.provenance_id


@pytest.mark.parametrize(
    "sha_value, err_fragment",
    [
        (None, "organization_missing_source_sha256"),
        ("not-a-hash", "organization_invalid_source_sha256"),
    ],
)
def test_generate_proposals_fails_closed_when_source_hash_missing_or_invalid(
    monkeypatch: pytest.MonkeyPatch,
    sha_value: str | None,
    err_fragment: str,
) -> None:
    db = _FakeDB(
        rows=[
            {
                "id": 101,
                "display_name": "sample.txt",
                "normalized_path": "/tmp/sample.txt",
                "status": "ready",
                "sha256": sha_value,
                "metadata_json": {"preview": "sample preview"},
            }
        ]
    )
    svc = OrganizationService(db)

    monkeypatch.setattr(
        "services.organization_service.OrganizationLLMPolicy.configured_status",
        lambda: {"xai": True, "deepseek": True},
    )
    monkeypatch.setattr(svc, "_auto_correct_existing_proposals", lambda **_: 0)
    monkeypatch.setattr(svc, "_known_folders_from_root", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(svc, "_folder_preference_scores", lambda: {})
    monkeypatch.setattr(svc, "_historical_folder_corrections", lambda **_: {})
    monkeypatch.setattr(svc, "_historical_filename_corrections", lambda **_: {})
    monkeypatch.setattr(
        svc,
        "_llm_suggest",
        lambda **_: {
            "proposed_folder": "Inbox/Review",
            "proposed_filename": "sample.txt",
            "confidence": 0.9,
            "rationale": "test",
            "alternatives": ["Inbox/Review"],
            "evidence_spans": [{"start_char": 0, "end_char": 6, "quote": "sample"}],
        },
    )

    with pytest.raises(RuntimeError, match=err_fragment):
        svc.generate_proposals(limit=1, provider="xai", model="unit-test")

    assert db.add_calls == 0


def test_generate_proposals_records_provenance_when_source_hash_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDB(
        rows=[
            {
                "id": 102,
                "display_name": "sample.txt",
                "normalized_path": "/tmp/sample.txt",
                "status": "ready",
                "sha256": "a" * 64,
                "metadata_json": {"preview": "sample preview"},
            }
        ]
    )
    svc = OrganizationService(db)
    fake_prov = _FakeProvenanceService()

    monkeypatch.setattr(
        "services.organization_service.OrganizationLLMPolicy.configured_status",
        lambda: {"xai": True, "deepseek": True},
    )
    monkeypatch.setattr("services.organization_service.get_provenance_service", lambda: fake_prov)
    monkeypatch.setattr(svc, "_auto_correct_existing_proposals", lambda **_: 0)
    monkeypatch.setattr(svc, "_known_folders_from_root", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(svc, "_folder_preference_scores", lambda: {})
    monkeypatch.setattr(svc, "_historical_folder_corrections", lambda **_: {})
    monkeypatch.setattr(svc, "_historical_filename_corrections", lambda **_: {})
    monkeypatch.setattr(
        svc,
        "_llm_suggest",
        lambda **_: {
            "proposed_folder": "Inbox/Review",
            "proposed_filename": "sample.txt",
            "confidence": 0.9,
            "rationale": "test",
            "alternatives": ["Inbox/Review"],
            "evidence_spans": [{"start_char": 0, "end_char": 6, "quote": "sample"}],
        },
    )

    out = svc.generate_proposals(limit=1, provider="xai", model="unit-test")

    assert out["success"] is True
    assert out["created"] == 1
    assert db.add_calls == 1
    assert len(fake_prov.calls) == 1
    _, target_type, target_id = fake_prov.calls[0]
    assert target_type == "organization_proposal"
    assert target_id == "41"
    assert out["items"][0]["metadata"]["provenance_id"] == 9001
