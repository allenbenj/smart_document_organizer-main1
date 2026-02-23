from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.core.models import AgentResult
from routes.extraction import router
from services.dependencies import get_agent_manager_strict_dep


class _FakeManager:
    async def extract_entities(self, text: str, **kwargs):
        entities = [
            {
                "id": "e1",
                "text": "downstairs",
                "entity_type": "location",
                "confidence": 0.9,
                "start_pos": 0,
                "end_pos": 10,
                "source": kwargs.get("extraction_type", "ner"),
                "attributes": {},
            }
        ]
        return AgentResult(
            success=True,
            data={
                "extraction_result": {
                    "entities": entities,
                    "relationships": [],
                    "extraction_stats": {"count": len(entities)},
                }
            },
            agent_type="entity_extractor",
        )


class _FailingManager:
    async def extract_entities(self, text: str, **kwargs):
        raise RuntimeError("simulated extractor timeout")


def _build_client() -> TestClient:
    return _build_client_with_manager(_FakeManager())


def _build_client_with_manager(manager_obj) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/extraction")

    async def _override_dep():
        return manager_obj

    app.dependency_overrides[get_agent_manager_strict_dep] = _override_dep
    return TestClient(app)


def test_extraction_run_returns_normalized_entities_payload() -> None:
    client = _build_client()

    resp = client.post(
        "/api/extraction/run",
        json={"text": "downstairs", "extraction_type": "llm", "options": {}},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"]["entities"], list)
    assert body["data"]["entities"][0]["text"] == "downstairs"
    assert body["data"]["entities"][0]["source"] == "llm"
    assert "extraction_stats" in body["data"]
    assert "extraction_methods_used" in body["data"]
    assert "validation_results" in body["data"]


def test_extraction_run_handles_manager_failure_with_structured_error() -> None:
    client = _build_client_with_manager(_FailingManager())

    resp = client.post(
        "/api/extraction/run",
        json={"text": "downstairs", "extraction_type": "ner", "options": {}},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "simulated extractor timeout" in (body.get("error") or "")
