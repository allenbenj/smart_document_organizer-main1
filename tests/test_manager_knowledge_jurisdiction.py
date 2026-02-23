from __future__ import annotations

import pytest

from mem_db.database import DatabaseManager
from services.knowledge_service import KnowledgeService
from services.memory_service import MemoryService


def test_manager_knowledge_jurisdiction_round_trip(tmp_path):
    db = DatabaseManager(str(tmp_path / "documents.db"))

    knowledge_id = db.knowledge_upsert(
        term="downstairs",
        category="LocationEntity",
        canonical_value="downstairs",
        ontology_entity_id="EVIDENCEITEM",
        framework_type="Evidentiary Standard",
        jurisdiction="North Carolina",
        legal_use_cases=[{"jurisdiction": "North Carolina State Court"}],
        confidence=1.0,
        status="verified",
        verified=True,
        verified_by="expert_approval",
    )
    item = db.knowledge_get_item(knowledge_id)
    assert item is not None
    assert item.get("jurisdiction") == "North Carolina"
    assert item.get("content") == item.get("term")

    ok = db.knowledge_update_item(
        knowledge_id,
        jurisdiction="North Carolina Superior Court",
    )
    assert ok
    updated = db.knowledge_get_item(knowledge_id)
    assert updated is not None
    assert updated.get("jurisdiction") == "North Carolina Superior Court"
    assert updated.get("content") == updated.get("term")


def test_memory_service_promotes_jurisdiction_from_proposal_metadata(tmp_path):
    db = DatabaseManager(str(tmp_path / "documents.db"))
    service = MemoryService(database_manager=db)

    promoted_id = service._upsert_manager_knowledge_from_payload(
        payload={
            "content": "downstairs",
            "confidence_score": 1.0,
            "metadata": {
                "entity_type": "LocationEntity",
                "canonical_value": "downstairs",
                "ontology_entity_id": "EVIDENCEITEM",
                "jurisdiction": "North Carolina",
                "source": "memory_proposal:342",
            },
        },
        proposal_id=342,
    )
    assert promoted_id
    item = db.knowledge_get_item(int(promoted_id))
    assert item is not None
    assert item.get("jurisdiction") == "North Carolina"


def test_manager_knowledge_supports_object_lists_for_frameworks_and_sources(tmp_path):
    db = DatabaseManager(str(tmp_path / "documents.db"))

    related_frameworks = [
        {
            "framework": "North Carolina Rules of Evidence 901",
            "description": "Authentication or identification",
        }
    ]
    sources = [
        {
            "source_type": "Hearing Transcript",
            "document_id": "TR-2026-02-09",
            "excerpt": "Defense Counsel asked about downstairs search sequence.",
        }
    ]

    knowledge_id = db.knowledge_upsert(
        term="downstairs",
        category="LocationEntity",
        related_frameworks=related_frameworks,
        sources=sources,
    )
    item = db.knowledge_get_item(knowledge_id)
    assert item is not None
    assert item.get("related_frameworks_json") == related_frameworks
    assert item.get("sources_json") == sources


def test_memory_service_uses_default_jurisdiction_when_missing_metadata(tmp_path, monkeypatch):
    db = DatabaseManager(str(tmp_path / "documents.db"))
    service = MemoryService(database_manager=db)

    monkeypatch.setattr(
        "services.memory_service.jurisdiction_service",
        type("J", (), {"resolve": staticmethod(lambda *_args, **_kwargs: "North Carolina")})(),
    )

    promoted_id = service._upsert_manager_knowledge_from_payload(
        payload={
            "content": "downstairs",
            "confidence_score": 1.0,
            "metadata": {
                "entity_type": "LocationEntity",
                "canonical_value": "downstairs",
                "ontology_entity_id": "EVIDENCEITEM",
                "source": "memory_proposal:900",
            },
        },
        proposal_id=900,
    )
    assert promoted_id
    item = db.knowledge_get_item(int(promoted_id))
    assert item is not None
    assert item.get("jurisdiction") == "North Carolina"


@pytest.mark.asyncio
async def test_knowledge_service_add_entity_uses_resolved_default_jurisdiction(monkeypatch):
    captured = {}

    class _FakeManager:
        async def add_entity(self, **kwargs):
            captured.update(kwargs)
            return "entity-1"

    svc = KnowledgeService(knowledge_manager=_FakeManager())
    monkeypatch.setattr(
        "services.knowledge_service.jurisdiction_service",
        type("J", (), {"resolve": staticmethod(lambda *_args, **_kwargs: "North Carolina")})(),
    )

    out = await svc.add_entity(
        name="downstairs",
        entity_type="LocationEntity",
        attributes={},
        content="downstairs",
        jurisdiction=None,
    )
    assert out["id"] == "entity-1"
    assert captured.get("jurisdiction") == "North Carolina"
