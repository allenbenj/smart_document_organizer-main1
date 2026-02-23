from __future__ import annotations

import sqlite3
from pathlib import Path

from services.code_hotspot_service import CodeHotspotService


def _init_file_index_db(path: Path) -> None:
    with sqlite3.connect(str(path)) as conn:
        conn.executescript(
            """
            CREATE TABLE files (
                id INTEGER PRIMARY KEY,
                file_path TEXT NOT NULL
            );
            CREATE TABLE file_change_history (
                id INTEGER PRIMARY KEY,
                file_path TEXT NOT NULL
            );
            CREATE TABLE file_issues (
                id INTEGER PRIMARY KEY,
                file_id INTEGER NOT NULL,
                severity TEXT,
                status TEXT
            );
            CREATE TABLE file_analysis (
                id INTEGER PRIMARY KEY,
                file_path TEXT NOT NULL,
                complexity_score REAL
            );
            """
        )
        conn.execute("INSERT INTO files (id, file_path) VALUES (?, ?)", (1, "src/high.py"))
        conn.execute("INSERT INTO files (id, file_path) VALUES (?, ?)", (2, "src/low.py"))

        for _ in range(10):
            conn.execute(
                "INSERT INTO file_change_history (file_path) VALUES (?)",
                ("src/high.py",),
            )
        conn.execute("INSERT INTO file_change_history (file_path) VALUES (?)", ("src/low.py",))

        conn.execute(
            "INSERT INTO file_issues (file_id, severity, status) VALUES (?, ?, ?)",
            (1, "critical", "open"),
        )
        conn.execute(
            "INSERT INTO file_issues (file_id, severity, status) VALUES (?, ?, ?)",
            (2, "low", "open"),
        )

        conn.execute(
            "INSERT INTO file_analysis (file_path, complexity_score) VALUES (?, ?)",
            ("src/high.py", 9.0),
        )
        conn.execute(
            "INSERT INTO file_analysis (file_path, complexity_score) VALUES (?, ?)",
            ("src/low.py", 1.0),
        )
        conn.commit()


def test_hotspot_service_ranks_high_risk_file_first(tmp_path: Path) -> None:
    db_path = tmp_path / "file_index.db"
    _init_file_index_db(db_path)
    service = CodeHotspotService(file_index_db_path=db_path)

    hotspots = service.get_hotspots(limit=10)
    assert len(hotspots) == 2
    assert hotspots[0]["file_path"] == "src/high.py"
    assert hotspots[0]["hotspot_score"] > hotspots[1]["hotspot_score"]
    assert hotspots[0]["risk_level"] in {"high", "critical"}
    assert hotspots[0]["recommended_action"]


def test_hotspot_service_missing_db_returns_empty(tmp_path: Path) -> None:
    service = CodeHotspotService(file_index_db_path=tmp_path / "missing.db")
    assert service.get_hotspots(limit=10) == []
