from __future__ import annotations

import argparse
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_PHASES = {"p1", "p2", "p3"}


@dataclass(frozen=True)
class PhaseScripts:
    up: Path
    down: Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_db_path() -> Path:
    return Path(__file__).resolve().parents[1] / "mem_db" / "data" / "documents.db"


def _phase_scripts(phase: str) -> PhaseScripts:
    base = Path(__file__).resolve().parents[1] / "mem_db" / "migrations" / "phases"
    return PhaseScripts(
        up=base / f"{phase}_up.sql",
        down=base / f"{phase}_down.sql",
    )


def _require_sql(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Migration SQL not found: {path}")
    sql = path.read_text(encoding="utf-8").strip()
    if not sql:
        raise ValueError(f"Migration SQL is empty: {path}")
    return sql


def _integrity_check(conn: sqlite3.Connection) -> dict[str, Any]:
    integrity_rows = conn.execute("PRAGMA integrity_check").fetchall()
    fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    integrity_values = [str(r[0]) for r in integrity_rows]
    return {
        "integrity_check": integrity_values,
        "foreign_key_violations": len(fk_rows),
    }


def _apply_sql(conn: sqlite3.Connection, sql: str) -> None:
    conn.executescript(sql)


def _run_phase(conn: sqlite3.Connection, phase: str, direction: str) -> dict[str, Any]:
    scripts = _phase_scripts(phase)
    sql_path = scripts.up if direction == "up" else scripts.down
    sql = _require_sql(sql_path)
    _apply_sql(conn, sql)
    return {
        "phase": phase,
        "direction": direction,
        "script": str(sql_path),
    }


def _run_command(
    *,
    command: str,
    phase: str,
    db_path: Path,
    verify_data_integrity: bool,
    retries: int,
    retry_delay_ms: int,
) -> dict[str, Any]:
    if phase not in VALID_PHASES:
        raise ValueError(f"Unsupported phase '{phase}'. Supported: {sorted(VALID_PHASES)}")
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    result: dict[str, Any] = {
        "status": "fail",
        "command": command,
        "phase": phase,
        "db_path": str(db_path),
        "started_at": _now(),
        "steps": [],
    }

    last_error: Exception | None = None
    attempts = max(1, int(retries) + 1)
    for attempt in range(1, attempts + 1):
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            if command == "up":
                result["steps"].append(_run_phase(conn, phase, "up"))
            elif command == "down":
                result["steps"].append(_run_phase(conn, phase, "down"))
            elif command == "redo":
                result["steps"].append(_run_phase(conn, phase, "down"))
                result["steps"].append(_run_phase(conn, phase, "up"))
            else:
                raise ValueError(f"Unsupported command: {command}")

            if verify_data_integrity:
                result["integrity"] = _integrity_check(conn)
                if result["integrity"]["integrity_check"] != ["ok"]:
                    raise RuntimeError(
                        "PRAGMA integrity_check failed: "
                        + ",".join(result["integrity"]["integrity_check"])
                    )
                if int(result["integrity"]["foreign_key_violations"]) > 0:
                    raise RuntimeError(
                        f"PRAGMA foreign_key_check returned violations: "
                        f"{result['integrity']['foreign_key_violations']}"
                    )

            conn.commit()
            result["status"] = "pass"
            result["attempts"] = attempt
            result["completed_at"] = _now()
            return result
        except sqlite3.OperationalError as exc:
            msg = str(exc).lower()
            conn.rollback()
            last_error = exc
            if "locked" in msg or "busy" in msg or "disk i/o error" in msg:
                if attempt < attempts:
                    time.sleep(max(0, retry_delay_ms) / 1000.0)
                    continue
            result["error"] = str(exc)
            result["attempts"] = attempt
            result["completed_at"] = _now()
            return result
        except Exception as exc:
            conn.rollback()
            result["error"] = str(exc)
            result["attempts"] = attempt
            result["completed_at"] = _now()
            return result
        finally:
            conn.close()
    if last_error is not None:
        result["error"] = str(last_error)
    result["completed_at"] = _now()
    return result


def _write_report(report_path: Path | None, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text + "\n", encoding="utf-8")
    print(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase migration runner (AEDIS gates)")
    parser.add_argument("command", choices=["up", "down", "redo"])
    parser.add_argument("--phase", required=True, choices=sorted(VALID_PHASES))
    parser.add_argument("--db-path", default=str(_default_db_path()))
    parser.add_argument("--verify-data-integrity", action="store_true")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-delay-ms", type=int, default=300)
    parser.add_argument("--report", default="")
    args = parser.parse_args(argv)

    payload = _run_command(
        command=str(args.command),
        phase=str(args.phase),
        db_path=Path(str(args.db_path)).resolve(),
        verify_data_integrity=bool(args.verify_data_integrity),
        retries=int(args.retries),
        retry_delay_ms=int(args.retry_delay_ms),
    )
    report_path = Path(str(args.report)).resolve() if str(args.report).strip() else None
    _write_report(report_path, payload)
    return 0 if payload.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
