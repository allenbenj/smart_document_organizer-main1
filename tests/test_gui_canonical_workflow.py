from __future__ import annotations

import sqlite3
from pathlib import Path

from mem_db.repositories.canonical_repository import CanonicalRepository
from services.canonical_artifact_service import CanonicalArtifactService


SHA = "c" * 64


def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _apply_p1_schema(db_path: Path) -> None:
    sql = Path("mem_db/migrations/phases/p1_up.sql").read_text(encoding="utf-8")
    with _connect(db_path) as conn:
        conn.executescript(sql)
        conn.commit()


def _repo(db_path: Path) -> CanonicalRepository:
    def connection_factory():
        return _connect(db_path)

    return CanonicalRepository(connection_factory)


def test_canonical_ingest_and_lineage_flow_for_gui_workflow(tmp_path: Path) -> None:
    db_path = tmp_path / "canonical_gui.db"
    _apply_p1_schema(db_path)
    service = CanonicalArtifactService(_repo(db_path))

    artifact_row_id = service.ingest_artifact(
        artifact_id="artifact-gui-1",
        sha256=SHA,
        source_uri="file:///gui.pdf",
        mime_type="application/pdf",
        metadata={"source": "gui"},
        blob_locator="blob://canonical/gui-1",
        content_size_bytes=1234,
    )

    service.append_lineage_event(
        artifact_row_id=artifact_row_id,
        event_type="lineage_inspected",
        event_data={"origin": "gui"},
    )

    lineage = service.get_lineage(artifact_row_id)
    assert [item["event_type"] for item in lineage] == ["ingested", "lineage_inspected"]
