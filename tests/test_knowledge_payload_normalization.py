from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mem_db.database import DatabaseManager
from routes.knowledge import router
from services.dependencies import get_database_manager_strict_dep


def _client_with_db(db: DatabaseManager) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_database_manager_strict_dep] = lambda: db
    return TestClient(app)


def test_manager_knowledge_payload_supports_object_lists_and_content_alias(tmp_path) -> None:
    db = DatabaseManager(str(tmp_path / "documents.db"))
    client = _client_with_db(db)

    payload = {
        "content": "downstairs",
        "category": "LocationEntity",
        "related_frameworks": [
            {
                "framework": "North Carolina Rules of Evidence 901",
                "description": "Authentication",
            }
        ],
        "sources": [
            {
                "source_type": "Hearing Transcript",
                "document_id": "TR-2026-02-09",
                "excerpt": "Witness referenced downstairs location.",
            }
        ],
    }

    created = client.post("/api/knowledge/manager/items", json=payload)
    assert created.status_code == 200
    kid = int(created.json()["id"])

    fetched = client.get(f"/api/knowledge/manager/items/{kid}")
    assert fetched.status_code == 200
    item = fetched.json()["item"]

    assert item["term"] == "downstairs"
    assert item["content"] == "downstairs"
    assert isinstance(item["related_frameworks_json"], list)
    assert isinstance(item["sources_json"], list)
    assert isinstance(item["related_frameworks_json"][0], dict)
    assert isinstance(item["sources_json"][0], dict)


def test_manager_knowledge_normalizes_category_and_ontology_entity_id(tmp_path) -> None:
    db = DatabaseManager(str(tmp_path / "documents.db"))
    client = _client_with_db(db)

    created = client.post(
        "/api/knowledge/manager/items",
        json={
            "term": "timeline gap",
            "category": "witness",
            "ontology_entity_id": "WITNESS",
        },
    )
    assert created.status_code == 200
    knowledge_id = int(created.json()["id"])

    updated = client.put(
        f"/api/knowledge/manager/items/{knowledge_id}",
        json={
            "category": "legal_violation",
            "ontology_entity_id": "legal_violation",
        },
    )
    assert updated.status_code == 200

    fetched = client.get(f"/api/knowledge/manager/items/{knowledge_id}")
    assert fetched.status_code == 200
    item = fetched.json()["item"]

    assert item["category"] == "LegalViolation"
    assert item["ontology_entity_id"] == "LegalViolation"
