from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from services.dependencies import get_database_manager_strict_dep
from services.taskmaster_service import TaskMasterService

router = APIRouter()


class TaskmasterSchedulePayload(BaseModel):
    name: Optional[str] = None
    mode: str
    payload: Optional[Dict[str, Any]] = None
    every_minutes: int = 60
    active: bool = True


class FilePipelineRequest(BaseModel):
    mode: str  # index | refresh | watch_refresh | analyze_indexed | organize_indexed
    roots: Optional[List[str]] = None
    recursive: bool = True
    allowed_exts: Optional[List[str]] = None
    max_files: int = 5000
    max_depth: Optional[int] = None
    max_runtime_seconds: Optional[float] = None
    follow_symlinks: bool = False
    stale_after_hours: int = 24
    max_files_per_watch: int = 5000
    include_paths: Optional[List[str]] = None
    exclude_paths: Optional[List[str]] = None
    min_size_bytes: Optional[int] = None
    max_size_bytes: Optional[int] = None
    modified_after_ts: Optional[float] = None
    persona_name: Optional[str] = None
    content_type: Optional[str] = None


@router.post("/runs/file-pipeline")
async def run_file_pipeline(
    payload: FilePipelineRequest,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    svc = TaskMasterService(db)
    request_payload = payload.model_dump()
    if request_payload.get("allowed_exts"):
        request_payload["allowed_exts"] = [
            e.lower() if str(e).startswith(".") else f".{str(e).lower()}"
            for e in request_payload["allowed_exts"]
        ]
    out = svc.run_file_pipeline(mode=payload.mode, payload=request_payload)
    if not out.get("success"):
        raise HTTPException(status_code=500, detail=out.get("error", "taskmaster pipeline failed"))
    return out


@router.get("/runs")
async def list_runs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    run_type: Optional[str] = Query(None),
    started_after: Optional[str] = Query(None),
    started_before: Optional[str] = Query(None),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    svc = TaskMasterService(db)
    return svc.list_runs(
        limit=limit,
        offset=offset,
        status=status,
        run_type=run_type,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/runs/{run_id}")
async def get_run(
    run_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    svc = TaskMasterService(db)
    run = svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"success": True, "run": run}


@router.get("/runs/{run_id}/events")
async def get_events(
    run_id: int,
    limit: int = Query(500, ge=1, le=5000),
    level: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    svc = TaskMasterService(db)
    return svc.get_events(run_id, limit=limit, level=level, event_type=event_type)


@router.get("/runs/{run_id}/skill-results")
async def get_skill_results(
    run_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    svc = TaskMasterService(db)
    return svc.get_skill_results(run_id)


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    svc = TaskMasterService(db)
    out = svc.cancel_run(run_id)
    if not out.get("run"):
        raise HTTPException(status_code=404, detail="Run not found")
    if not out.get("success"):
        raise HTTPException(status_code=409, detail="Run cannot be cancelled")
    return out


@router.post("/runs/{run_id}/retry")
async def retry_run(
    run_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    svc = TaskMasterService(db)
    out = svc.retry_run(run_id)
    if not out.get("success"):
        err = out.get("error", "retry_failed")
        code = 404 if err == "run_not_found" else 400
        raise HTTPException(status_code=code, detail=err)
    return out


@router.get("/dashboard")
async def dashboard(
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    svc = TaskMasterService(db)
    return svc.dashboard()


@router.post("/schedules")
async def create_schedule(
    payload: TaskmasterSchedulePayload,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    svc = TaskMasterService(db)
    return svc.create_schedule(
        name=payload.name,
        mode=payload.mode,
        payload=payload.payload,
        every_minutes=payload.every_minutes,
        active=payload.active,
    )


@router.get("/schedules")
async def list_schedules(
    active_only: bool = Query(False),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    svc = TaskMasterService(db)
    return svc.list_schedules(active_only=active_only)


@router.post("/schedules/run-due")
async def run_due_schedules(
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    svc = TaskMasterService(db)
    return svc.run_due_schedules()
