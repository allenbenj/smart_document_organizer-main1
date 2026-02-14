from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from app.contracts.workflow import JobStatus, StepStatusItem

from .constants import STEP_ORDER


def default_stepper() -> list[StepStatusItem]:
    return [StepStatusItem(name=s, status="not_started") for s in STEP_ORDER]


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except Exception:
            pass
    return str(value)


def _job_from_row(row: Dict[str, Any]) -> JobStatus:
    data = dict(row)
    stepper = []
    try:
        for item in json.loads(data.get("stepper_json") or "[]"):
            stepper.append(StepStatusItem.model_validate(item))
    except Exception:
        stepper = default_stepper()

    try:
        pagination = json.loads(data.get("pagination_json") or "{}")
    except Exception:
        pagination = {}

    try:
        undo = json.loads(data.get("undo_json") or "{}")
    except Exception:
        undo = {}

    try:
        metadata = json.loads(data.get("metadata_json") or "{}")
    except Exception:
        metadata = {}

    return JobStatus(
        job_id=str(data.get("job_id")),
        workflow=str(data.get("workflow") or "memory_first_v2"),
        status=str(data.get("status") or "queued"),
        current_step=str(data.get("current_step") or "sources"),
        progress=float(data.get("progress") or 0.0),
        draft_state=str(data.get("draft_state") or "clean"),
        started_at=data.get("started_at") or datetime.utcnow(),
        updated_at=data.get("updated_at") or datetime.utcnow(),
        completed_at=data.get("completed_at"),
        idempotency_key=data.get("idempotency_key"),
        webhook={
            "enabled": bool(data.get("webhook_enabled")),
            "url": data.get("webhook_url"),
            "last_delivery_status": data.get("webhook_last_delivery_status"),
            "last_delivery_at": data.get("webhook_last_delivery_at"),
        },
        stepper=stepper or default_stepper(),
        pagination=pagination,
        undo=undo,
        metadata=metadata,
    )


def save_job(db: Any, job: JobStatus) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO workflow_jobs (
                job_id, workflow, status, current_step, progress, draft_state,
                started_at, updated_at, completed_at, idempotency_key,
                webhook_enabled, webhook_url, webhook_last_delivery_status, webhook_last_delivery_at,
                stepper_json, pagination_json, undo_json, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                workflow = excluded.workflow,
                status = excluded.status,
                current_step = excluded.current_step,
                progress = excluded.progress,
                draft_state = excluded.draft_state,
                started_at = excluded.started_at,
                updated_at = excluded.updated_at,
                completed_at = excluded.completed_at,
                idempotency_key = excluded.idempotency_key,
                webhook_enabled = excluded.webhook_enabled,
                webhook_url = excluded.webhook_url,
                webhook_last_delivery_status = excluded.webhook_last_delivery_status,
                webhook_last_delivery_at = excluded.webhook_last_delivery_at,
                stepper_json = excluded.stepper_json,
                pagination_json = excluded.pagination_json,
                undo_json = excluded.undo_json,
                metadata_json = excluded.metadata_json
            """,
            (
                job.job_id,
                job.workflow,
                job.status,
                job.current_step,
                job.progress,
                job.draft_state,
                job.started_at,
                job.updated_at,
                job.completed_at,
                job.idempotency_key,
                1 if job.webhook.enabled else 0,
                job.webhook.url,
                job.webhook.last_delivery_status,
                job.webhook.last_delivery_at,
                json.dumps([s.model_dump(mode="json") for s in job.stepper], default=_json_default),
                json.dumps(job.pagination, default=_json_default),
                json.dumps(job.undo.model_dump(mode="json"), default=_json_default),
                json.dumps(job.metadata, default=_json_default),
            ),
        )
        conn.commit()


def load_job(db: Any, job_id: str) -> Optional[JobStatus]:
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM workflow_jobs WHERE job_id = ?", (job_id,)).fetchone()
    if not row:
        return None
    return _job_from_row(dict(row))


def read_idempotent_response(db: Any, scope: str, key: Optional[str]) -> Optional[Dict[str, Any]]:
    if not key:
        return None
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT response_json FROM workflow_idempotency_keys WHERE scope = ? AND idempotency_key = ?",
            (scope, key),
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def write_idempotent_response(db: Any, scope: str, key: Optional[str], response_body: Dict[str, Any]) -> None:
    if not key:
        return
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO workflow_idempotency_keys(scope, idempotency_key, response_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(scope, idempotency_key) DO UPDATE SET
                response_json = excluded.response_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (scope, key, json.dumps(response_body, default=_json_default)),
        )
        conn.commit()
