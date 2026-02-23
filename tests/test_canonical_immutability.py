from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from mem_db.repositories.canonical_repository import CanonicalRepository
from services.canonical_artifact_service import CanonicalArtifactService


SHA = "a" * 64


def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _apply_p1_schema(db_path: Path) -> None:
    sql = (Path("mem_db/migrations/phases/p1_up.sql").read_text(encoding="utf-8"))
    with _connect(db_path) as conn:
        conn.executescript(sql)
        conn.commit()


def _repo(db_path: Path) -> CanonicalRepository:
    def connection_factory():
        return _connect(db_path)

    return CanonicalRepository(connection_factory)


def test_sql_trigger_blocks_update_and_delete(tmp_path: Path) -> None:
    db_path = tmp_path / "canonical.db"
    _apply_p1_schema(db_path)

    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO canonical_artifacts (artifact_id, sha256)
            VALUES (?, ?)
            """,
            ("artifact-1", SHA),
        )
        row_id = int(cur.lastrowid)
        conn.commit()

        with pytest.raises(sqlite3.DatabaseError):
            conn.execute(
                "UPDATE canonical_artifacts SET source_uri = ? WHERE id = ?",
                ("updated", row_id),
            )

        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM canonical_artifacts WHERE id = ?", (row_id,))


def test_service_enforces_immutability_api(tmp_path: Path) -> None:
    db_path = tmp_path / "canonical_service.db"
    _apply_p1_schema(db_path)
    service = CanonicalArtifactService(_repo(db_path))

    artifact_row_id = service.ingest_artifact(
        artifact_id="artifact-2",
        sha256=SHA,
        source_uri="file:///a.txt",
        mime_type="text/plain",
    )

    assert artifact_row_id > 0
    with pytest.raises(PermissionError):
        service.update_artifact(id=artifact_row_id)
    with pytest.raises(PermissionError):
        service.delete_artifact(id=artifact_row_id)
