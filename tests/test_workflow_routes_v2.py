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


def test_workflow_index_extract_and_summarize_persist_resume_state(client, tmp_path):
    db = _with_test_db(client, tmp_path)
    with db.get_connection() as conn:
        conn.execute("DELETE FROM workflow_jobs")
        conn.execute("DELETE FROM workflow_idempotency_keys")
        conn.commit()

    fid = db.upsert_indexed_file(
        display_name="sample_receipt.pdf",
        original_path="/tmp/sample_receipt.pdf",
        normalized_path="/tmp/sample_receipt.pdf",
        file_size=200,
        mtime=2.0,
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
            "current_path": "/tmp/sample_receipt.pdf",
            "proposed_folder": "Finance/Billing",
            "proposed_filename": "sample_receipt.pdf",
            "confidence": 0.88,
            "rationale": "Heuristic classification",
            "alternatives": ["Inbox/Review"],
            "provider": "xai",
            "model": "grok-test",
            "status": "proposed",
            "metadata": {"decision_source": "heuristic"},
        }
    )

    job_id = client.post("/api/workflow/jobs", json={"workflow": "memory_first_v2"}).json()["job"]["job_id"]

    ex1 = client.post(
        f"/api/workflow/jobs/{job_id}/steps/index_extract/execute",
        json={"payload": {"mode": "watched", "max_files": 50}},
    )
    assert ex1.status_code == 200
    assert ex1.json()["success"] is True

    ex2 = client.post(
        f"/api/workflow/jobs/{job_id}/steps/summarize/execute",
        json={"payload": {"limit": 100}},
    )
    assert ex2.status_code == 200
    assert ex2.json()["success"] is True

    status = client.get(f"/api/workflow/jobs/{job_id}/status")
    body = status.json()["job"]
    assert "index_extract" in body["metadata"].get("completed_steps", [])
    assert "summarize" in body["metadata"].get("completed_steps", [])
    assert body["metadata"].get("last_result_by_step", {}).get("summarize") is not None
    assert body.get("current_step") == "summarize"

    rs = client.get(f"/api/workflow/jobs/{job_id}/results?step=summarize")
    assert rs.status_code == 200
    assert rs.json()["result"]["pagination"]["count"] == 1


def test_workflow_frontend_route_smoke_contract(client, tmp_path):
    db = _with_test_db(client, tmp_path)
    with db.get_connection() as conn:
        conn.execute("DELETE FROM workflow_jobs")
        conn.execute("DELETE FROM workflow_idempotency_keys")
        conn.execute("DELETE FROM organization_proposals")
        conn.execute("DELETE FROM files_index")
        conn.commit()

    # seed one proposal so frontend results grid has data
    fid = db.upsert_indexed_file(
        display_name="smoke_1.pdf",
        original_path="/tmp/smoke_1.pdf",
        normalized_path="/tmp/smoke_1.pdf",
        file_size=100,
        mtime=1.0,
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
            "current_path": "/tmp/smoke_1.pdf",
            "proposed_folder": "Inbox/Review",
            "proposed_filename": "smoke_1.pdf",
            "confidence": 0.91,
            "rationale": "smoke",
            "alternatives": ["Inbox/Review"],
            "provider": "xai",
            "model": "grok-test",
            "status": "proposed",
            "metadata": {"decision_source": "heuristic"},
        }
    )

    create = client.post(
        "/api/workflow/jobs",
        json={"workflow": "memory_first_v2"},
        headers={"Idempotency-Key": "frontend-smoke-create"},
    )
    assert create.status_code == 200
    job_id = create.json()["job"]["job_id"]

    status = client.get(f"/api/workflow/jobs/{job_id}/status")
    assert status.status_code == 200
    job = status.json()["job"]
    assert job["workflow"] == "memory_first_v2"
    assert len(job["stepper"]) == 7

    exec_step = client.post(
        f"/api/workflow/jobs/{job_id}/steps/proposals/execute",
        json={"payload": {"limit": 10}},
        headers={"Idempotency-Key": "frontend-smoke-proposals"},
    )
    assert exec_step.status_code == 200
    assert exec_step.json()["success"] is True

    results = client.get(f"/api/workflow/jobs/{job_id}/results?step=proposals&limit=10&offset=0")
    assert results.status_code == 200
    body = results.json()
    assert body["success"] is True
    assert body["step"] == "proposals"
    assert body["result"]["pagination"]["count"] >= 1
    first = body["result"]["items"][0]["payload"]
    assert "proposal_id" in first
    assert "draft_state" in first


def test_workflow_bulk_approve_reject_endpoint(client, tmp_path):
    db = _with_test_db(client, tmp_path)
    with db.get_connection() as conn:
        conn.execute("DELETE FROM organization_feedback")
        conn.execute("DELETE FROM organization_proposals")
        conn.execute("DELETE FROM files_index")
        conn.execute("DELETE FROM workflow_jobs")
        conn.commit()

    ids = []
    for i in range(3):
        fid = db.upsert_indexed_file(
            display_name=f"bulk_{i}.pdf",
            original_path=f"/tmp/bulk_{i}.pdf",
            normalized_path=f"/tmp/bulk_{i}.pdf",
            file_size=100,
            mtime=1.0 + i,
            mime_type="application/pdf",
            mime_source="pytest",
            sha256=None,
            ext=".pdf",
            status="ready",
        )
        pid = db.organization_add_proposal(
            {
                "run_id": None,
                "file_id": fid,
                "current_path": f"/tmp/bulk_{i}.pdf",
                "proposed_folder": "Inbox/Review",
                "proposed_filename": f"bulk_{i}.pdf",
                "confidence": 0.71,
                "rationale": "initial",
                "alternatives": ["Inbox/Review"],
                "provider": "xai",
                "model": "grok-test",
                "status": "proposed",
                "metadata": {"decision_source": "heuristic"},
            }
        )
        ids.append(pid)

    job_id = client.post("/api/workflow/jobs", json={"workflow": "memory_first_v2"}).json()["job"]["job_id"]

    r = client.post(
        f"/api/workflow/jobs/{job_id}/proposals/bulk",
        json={"proposal_ids": ids[:2], "action": "approve"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["applied"] == 2
    assert body["failed"] == 0

    status_1 = db.organization_get_proposal(ids[0])
    status_2 = db.organization_get_proposal(ids[1])
    assert status_1 and status_1.get("status") == "approved"
    assert status_2 and status_2.get("status") == "approved"



def test_workflow_ontology_patch_endpoint_updates_fields(client, tmp_path):
    db = _with_test_db(client, tmp_path)
    with db.get_connection() as conn:
        conn.execute("DELETE FROM organization_feedback")
        conn.execute("DELETE FROM organization_proposals")
        conn.execute("DELETE FROM files_index")
        conn.execute("DELETE FROM workflow_jobs")
        conn.commit()

    fid = db.upsert_indexed_file(
        display_name="ontology_doc.pdf",
        original_path="/tmp/ontology_doc.pdf",
        normalized_path="/tmp/ontology_doc.pdf",
        file_size=100,
        mtime=1.0,
        mime_type="application/pdf",
        mime_source="pytest",
        sha256=None,
        ext=".pdf",
        status="ready",
    )

    pid = db.organization_add_proposal(
        {
            "run_id": None,
            "file_id": fid,
            "current_path": "/tmp/ontology_doc.pdf",
            "proposed_folder": "Inbox/Review",
            "proposed_filename": "ontology_doc.pdf",
            "confidence": 0.71,
            "rationale": "initial",
            "alternatives": ["Inbox/Review"],
            "provider": "xai",
            "model": "grok-test",
            "status": "proposed",
            "metadata": {"decision_source": "heuristic"},
        }
    )

    job_id = client.post("/api/workflow/jobs", json={"workflow": "memory_first_v2"}).json()["job"]["job_id"]

    r = client.patch(
        f"/api/workflow/jobs/{job_id}/proposals/{pid}/ontology",
        json={
            "proposed_folder": "Legal/Contracts",
            "proposed_filename": "master_service_agreement.pdf",
            "confidence": 0.95,
            "rationale": "User ontology correction",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["applied"] == 1

    updated = db.organization_get_proposal(pid)
    assert updated is not None
    assert updated.get("status") == "approved"
    assert updated.get("proposed_folder") == "Legal/Contracts"
    assert updated.get("proposed_filename") == "master_service_agreement.pdf"
    assert float(updated.get("confidence") or 0) == 0.95
    assert updated.get("rationale") == "User ontology correction"



def test_workflow_draft_state_uses_feedback_history(client, tmp_path):
    db = _with_test_db(client, tmp_path)
    with db.get_connection() as conn:
        conn.execute("DELETE FROM organization_feedback")
        conn.execute("DELETE FROM organization_actions")
        conn.execute("DELETE FROM organization_proposals")
        conn.execute("DELETE FROM files_index")
        conn.execute("DELETE FROM workflow_jobs")
        conn.commit()

    fid = db.upsert_indexed_file(
        display_name="contract_1.pdf",
        original_path="/tmp/contract_1.pdf",
        normalized_path="/tmp/contract_1.pdf",
        file_size=100,
        mtime=1.0,
        mime_type="application/pdf",
        mime_source="pytest",
        sha256=None,
        ext=".pdf",
        status="ready",
    )

    pid = db.organization_add_proposal(
        {
            "run_id": None,
            "file_id": fid,
            "current_path": "/tmp/contract_1.pdf",
            "proposed_folder": "Legal/Contracts",
            "proposed_filename": "contract_1.pdf",
            "confidence": 0.7,
            "rationale": "Initial proposal",
            "alternatives": ["Inbox/Review"],
            "provider": "xai",
            "model": "grok-test",
            "status": "approved",
            "metadata": {"decision_source": "heuristic"},
        }
    )

    db.organization_add_feedback(
        {
            "proposal_id": pid,
            "file_id": fid,
            "action": "edit",
            "original": {"proposed_folder": "Legal/Contracts"},
            "final": {"proposed_folder": "Legal/Litigation"},
            "note": "manual correction",
        }
    )

    job_id = client.post("/api/workflow/jobs", json={"workflow": "memory_first_v2"}).json()["job"]["job_id"]
    r = client.get(f"/api/workflow/jobs/{job_id}/results?step=proposals&limit=10&offset=0")
    assert r.status_code == 200
    payload = r.json()["result"]["items"][0]["payload"]
    assert payload["draft_state"] == "human_edited"
