from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .base import BaseRepository


class AnalysisVersionRepository(BaseRepository):
    def add_analysis_version(self, analysis_version_data: Dict[str, Any]) -> int:
        def _op(conn: Any) -> int:
            cur = conn.execute(
                """
                INSERT INTO aedis_analysis_versions
                (analysis_id, artifact_row_id, version, parent_version, status, payload_json, audit_deltas_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_version_data.get("analysis_id"),
                    analysis_version_data.get("artifact_row_id"),
                    analysis_version_data.get("version"),
                    analysis_version_data.get("parent_version"),
                    analysis_version_data.get("status", "draft"),
                    json.dumps(analysis_version_data.get("payload") or {}),
                    json.dumps(analysis_version_data.get("audit_deltas") or []),
                    analysis_version_data.get("created_at"),
                ),
            )
            return int(cur.lastrowid)

        return self.write_with_retry(_op)

    def get_analysis_version(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM aedis_analysis_versions WHERE analysis_id = ?", (analysis_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["payload"] = json.loads(d.pop("payload_json", "{}"))
        d["audit_deltas"] = json.loads(d.pop("audit_deltas_json", "[]"))
        return d

    def update_analysis_version(
        self,
        analysis_id: str,
        *,
        status: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        audit_deltas: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        updates = []
        params: List[Any] = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if payload is not None:
            updates.append("payload_json = ?")
            params.append(json.dumps(payload))
        if audit_deltas is not None:
            updates.append("audit_deltas_json = ?")
            params.append(json.dumps(audit_deltas))
        updates.append("created_at = CURRENT_TIMESTAMP") # Using created_at for updated_at based on schema
        if not updates:
            return False
        params.append(analysis_id)
        def _op(conn: Any) -> bool:
            cur = conn.execute(
                f"UPDATE aedis_analysis_versions SET {', '.join(updates)} WHERE analysis_id = ?",
                params,
            )
            return (cur.rowcount or 0) > 0
        return self.write_with_retry(_op)

    def list_analysis_versions(
        self,
        *,
        artifact_row_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        where_clauses = []
        params: List[Any] = []
        if artifact_row_id is not None:
            where_clauses.append("artifact_row_id = ?")
            params.append(artifact_row_id)
        if status is not None:
            where_clauses.append("status = ?")
            params.append(status)

        where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        params.extend([limit, offset])

        with self.connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM aedis_analysis_versions {where_str} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d.pop("payload_json", "{}"))
            d["audit_deltas"] = json.loads(d.pop("audit_deltas_json", "[]"))
            out.append(d)
        return out

    def delete_analysis_version(self, analysis_id: str) -> bool:
        def _op(conn: Any) -> bool:
            cur = conn.execute(
                "DELETE FROM aedis_analysis_versions WHERE analysis_id = ?",
                (analysis_id,),
            )
            return (cur.rowcount or 0) > 0
        return self.write_with_retry(_op)