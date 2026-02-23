from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

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
            ("artifact-2", "b" * 64),
        )
        conn.commit()


def test_provenance_trace_reconstructs_record(tmp_path: Path) -> None:
    db_path = tmp_path / "p3_trace.db"
    _init_schema(db_path)
    service = ProvenanceService(_DbStub(db_path))

    original = ProvenanceRecord(
        source_artifact_row_id=1,
        source_sha256="b" * 64,
        captured_at=datetime(2026, 2, 19, tzinfo=UTC),
        extractor="trace-test",
        spans=[EvidenceSpan(artifact_row_id=1, start_char=10, end_char=20, quote="example")],
        notes="trace",
    )

    service.record_provenance(original, target_type="analysis", target_id="analysis-1")
    reconstructed = service.get_provenance_for_artifact("analysis", "analysis-1")

    assert reconstructed is not None
    assert reconstructed.source_artifact_row_id == 1
    assert reconstructed.source_sha256 == "b" * 64
    assert reconstructed.extractor == "trace-test"
    assert reconstructed.spans[0].start_char == 10
    assert reconstructed.spans[0].end_char == 20
