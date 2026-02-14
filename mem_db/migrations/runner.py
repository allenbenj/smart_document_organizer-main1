from __future__ import annotations

import argparse
import importlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

MIGRATION_MODULES = [
    "mem_db.migrations.versions.0001_baseline",
    "mem_db.migrations.versions.0002_legacy_schema_upgrades",
]


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            checksum TEXT,
            success INTEGER NOT NULL,
            error TEXT
        )
        """
    )


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    rows = conn.execute(
        "SELECT version FROM schema_migrations WHERE success = 1 ORDER BY version"
    ).fetchall()
    return {int(r[0]) for r in rows}


def apply_migrations(conn: sqlite3.Connection, *, strict: bool = True) -> List[Dict[str, Any]]:
    _ensure_migrations_table(conn)
    applied = _applied_versions(conn)
    out: List[Dict[str, Any]] = []

    for module_name in MIGRATION_MODULES:
        mod = importlib.import_module(module_name)
        version = int(getattr(mod, "VERSION"))
        name = str(getattr(mod, "NAME"))

        if version in applied:
            out.append({"version": version, "name": name, "status": "already_applied"})
            continue

        try:
            mod.up(conn)
            conn.execute(
                "INSERT OR REPLACE INTO schema_migrations (version, name, checksum, success, error) VALUES (?, ?, ?, 1, NULL)",
                (version, name, None),
            )
            out.append({"version": version, "name": name, "status": "applied"})
        except Exception as e:
            conn.execute(
                "INSERT OR REPLACE INTO schema_migrations (version, name, checksum, success, error) VALUES (?, ?, ?, 0, ?)",
                (version, name, None, str(e)),
            )
            out.append({"version": version, "name": name, "status": "failed", "error": str(e)})
            if strict:
                raise

    return out


def migration_status(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    _ensure_migrations_table(conn)
    rows = conn.execute(
        "SELECT version, name, applied_at, success, error FROM schema_migrations ORDER BY version"
    ).fetchall()
    return [
        {
            "version": int(r[0]),
            "name": str(r[1]),
            "applied_at": r[2],
            "success": bool(r[3]),
            "error": r[4],
        }
        for r in rows
    ]


def _default_db_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "documents.db"


def _open_connection(db_path: str | None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else _default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _cmd_status(db_path: str | None) -> int:
    conn = _open_connection(db_path)
    try:
        print(json.dumps({"success": True, "items": migration_status(conn)}, indent=2))
        return 0
    finally:
        conn.close()


def _cmd_migrate(db_path: str | None, strict: bool = True) -> int:
    conn = _open_connection(db_path)
    try:
        items = apply_migrations(conn, strict=strict)
        conn.commit()
        print(json.dumps({"success": True, "applied": items}, indent=2))
        return 0
    except Exception as e:
        conn.rollback()
        print(json.dumps({"success": False, "error": str(e)}, indent=2))
        return 1
    finally:
        conn.close()


def _cmd_current(db_path: str | None) -> int:
    conn = _open_connection(db_path)
    try:
        items = migration_status(conn)
        current = max((x["version"] for x in items if x.get("success")), default=0)
        print(json.dumps({"success": True, "current": current}, indent=2))
        return 0
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Schema migration runner")
    parser.add_argument("command", choices=["status", "migrate", "current"])
    parser.add_argument("--db-path", dest="db_path", default=None, help="Path to sqlite db file")
    parser.add_argument("--strict", dest="strict", action="store_true", default=True, help="Fail fast on first migration error (default)")
    parser.add_argument("--no-strict", dest="strict", action="store_false", help="Record migration failures and continue")
    args = parser.parse_args(argv)

    if args.command == "status":
        return _cmd_status(args.db_path)
    if args.command == "migrate":
        return _cmd_migrate(args.db_path, strict=bool(args.strict))
    return _cmd_current(args.db_path)


if __name__ == "__main__":
    raise SystemExit(main())
