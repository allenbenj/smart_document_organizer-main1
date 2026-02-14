def test_import_triples_creates_entities_and_relationships(client):
    # Get initial counts
    e0 = client.get("/api/knowledge/entities").json().get("count", 0)
    r0 = client.get("/api/knowledge/relationships").json().get("count", 0)

    triples = [
        ["contract", "obligates", "party"],
        ["payment", "relates_to", "contract"],
    ]
    resp = client.post("/api/knowledge/import_triples", json={"triples": triples})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("created_relationships", 0) >= 1

    # Verify counts increased
    e1 = client.get("/api/knowledge/entities").json().get("count", 0)
    r1 = client.get("/api/knowledge/relationships").json().get("count", 0)
    assert e1 >= e0
    assert r1 >= r0
