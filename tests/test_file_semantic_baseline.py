from mem_db.database import DatabaseManager
from services.semantic_file_service import SemanticFileService


def test_semantic_baseline_chunk_embedding_and_search(tmp_path):
    db_path = tmp_path / "semantic_test.db"
    db = DatabaseManager(str(db_path))

    doc_path = tmp_path / "sample.md"
    doc_path.write_text("# Intro\nAlpha beta gamma\n\n# Next\nDelta epsilon zeta\n", encoding="utf-8")

    file_id = db.upsert_indexed_file(
        display_name=doc_path.name,
        original_path=str(doc_path),
        normalized_path=str(doc_path),
        file_size=doc_path.stat().st_size,
        mtime=doc_path.stat().st_mtime,
        mime_type="text/markdown",
        mime_source="test",
        sha256="abc",
        ext=".md",
        status="ready",
        metadata={},
    )

    svc = SemanticFileService(db)
    res = svc.enrich_file(file_id)

    assert res["success"] is True
    assert res["chunks"] >= 1
    assert res["embeddings"] == res["chunks"]

    chunks = db.list_file_chunks(file_id)
    assert len(chunks) == res["chunks"]

    first_chunk_text = chunks[0]["content"]
    query_embedding = svc._deterministic_embedding(first_chunk_text)
    hits = db.semantic_similarity_search(
        query_embedding=query_embedding,
        embedding_model="local-hash-v1",
        limit=3,
    )
    assert len(hits) >= 1
    assert hits[0]["file_id"] == file_id
    assert hits[0]["similarity"] > 0.99
