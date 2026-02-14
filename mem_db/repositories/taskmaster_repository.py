from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .base import BaseRepository


class TaskMasterRepository(BaseRepository):
    def create_run(self, run_type: str, payload: Optional[Dict[str, Any]] = None) -> int:
        def _op(conn: Any) -> int:
            cur = conn.execute(
                """
                INSERT INTO taskmaster_runs (run_type, status, payload_json)
                VALUES (?, 'running', ?)
                """,
                (run_type, json.dumps(payload or {})),
            )
            return int(cur.lastrowid)

        return self.write_with_retry(_op)

    def complete_run(self, run_id: int, status: str, summary: Optional[Dict[str, Any]] = None) -> None:
        def _op(conn: Any) -> None:
            conn.execute(
                """
                UPDATE taskmaster_runs
                SET status = ?, summary_json = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, json.dumps(summary or {}), run_id),
            )

        self.write_with_retry(_op)

    def create_task(self, run_id: int, task_name: str, payload: Optional[Dict[str, Any]] = None) -> int:
        def _op(conn: Any) -> int:
            cur = conn.execute(
                """
                INSERT INTO taskmaster_tasks (run_id, task_name, status, progress, payload_json)
                VALUES (?, ?, 'running', 0, ?)
                """,
                (run_id, task_name, json.dumps(payload or {})),
            )
            return int(cur.lastrowid)

        return self.write_with_retry(_op)

    def update_task(
        self,
        task_id: int,
        *,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        result: Optional[Dict[str, Any]] = None,
        done: bool = False,
    ) -> None:
        fields = []
        values: List[Any] = []
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if progress is not None:
            fields.append("progress = ?")
            values.append(progress)
        if result is not None:
            fields.append("result_json = ?")
            values.append(json.dumps(result))
        if done:
            fields.append("completed_at = CURRENT_TIMESTAMP")
        if not fields:
            return
        def _op(conn: Any) -> None:
            conn.execute(
                f"UPDATE taskmaster_tasks SET {', '.join(fields)} WHERE id = ?",
                [*values, task_id],
            )

        self.write_with_retry(_op)

    def add_event(
        self,
        run_id: int,
        *,
        level: str,
        event_type: str,
        message: str,
        task_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> int:
        def _op(conn: Any) -> int:
            cur = conn.execute(
                """
                INSERT INTO taskmaster_events (run_id, task_id, level, event_type, message, data_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, task_id, level, event_type, message, json.dumps(data or {})),
            )
            return int(cur.lastrowid)

        return self.write_with_retry(_op)

    def get_run_status(self, run_id: int) -> Optional[str]:
        with self.connection() as conn:
            row = conn.execute("SELECT status FROM taskmaster_runs WHERE id = ?", (run_id,)).fetchone()
            return str(row["status"]) if row else None

    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            run = conn.execute("SELECT * FROM taskmaster_runs WHERE id = ?", (run_id,)).fetchone()
            if not run:
                return None
            tasks = conn.execute(
                "SELECT * FROM taskmaster_tasks WHERE run_id = ? ORDER BY id ASC", (run_id,)
            ).fetchall()
            out = dict(run)
            for key in ("payload_json", "summary_json"):
                try:
                    out[key] = json.loads(out.get(key) or "{}")
                except Exception:
                    out[key] = {}
            out["tasks"] = []
            for t in tasks:
                item = dict(t)
                for key in ("payload_json", "result_json"):
                    try:
                        item[key] = json.loads(item.get(key) or "{}")
                    except Exception:
                        item[key] = {}
                out["tasks"].append(item)
            return out

    def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        run_type: Optional[str] = None,
        started_after: Optional[str] = None,
        started_before: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            where = []
            params: List[Any] = []
            if status:
                where.append("status = ?")
                params.append(status)
            if run_type:
                where.append("run_type = ?")
                params.append(run_type)
            if started_after:
                where.append("started_at >= ?")
                params.append(started_after)
            if started_before:
                where.append("started_at <= ?")
                params.append(started_before)
            where_clause = f"WHERE {' AND '.join(where)}" if where else ""

            rows = conn.execute(
                f"SELECT * FROM taskmaster_runs {where_clause} ORDER BY id DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                for key in ("payload_json", "summary_json"):
                    try:
                        item[key] = json.loads(item.get(key) or "{}")
                    except Exception:
                        item[key] = {}
                out.append(item)
            return out

    def list_events(self, run_id: int, limit: int = 500, level: Optional[str] = None, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            where = ["run_id = ?"]
            params: List[Any] = [run_id]
            if level:
                where.append("level = ?")
                params.append(level)
            if event_type:
                where.append("event_type = ?")
                params.append(event_type)

            rows = conn.execute(
                f"SELECT * FROM taskmaster_events WHERE {' AND '.join(where)} ORDER BY id ASC LIMIT ?",
                [*params, limit],
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                try:
                    item["data_json"] = json.loads(item.get("data_json") or "{}")
                except Exception:
                    item["data_json"] = {}
                out.append(item)
            return out

    def cancel_run(self, run_id: int) -> bool:
        with self.connection() as conn:
            run = conn.execute("SELECT status FROM taskmaster_runs WHERE id = ?", (run_id,)).fetchone()
            if not run:
                return False
            cur_status = str(run["status"])
            if cur_status in {"completed", "failed", "cancelled"}:
                return False
            conn.execute(
                "UPDATE taskmaster_runs SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (run_id,),
            )
            conn.execute(
                "UPDATE taskmaster_tasks SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP WHERE run_id = ? AND status = 'running'",
                (run_id,),
            )
            conn.commit()
            return True

    def queue_depth(self, *, include_running: bool = False) -> int:
        with self.connection() as conn:
            if include_running:
                row = conn.execute(
                    "SELECT COUNT(1) AS c FROM taskmaster_job_queue WHERE status IN ('queued', 'running')"
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(1) AS c FROM taskmaster_job_queue WHERE status = 'queued'"
                ).fetchone()
            return int((row or {"c": 0})["c"])

    def queue_enqueue(self, *, mode: str, payload: Optional[Dict[str, Any]] = None, max_retries: int = 2) -> int:
        def _op(conn: Any) -> int:
            cur = conn.execute(
                """
                INSERT INTO taskmaster_job_queue (mode, payload_json, max_retries, status)
                VALUES (?, ?, ?, 'queued')
                """,
                (str(mode), json.dumps(payload or {}), int(max_retries)),
            )
            return int(cur.lastrowid)

        return self.write_with_retry(_op)

    def queue_claim_next(self, *, worker_name: str) -> Optional[Dict[str, Any]]:
        def _op(conn: Any) -> Optional[Dict[str, Any]]:
            row = conn.execute(
                """
                SELECT * FROM taskmaster_job_queue
                WHERE status = 'queued' AND available_at <= datetime('now')
                ORDER BY id ASC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            job_id = int(row["id"])
            conn.execute(
                """
                UPDATE taskmaster_job_queue
                SET status = 'running', worker_name = ?, started_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'queued'
                """,
                (worker_name, job_id),
            )
            claimed = conn.execute("SELECT * FROM taskmaster_job_queue WHERE id = ?", (job_id,)).fetchone()
            if not claimed or str(claimed["status"]) != "running":
                return None
            out = dict(claimed)
            try:
                out["payload_json"] = json.loads(out.get("payload_json") or "{}")
            except Exception:
                out["payload_json"] = {}
            return out

        return self.write_with_retry(_op)

    def queue_mark_completed(self, queue_job_id: int) -> None:
        def _op(conn: Any) -> None:
            conn.execute(
                """
                UPDATE taskmaster_job_queue
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (queue_job_id,),
            )

        self.write_with_retry(_op)

    def queue_mark_retry_or_dead_letter(self, queue_job_id: int, *, error_message: str) -> str:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM taskmaster_job_queue WHERE id = ?", (queue_job_id,)).fetchone()
            if not row:
                return "missing"
            retry_count = int(row["retry_count"] or 0) + 1
            max_retries = int(row["max_retries"] or 0)
            mode = str(row["mode"])
            payload_raw = str(row["payload_json"] or "{}")
            if retry_count <= max_retries:
                conn.execute(
                    """
                    UPDATE taskmaster_job_queue
                    SET status = 'queued', retry_count = ?, last_error = ?,
                        available_at = datetime('now', '+10 seconds'), updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (retry_count, str(error_message), queue_job_id),
                )
                conn.commit()
                return "retry"

            conn.execute(
                """
                UPDATE taskmaster_job_queue
                SET status = 'dead_letter', retry_count = ?, last_error = ?, completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (retry_count, str(error_message), queue_job_id),
            )
            conn.execute(
                """
                INSERT INTO taskmaster_dead_letters (queue_job_id, mode, payload_json, error_message, retry_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (queue_job_id, mode, payload_raw, str(error_message), retry_count),
            )
            conn.commit()
            return "dead_letter"

    def dead_letters(self, *, limit: int = 100) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM taskmaster_dead_letters ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                try:
                    item["payload_json"] = json.loads(item.get("payload_json") or "{}")
                except Exception:
                    item["payload_json"] = {}
                out.append(item)
            return out

    def schedule_upsert(self, *, name: Optional[str], mode: str, payload: Optional[Dict[str, Any]], every_minutes: int, active: bool = True) -> int:
        def _op(conn: Any) -> int:
            cur = conn.execute(
                """
                INSERT INTO taskmaster_schedules (name, mode, payload_json, every_minutes, active, next_run_at, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now', '+' || ? || ' minutes'), CURRENT_TIMESTAMP)
                """,
                (name, mode, json.dumps(payload or {}), int(every_minutes), 1 if active else 0, int(every_minutes)),
            )
            return int(cur.lastrowid)

        return self.write_with_retry(_op)

    def schedule_list(self, active_only: bool = False) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            where = "WHERE active = 1" if active_only else ""
            rows = conn.execute(f"SELECT * FROM taskmaster_schedules {where} ORDER BY id DESC").fetchall()
            out = []
            for r in rows:
                item = dict(r)
                try:
                    item["payload_json"] = json.loads(item.get("payload_json") or "{}")
                except Exception:
                    item["payload_json"] = {}
                item["active"] = bool(item.get("active"))
                out.append(item)
            return out

    def schedule_due(self) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM taskmaster_schedules WHERE active = 1 AND next_run_at <= datetime('now') ORDER BY next_run_at ASC"
            ).fetchall()
            out = []
            for r in rows:
                item = dict(r)
                try:
                    item["payload_json"] = json.loads(item.get("payload_json") or "{}")
                except Exception:
                    item["payload_json"] = {}
                out.append(item)
            return out

    def schedule_mark_ran(self, schedule_id: int, every_minutes: int) -> None:
        def _op(conn: Any) -> None:
            conn.execute(
                """
                UPDATE taskmaster_schedules
                SET last_run_at = CURRENT_TIMESTAMP,
                    next_run_at = datetime('now', '+' || ? || ' minutes'),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (int(every_minutes), schedule_id),
            )

        self.write_with_retry(_op)
