from dataclasses import dataclass
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.testclient import TestClient


@dataclass
class FakeResult:
    success: bool = True
    data: Dict[str, Any] = None
    error: str | None = None
    processing_time: float = 0.01
    agent_type: str = "test"
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.metadata is None:
            self.metadata = {}


class FakeManager:
    async def get_system_health(self) -> Dict[str, Any]:
        return {"system_initialized": True}

    async def get_agent_status(self, _agent_type) -> Dict[str, Any]:
        return {"healthy": True}

    async def analyze_legal_reasoning(self, _text: str, **_opts: Any) -> FakeResult:
        return FakeResult(agent_type="legal_reasoning", data={"ok": True})


class FakeAgentService:
    async def get_agent_status(self) -> Dict[str, Any]:
        return {"agents": {"document_processor": {"healthy": True}}}

    async def get_available_agents(self) -> List[str]:
        return ["document_processor", "entity_extractor", "legal_reasoning"]

    async def dispatch_task(self, task_type: str, payload: Dict[str, Any]) -> Any:
        if task_type == "analyze_legal":
            return FakeResult(
                success=True,
                data={"ok": True, "text": payload.get("text", "")},
                agent_type="legal_reasoning",
                metadata={"document_id": "test-doc", "confidence": 0.9},
            )
        return FakeResult(success=True, data={"task_type": task_type})


class FakeMemoryService:
    async def get_pending_proposals(self, limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
        return [{"id": 1, "namespace": "n", "key": "k", "status": "pending", "flags": []}]

    async def create_proposal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"id": 1, "status": "pending", "echo": payload}

    async def approve_proposal(self, proposal_id: int, corrections=None) -> Dict[str, Any]:
        return {"id": proposal_id, "status": "approved", "corrections": corrections}

    async def reject_proposal(self, proposal_id: int) -> Dict[str, Any]:
        return {"id": proposal_id, "status": "rejected"}

    async def correct_record(self, record_id: str, updates: Dict[str, Any]) -> bool:
        return bool(record_id) and isinstance(updates, dict)

    async def delete_record(self, record_id: str) -> bool:
        return bool(record_id)

    async def get_flagged_proposals(self) -> Dict[str, Any]:
        return {"count": 0, "flags": {}, "items": []}

    async def get_stats(self) -> Dict[str, Any]:
        return {"proposals_total": 1, "by_status": {"pending": 1}}


def _build_client() -> TestClient:
    from routes.agents import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_agents_routes_have_no_duplicate_method_path_pairs():
    client = _build_client()
    seen = set()
    dupes = []
    for route in client.app.routes:
        methods = sorted(getattr(route, "methods", []) or [])
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            key = (method, route.path)
            if key in seen:
                dupes.append(key)
            seen.add(key)

    agents_dupes = [d for d in dupes if d[1].startswith("/api/agents")]
    assert agents_dupes == []


def test_agents_management_health_and_status_with_patched_manager(monkeypatch):
    from routes.agent_routes import management

    async def _fake_get_agent_service(_request):
        return FakeAgentService()

    monkeypatch.setattr(management, "get_agent_service", _fake_get_agent_service)

    client = _build_client()

    r_health = client.get("/api/agents/health")
    assert r_health.status_code == 200
    assert "health" in r_health.json()

    r_status = client.get("/api/agents/status/document_processor")
    assert r_status.status_code == 200
    body = r_status.json()
    assert body["agent"] == "document_processor"


def test_agents_analysis_and_memory_routes_with_patched_services(monkeypatch):
    from routes.agent_routes import analysis, memory

    async def _fake_get_agent_service(_request):
        return FakeAgentService()

    async def _fake_get_memory_service(_request):
        return FakeMemoryService()

    monkeypatch.setattr(analysis, "get_agent_service", _fake_get_agent_service)
    monkeypatch.setattr(analysis, "get_memory_service", _fake_get_memory_service)
    monkeypatch.setattr(memory, "get_memory_service", _fake_get_memory_service)

    client = _build_client()

    r_legal = client.post("/api/agents/legal", json={"text": "hello"})
    assert r_legal.status_code == 200
    assert r_legal.json().get("success") is True

    r_props = client.get("/api/agents/memory/proposals")
    assert r_props.status_code == 200
    assert isinstance(r_props.json().get("proposals"), list)

    r_approve = client.post("/api/agents/memory/proposals/approve", json={"proposal_id": 1})
    assert r_approve.status_code == 200
    assert r_approve.json().get("status") == "approved"
