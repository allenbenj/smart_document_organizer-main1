from mem_db.database import DatabaseManager
from services.dependencies import get_database_manager_strict_dep


def _with_test_db(client, tmp_path):
    db = DatabaseManager(str(tmp_path / "workflow-bulk-ontology.db"))
    client.app.dependency_overrides[get_database_manager_strict_dep] = lambda: db
    return db


def test_bulk_proposal_actions_v2_contract(client, tmp_path):
    db = _with_test_db(client, tmp_path)

    with db.get_connection() as conn:
        conn.execute("DELETE FROM organization_feedback")
        conn.execute("DELETE FROM organization_proposals")
        conn.execute("DELETE FROM files_index")
        conn.execute("DELETE FROM workflow_jobs")
        conn.commit()

    proposal_ids = []
    for i in range(3):
        fid = db.upsert_indexed_file(
            display_name=f"bulk_case_{i}.pdf",
            original_path=f"/tmp/bulk_case_{i}.pdf",
            normalized_path=f"/tmp/bulk_case_{i}.pdf",
            file_size=100,
            mtime=10.0 + i,
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
                "current_path": f"/tmp/bulk_case_{i}.pdf",
                "proposed_folder": "Inbox/Review",
                "proposed_filename": f"bulk_case_{i}.pdf",
                "confidence": 0.73,
                "rationale": "initial",
                "alternatives": ["Inbox/Review"],
                "provider": "xai",
                "model": "grok-test",
                "status": "proposed",
                "metadata": {"decision_source": "heuristic"},
            }
        )
        proposal_ids.append(pid)

    job_id = client.post("/api/workflow/jobs", json={"workflow": "memory_first_v2"}).json()["job"]["job_id"]

    resp = client.post(
        f"/api/workflow/jobs/{job_id}/proposals/bulk",
        json={"proposal_ids": proposal_ids[:2], "action": "approve"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["job_id"] == job_id
    assert body["applied"] == 2
    assert body["failed"] == 0



def test_patch_ontology_fields_v2_contract(client, tmp_path):
    db = _with_test_db(client, tmp_path)

    with db.get_connection() as conn:
        conn.execute("DELETE FROM organization_feedback")
        conn.execute("DELETE FROM organization_proposals")
        conn.execute("DELETE FROM files_index")
        conn.execute("DELETE FROM workflow_jobs")
        conn.commit()

    fid = db.upsert_indexed_file(
        display_name="nda_v3.pdf",
        original_path="/tmp/nda_v3.pdf",
        normalized_path="/tmp/nda_v3.pdf",
        file_size=100,
        mtime=11.0,
        mime_type="application/pdf",
        mime_source="pytest",
        sha256=None,
        ext=".pdf",
        status="ready",
    )

    proposal_id = db.organization_add_proposal(
        {
            "run_id": None,
            "file_id": fid,
            "current_path": "/tmp/nda_v3.pdf",
            "proposed_folder": "Inbox/Review",
            "proposed_filename": "nda_v3.pdf",
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

    resp = client.patch(
        f"/api/workflow/jobs/{job_id}/proposals/{proposal_id}/ontology",
        json={
            "proposed_folder": "Legal/Contracts",
            "proposed_filename": "nda_2026_final.pdf",
            "confidence": 0.97,
            "rationale": "ontology correction",
            "note": "v2 inline edit",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["job_id"] == job_id
    assert body["applied"] == 1
    assert body["failed"] == 0

    updated = db.organization_get_proposal(proposal_id)
    assert updated is not None
    assert updated.get("status") == "approved"
    assert updated.get("proposed_folder") == "Legal/Contracts"
    assert updated.get("proposed_filename") == "nda_2026_final.pdf"
