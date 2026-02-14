from __future__ import annotations

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
    WorkflowBulkActionRequest,
    WorkflowMutationResponse,
    WorkflowOntologyEditRequest,
)
from services.dependencies import get_database_manager_strict_dep
from services.organization_service import OrganizationService
from services.workflow import (
    STEP_ORDER,
    default_stepper,
    deliver_workflow_callback,
    derive_draft_state_for_proposal,
    execute_index_extract,
    execute_summarize,
    load_job,
    persist_step_result,
    read_idempotent_response,
    save_job,
    step_index,
    update_step_status,
    write_idempotent_response,
)

router = APIRouter()


@router.post("/workflow/jobs", response_model=JobStatusResponse)
async def create_workflow_job(
    payload: CreateJobRequest,
    idempotency_key: Optional[str] = Header(None),
    db=Depends(get_database_manager_strict_dep),
) -> JobStatusResponse:
    key = payload.idempotency_key or idempotency_key
    scope = "create_job"
    cached = read_idempotent_response(db, scope, key)
    if cached:
        return JobStatusResponse.model_validate(cached)

    job_id = f"wf_{uuid4().hex[:12]}"
    job = JobStatus(
        job_id=job_id,
        workflow=payload.workflow,
        idempotency_key=key,
        stepper=default_stepper(),
        metadata={**payload.metadata, "completed_steps": [], "last_result_by_step": {}},
    )
    if payload.webhook_url:
        job.webhook.enabled = True
        job.webhook.url = payload.webhook_url

    save_job(db, job)
    deliver_workflow_callback(
        db,
        job=job,
        event_type="job.created",
        payload={"metadata": payload.metadata},
    )
    body = JobStatusResponse(success=True, job=job)
    body_dict = body.model_dump(mode="json")
    write_idempotent_response(db, scope, key, body_dict)
    return body


@router.get("/workflow/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_workflow_job_status(job_id: str, db=Depends(get_database_manager_strict_dep)) -> JobStatusResponse:
    job = load_job(db, job_id)
    if not job:
        job = JobStatus(job_id=job_id, status="failed", draft_state="failed", stepper=default_stepper())
    job.updated_at = datetime.utcnow()
    if job.job_id.startswith("wf_"):
        save_job(db, job)
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
    cached = read_idempotent_response(db, scope, key)
    if cached:
        return ResultResponse.model_validate(cached)

    job = load_job(db, job_id)
    if not job:
        job = JobStatus(job_id=job_id, stepper=default_stepper(), metadata={"completed_steps": [], "last_result_by_step": {}})

    job.status = "running"
    job.current_step = step_name  # type: ignore[assignment]
    job.draft_state = "saving"
    job.progress = max(job.progress, min((step_index(step_name) + 1) / max(len(STEP_ORDER), 1), 1.0))
    job.idempotency_key = key or job.idempotency_key
    job.updated_at = datetime.utcnow()
    update_step_status(job, step_name, "in_progress")

    result = ResultSchema(
        summary=f"Execution accepted for step '{step_name}'",
        items=[],
        bulk={"supported": True},
        ontology_edits={"supported": True, "granular": True},
        pagination=PaginationMeta(count=0, has_more=False, next_cursor=None),
    )

    try:
        if step_name == "index_extract":
            result = execute_index_extract(db, payload.payload)
        elif step_name == "summarize":
            result = execute_summarize(db, payload.payload)
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
        update_step_status(job, step_name, "failed")
        job.status = "failed"
        job.draft_state = "failed"
        job.metadata["last_error"] = str(e)
        save_job(db, job)
        response = ResultResponse(success=False, job_id=job_id, step=step_name, result=result, errors=[str(e)])
        write_idempotent_response(db, scope, key, response.model_dump(mode="json"))
        deliver_workflow_callback(
            db,
            job=job,
            event_type="step.failed",
            payload={"step": step_name, "errors": [str(e)]},
        )
        return response

    update_step_status(job, step_name, "complete")
    persist_step_result(job, step_name=step_name, result=result)
    job.draft_state = "clean"
    save_job(db, job)

    response = ResultResponse(success=True, job_id=job_id, step=step_name, result=result, errors=[])
    write_idempotent_response(db, scope, key, response.model_dump(mode="json"))
    deliver_workflow_callback(
        db,
        job=job,
        event_type="step.completed",
        payload={"step": step_name, "summary": result.summary, "count": result.pagination.count},
    )
    return response


@router.post("/workflow/jobs/{job_id}/proposals/bulk", response_model=WorkflowMutationResponse)
async def workflow_bulk_proposal_action(
    job_id: str,
    payload: WorkflowBulkActionRequest,
    db=Depends(get_database_manager_strict_dep),
) -> WorkflowMutationResponse:
    svc = OrganizationService(db)
    items = []
    errors = []
    applied = 0
    failed = 0

    for proposal_id in payload.proposal_ids:
        if payload.action == "approve":
            out = svc.approve_proposal(int(proposal_id))
        else:
            out = svc.reject_proposal(int(proposal_id), note=payload.note)
        if out.get("success"):
            applied += 1
        else:
            failed += 1
            errors.append(f"proposal_id={proposal_id}:{out.get('error', 'unknown_error')}")
        items.append(out)

    return WorkflowMutationResponse(
        success=(failed == 0),
        job_id=job_id,
        step="proposals",
        applied=applied,
        failed=failed,
        items=items,
        errors=errors,
    )


@router.patch("/workflow/jobs/{job_id}/proposals/{proposal_id}/ontology", response_model=WorkflowMutationResponse)
async def workflow_edit_proposal_ontology(
    job_id: str,
    proposal_id: int,
    payload: WorkflowOntologyEditRequest,
    db=Depends(get_database_manager_strict_dep),
) -> WorkflowMutationResponse:
    svc = OrganizationService(db)
    out = svc.edit_proposal_fields(
        proposal_id,
        proposed_folder=payload.proposed_folder,
        proposed_filename=payload.proposed_filename,
        confidence=payload.confidence,
        rationale=payload.rationale,
        note=payload.note,
        auto_approve=True,
    )
    success = bool(out.get("success"))
    return WorkflowMutationResponse(
        success=success,
        job_id=job_id,
        step="proposals",
        applied=1 if success else 0,
        failed=0 if success else 1,
        items=[out],
        errors=[] if success else [str(out.get("error") or "update_failed")],
    )


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
            draft_state = derive_draft_state_for_proposal(p, feedback_by_pid, action_by_pid)
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
                        "status": p.get("status"),
                        "decision_source": (p.get("metadata") or {}).get("decision_source"),
                        "ontology": {
                            "folder": p.get("proposed_folder"),
                            "filename": p.get("proposed_filename"),
                            "confidence": p.get("confidence"),
                            "rationale": p.get("rationale"),
                        },
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
        job = load_job(db, job_id)
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


@router.post("/workflow/jobs/{job_id}/proposals/bulk")
async def workflow_bulk_proposal_action(
    job_id: str,
    payload: Dict[str, Any] = Body(...),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    _ = job_id  # reserved for future job-level auditing
    ids = payload.get("proposal_ids") or []
    action = str(payload.get("action") or "").strip().lower()

    svc = OrganizationService(db)
    applied = 0
    failed = 0
    errors: list[Dict[str, Any]] = []

    for raw_id in ids:
        try:
            pid = int(raw_id)
        except Exception:
            failed += 1
            errors.append({"proposal_id": raw_id, "error": "invalid_proposal_id"})
            continue

        if action == "approve":
            out = svc.approve_proposal(pid)
        elif action == "reject":
            out = svc.reject_proposal(pid, note=str(payload.get("note") or "bulk_action"))
        else:
            return {"success": False, "applied": 0, "failed": len(ids), "errors": [{"error": "invalid_action"}]}

        if out.get("success"):
            applied += 1
        else:
            failed += 1
            errors.append({"proposal_id": pid, "error": out.get("error") or "operation_failed"})

    return {"success": failed == 0, "applied": applied, "failed": failed, "errors": errors}


@router.patch("/workflow/jobs/{job_id}/proposals/{proposal_id}/ontology")
async def workflow_patch_proposal_ontology(
    job_id: str,
    proposal_id: int,
    payload: Dict[str, Any] = Body(...),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    _ = job_id  # reserved for future job-level auditing
    svc = OrganizationService(db)
    out = svc.edit_proposal_fields(
        proposal_id,
        proposed_folder=payload.get("proposed_folder"),
        proposed_filename=payload.get("proposed_filename"),
        confidence=payload.get("confidence"),
        rationale=payload.get("rationale"),
        note=str(payload.get("note") or "ontology_patch"),
        auto_approve=True,
    )
    return {
        "success": bool(out.get("success")),
        "applied": 1 if out.get("success") else 0,
        "proposal_id": proposal_id,
        "item": out.get("item"),
        "error": out.get("error"),
    }
