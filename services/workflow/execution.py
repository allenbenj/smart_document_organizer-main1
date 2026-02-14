from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from app.contracts.workflow import JobStatus, PaginationMeta, ResultItem, ResultSchema
from services.file_index_service import FileIndexService
from services.organization_service import OrganizationService
from services.workflow_webhook_service import WorkflowWebhookService

from .constants import STEP_ORDER
from .repository import save_job


def update_step_status(job: JobStatus, step_name: str, status: str) -> None:
    for step in job.stepper:
        if step.name == step_name:
            step.status = status  # type: ignore[assignment]
            step.updated_at = datetime.utcnow()
            break


def step_index(step_name: str) -> int:
    try:
        return STEP_ORDER.index(step_name)
    except ValueError:
        return 0


def persist_step_result(job: JobStatus, *, step_name: str, result: ResultSchema) -> None:
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


def deliver_workflow_callback(
    db: Any,
    *,
    job: JobStatus,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    if not (job.webhook and job.webhook.enabled and job.webhook.url):
        return

    try:
        svc = WorkflowWebhookService()
        event_id = f"{job.job_id}:{event_type}:{uuid4().hex[:10]}"
        result = svc.deliver(
            url=str(job.webhook.url),
            payload={
                "event_id": event_id,
                "event_type": event_type,
                "job_id": job.job_id,
                "workflow": job.workflow,
                "status": job.status,
                "current_step": job.current_step,
                "payload": payload,
                "emitted_at": datetime.utcnow().isoformat(),
            },
            event_id=event_id,
        )
        job.webhook.last_delivery_at = datetime.utcnow()
        job.webhook.last_delivery_status = (
            f"delivered:{result.get('status')}@attempt={result.get('attempt')}"
            if result.get("ok")
            else f"failed:{result.get('status')}@attempt={result.get('attempt')}"
        )

        webhook_meta = dict(job.metadata.get("webhook") or {})
        deliveries = list(webhook_meta.get("deliveries") or [])
        deliveries.append(
            {
                "event_id": event_id,
                "event_type": event_type,
                "ok": bool(result.get("ok")),
                "status": result.get("status"),
                "attempt": int(result.get("attempt") or 0),
                "retryable": bool(result.get("retryable", False)),
                "signature_version": result.get("signature_version"),
                "last_error": result.get("last_error"),
                "delivered_at": datetime.utcnow().isoformat(),
            }
        )
        webhook_meta["deliveries"] = deliveries[-50:]
        webhook_meta["last_delivery"] = deliveries[-1]
        job.metadata["webhook"] = webhook_meta
        save_job(db, job)
    except Exception as e:
        # Log the error but don't fail the workflow
        import logging
        logging.getLogger(__name__).warning(f"Failed to deliver workflow callback: {e}")
        return


def execute_index_extract(db: Any, payload: Dict[str, Any]) -> ResultSchema:
    indexer = FileIndexService(db)

    mode = str(payload.get("mode") or "auto").strip().lower()
    try:
        max_files = int(payload.get("max_files", 5000))
    except (ValueError, TypeError):
        max_files = 5000

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


def execute_summarize(db: Any, payload: Dict[str, Any]) -> ResultSchema:
    try:
        limit = int(payload.get("limit", 500))
    except (ValueError, TypeError):
        limit = 500
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


def derive_draft_state_for_proposal(
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
