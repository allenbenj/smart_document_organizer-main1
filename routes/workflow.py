from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, Header, Query

from app.contracts.workflow import (
    CreateJobRequest,
    ExecuteStepRequest,
    JobStatus,
    JobStatusResponse,
    PaginationMeta,
    ResultResponse,
    ResultSchema,
    StepStatusItem,
)

router = APIRouter()

# In-memory placeholder store for kickoff scaffold only.
_WORKFLOW_JOBS: Dict[str, JobStatus] = {}


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


@router.post("/workflow/jobs", response_model=JobStatusResponse)
async def create_workflow_job(payload: CreateJobRequest, idempotency_key: Optional[str] = Header(None)) -> JobStatusResponse:
    job_id = f"wf_{uuid4().hex[:12]}"
    key = payload.idempotency_key or idempotency_key
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
    _WORKFLOW_JOBS[job_id] = job
    return JobStatusResponse(success=True, job=job)


@router.get("/workflow/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_workflow_job_status(job_id: str) -> JobStatusResponse:
    job = _WORKFLOW_JOBS.get(job_id)
    if not job:
        job = JobStatus(job_id=job_id, status="failed", draft_state="failed", stepper=_default_stepper())
    job.updated_at = datetime.utcnow()
    return JobStatusResponse(success=True, job=job)


@router.post("/workflow/jobs/{job_id}/steps/{step_name}/execute", response_model=ResultResponse)
async def execute_workflow_step(
    job_id: str,
    step_name: str,
    payload: ExecuteStepRequest,
    idempotency_key: Optional[str] = Header(None),
) -> ResultResponse:
    job = _WORKFLOW_JOBS.get(job_id)
    if not job:
        job = JobStatus(job_id=job_id, stepper=_default_stepper())
        _WORKFLOW_JOBS[job_id] = job

    job.status = "running"
    job.current_step = step_name  # type: ignore[assignment]
    job.draft_state = "saving"
    job.progress = min(job.progress + 0.12, 1.0)
    job.idempotency_key = payload.idempotency_key or idempotency_key or job.idempotency_key
    job.updated_at = datetime.utcnow()

    for s in job.stepper:
        if s.name == step_name:
            s.status = "in_progress"
            s.updated_at = datetime.utcnow()

    result = ResultSchema(
        summary=f"Placeholder execution accepted for step '{step_name}'",
        items=[],
        bulk={"supported": True},
        ontology_edits={"supported": True, "granular": True},
        pagination=PaginationMeta(count=0, has_more=False, next_cursor=None),
    )
    job.draft_state = "clean"

    return ResultResponse(success=True, job_id=job_id, step=step_name, result=result, errors=[])


@router.get("/workflow/jobs/{job_id}/results", response_model=ResultResponse)
async def get_workflow_results(
    job_id: str,
    step: str = Query("analytics"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ResultResponse:
    _ = (limit, offset)
    result = ResultSchema(
        summary="Placeholder paginated results",
        items=[],
        bulk={"supported": True},
        ontology_edits={"supported": True, "granular": True},
        pagination=PaginationMeta(count=0, has_more=False, next_cursor=None),
    )
    return ResultResponse(success=True, job_id=job_id, step=step, result=result, errors=[])
