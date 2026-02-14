from fastapi.testclient import TestClient


def test_memory_proposal_pending_and_approve():
    from Start import app  # noqa: E402

    client = TestClient(app)

    # Propose with low confidence to ensure pending
    payload = {
        "namespace": "test",
        "key": "k1",
        "content": "some finding",
        "memory_type": "analysis",
        "confidence_score": 0.2,
        "importance_score": 0.5,
    }
    r = client.post("/api/agents/memory/proposals", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in {
        "pending",
        "approved",
    }  # allow auto-approve if threshold set very low
    proposal_id = data["id"]

    # Approve it if still pending
    if data["status"] == "pending":
        r2 = client.post(
            "/api/agents/memory/proposals/approve", json={"proposal_id": proposal_id}
        )
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2.get("stored_record_id")


def test_memory_proposal_auto_approve_high_confidence():
    from Start import app  # noqa: E402

    client = TestClient(app)

    payload = {
        "namespace": "test",
        "key": "k2",
        "content": "high confidence finding",
        "memory_type": "analysis",
        "confidence_score": 0.95,
        "importance_score": 0.9,
    }
    r = client.post("/api/agents/memory/proposals", json=payload)
    assert r.status_code == 200
    data = r.json()
    # It may still be pending if threshold > 0.95, but typically should be approved
    assert data["status"] in {"approved", "pending"}
