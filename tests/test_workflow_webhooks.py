from __future__ import annotations

import json
import urllib.error

from mem_db.database import DatabaseManager
from services.dependencies import get_database_manager_strict_dep
from services.workflow_webhook_service import WorkflowWebhookService


def test_webhook_service_retries_and_writes_dlq(monkeypatch, tmp_path):
    dlq = tmp_path / "workflow_dlq.jsonl"
    monkeypatch.setenv("WORKFLOW_WEBHOOK_MAX_RETRIES", "1")
    monkeypatch.setenv("WORKFLOW_WEBHOOK_RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("WORKFLOW_WEBHOOK_DLQ_PATH", str(dlq))

    calls = {"n": 0}

    def _fail(*args, **kwargs):
        calls["n"] += 1
        raise urllib.error.URLError("boom")

    monkeypatch.setattr("urllib.request.urlopen", _fail)

    svc = WorkflowWebhookService()
    out = svc.deliver(url="http://127.0.0.1:9999/callback", payload={"ok": True}, event_id="evt_1")

    assert out["ok"] is False
    assert calls["n"] == 2  # first + one retry
    lines = dlq.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event_id"] == "evt_1"
    assert entry["attempts"] == 2


def test_workflow_route_triggers_webhook_and_updates_status(client, tmp_path, monkeypatch):
    db = DatabaseManager(str(tmp_path / "workflow-webhook.db"))
    client.app.dependency_overrides[get_database_manager_strict_dep] = lambda: db

    monkeypatch.setenv("WORKFLOW_WEBHOOK_MAX_RETRIES", "0")
    monkeypatch.setenv("WORKFLOW_WEBHOOK_RETRY_BACKOFF_SECONDS", "0")

    class _Resp:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Resp())

    create = client.post(
        "/api/workflow/jobs",
        json={"workflow": "memory_first_v2", "webhook_url": "http://example.com/hook"},
    )
    assert create.status_code == 200
    job_id = create.json()["job"]["job_id"]

    status = client.get(f"/api/workflow/jobs/{job_id}/status")
    assert status.status_code == 200
    webhook = status.json()["job"]["webhook"]
    assert webhook["enabled"] is True
    assert str(webhook["last_delivery_status"]).startswith("delivered:204")
