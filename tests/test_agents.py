def test_agents_list(client):
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)


def test_irac_analysis(client):
    resp = client.post(
        "/api/agents/irac",
        json={"text": "This contract may be void due to illegality."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    assert isinstance(body.get("data"), dict)


def test_toulmin_analysis(client):
    resp = client.post(
        "/api/agents/toulmin",
        json={"text": "The plaintiff claims breach of contract due to non-payment."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    assert isinstance(body.get("data"), dict)


def test_entities_and_semantic(client):
    text = "The contract shall be binding. Payment breach occurs on non-payment."
    r1 = client.post("/api/agents/entities", json={"text": text})
    assert r1.status_code == 200
    r2 = client.post("/api/agents/semantic", json={"text": text})
    assert r2.status_code == 200


def test_contradictions_and_violations(client):
    text = "This is prohibited but also allowed in certain cases."
    r1 = client.post("/api/agents/contradictions", json={"text": text})
    assert r1.status_code == 200
    r2 = client.post("/api/agents/violations", json={"text": text})
    assert r2.status_code == 200


def test_embed_and_orchestrate(client):
    r1 = client.post("/api/agents/embed", json={"texts": ["alpha", "beta"]})
    assert r1.status_code == 200
    r2 = client.post(
        "/api/agents/orchestrate",
        json={"text": "The contract may be illegal due to non-payment."},
    )
    assert r2.status_code == 200
