from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .base import BaseRepository


class LearningPathRepository(BaseRepository):
    def upsert_path(self, path: Dict[str, Any]) -> bool:
        def _op(conn: Any) -> bool:
            conn.execute(
                """
                INSERT INTO aedis_learning_paths
                (path_id, user_id, objective_id, status, ontology_version, heuristic_snapshot_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    objective_id=excluded.objective_id,
                    status=excluded.status,
                    ontology_version=excluded.ontology_version,
                    heuristic_snapshot_json=excluded.heuristic_snapshot_json,
                    updated_at=excluded.updated_at
                """,
                (
                    path.get("path_id"),
                    path.get("user_id"),
                    path.get("objective_id"),
                    path.get("status", "active"),
                    int(path.get("ontology_version") or 1),
                    json.dumps(path.get("heuristic_snapshot") or []),
                    path.get("created_at"),
                    path.get("updated_at"),
                ),
            )
            conn.execute(
                "DELETE FROM aedis_learning_path_steps WHERE path_id = ?",
                (path.get("path_id"),),
            )
            for idx, step in enumerate(path.get("steps") or [], start=1):
                conn.execute(
                    """
                    INSERT INTO aedis_learning_path_steps
                    (path_id, step_id, title, instruction, objective_id, heuristic_ids_json, evidence_spans_json, difficulty, completed, step_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        path.get("path_id"),
                        step.get("step_id"),
                        step.get("title"),
                        step.get("instruction"),
                        step.get("objective_id"),
                        json.dumps(step.get("heuristic_ids") or []),
                        json.dumps(step.get("evidence_spans") or []),
                        int(step.get("difficulty") or 1),
                        1 if bool(step.get("completed")) else 0,
                        idx,
                    ),
                )
            return True

        return self.write_with_retry(_op)

    def get_path(self, path_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM aedis_learning_paths WHERE path_id = ?",
                (path_id,),
            ).fetchone()
            if not row:
                return None
            path = dict(row)
            steps_rows = conn.execute(
                "SELECT * FROM aedis_learning_path_steps WHERE path_id = ? ORDER BY step_order ASC",
                (path_id,),
            ).fetchall()

        try:
            path["heuristic_snapshot"] = json.loads(path.get("heuristic_snapshot_json") or "[]")
        except Exception:
            path["heuristic_snapshot"] = []

        steps: List[Dict[str, Any]] = []
        for row in steps_rows:
            item = dict(row)
            try:
                heuristic_ids = json.loads(item.get("heuristic_ids_json") or "[]")
            except Exception:
                heuristic_ids = []
            try:
                evidence_spans = json.loads(item.get("evidence_spans_json") or "[]")
            except Exception:
                evidence_spans = []
            steps.append(
                {
                    "step_id": item.get("step_id"),
                    "title": item.get("title"),
                    "instruction": item.get("instruction"),
                    "objective_id": item.get("objective_id"),
                    "heuristic_ids": heuristic_ids,
                    "evidence_spans": evidence_spans,
                    "difficulty": int(item.get("difficulty") or 1),
                    "completed": bool(item.get("completed")),
                }
            )

        return {
            "path_id": path.get("path_id"),
            "user_id": path.get("user_id"),
            "objective_id": path.get("objective_id"),
            "status": path.get("status"),
            "steps": steps,
            "ontology_version": int(path.get("ontology_version") or 1),
            "heuristic_snapshot": path.get("heuristic_snapshot"),
            "created_at": path.get("created_at"),
            "updated_at": path.get("updated_at"),
        }

    def update_step_completion(
        self,
        *,
        path_id: str,
        step_id: str,
        completed: bool,
        updated_at: str,
    ) -> bool:
        def _op(conn: Any) -> bool:
            cur = conn.execute(
                """
                UPDATE aedis_learning_path_steps
                SET completed = ?
                WHERE path_id = ? AND step_id = ?
                """,
                (1 if completed else 0, path_id, step_id),
            )
            if (cur.rowcount or 0) <= 0:
                return False

            total_row = conn.execute(
                "SELECT COUNT(*) AS c FROM aedis_learning_path_steps WHERE path_id = ?",
                (path_id,),
            ).fetchone()
            done_row = conn.execute(
                "SELECT COUNT(*) AS c FROM aedis_learning_path_steps WHERE path_id = ? AND completed = 1",
                (path_id,),
            ).fetchone()
            total = int(total_row[0] or 0) if total_row else 0
            done = int(done_row[0] or 0) if done_row else 0
            status = "completed" if total > 0 and done == total else "active"
            conn.execute(
                """
                UPDATE aedis_learning_paths
                SET status = ?, updated_at = ?
                WHERE path_id = ?
                """,
                (status, updated_at, path_id),
            )
            return True

        return self.write_with_retry(_op)

    def list_recommended_steps(self, path_id: str) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM aedis_learning_path_steps
                WHERE path_id = ? AND completed = 0
                ORDER BY step_order ASC
                """,
                (path_id,),
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                heuristic_ids = json.loads(item.get("heuristic_ids_json") or "[]")
            except Exception:
                heuristic_ids = []
            try:
                evidence_spans = json.loads(item.get("evidence_spans_json") or "[]")
            except Exception:
                evidence_spans = []
            out.append(
                {
                    "step_id": item.get("step_id"),
                    "title": item.get("title"),
                    "instruction": item.get("instruction"),
                    "objective_id": item.get("objective_id"),
                    "heuristic_ids": heuristic_ids,
                    "evidence_spans": evidence_spans,
                }
            )
        return out
