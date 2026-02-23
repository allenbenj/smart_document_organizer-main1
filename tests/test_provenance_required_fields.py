from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from services.contracts.aedis_models import EvidenceSpan, ProvenanceRecord
from services.provenance_service import ProvenanceService


class _DbStub:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _init_schema(db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE canonical_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_id TEXT NOT NULL,
                sha256 TEXT NOT NULL
            );
            """
        )
        p3_sql = Path("mem_db/migrations/phases/p3_up.sql").read_text(encoding="utf-8")
        conn.executescript(p3_sql)
        conn.execute(
            "INSERT INTO canonical_artifacts (artifact_id, sha256) VALUES (?, ?)",
            ("artifact-1", "a" * 64),
        )
        conn.commit()


def test_record_provenance_requires_evidence_span(tmp_path: Path) -> None:
    db_path = tmp_path / "p3_required.db"
    _init_schema(db_path)
    service = ProvenanceService(_DbStub(db_path))

    record = ProvenanceRecord(
        source_artifact_row_id=1,
        source_sha256="a" * 64,
        captured_at=datetime(2026, 2, 19, tzinfo=UTC),
        extractor="unit-test",
        spans=[],
    )

    with pytest.raises(RuntimeError):
        service.record_provenance(record, target_type="analysis", target_id="a-1")


def test_record_provenance_rejects_invalid_span_offsets() -> None:
    with pytest.raises(Exception):
        EvidenceSpan(artifact_row_id=1, start_char=5, end_char=5)
