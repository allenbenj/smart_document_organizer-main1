from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query

from app.contracts.workflow import (
    CreateJobRequest,
    ExecuteStepRequest,
    JobStatus,
    JobStatusResponse,
    PaginationMeta,
    ResultItem,
    ResultResponse,
    ResultSchema,
    StepStatusItem,
)
from services.dependencies import get_database_manager_strict_dep
from services.organization_service import OrganizationService

router = APIRouter()


def _default_stepper() -> list[StepStatusItem]:
    return [
        StepStatusItem(name="sources", status="not_started"),
        StepStatusItem(name="index_extract", status="not_started"),
        StepStatusItem(name="summarize", status="not_started"),
        StepStatusItem(name="proposals", status="not_started"),
        StepStatusItem(name="review", status="not_started"),
        StepStatusItem(name="apply", status="not_started"),
        StepStatusItem(name="analytics", status="not_started"),
    ]


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _job_from_row(row: Dict[str, Any]) -> JobStatus:
    data = dict(row)
    stepper = []
    try:
        for item in json.loads(data.get("stepper_json") or "[]"):
            stepper.append(StepStatusItem.model_validate(item))
    except Exception:
        stepper = _default_stepper()

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

    job = JobStatus(
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
        stepper=stepper or _default_stepper(),
        pagination=pagination,
        undo=undo,
        metadata=metadata,
    )
    return job


def _save_job(db: Any, job: JobStatus) -> None:
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


def _load_job(db: Any, job_id: str) -> Optional[JobStatus]:
    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM workflow_jobs WHERE job_id = ?", (job_id,)).fetchone()
    if not row:
        return None
    return _job_from_row(dict(row))


def _read_idempotent_response(db: Any, scope: str, key: Optional[str]) -> Optional[Dict[str, Any]]:
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


def _write_idempotent_response(db: Any, scope: str, key: Optional[str], response_body: Dict[str, Any]) -> None:
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


def _update_step_status(job: JobStatus, step_name: str, status: str) -> None:
    for step in job.stepper:
        if step.name == step_name:
            step.status = status  # type: ignore[assignment]
            step.updated_at = datetime.utcnow()
            break


def _proposal_item_draft_state(proposal: Dict[str, Any]) -> str:
    rationale = str(proposal.get("rationale") or "").lower()
    if "user edited" in rationale:
        return "human_edited"
    return "auto"


@router.post("/workflow/jobs", response_model=JobStatusResponse)
async def create_workflow_job(
    payload: CreateJobRequest,
    idempotency_key: Optional[str] = Header(None),
    db=Depends(get_database_manager_strict_dep),
) -> JobStatusResponse:
    key = payload.idempotency_key or idempotency_key
    scope = "create_job"
    cached = _read_idempotent_response(db, scope, key)
    if cached:
        return JobStatusResponse.model_validate(cached)

    job_id = f"wf_{uuid4().hex[:12]}"
    job = JobStatus(
        job_id=job_id,
        workflow=payload.workflow,
        idempotency_key=key,
        stepper=_default_stepper(),
        metadata=payload.metadata,
    )
    if payload.webhook_url:
        job.webhook.enabled = True
        job.webhook.url = payload.webhook_url

    _save_job(db, job)
    body = JobStatusResponse(success=True, job=job)
    body_dict = body.model_dump(mode="json")
    _write_idempotent_response(db, scope, key, body_dict)
    return body


@router.get("/workflow/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_workflow_job_status(job_id: str, db=Depends(get_database_manager_strict_dep)) -> JobStatusResponse:
    job = _load_job(db, job_id)
    if not job:
        job = JobStatus(job_id=job_id, status="failed", draft_state="failed", stepper=_default_stepper())
    job.updated_at = datetime.utcnow()
    if job.job_id.startswith("wf_"):
        _save_job(db, job)
    return JobStatusResponse(success=True, job=job)


@router.post("/workflow/jobs/{job_id}/steps/{step_name}/execute", response_model=ResultResponse)
async def execute_workflow_step(
    job_id: str,
    step_name: str,
    payload: ExecuteStepRequest,
    idempotency_key: Optional[str] = Header(None),
    db=Depends(get_database_manager_strict_dep),
) -> ResultResponse:
    key = payload.idempotency_key or idempotency_key
    scope = f"execute_step:{job_id}:{step_name}"
    cached = _read_idempotent_response(db, scope, key)
    if cached:
        return ResultResponse.model_validate(cached)

    job = _load_job(db, job_id)
    if not job:
        job = JobStatus(job_id=job_id, stepper=_default_stepper())

    job.status = "running"
    job.current_step = step_name  # type: ignore[assignment]
    job.draft_state = "saving"
    job.progress = min(job.progress + 0.12, 1.0)
    job.idempotency_key = key or job.idempotency_key
    job.updated_at = datetime.utcnow()
    _update_step_status(job, step_name, "in_progress")

    result = ResultSchema(
        summary=f"Execution accepted for step '{step_name}'",
        items=[],
        bulk={"supported": True},
        ontology_edits={"supported": True, "granular": True},
        pagination=PaginationMeta(count=0, has_more=False, next_cursor=None),
    )

    if step_name == "proposals":
        svc = OrganizationService(db)
        generate_out = svc.generate_proposals(
            run_id=payload.payload.get("run_id"),
            limit=int(payload.payload.get("limit", 50)),
            provider=payload.payload.get("provider"),
            model=payload.payload.get("model"),
            root_prefix=payload.payload.get("root_prefix"),
        )
        created = int(generate_out.get("created", 0))
        result.summary = f"Generated {created} proposal(s)"
        result.pagination = PaginationMeta(count=created, has_more=False, next_cursor=None)

    _update_step_status(job, step_name, "complete")
    job.draft_state = "clean"
    _save_job(db, job)

    response = ResultResponse(success=True, job_id=job_id, step=step_name, result=result, errors=[])
    _write_idempotent_response(db, scope, key, response.model_dump(mode="json"))
    return response


@router.get("/workflow/jobs/{job_id}/results", response_model=ResultResponse)
async def get_workflow_results(
    job_id: str,
    step: str = Query("analytics"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db=Depends(get_database_manager_strict_dep),
) -> ResultResponse:
    if step == "proposals":
        svc = OrganizationService(db)
        out = svc.list_proposals(limit=limit, offset=offset)
        proposals = out.get("items", [])
        total_returned = len(proposals)
        items = [
            ResultItem(
                id=f"proposal_{p.get('id')}",
                type="proposal",
                status=str(p.get("status") or "proposed"),
                payload={
                    "proposal_id": p.get("id"),
                    "file_id": p.get("file_id"),
                    "current_path": p.get("current_path"),
                    "proposed_folder": p.get("proposed_folder"),
                    "proposed_filename": p.get("proposed_filename"),
                    "confidence": p.get("confidence"),
                    "rationale": p.get("rationale"),
                    "draft_state": _proposal_item_draft_state(p),
                    "decision_source": (p.get("metadata") or {}).get("decision_source"),
                },
                version=1,
            )
            for p in proposals
        ]
        has_more = total_returned == limit
        result = ResultSchema(
            summary=f"Loaded {total_returned} proposal result(s)",
            items=items,
            bulk={"supported": True},
            ontology_edits={"supported": True, "granular": True},
            pagination=PaginationMeta(count=total_returned, has_more=has_more, next_cursor=str(offset + limit) if has_more else None),
        )
        return ResultResponse(success=True, job_id=job_id, step="proposals", result=result, errors=[])

    result = ResultSchema(
        summary="No results available for requested step",
        items=[],
        bulk={"supported": True},
        ontology_edits={"supported": True, "granular": True},
        pagination=PaginationMeta(count=0, has_more=False, next_cursor=None),
    )
    return ResultResponse(success=True, job_id=job_id, step=step, result=result, errors=[])
