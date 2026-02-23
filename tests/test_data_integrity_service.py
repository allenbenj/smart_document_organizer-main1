from __future__ import annotations

import sqlite3
from pathlib import Path

from services.data_integrity_service import DataIntegrityService


def _init_file_index_db(path: Path) -> None:
    with sqlite3.connect(str(path)) as conn:
        conn.executescript(
            """
            CREATE TABLE files (
                id INTEGER PRIMARY KEY,
                file_path TEXT NOT NULL
            );
            CREATE TABLE file_analysis (
                id INTEGER PRIMARY KEY,
                file_path TEXT NOT NULL
            );
            """
        )
        conn.execute("INSERT INTO files (file_path) VALUES (?)", ("src/a.py",))
        conn.execute("INSERT INTO file_analysis (file_path) VALUES (?)", ("src/missing.py",))
        conn.commit()


def _init_unified_memory_db(path: Path) -> None:
    with sqlite3.connect(str(path)) as conn:
        conn.executescript(
            """
            CREATE TABLE memory_records (
                record_id TEXT PRIMARY KEY,
                content TEXT,
                confidence_score REAL
            );
            CREATE TABLE memory_code_links (
                memory_record_id TEXT NOT NULL,
                file_path TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO memory_records (record_id, content, confidence_score) VALUES (?, ?, ?)",
            ("r1", "", 1.2),
        )
        conn.execute(
            "INSERT INTO memory_code_links (memory_record_id, file_path) VALUES (?, ?)",
            ("missing_record", "src/a.py"),
        )
        conn.commit()


def test_data_integrity_service_reports_expected_issues(tmp_path: Path) -> None:
    file_index_db = tmp_path / "file_index.db"
    unified_memory_db = tmp_path / "unified_memory.db"
    _init_file_index_db(file_index_db)
    _init_unified_memory_db(unified_memory_db)

    service = DataIntegrityService(
        file_index_db_path=file_index_db,
        unified_memory_db_path=unified_memory_db,
    )
    report = service.generate_report()

    assert report["status"] == "issues_detected"
    assert report["total_checks"] == 5
    assert report["total_issues"] >= 4

    by_check = {item["check_name"]: item for item in report["issues"]}
    assert by_check["file_analysis_orphans"]["issue_count"] == 1
    assert by_check["files_without_analysis"]["issue_count"] == 1
    assert by_check["memory_code_orphan_links"]["issue_count"] == 1
    assert by_check["empty_memory_content"]["issue_count"] == 1
    assert by_check["invalid_memory_confidence"]["issue_count"] == 1


def test_data_integrity_service_handles_missing_databases(tmp_path: Path) -> None:
    service = DataIntegrityService(
        file_index_db_path=tmp_path / "missing_file_index.db",
        unified_memory_db_path=tmp_path / "missing_unified_memory.db",
    )
    report = service.generate_report()

    assert report["status"] == "issues_detected"
    assert report["total_checks"] == 2
    assert report["total_issues"] == 2
