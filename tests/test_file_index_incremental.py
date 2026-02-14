from mem_db.database import DatabaseManager
from services.file_index_service import FileIndexService


def test_index_roots_skips_unchanged_files_incrementally(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = FileIndexService(db)

    root = tmp_path / "docs"
    root.mkdir()
    f = root / "note.md"
    f.write_text("# Title\nhello world\n", encoding="utf-8")

    first = svc.index_roots([str(root)], allowed_exts={".md"})
    assert first["success"] is True
    assert first["indexed"] == 1
    assert first["skipped"] == 0

    second = svc.index_roots([str(root)], allowed_exts={".md"})
    assert second["success"] is True
    assert second["indexed"] == 0
    assert second["skipped"] == 1

    # change file so it is reprocessed
    f.write_text("# Title\nhello world changed\n", encoding="utf-8")
    third = svc.index_roots([str(root)], allowed_exts={".md"})
    assert third["indexed"] == 1
    assert third["skipped"] == 0
