from __future__ import annotations


def test_watch_repository_roundtrip(temp_db_manager):
    db = temp_db_manager

    wid = db.upsert_watched_directory(
        original_path="E:/Organization_Folder",
        normalized_path="/mnt/e/Organization_Folder",
        recursive=True,
        keywords=["legal", "invoice"],
        allowed_exts=[".pdf", ".docx"],
        active=True,
    )
    assert isinstance(wid, int) and wid > 0

    rows = db.list_watched_directories(active_only=True)
    assert rows and rows[0]["normalized_path"] == "/mnt/e/Organization_Folder"

    db.scan_manifest_upsert(
        path_hash="abc123",
        normalized_path="/mnt/e/Organization_Folder/file.pdf",
        file_size=123,
        mtime=1.0,
        sha256="deadbeef",
        last_status="ready",
        last_error=None,
    )
    rec = db.scan_manifest_get("abc123")
    assert rec is not None
    assert rec["sha256"] == "deadbeef"


def test_document_repository_roundtrip(temp_db_manager):
    db = temp_db_manager

    from utils.models import DocumentCreate, SearchQuery, TagCreate

    created = db.create_document(
        DocumentCreate(
            file_name="test-contract.docx",
            file_type="docx",
            category="Legal/Contracts",
            file_path="/tmp/test-contract.docx",
            primary_purpose="contract_review",
            content_text="This agreement is made between Acme LLC and Ben.",
            content_type="text/plain",
        )
    )

    assert created.id > 0

    tags = db.add_document_tags(created.id, [TagCreate(tag_name="client", tag_value="Acme")])
    assert len(tags) == 1

    results, total = db.search_documents(SearchQuery(query="agreement", limit=10, offset=0))
    assert total >= 1
    assert any(r.id == created.id for r in results)

    stats = db.get_database_stats()
    assert stats["total_documents"] >= 1
