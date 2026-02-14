from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
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
from services.file_index_service import FileIndexService
from services.organization_service import OrganizationService

router = APIRouter()


STEP_ORDER = ["sources", "index_extract", "summarize", "proposals", "review", "apply", "analytics"]


def _default_stepper() -> list[StepStatusItem]:
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
        stepper=stepper or _default_stepper(),
        pagination=pagination,
        undo=undo,
        metadata=metadata,
    )


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


def _step_index(step_name: str) -> int:
    try:
        return STEP_ORDER.index(step_name)
    except ValueError:
        return 0


def _persist_step_result(job: JobStatus, *, step_name: str, result: ResultSchema) -> None:
    completed = list(job.metadata.get("completed_steps") or [])
    if step_name not in completed:
        completed.append(step_name)

    last_result = dict(job.metadata.get("last_result_by_step") or {})
    last_result[step_name] = {
        "updated_at": datetime.utcnow().isoformat(),
        "count": int(result.pagination.count),
        "next_cursor": result.pagination.next_cursor,
        "summary": result.summary,
    }

    job.pagination[step_name] = result.pagination.model_dump(mode="json")
    job.metadata["completed_steps"] = completed
    job.metadata["last_result_by_step"] = last_result


def _execute_index_extract(db: Any, payload: Dict[str, Any]) -> ResultSchema:
    indexer = FileIndexService(db)

    mode = str(payload.get("mode") or "auto").strip().lower()
    max_files = int(payload.get("max_files", 5000))

    if mode == "watched":
        out = indexer.run_watched_index(max_files_per_watch=max_files)
    elif mode == "refresh":
        out = indexer.refresh_index(stale_after_hours=int(payload.get("stale_after_hours", 24)))
    else:
        roots = payload.get("roots")
        if isinstance(roots, list) and roots:
            out = indexer.index_roots(
                [str(x) for x in roots if str(x).strip()],
                recursive=bool(payload.get("recursive", True)),
                max_files=max_files,
                max_runtime_seconds=(float(payload["max_runtime_seconds"]) if payload.get("max_runtime_seconds") else None),
            )
        else:
            out = indexer.run_watched_index(max_files_per_watch=max_files)

    indexed = int(out.get("indexed", 0))
    scanned = int(out.get("scanned", 0))
    errors = int(out.get("errors", 0))
    summary = f"Index/extract finished: indexed={indexed}, scanned={scanned}, errors={errors}"

    return ResultSchema(
        summary=summary,
        items=[
            ResultItem(
                id=f"index_extract_{uuid4().hex[:10]}",
                type="index_extract",
                status="complete" if out.get("success", True) else "failed",
                payload={"metrics": out},
                version=1,
            )
        ],
        bulk={"supported": False},
        ontology_edits={"supported": False, "granular": False},
        pagination=PaginationMeta(count=1, has_more=False, next_cursor=None),
    )


def _execute_summarize(db: Any, payload: Dict[str, Any]) -> ResultSchema:
    limit = int(payload.get("limit", 500))
    files, _total = db.list_indexed_files(limit=limit, offset=0, status="ready")
    svc = OrganizationService(db)
    proposals = svc.list_proposals(limit=min(1000, max(50, limit)), offset=0).get("items", [])

    ext_counts: Dict[str, int] = {}
    folder_counts: Dict[str, int] = {}
    examples: list[Dict[str, Any]] = []

    for rec in files:
        ext = str(rec.get("ext") or "").lower() or "(none)"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    for p in proposals:
        folder = str(p.get("proposed_folder") or "Inbox/Review")
        folder_counts[folder] = folder_counts.get(folder, 0) + 1
        if len(examples) < 25:
            examples.append(
                {
                    "proposal_id": p.get("id"),
                    "from": p.get("current_path"),
                    "to": f"{folder}/{p.get('proposed_filename')}",
                    "confidence": p.get("confidence"),
                }
            )

    naming_conventions = {
        "top_extensions": sorted(ext_counts.items(), key=lambda kv: kv[1], reverse=True)[:12],
        "filename_style": "preserve-source-stem-with-sanitization",
    }
    folder_structure = {
        "top_destination_folders": sorted(folder_counts.items(), key=lambda kv: kv[1], reverse=True)[:20],
        "default_folder": "Inbox/Review",
    }

    artifact = {
        "generated_at": datetime.utcnow().isoformat(),
        "naming_conventions": naming_conventions,
        "folder_structure": folder_structure,
        "examples": examples,
        "source_counts": {"indexed_files": len(files), "proposals": len(proposals)},
    }

    return ResultSchema(
        summary=f"Summary artifacts built from {len(files)} indexed file(s) and {len(proposals)} proposal(s)",
        items=[
            ResultItem(
                id=f"summarize_{uuid4().hex[:10]}",
                type="summary_artifact",
                status="complete",
                payload=artifact,
                version=1,
            )
        ],
        bulk={"supported": False},
        ontology_edits={"supported": False, "granular": False},
        pagination=PaginationMeta(count=1, has_more=False, next_cursor=None),
    )


def _derive_draft_state_for_proposal(
    proposal: Dict[str, Any],
    feedback_by_pid: Dict[int, list[Dict[str, Any]]],
    action_by_pid: Dict[int, list[Dict[str, Any]]],
) -> str:
    pid = int(proposal.get("id") or 0)
    status = str(proposal.get("status") or "proposed").lower()

    if status == "applied":
        return "clean"

    feedback = feedback_by_pid.get(pid, [])
    actions = action_by_pid.get(pid, [])

    if any(str(f.get("action") or "") == "edit" for f in feedback):
        return "human_edited"
    if any(str(f.get("action") or "") == "reject" for f in feedback):
        return "dirty"
    if any(bool(a.get("success")) for a in actions):
        return "saving"

    rationale = str(proposal.get("rationale") or "").lower()
    if "user edited" in rationale:
        return "human_edited"
    if status in {"approved"}:
        return "dirty"
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
        metadata={**payload.metadata, "completed_steps": [], "last_result_by_step": {}},
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
        job = JobStatus(job_id=job_id, stepper=_default_stepper(), metadata={"completed_steps": [], "last_result_by_step": {}})

    job.status = "running"
    job.current_step = step_name  # type: ignore[assignment]
    job.draft_state = "saving"
    job.progress = max(job.progress, min((_step_index(step_name) + 1) / max(len(STEP_ORDER), 1), 1.0))
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

    try:
        if step_name == "index_extract":
            result = _execute_index_extract(db, payload.payload)
        elif step_name == "summarize":
            result = _execute_summarize(db, payload.payload)
            job.metadata["summary_artifact"] = result.items[0].payload if result.items else {}
        elif step_name == "proposals":
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
        elif step_name == "apply":
            svc = OrganizationService(db)
            dry_run = bool(payload.payload.get("dry_run", True))
            out = svc.apply_approved(limit=int(payload.payload.get("limit", 200)), dry_run=dry_run)
            undo_token = str(out.get("rollback_group") or uuid4().hex)
            undo_entry = {
                "undo_token": undo_token,
                "step": "apply",
                "created_at": datetime.utcnow().isoformat(),
                "dry_run": dry_run,
                "operation": "organization_move_batch",
                "result": {"applied": out.get("applied", 0), "failed": out.get("failed", 0)},
            }
            stack = list(job.metadata.get("undo_stack") or [])
            stack.append(undo_entry)
            job.metadata["undo_stack"] = stack[-25:]
            job.undo.depth = len(job.metadata.get("undo_stack") or [])
            job.undo.last_undo_token = undo_token
            result.summary = f"Apply finished: applied={out.get('applied', 0)}, failed={out.get('failed', 0)}, dry_run={dry_run}"
            result.items = [
                ResultItem(
                    id=f"apply_{undo_token[:12]}",
                    type="apply_result",
                    status="complete" if out.get("success") else "failed",
                    payload=out,
                    undo_token=undo_token,
                    version=1,
                )
            ]
            result.pagination = PaginationMeta(count=1, has_more=False, next_cursor=None)
    except Exception as e:
        _update_step_status(job, step_name, "failed")
        job.status = "failed"
        job.draft_state = "failed"
        job.metadata["last_error"] = str(e)
        _save_job(db, job)
        response = ResultResponse(success=False, job_id=job_id, step=step_name, result=result, errors=[str(e)])
        _write_idempotent_response(db, scope, key, response.model_dump(mode="json"))
        return response

    _update_step_status(job, step_name, "complete")
    _persist_step_result(job, step_name=step_name, result=result)
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

        feedback = svc.list_feedback(limit=2000, offset=0).get("items", [])
        actions = svc.list_actions(limit=2000, offset=0).get("items", [])
        feedback_by_pid: Dict[int, list[Dict[str, Any]]] = {}
        action_by_pid: Dict[int, list[Dict[str, Any]]] = {}
        for f in feedback:
            pid = int(f.get("proposal_id") or 0)
            if pid:
                feedback_by_pid.setdefault(pid, []).append(f)
        for a in actions:
            pid = int(a.get("proposal_id") or 0)
            if pid:
                action_by_pid.setdefault(pid, []).append(a)

        total_returned = len(proposals)
        items = []
        for p in proposals:
            draft_state = _derive_draft_state_for_proposal(p, feedback_by_pid, action_by_pid)
            items.append(
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
                        "draft_state": draft_state,
                        "decision_source": (p.get("metadata") or {}).get("decision_source"),
                    },
                    version=1,
                )
            )

        has_more = total_returned == limit
        result = ResultSchema(
            summary=f"Loaded {total_returned} proposal result(s)",
            items=items,
            bulk={"supported": True},
            ontology_edits={"supported": True, "granular": True},
            pagination=PaginationMeta(count=total_returned, has_more=has_more, next_cursor=str(offset + limit) if has_more else None),
        )
        return ResultResponse(success=True, job_id=job_id, step="proposals", result=result, errors=[])

    if step == "summarize":
        job = _load_job(db, job_id)
        artifact = (job.metadata.get("summary_artifact") if job else None) or {}
        items = []
        if artifact:
            items.append(ResultItem(id=f"summary_{job_id}", type="summary_artifact", status="complete", payload=artifact, version=1))
        result = ResultSchema(
            summary="Loaded summary artifacts" if artifact else "No summary artifacts available",
            items=items,
            bulk={"supported": False},
            ontology_edits={"supported": False, "granular": False},
            pagination=PaginationMeta(count=len(items), has_more=False, next_cursor=None),
        )
        return ResultResponse(success=True, job_id=job_id, step="summarize", result=result, errors=[])

    result = ResultSchema(
        summary="No results available for requested step",
        items=[],
        bulk={"supported": True},
        ontology_edits={"supported": True, "granular": True},
        pagination=PaginationMeta(count=0, has_more=False, next_cursor=None),
    )
    return ResultResponse(success=True, job_id=job_id, step=step, result=result, errors=[])
