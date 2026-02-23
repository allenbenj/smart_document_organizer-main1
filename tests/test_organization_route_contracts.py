from fastapi import FastAPI
from fastapi.testclient import TestClient

from mem_db.database import DatabaseManager
from routes.organization import router
from services.dependencies import get_database_manager_strict_dep


def _build_client(tmp_path) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    db = DatabaseManager(str(tmp_path / "documents.db"))
    app.dependency_overrides[get_database_manager_strict_dep] = lambda: db
    return TestClient(app)


def test_organization_llm_contracts(tmp_path):
    client = _build_client(tmp_path)

    r = client.get('/api/organization/llm')
    assert r.status_code == 200
    data = r.json()
    assert data.get('success') is True
    assert 'active' in data


def test_organization_llm_switch_validation_contract(tmp_path):
    client = _build_client(tmp_path)

    bad = client.post('/api/organization/llm/switch', json={'provider': 'bad-provider'})
    assert bad.status_code == 400

    ok = client.post('/api/organization/llm/switch', json={'provider': 'xai'})
    assert ok.status_code == 200
    body = ok.json()
    assert body.get('success') is True
    assert 'active' in body


def test_organization_apply_alias_contract(tmp_path):
    client = _build_client(tmp_path)
    r = client.post('/api/organization/proposals/apply', json={'limit': 1, 'dry_run': True})
    assert r.status_code == 200
    body = r.json()
    assert body.get('success') is True
