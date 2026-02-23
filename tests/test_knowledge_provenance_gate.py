from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.knowledge import get_knowledge_service, router
from services.dependencies import get_database_manager_strict_dep


class _FakeKnowledgeService:
    def __init__(self) -> None:
        self.approved_ids: list[int] = []

    async def approve_proposal(self, proposal_id: int):
        self.approved_ids.append(proposal_id)
        return {"approved": True, "created": {"id": "entity-1"}}


class _FakeDB:
    def __init__(self) -> None:
        self.verify_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []

    def knowledge_set_verification(
        self,
        knowledge_id: int,
        *,
        verified: bool,
        verified_by: str | None = None,
        user_notes: str | None = None,
    ) -> bool:
        self.verify_calls.append(
            {
                "knowledge_id": knowledge_id,
                "verified": verified,
                "verified_by": verified_by,
                "user_notes": user_notes,
            }
        )
        return True

    def knowledge_update_item(self, knowledge_id: int, **kwargs: Any) -> bool:
        self.update_calls.append({"knowledge_id": knowledge_id, **kwargs})
        return True

    def knowledge_get_item(self, knowledge_id: int) -> dict[str, Any]:
        return {"id": knowledge_id, "term": "downstairs", "status": "verified"}


class _FakeProvenanceService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def record_provenance(self, record, target_type: str, target_id: str) -> int:
        self.calls.append((target_type, target_id))
        return 777


def _provenance_payload(artifact_row_id: int = 1) -> dict[str, Any]:
    return {
        "source_artifact_row_id": artifact_row_id,
        "source_sha256": "a" * 64,
        "captured_at": "2026-02-21T00:00:00+00:00",
        "extractor": "pytest-knowledge",
        "spans": [
            {
                "artifact_row_id": artifact_row_id,
                "start_char": 0,
                "end_char": 10,
                "quote": "test quote",
            }
        ],
        "notes": "test provenance",
    }


def _build_client(fake_service: _FakeKnowledgeService, fake_db: _FakeDB) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def _svc_override():
        return fake_service

    app.dependency_overrides[get_knowledge_service] = _svc_override
    app.dependency_overrides[get_database_manager_strict_dep] = lambda: fake_db
    return TestClient(app)


def test_knowledge_proposal_approval_requires_provenance(monkeypatch) -> None:
    fake_service = _FakeKnowledgeService()
    fake_db = _FakeDB()
    client = _build_client(fake_service, fake_db)

    monkeypatch.setattr(
        "routes.knowledge.get_provenance_service",
        lambda: _FakeProvenanceService(),
    )

    resp = client.post("/api/knowledge/proposals/approve", json={"id": 101})
    assert resp.status_code == 422
    assert fake_service.approved_ids == []


def test_knowledge_proposal_approval_persists_provenance(monkeypatch) -> None:
    fake_service = _FakeKnowledgeService()
    fake_db = _FakeDB()
    prov = _FakeProvenanceService()
    client = _build_client(fake_service, fake_db)

    monkeypatch.setattr("routes.knowledge.get_provenance_service", lambda: prov)

    resp = client.post(
        "/api/knowledge/proposals/approve",
        json={"id": 102, "provenance": _provenance_payload(10)},
    )
    assert resp.status_code == 200
    assert fake_service.approved_ids == [102]
    assert prov.calls == [("knowledge_proposal_approval", "102")]
    assert resp.json().get("provenance_id") == 777


def test_manager_verify_requires_provenance_for_verified_true(monkeypatch) -> None:
    fake_service = _FakeKnowledgeService()
    fake_db = _FakeDB()
    client = _build_client(fake_service, fake_db)

    monkeypatch.setattr(
        "routes.knowledge.get_provenance_service",
        lambda: _FakeProvenanceService(),
    )

    resp = client.post(
        "/api/knowledge/manager/items/11/verify",
        json={"verified": True, "verified_by": "expert"},
    )
    assert resp.status_code == 422
    assert fake_db.verify_calls == []


def test_manager_verify_accepts_valid_provenance(monkeypatch) -> None:
    fake_service = _FakeKnowledgeService()
    fake_db = _FakeDB()
    prov = _FakeProvenanceService()
    client = _build_client(fake_service, fake_db)

    monkeypatch.setattr("routes.knowledge.get_provenance_service", lambda: prov)

    resp = client.post(
        "/api/knowledge/manager/items/12/verify",
        json={
            "verified": True,
            "verified_by": "expert",
            "provenance": _provenance_payload(12),
        },
    )
    assert resp.status_code == 200
    assert len(fake_db.verify_calls) == 1
    assert prov.calls == [("manager_knowledge_verification", "12")]
    assert resp.json().get("provenance_id") == 777


def test_manager_update_curation_requires_provenance(monkeypatch) -> None:
    fake_service = _FakeKnowledgeService()
    fake_db = _FakeDB()
    client = _build_client(fake_service, fake_db)

    monkeypatch.setattr(
        "routes.knowledge.get_provenance_service",
        lambda: _FakeProvenanceService(),
    )

    resp = client.put(
        "/api/knowledge/manager/items/15",
        json={"status": "verified", "term": "downstairs"},
    )
    assert resp.status_code == 422
    assert fake_db.update_calls == []


def test_manager_update_curation_accepts_valid_provenance(monkeypatch) -> None:
    fake_service = _FakeKnowledgeService()
    fake_db = _FakeDB()
    prov = _FakeProvenanceService()
    client = _build_client(fake_service, fake_db)

    monkeypatch.setattr("routes.knowledge.get_provenance_service", lambda: prov)

    resp = client.put(
        "/api/knowledge/manager/items/16",
        json={
            "status": "curated",
            "term": "downstairs",
            "provenance": _provenance_payload(16),
        },
    )
    assert resp.status_code == 200
    assert len(fake_db.update_calls) == 1
    assert prov.calls == [("manager_knowledge_curation", "16")]
    assert resp.json().get("provenance_id") == 777
