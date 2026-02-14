from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .base import BaseRepository


class OrganizationRepository(BaseRepository):
    def add_proposal(self, proposal: Dict[str, Any]) -> int:
        def _op(conn: Any) -> int:
            cur = conn.execute(
                """
                INSERT INTO organization_proposals
                (run_id, file_id, current_path, proposed_folder, proposed_filename, confidence,
                 rationale, alternatives_json, provider, model, status, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.get("run_id"),
                    proposal.get("file_id"),
                    proposal.get("current_path"),
                    proposal.get("proposed_folder"),
                    proposal.get("proposed_filename"),
                    float(proposal.get("confidence", 0.5)),
                    proposal.get("rationale"),
                    json.dumps(proposal.get("alternatives") or []),
                    proposal.get("provider"),
                    proposal.get("model"),
                    proposal.get("status", "proposed"),
                    json.dumps(proposal.get("metadata") or {}),
                ),
            )
            return int(cur.lastrowid)

        return self.write_with_retry(_op)

    def list_proposals(self, *, status: Optional[str] = None, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        where = ""
        params: List[Any] = []
        if status:
            where = "WHERE status = ?"
            params.append(status)
        params.extend([int(limit), int(offset)])
        with self.connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM organization_proposals {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["alternatives"] = json.loads(d.get("alternatives_json") or "[]")
            except Exception:
                d["alternatives"] = []
            try:
                d["metadata"] = json.loads(d.get("metadata_json") or "{}")
            except Exception:
                d["metadata"] = {}
            out.append(d)
        return out

    def get_proposal(self, proposal_id: int) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM organization_proposals WHERE id = ?", (proposal_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["alternatives"] = json.loads(d.get("alternatives_json") or "[]")
        except Exception:
            d["alternatives"] = []
        try:
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
        except Exception:
            d["metadata"] = {}
        return d

    def update_proposal(
        self,
        proposal_id: int,
        *,
        status: Optional[str] = None,
        proposed_folder: Optional[str] = None,
        proposed_filename: Optional[str] = None,
        confidence: Optional[float] = None,
        rationale: Optional[str] = None,
    ) -> bool:
        updates = []
        params: List[Any] = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if proposed_folder is not None:
            updates.append("proposed_folder = ?")
            params.append(proposed_folder)
        if proposed_filename is not None:
            updates.append("proposed_filename = ?")
            params.append(proposed_filename)
        if confidence is not None:
            updates.append("confidence = ?")
            params.append(float(confidence))
        if rationale is not None:
            updates.append("rationale = ?")
            params.append(rationale)
        updates.append("updated_at = CURRENT_TIMESTAMP")
        if not updates:
            return False
        params.append(int(proposal_id))
        def _op(conn: Any) -> bool:
            cur = conn.execute(
                f"UPDATE organization_proposals SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            return (cur.rowcount or 0) > 0

        return self.write_with_retry(_op)

    def add_feedback(self, feedback: Dict[str, Any]) -> int:
        def _op(conn: Any) -> int:
            cur = conn.execute(
                """
                INSERT INTO organization_feedback
                (proposal_id, file_id, action, original_json, final_json, note)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback.get("proposal_id"),
                    feedback.get("file_id"),
                    feedback.get("action"),
                    json.dumps(feedback.get("original") or {}),
                    json.dumps(feedback.get("final") or {}),
                    feedback.get("note"),
                ),
            )
            return int(cur.lastrowid)

        return self.write_with_retry(_op)

    def add_action(self, action: Dict[str, Any]) -> int:
        def _op(conn: Any) -> int:
            cur = conn.execute(
                """
                INSERT INTO organization_actions
                (proposal_id, file_id, action_type, from_path, to_path, success, error, rollback_group)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action.get("proposal_id"),
                    action.get("file_id"),
                    action.get("action_type"),
                    action.get("from_path"),
                    action.get("to_path"),
                    1 if action.get("success") else 0,
                    action.get("error"),
                    action.get("rollback_group"),
                ),
            )
            return int(cur.lastrowid)

        return self.write_with_retry(_op)

    def list_feedback(self, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM organization_feedback ORDER BY id DESC LIMIT ? OFFSET ?",
                (int(limit), int(offset)),
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["original"] = json.loads(d.get("original_json") or "{}")
            except Exception:
                d["original"] = {}
            try:
                d["final"] = json.loads(d.get("final_json") or "{}")
            except Exception:
                d["final"] = {}
            out.append(d)
        return out

    def list_actions(self, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM organization_actions ORDER BY id DESC LIMIT ? OFFSET ?",
                (int(limit), int(offset)),
            ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> Dict[str, Any]:
        with self.connection() as conn:
            total = int(conn.execute("SELECT COUNT(*) c FROM organization_proposals").fetchone()[0])
            by_status_rows = conn.execute(
                "SELECT status, COUNT(*) c FROM organization_proposals GROUP BY status"
            ).fetchall()
            feedback = int(conn.execute("SELECT COUNT(*) c FROM organization_feedback").fetchone()[0])
            actions = int(conn.execute("SELECT COUNT(*) c FROM organization_actions").fetchone()[0])
        by_status = {str(r[0] or "unknown"): int(r[1]) for r in by_status_rows}
        return {
            "proposals_total": total,
            "proposals_by_status": by_status,
            "feedback_total": feedback,
            "actions_total": actions,
        }
