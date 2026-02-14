def test_knowledge_status(client):
    r = client.get("/api/knowledge")
    assert r.status_code == 200
    assert "available" in r.json()


def test_vector_status(client):
    r = client.get("/api/vector")
    assert r.status_code == 200
    assert "available" in r.json()
