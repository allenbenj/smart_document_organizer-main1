from mem_db.database import DatabaseManager
from routes.files import _extract_candidate_entities
from services.file_index_service import FileIndexService


def _rows(db: DatabaseManager):
    with db.get_connection() as conn:
        return conn.execute("SELECT id, display_name, status, metadata_json FROM files_index ORDER BY id").fetchall()


def test_golden_dataset_legal_forensic_like_samples(tmp_path):
    root = tmp_path / "golden"
    root.mkdir()

    (root / "chain_of_custody.md").write_text(
        "# Chain of Custody\n"
        "Case #A-1029\n"
        "Judge Alice Monroe reviewed Delta-9 THC lab report on 2025-12-31 in Austin, TX.\n",
        encoding="utf-8",
    )
    (root / "lab_report.txt").write_text(
        "Lab report: CBD and HHC values attached for Case B-4401 dated 01/04/2026.",
        encoding="utf-8",
    )
    (root / "evidence_log.csv").write_text(
        "item_id,desc\n1,photo evidence\n2,instruction sheet\n",
        encoding="utf-8",
    )

    db = DatabaseManager(str(tmp_path / "golden.db"))
    svc = FileIndexService(db)

    res = svc.index_roots([str(root)], recursive=True)
    assert res["success"] is True
    assert res["indexed"] == 3

    rows = _rows(db)
    assert len(rows) == 3
    assert all(r[2] == "ready" for r in rows)

    md_meta = next(r[3] for r in rows if r[1] == "chain_of_custody.md")
    txt_meta = next(r[3] for r in rows if r[1] == "lab_report.txt")

    md_tags = set((md_meta or {}).get("rule_tags") or [])
    txt_tags = set((txt_meta or {}).get("rule_tags") or [])

    assert "document:lab-report" in md_tags
    assert "domain:thc" in md_tags
    assert "legal:case-number" in md_tags
    assert "entity:date" in md_tags

    assert "document:lab-report" in txt_tags
    assert "domain:cbd" in txt_tags
    assert "domain:hhc" in txt_tags

    candidates = _extract_candidate_entities((md_meta or {}).get("preview") or "")
    labels = {c["label"] for c in candidates}
    texts = {c["text"] for c in candidates}

    assert {"Person", "Date", "DomainTerm"}.issubset(labels)
    assert "Alice Monroe" in texts
    assert "2025-12-31" in texts
