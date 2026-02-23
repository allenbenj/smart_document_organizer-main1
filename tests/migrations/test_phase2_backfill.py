from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts import migrate


def _init_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()


def test_phase2_migration_redo_verify_data_integrity(tmp_path: Path) -> None:
    db_path = tmp_path / "phase2.db"
    _init_db(db_path)

    up = migrate._run_command(
        command="up",
        phase="p2",
        db_path=db_path,
        verify_data_integrity=True,
        retries=1,
        retry_delay_ms=1,
    )
    assert up["status"] == "pass"

    redo = migrate._run_command(
        command="redo",
        phase="p2",
        db_path=db_path,
        verify_data_integrity=True,
        retries=1,
        retry_delay_ms=1,
    )
    assert redo["status"] == "pass"

    down = migrate._run_command(
        command="down",
        phase="p2",
        db_path=db_path,
        verify_data_integrity=True,
        retries=1,
        retry_delay_ms=1,
    )
    assert down["status"] == "pass"
