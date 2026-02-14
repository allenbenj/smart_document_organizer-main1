from fastapi.testclient import TestClient


def test_organization_llm_contracts():
    from Start import app  # noqa: E402

    client = TestClient(app)

    r = client.get('/api/organization/llm')
    assert r.status_code == 200
    data = r.json()
    assert data.get('success') is True
    assert 'active' in data


def test_organization_llm_switch_validation_contract():
    from Start import app  # noqa: E402

    client = TestClient(app)

    bad = client.post('/api/organization/llm/switch', json={'provider': 'bad-provider'})
    assert bad.status_code == 400

    ok = client.post('/api/organization/llm/switch', json={'provider': 'xai'})
    assert ok.status_code == 200
    body = ok.json()
    assert body.get('success') is True
    assert 'active' in body
