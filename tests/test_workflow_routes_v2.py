from mem_db.database import DatabaseManager
from services.dependencies import get_database_manager_strict_dep


def _with_test_db(client, tmp_path):
    db = DatabaseManager(str(tmp_path / "workflow-tests.db"))
    client.app.dependency_overrides[get_database_manager_strict_dep] = lambda: db
    return db


def test_workflow_create_is_idempotent_and_status_retrievable(client, tmp_path):
    db = _with_test_db(client, tmp_path)
    with db.get_connection() as conn:
        conn.execute("DELETE FROM workflow_idempotency_keys")
        conn.execute("DELETE FROM workflow_jobs")
        conn.commit()

    key = "test-create-idempotency-1"
    payload = {"workflow": "memory_first_v2", "metadata": {"source": "pytest"}}

    r1 = client.post("/api/workflow/jobs", json=payload, headers={"Idempotency-Key": key})
    assert r1.status_code == 200
    b1 = r1.json()
    job_id = b1["job"]["job_id"]

    r2 = client.post("/api/workflow/jobs", json=payload, headers={"Idempotency-Key": key})
    assert r2.status_code == 200
    b2 = r2.json()

    assert b2["job"]["job_id"] == job_id

    status = client.get(f"/api/workflow/jobs/{job_id}/status")
    assert status.status_code == 200
    s = status.json()
    assert s["success"] is True
    assert s["job"]["job_id"] == job_id


def test_workflow_proposals_results_pagination_contract(client, tmp_path):
    db = _with_test_db(client, tmp_path)
    with db.get_connection() as conn:
        conn.execute("DELETE FROM organization_proposals")
        conn.execute("DELETE FROM files_index")
        conn.execute("DELETE FROM workflow_jobs")
        conn.commit()

    for i in range(5):
        fid = db.upsert_indexed_file(
            display_name=f"file_{i}.pdf",
            original_path=f"/tmp/file_{i}.pdf",
            normalized_path=f"/tmp/file_{i}.pdf",
            file_size=100,
            mtime=1.0 + i,
            mime_type="application/pdf",
            mime_source="pytest",
            sha256=None,
            ext=".pdf",
            status="ready",
        )
        db.organization_add_proposal(
            {
                "run_id": None,
                "file_id": fid,
                "current_path": f"/tmp/file_{i}.pdf",
                "proposed_folder": "Inbox/Review",
                "proposed_filename": f"file_{i}.pdf",
                "confidence": 0.7 + (i * 0.01),
                "rationale": "Heuristic classification",
                "alternatives": ["Inbox/Review"],
                "provider": "xai",
                "model": "grok-test",
                "status": "proposed",
                "metadata": {"decision_source": "heuristic"},
            }
        )

    job_resp = client.post("/api/workflow/jobs", json={"workflow": "memory_first_v2"})
    assert job_resp.status_code == 200
    job_id = job_resp.json()["job"]["job_id"]

    r = client.get(f"/api/workflow/jobs/{job_id}/results?step=proposals&limit=2&offset=1")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["step"] == "proposals"
    assert len(body["result"]["items"]) == 2

    item_payload = body["result"]["items"][0]["payload"]
    assert "confidence" in item_payload
    assert "draft_state" in item_payload
    assert body["result"]["pagination"]["count"] == 2
