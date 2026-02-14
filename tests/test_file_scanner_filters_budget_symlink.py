from mem_db.database import DatabaseManager
from services.file_index_service import FileIndexService


def test_depth_control_and_runtime_budget(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = FileIndexService(db)

    root = tmp_path / "root"
    (root / "a" / "b").mkdir(parents=True)
    (root / "top.txt").write_text("top", encoding="utf-8")
    (root / "a" / "mid.txt").write_text("mid", encoding="utf-8")
    (root / "a" / "b" / "deep.txt").write_text("deep", encoding="utf-8")

    res_depth = svc.index_roots([str(root)], allowed_exts={".txt"}, max_depth=1)
    assert res_depth["indexed"] == 2

    res_budget = svc.index_roots([str(root)], allowed_exts={".txt"}, max_runtime_seconds=0)
    assert res_budget["truncated"] is True
    assert res_budget.get("runtime_budget_hit") is True


def test_symlink_policy_skip_vs_follow(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = FileIndexService(db)

    root = tmp_path / "root"
    root.mkdir()
    target = root / "target.txt"
    target.write_text("hello", encoding="utf-8")
    link = root / "link.txt"
    link.symlink_to(target)

    skip = svc.index_roots([str(root)], allowed_exts={".txt"}, follow_symlinks=False)
    assert skip["indexed"] == 1

    # force re-index by changing file
    target.write_text("hello2", encoding="utf-8")
    follow = svc.index_roots([str(root)], allowed_exts={".txt"}, follow_symlinks=True)
    assert follow["indexed"] >= 1


def test_preview_snippet_and_confidence_present(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = FileIndexService(db)

    root = tmp_path / "docs"
    root.mkdir()
    (root / "x.txt").write_text("Alpha Beta Gamma\n" * 30, encoding="utf-8")

    res = svc.index_roots([str(root)], allowed_exts={".txt"})
    assert res["indexed"] == 1

    items, _ = db.list_indexed_files(limit=10, offset=0, ext=".txt")
    meta = items[0]["metadata_json"]
    assert "preview_snippet" in meta
    assert isinstance(meta["preview_snippet"].get("text"), str)
    assert "extraction_quality" in meta
    assert 0.0 <= float(meta["extraction_quality"].get("confidence", 0.0)) <= 1.0
