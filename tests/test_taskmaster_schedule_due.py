from mem_db.database import DatabaseManager
from services.taskmaster_service import TaskMasterService


def test_run_due_schedules_executes_due_and_marks_ran(monkeypatch, tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = TaskMasterService(db)

    sid = db.schedule_upsert(
        name="due-index",
        mode="index",
        payload={"roots": ["/tmp"]},
        every_minutes=60,
        active=True,
    )

    # force schedule due now
    with db.get_connection() as conn:
        conn.execute("UPDATE taskmaster_schedules SET next_run_at = datetime('now', '-1 minute') WHERE id = ?", (sid,))
        conn.commit()

    calls = []

    def fake_run_file_pipeline(*, mode, payload):
        calls.append({"mode": mode, "payload": payload})
        return {"success": True, "run": {"id": 123, "status": "completed"}}

    monkeypatch.setattr(svc, "run_file_pipeline", fake_run_file_pipeline)

    out = svc.run_due_schedules()
    assert out["success"] is True
    assert out["due"] == 1
    assert len(out["runs"]) == 1
    assert calls and calls[0]["mode"] == "index"

    schedules = db.schedule_list(active_only=False)
    ran = next(s for s in schedules if s["id"] == sid)
    assert ran["last_run_at"] is not None
    assert ran["next_run_at"] is not None
