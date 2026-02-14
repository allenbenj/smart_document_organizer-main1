from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.dependencies import get_database_manager_strict_dep
from services.organization_service import OrganizationService

router = APIRouter()


class GeneratePayload(BaseModel):
    limit: int = 200
    provider: Optional[str] = None
    model: Optional[str] = None
    run_id: Optional[int] = None
    root_prefix: Optional[str] = None


class RejectPayload(BaseModel):
    note: Optional[str] = None


class EditPayload(BaseModel):
    proposed_folder: str
    proposed_filename: str
    note: Optional[str] = None


class ApplyPayload(BaseModel):
    limit: int = 200
    dry_run: bool = True


class LLMSwitchPayload(BaseModel):
    provider: Optional[str] = None  # xai|deepseek|None(reset)
    model: Optional[str] = None


class ClearPayload(BaseModel):
    status: Optional[str] = "proposed"
    root_prefix: Optional[str] = None
    note: Optional[str] = "bulk_clear"


@router.get("/organization/llm")
async def llm_status(db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    svc = OrganizationService(db)
    return {"success": True, **svc.llm_status()}


@router.post("/organization/llm/switch")
async def llm_switch(payload: LLMSwitchPayload, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    provider = payload.provider.strip().lower() if isinstance(payload.provider, str) and payload.provider.strip() else None
    if provider not in {None, "xai", "deepseek"}:
        raise HTTPException(status_code=400, detail="provider must be one of: xai, deepseek, null")
    svc = OrganizationService(db)
    svc.set_runtime_llm(provider=provider, model=payload.model)
    return {"success": True, "active": svc.llm_status().get("active"), "runtime_override": svc.get_runtime_llm()}


@router.post("/organization/proposals/generate")
async def generate_proposals(payload: GeneratePayload, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    svc = OrganizationService(db)
    return svc.generate_proposals(
        run_id=payload.run_id,
        limit=payload.limit,
        provider=payload.provider,
        model=payload.model,
        root_prefix=payload.root_prefix,
    )


@router.get("/organization/proposals")
async def list_proposals(status: Optional[str] = None, limit: int = 200, offset: int = 0, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    svc = OrganizationService(db)
    return svc.list_proposals(status=status, limit=limit, offset=offset)


@router.get("/organization/feedback")
async def list_feedback(limit: int = 200, offset: int = 0, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    svc = OrganizationService(db)
    return svc.list_feedback(limit=limit, offset=offset)


@router.get("/organization/actions")
async def list_actions(limit: int = 200, offset: int = 0, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    svc = OrganizationService(db)
    return svc.list_actions(limit=limit, offset=offset)


@router.get("/organization/stats")
async def org_stats(db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    svc = OrganizationService(db)
    return svc.stats()


@router.post("/organization/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: int, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    svc = OrganizationService(db)
    out = svc.approve_proposal(proposal_id)
    if not out.get("success"):
        raise HTTPException(status_code=404, detail=out.get("error", "not_found"))
    return out


@router.post("/organization/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: int, payload: RejectPayload, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    svc = OrganizationService(db)
    out = svc.reject_proposal(proposal_id, note=payload.note)
    if not out.get("success"):
        raise HTTPException(status_code=404, detail=out.get("error", "not_found"))
    return out


@router.post("/organization/proposals/{proposal_id}/edit")
async def edit_proposal(proposal_id: int, payload: EditPayload, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    svc = OrganizationService(db)
    out = svc.edit_proposal(
        proposal_id,
        proposed_folder=payload.proposed_folder,
        proposed_filename=payload.proposed_filename,
        note=payload.note,
    )
    if not out.get("success"):
        raise HTTPException(status_code=404, detail=out.get("error", "not_found"))
    return out


@router.post("/organization/apply")
async def apply_approved(payload: ApplyPayload, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    svc = OrganizationService(db)
    return svc.apply_approved(limit=payload.limit, dry_run=payload.dry_run)


@router.post("/organization/proposals/clear")
async def clear_proposals(payload: ClearPayload, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    svc = OrganizationService(db)
    return svc.clear_proposals(status=payload.status, root_prefix=payload.root_prefix, note=payload.note)
