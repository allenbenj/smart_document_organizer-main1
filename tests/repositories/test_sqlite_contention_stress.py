from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from utils.models import DocumentCreate


def test_sqlite_contention_stress_api_and_scheduler_writes(temp_db_manager):
    """Stress concurrent writes from API-like organization writes and scheduler-like writes."""
    db = temp_db_manager

    dummy_file_id = db.file_index_repo.upsert_indexed_file(
        display_name="stress-dummy.txt",
        original_path="/tmp/stress-dummy.txt",
        normalized_path="/tmp/stress-dummy.txt",
        status="ready"
    )

    loops = 80
    workers = 4
    gate = Barrier(workers)

    def api_writer(idx: int) -> int:
        gate.wait()
        ok = 0
        for i in range(loops):
            pid = db.organization_add_proposal(
                {
                    "run_id": None,
                    "file_id": dummy_file_id,
                    "current_path": f"/tmp/in/{idx}-{i}.txt",
                    "proposed_folder": "Inbox",
                    "proposed_filename": f"doc-{idx}-{i}.txt",
                    "confidence": 0.6,
                    "rationale": "stress",
                    "alternatives": [],
                    "provider": "xai",
                    "model": "grok-4-fast-reasoning",
                    "status": "proposed",
                    "metadata": {},
                }
            )
            if pid > 0:
                ok += 1
        return ok

    def scheduler_writer(idx: int) -> int:
        gate.wait()
        ok = 0
        for i in range(loops):
            sid = db.schedule_upsert(
                name=f"stress-{idx}-{i}",
                mode="index",
                payload={"roots": ["/tmp"]},
                every_minutes=60,
                active=True,
            )
            if sid > 0:
                ok += 1
        return ok

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [
            ex.submit(api_writer, 1),
            ex.submit(api_writer, 2),
            ex.submit(scheduler_writer, 3),
            ex.submit(scheduler_writer, 4),
        ]
        counts = [f.result() for f in futures]

    assert sum(counts) == loops * workers
    assert db.organization_stats()["proposals_total"] >= loops * 2
    assert len(db.schedule_list(active_only=False)) >= loops * 2
