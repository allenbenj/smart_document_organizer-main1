from __future__ import annotations

import sqlite3
from pathlib import Path

from mem_db.repositories.canonical_repository import CanonicalRepository
from services.canonical_artifact_service import CanonicalArtifactService


SHA = "b" * 64


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


def test_lineage_events_reference_artifact_row_id_fk(tmp_path: Path) -> None:
    db_path = tmp_path / "canonical_lineage.db"
    _apply_p1_schema(db_path)
    service = CanonicalArtifactService(_repo(db_path))

    artifact_row_id = service.ingest_artifact(
        artifact_id="artifact-3",
        sha256=SHA,
        source_uri="file:///b.txt",
    )
    service.append_lineage_event(
        artifact_row_id=artifact_row_id,
        event_type="validated",
        event_data={"by": "judge"},
    )

    lineage = service.get_lineage(artifact_row_id)
    assert len(lineage) == 2
    assert lineage[0]["event_type"] == "ingested"
    assert lineage[1]["event_type"] == "validated"
    assert lineage[1]["artifact_row_id"] == artifact_row_id
