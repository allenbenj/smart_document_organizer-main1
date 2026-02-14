import os
from pathlib import Path

import pytest

from mem_db.database import DatabaseManager
from routes import files as files_routes
from services.file_index_service import FileIndexService, normalize_runtime_path


def test_markdown_discoverable_chunked_and_queryable(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = FileIndexService(db)

    root = tmp_path / "docs"
    root.mkdir()
    md = root / "investigation_notes.md"
    md.write_text(
        "# Intake\nCase overview\n\n## Evidence\n- item 1\n\n```python\nprint('x')\n```\n",
        encoding="utf-8",
    )

    result = svc.index_roots([str(root)], allowed_exts={".md"})
    assert result["success"] is True
    assert result["indexed"] == 1

    items, total = db.list_indexed_files(ext=".md", query="investigation_notes", limit=10, offset=0)
    assert total == 1
    rec = items[0]
    assert rec["display_name"] == "investigation_notes.md"
    meta = rec.get("metadata_json") or {}
    assert meta.get("chunk_count", 0) >= 2
    assert len(meta.get("headings") or []) >= 2
    assert meta.get("code_block_count", 0) == 1


def test_incremental_resume_after_cancellation(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = FileIndexService(db)

    root = tmp_path / "batch"
    root.mkdir()
    for i in range(3):
        (root / f"doc_{i}.txt").write_text(f"line {i}\n", encoding="utf-8")

    calls = {"n": 0}

    def should_stop():
        calls["n"] += 1
        return calls["n"] > 1

    first = svc.index_roots([str(root)], allowed_exts={".txt"}, should_stop=should_stop)
    assert first["cancelled"] is True
    assert first["indexed"] == 1

    second = svc.index_roots([str(root)], allowed_exts={".txt"})
    assert second["success"] is True
    assert second["indexed"] == 2
    assert second["skipped"] == 1


@pytest.mark.asyncio
async def test_missing_damaged_and_stale_are_surfaced(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = FileIndexService(db)

    root = tmp_path / "scan"
    root.mkdir()

    damaged_pdf = root / "broken.pdf"
    damaged_pdf.write_text("not a real pdf", encoding="utf-8")
    valid_txt = root / "ok.txt"
    valid_txt.write_text("hello", encoding="utf-8")

    indexed = svc.index_roots([str(root)], allowed_exts={".pdf", ".txt"})
    assert indexed["indexed"] == 2

    valid_txt.unlink()
    refreshed = svc.refresh_index(stale_after_hours=1)
    assert refreshed["missing"] == 1
    assert refreshed["damaged"] == 1

    # Force stale timestamp to validate API/UI stale projection.
    with db.get_connection() as conn:
        conn.execute("UPDATE files_index SET last_checked_at = '2000-01-01T00:00:00+00:00'")
        conn.commit()

    api_view = await files_routes.list_indexed_files(
        status=None,
        ext=None,
        q=None,
        keyword=None,
        sort_by="mtime",
        sort_dir="desc",
        stale_after_hours=1,
        limit=100,
        offset=0,
        db=db,
    )
    assert api_view["success"] is True
    assert len(api_view["items"]) >= 1
    assert all(item["is_stale"] is True for item in api_view["items"])


def test_dedup_correctness_exact_duplicate_relationships(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = FileIndexService(db)

    root = tmp_path / "dupes"
    root.mkdir()
    (root / "a.txt").write_text("same content", encoding="utf-8")
    (root / "b.txt").write_text("same content", encoding="utf-8")

    indexed = svc.index_roots([str(root)], allowed_exts={".txt"})
    assert indexed["indexed"] == 2
    assert indexed["dedupe"]["groups"] == 1
    assert indexed["dedupe"]["relationships"] == 1

    items, _ = db.list_indexed_files(limit=10, offset=0, ext=".txt")
    ids = sorted([it["id"] for it in items])
    rel = db.get_file_duplicate_relationships(ids[0])
    assert rel["found"] is True
    assert len(rel["canonical_for"]) == 1


def test_recursive_scanner_and_mounted_path_normalization(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = FileIndexService(db)

    nested = tmp_path / "root" / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "deep.md").write_text("# deep", encoding="utf-8")

    recursive = svc.index_roots([str(tmp_path / "root")], recursive=True, allowed_exts={".md"})
    assert recursive["indexed"] == 1

    non_recursive = svc.index_roots([str(tmp_path / "root")], recursive=False, allowed_exts={".md"})
    assert non_recursive["indexed"] == 0

    assert normalize_runtime_path(r"E:\Project\smart_document_organizer-main") == "/mnt/e/Project/smart_document_organizer-main"
    # Non-Windows absolute paths remain usable.
    assert os.path.isabs(normalize_runtime_path(str(Path("/tmp/example"))))


@pytest.mark.asyncio
async def test_file_workflows_are_file_id_based(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = FileIndexService(db)

    root = tmp_path / "workflow"
    root.mkdir()
    (root / "workflow.md").write_text("# Workflow\n", encoding="utf-8")
    indexed = svc.index_roots([str(root)], allowed_exts={".md"})
    assert indexed["indexed"] == 1

    items, _ = db.list_indexed_files(limit=10, offset=0)
    file_id = items[0]["id"]

    quality = await files_routes.file_quality(file_id=file_id, db=db)
    entities = await files_routes.file_entities(file_id=file_id, db=db)
    timeline = await files_routes.file_timeline_events(file_id=file_id, db=db)

    assert quality["success"] is True
    assert entities["success"] is True
    assert timeline["success"] is True
    assert quality["file_id"] == file_id
    assert entities["file_id"] == file_id
    assert timeline["file_id"] == file_id
