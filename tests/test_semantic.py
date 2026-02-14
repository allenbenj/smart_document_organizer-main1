def test_semantic_endpoint_schema(client):
    text = "This agreement sets out obligations, payment schedules, and termination clauses."
    resp = client.post("/api/agents/semantic", json={"text": text})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    data = body.get("data", {})
    # Core keys
    assert isinstance(data.get("summary"), str)
    assert isinstance(data.get("topics"), list)
    assert isinstance(data.get("key_phrases"), list)
    # Topics should be strings when present
    if data.get("topics"):
        assert all(isinstance(t, str) for t in data["topics"])
