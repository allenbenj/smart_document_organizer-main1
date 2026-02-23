from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List


class OrganizationAuditStore:
    """Local SQLite event store for organization workflow actions."""

    def __init__(self, db_path: str | None = None) -> None:
        default_path = Path("logs") / "organization_audit.db"
        self.db_path = Path(db_path) if db_path else default_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS organization_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_org_events_type ON organization_events(event_type)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_org_events_created ON organization_events(created_at DESC)"
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS organization_learning_cases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER,
                        event_type TEXT NOT NULL,
                        action TEXT,
                        outcome TEXT,
                        proposal_id INTEGER,
                        file_id INTEGER,
                        root_scope TEXT,
                        current_path TEXT,
                        recommended_folder TEXT,
                        recommended_filename TEXT,
                        final_folder TEXT,
                        final_filename TEXT,
                        old_path TEXT,
                        new_path TEXT,
                        confidence REAL,
                        provider TEXT,
                        model TEXT,
                        note TEXT,
                        error TEXT,
                        payload_json TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_org_cases_proposal_id ON organization_learning_cases(proposal_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_org_cases_file_id ON organization_learning_cases(file_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_org_cases_action ON organization_learning_cases(action)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_org_cases_outcome ON organization_learning_cases(outcome)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_org_cases_created ON organization_learning_cases(created_at DESC)"
                )
                conn.commit()

    @staticmethod
    def _canonical_case(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Build normalized learning record from raw event payload."""
        proposal = payload.get("proposal") if isinstance(payload.get("proposal"), dict) else {}
        current_path = str(
            payload.get("current_path")
            or payload.get("old_path")
            or proposal.get("current_path")
            or ""
        ).strip()
        recommended_folder = str(
            payload.get("recommended_folder")
            or payload.get("proposed_folder")
            or proposal.get("recommended_folder")
            or proposal.get("proposed_folder")
            or ""
        ).strip()
        recommended_filename = str(
            payload.get("recommended_filename")
            or payload.get("proposed_filename")
            or proposal.get("recommended_filename")
            or proposal.get("proposed_filename")
            or ""
        ).strip()
        final_folder = str(payload.get("final_folder") or "").strip()
        final_filename = str(payload.get("final_filename") or "").strip()
        old_path = str(payload.get("old_path") or current_path or "").strip()
        new_path = str(payload.get("new_path") or payload.get("to_path") or "").strip()

        action = str(payload.get("action") or event_type or "").strip().lower()
        outcome = str(payload.get("outcome") or "").strip().lower()
        if not outcome:
            if payload.get("ok") is True:
                outcome = "success"
            elif payload.get("ok") is False:
                outcome = "failed"
        if event_type == "apply_result" and not outcome:
            outcome = "success" if bool(payload.get("ok")) else "failed"

        if not final_folder:
            if action in {"edit_approve", "refine_approve"}:
                final_folder = recommended_folder
        if not final_filename:
            if action in {"edit_approve", "refine_approve"}:
                final_filename = recommended_filename

        return {
            "event_type": str(event_type),
            "action": action or None,
            "outcome": outcome or None,
            "proposal_id": payload.get("proposal_id") or proposal.get("proposal_id"),
            "file_id": payload.get("file_id") or proposal.get("file_id"),
            "root_scope": payload.get("root") or payload.get("root_scope"),
            "current_path": current_path or None,
            "recommended_folder": recommended_folder or None,
            "recommended_filename": recommended_filename or None,
            "final_folder": final_folder or None,
            "final_filename": final_filename or None,
            "old_path": old_path or None,
            "new_path": new_path or None,
            "confidence": payload.get("confidence") or proposal.get("confidence"),
            "provider": payload.get("provider") or proposal.get("provider"),
            "model": payload.get("model") or proposal.get("model"),
            "note": payload.get("note"),
            "error": payload.get("error"),
            "payload_json": json.dumps(payload, ensure_ascii=False),
        }

    def log_event(self, event_type: str, payload: Dict[str, Any]) -> int:
        safe_payload = payload if isinstance(payload, dict) else {"raw": str(payload)}
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO organization_events (event_type, payload_json) VALUES (?, ?)",
                    (str(event_type), json.dumps(safe_payload, ensure_ascii=False)),
                )
                event_id = int(cur.lastrowid)
                case = self._canonical_case(str(event_type), safe_payload)
                conn.execute(
                    """
                    INSERT INTO organization_learning_cases (
                        event_id, event_type, action, outcome, proposal_id, file_id, root_scope,
                        current_path, recommended_folder, recommended_filename,
                        final_folder, final_filename, old_path, new_path,
                        confidence, provider, model, note, error, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        case.get("event_type"),
                        case.get("action"),
                        case.get("outcome"),
                        case.get("proposal_id"),
                        case.get("file_id"),
                        case.get("root_scope"),
                        case.get("current_path"),
                        case.get("recommended_folder"),
                        case.get("recommended_filename"),
                        case.get("final_folder"),
                        case.get("final_filename"),
                        case.get("old_path"),
                        case.get("new_path"),
                        case.get("confidence"),
                        case.get("provider"),
                        case.get("model"),
                        case.get("note"),
                        case.get("error"),
                        case.get("payload_json"),
                    ),
                )
                conn.commit()
                return event_id

    def list_events(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, event_type, payload_json, created_at
                    FROM organization_events
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (max(1, int(limit)),),
                ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            try:
                item["payload"] = json.loads(item.get("payload_json") or "{}")
            except json.JSONDecodeError:
                logging.warning("Failed to decode payload_json for event ID %s", item.get("id"))
                item["payload"] = {"_error": "JSON decode failed"}
            except Exception as e:
                logging.exception("Unexpected error processing event ID %s: %s", item.get("id"), e)
                item["payload"] = {"_error": f"Unexpected error: {e}"}
            out.append(item)
        return out

    def list_learning_cases(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, event_id, event_type, action, outcome, proposal_id, file_id, root_scope,
                           current_path, recommended_folder, recommended_filename,
                           final_folder, final_filename, old_path, new_path,
                           confidence, provider, model, note, error, payload_json, created_at
                    FROM organization_learning_cases
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (max(1, int(limit)),),
                ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            try:
                item["payload"] = json.loads(item.get("payload_json") or "{}")
            except json.JSONDecodeError:
                logging.warning("Failed to decode payload_json for learning case ID %s", item.get("id"))
                item["payload"] = {"_error": "JSON decode failed"}
            except Exception as e:
                logging.exception("Unexpected error processing learning case ID %s: %s", item.get("id"), e)
                item["payload"] = {"_error": f"Unexpected error: {e}"}
            out.append(item)
        return out
