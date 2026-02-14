import time

from mem_db.database import DatabaseManager
from services.file_index_service import FileIndexService


def test_file_scanner_benchmark_smoke(tmp_path):
    root = tmp_path / "bench"
    root.mkdir()
    for i in range(120):
        (root / f"f_{i:03d}.md").write_text(f"# Doc {i}\ncontent line\n", encoding="utf-8")

    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = FileIndexService(db)

    t0 = time.perf_counter()
    out = svc.index_roots([str(root)], recursive=True, max_files=1000)
    elapsed = time.perf_counter() - t0

    assert out["indexed"] >= 120
    # very relaxed threshold for CI/WSL noise; this is a closure guard, not a strict perf gate.
    assert elapsed < 20.0
