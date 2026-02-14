from mem_db.database import DatabaseManager
from services.taskmaster_service import TaskMasterService


def test_taskmaster_queue_backpressure_blocks_enqueue(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = TaskMasterService(db)

    first = svc.enqueue_file_pipeline(mode="index", payload={"roots": ["/tmp"]}, max_queue_depth=1)
    assert first["success"] is True

    second = svc.enqueue_file_pipeline(mode="index", payload={"roots": ["/tmp"]}, max_queue_depth=1)
    assert second["success"] is False
    assert second["error"] == "backpressure_queue_full"


def test_taskmaster_queue_retry_then_dead_letter(monkeypatch, tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = TaskMasterService(db)

    enq = svc.enqueue_file_pipeline(mode="index", payload={"roots": ["/tmp"]}, max_retries=1)
    assert enq["success"] is True

    def always_fail(*, mode, payload):
        return {"success": False, "error": "boom"}

    monkeypatch.setattr(svc, "run_file_pipeline", always_fail)

    first = svc.run_worker_once(worker_name="w1")
    assert first["status"] == "retry"

    with db.get_connection() as conn:
        conn.execute("UPDATE taskmaster_job_queue SET available_at = datetime('now', '-1 second')")
        conn.commit()

    second = svc.run_worker_once(worker_name="w1")
    assert second["status"] == "dead_letter"

    dead = db.taskmaster_dead_letters(limit=10)
    assert len(dead) == 1
    assert dead[0]["error_message"] == "boom"
