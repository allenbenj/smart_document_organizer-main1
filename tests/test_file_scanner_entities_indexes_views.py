import sqlite3

from mem_db.database import DatabaseManager


def test_entities_links_materialized_views_and_indexes(tmp_path):
    db = DatabaseManager(str(tmp_path / "scanner.db"))

    fid1 = db.upsert_indexed_file(
        display_name="alpha_report.txt",
        original_path="/tmp/case/alpha_report.txt",
        normalized_path="/tmp/case/alpha_report.txt",
        file_size=100,
        mtime=1700000000.0,
        mime_type="text/plain",
        mime_source="mimetypes",
        sha256="h1",
        ext=".txt",
        status="ready",
        metadata={"preview": "Judge Alice reviewed contract on 2025-12-31", "rule_tags": ["lab_report"]},
    )
    fid2 = db.upsert_indexed_file(
        display_name="beta_report.txt",
        original_path="/tmp/case/beta_report.txt",
        normalized_path="/tmp/case/beta_report.txt",
        file_size=120,
        mtime=1700000100.0,
        mime_type="text/plain",
        mime_source="mimetypes",
        sha256="h2",
        ext=".txt",
        status="ready",
        metadata={"preview": "Judge Bob reviewed contract"},
    )

    db.replace_file_entities(
        file_id=fid1,
        entities=[{"text": "Judge", "entity_type": "Person", "ontology_id": "judge", "confidence": 0.8}],
    )
    db.replace_file_entities(
        file_id=fid2,
        entities=[{"text": "Judge", "entity_type": "Person", "ontology_id": "judge", "confidence": 0.82}],
    )

    inserted_links = db.refresh_file_entity_links()
    assert inserted_links >= 1
    assert db.list_file_entity_links(fid1)

    mv = db.refresh_materialized_file_summaries()
    assert mv["files"] >= 2

    with db.get_connection() as conn:
        idx_rows = conn.execute("PRAGMA index_list('files_index')").fetchall()
        idx_names = {r[1] for r in idx_rows}
        assert "idx_files_index_path_hash" in idx_names
        assert "idx_files_index_mime" in idx_names

        timeline = conn.execute("SELECT * FROM mv_timeline_summary WHERE file_id = ?", (fid1,)).fetchone()
        keyword = conn.execute("SELECT * FROM mv_keyword_entity_summary WHERE file_id = ?", (fid1,)).fetchone()
        health = conn.execute("SELECT * FROM mv_file_health_summary WHERE file_id = ?", (fid1,)).fetchone()
        assert timeline is not None
        assert keyword is not None
        assert health is not None


def test_chunk_fulltext_index(tmp_path):
    db = DatabaseManager(str(tmp_path / "fts.db"))
    fid = db.upsert_indexed_file(
        display_name="notes.txt",
        original_path="/tmp/notes.txt",
        normalized_path="/tmp/notes.txt",
        file_size=50,
        mtime=1700000000.0,
        mime_type="text/plain",
        mime_source="mimetypes",
        sha256="hs",
        ext=".txt",
        status="ready",
        metadata={},
    )
    db.replace_file_chunks(
        file_id=fid,
        chunks=[{"chunk_index": 0, "title": "Summary", "content": "Timeline includes 2025-12-31 hearing"}],
    )

    hits = db.search_file_chunks_fulltext("timeline", limit=5)
    assert hits
    assert hits[0]["file_id"] == fid
