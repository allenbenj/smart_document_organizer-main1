"""SQLite-backed persistence for memory proposals.

Stores proposed memory entries for human review before writing to unified memory.
"""

import json
import sqlite3  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "memory_proposals.db"


def _ensure_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def _conn():
    _ensure_dir()
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_schema() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS memory_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                agent_id TEXT,
                document_id TEXT,
                metadata_json TEXT,
                confidence REAL DEFAULT 1.0,
                importance REAL DEFAULT 1.0,
                status TEXT DEFAULT 'pending',
                flags_json TEXT,
                stored_record_id TEXT,
                created_at TEXT,
                approved_at TEXT,
                rejected_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_proposals_status ON memory_proposals(status);
            CREATE INDEX IF NOT EXISTS idx_proposals_ns_key ON memory_proposals(namespace, key);
            """)


def add_proposal(data: Dict[str, Any]) -> int:
    init_schema()
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO memory_proposals
            (namespace, key, content, memory_type, agent_id, document_id, metadata_json,
             confidence, importance, status, flags_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("namespace"),
                data.get("key"),
                data.get("content"),
                data.get("memory_type", "analysis"),
                data.get("agent_id"),
                data.get("document_id"),
                json.dumps(data.get("metadata") or {}),
                float(data.get("confidence_score", 1.0)),
                float(data.get("importance_score", 1.0)),
                data.get("status", "pending"),
                json.dumps(data.get("flags") or []),
                data.get("created_at"),
            ),
        )
        return int(cur.lastrowid)


def list_proposals(limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
    init_schema()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM memory_proposals ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def get_proposal(pid: int) -> Optional[Dict[str, Any]]:
    """Fetch one proposal by id."""
    init_schema()
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM memory_proposals WHERE id = ?",
            (int(pid),),
        ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)


def approve_proposal(pid: int, stored_record_id: str, approved_at: str) -> bool:
    init_schema()
    with _conn() as con:
        cur = con.execute(
            """
            UPDATE memory_proposals
            SET status='approved', stored_record_id=?, approved_at=?
            WHERE id=?
            """,
            (stored_record_id, approved_at, pid),
        )
        return cur.rowcount > 0


def reject_proposal(pid: int, rejected_at: str) -> bool:
    init_schema()
    with _conn() as con:
        cur = con.execute(
            "UPDATE memory_proposals SET status='rejected', rejected_at=? WHERE id=?",
            (rejected_at, pid),
        )
        return cur.rowcount > 0


def delete_proposal(pid: int) -> bool:
    """Permanently delete a proposal row."""
    init_schema()
    with _conn() as con:
        cur = con.execute("DELETE FROM memory_proposals WHERE id=?", (pid,))
        return cur.rowcount > 0


def update_proposal(pid: int, content: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Update the content and metadata_json of a pending proposal."""
    init_schema()
    with _conn() as con:
        updates = []
        params = []
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if metadata is not None:
            updates.append("metadata_json = ?")
            params.append(json.dumps(metadata))
        if not updates:
            return False
        params.append(pid)
        cur = con.execute(
            f"UPDATE memory_proposals SET {', '.join(updates)} WHERE id=?",
            params,
        )
        return cur.rowcount > 0


def stats() -> Dict[str, Any]:
    init_schema()
    with _conn() as con:
        total = con.execute("SELECT COUNT(*) FROM memory_proposals").fetchone()[0]
        by_status_rows = con.execute(
            "SELECT status, COUNT(*) c FROM memory_proposals GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["c"] for r in by_status_rows}
        flags_rows = con.execute(
            "SELECT flags_json FROM memory_proposals WHERE flags_json IS NOT NULL AND flags_json <> ''"
        ).fetchall()
        flag_counts: Dict[str, int] = {}
        for r in flags_rows:
            try:
                flags = json.loads(r["flags_json"]) or []
                for f in flags:
                    flag_counts[f] = flag_counts.get(f, 0) + 1
            except Exception:
                pass
        return {"total": total, "by_status": by_status, "flags": flag_counts}


def _row_to_dict(r: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": r["id"],
        "namespace": r["namespace"],
        "key": r["key"],
        "content": r["content"],
        "memory_type": r["memory_type"],
        "agent_id": r["agent_id"],
        "document_id": r["document_id"],
        "metadata": json.loads(r["metadata_json"] or "{}"),
        "confidence_score": r["confidence"],
        "importance_score": r["importance"],
        "status": r["status"],
        "flags": json.loads(r["flags_json"] or "[]"),
        "stored_record_id": r["stored_record_id"],
        "created_at": r["created_at"],
        "approved_at": r["approved_at"],
        "rejected_at": r["rejected_at"],
    }
