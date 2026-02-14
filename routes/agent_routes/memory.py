"""
Agent Memory Routes
===================

Endpoints for managing agent memory: proposals, corrections, deletions, stats.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from .common import get_memory_service

router = APIRouter()
logger = logging.getLogger(__name__)


class MemoryProposalPayload(BaseModel):
    namespace: str
    key: str
    content: str
    memory_type: str = "analysis"  # maps to MemoryType
    agent_id: Optional[str] = None
    document_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    confidence_score: float = 1.0
    importance_score: float = 1.0


class MemoryDecisionPayload(BaseModel):
    proposal_id: int
    corrections: Optional[Dict[str, Any]] = None


class MemoryCorrectionPayload(BaseModel):
    record_id: str
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    importance_score: Optional[float] = None
    confidence_score: Optional[float] = None


class MemoryDeletePayload(BaseModel):
    record_id: str


@router.get("/agents/memory/proposals")
async def list_memory_proposals(request: Request) -> Dict[str, Any]:
    svc = await get_memory_service(request)
    if not svc:
        # Fallback empty or error
        return {"proposals": []}
    items = await svc.get_pending_proposals(limit=500, offset=0)
    return {"proposals": items}


@router.post("/agents/memory/proposals")
async def propose_memory_entry(
    payload: MemoryProposalPayload, request: Request
) -> Dict[str, Any]:
    """Propose a memory record for human review."""
    svc = await get_memory_service(request)
    if not svc:
        raise HTTPException(status_code=503, detail="Memory service unavailable")

    return await svc.create_proposal(payload.model_dump())


@router.post("/agents/memory/proposals/approve")
async def approve_memory_proposal(
    decision: MemoryDecisionPayload, request: Request
) -> Dict[str, Any]:
    svc = await get_memory_service(request)
    if not svc:
        raise HTTPException(status_code=503, detail="Memory service unavailable")

    try:
        return await svc.approve_proposal(decision.proposal_id, decision.corrections)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Approval failed: {e}")
        raise HTTPException(status_code=500, detail="Approval failed")


@router.post("/agents/memory/proposals/reject")
async def reject_memory_proposal(decision: MemoryDecisionPayload, request: Request) -> Dict[str, Any]:
    svc = await get_memory_service(request)
    if not svc:
        raise HTTPException(status_code=503, detail="Memory service unavailable")

    try:
        return await svc.reject_proposal(decision.proposal_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/agents/memory/correct")
async def correct_memory_record(
    payload: MemoryCorrectionPayload, request: Request
) -> Dict[str, Any]:
    svc = await get_memory_service(request)
    if not svc:
        raise HTTPException(status_code=503, detail="Memory service unavailable")

    ok = await svc.correct_record(payload.record_id, payload.model_dump(exclude_unset=True, exclude={"record_id"}))
    if not ok:
        raise HTTPException(status_code=404, detail="Record not found or update failed")
    return {"updated": ok}


@router.post("/agents/memory/delete")
async def delete_memory_record(
    payload: MemoryDeletePayload, request: Request
) -> Dict[str, Any]:
    svc = await get_memory_service(request)
    if not svc:
        raise HTTPException(status_code=503, detail="Memory service unavailable")
    ok = await svc.delete_record(payload.record_id)
    return {"deleted": ok}


@router.get("/agents/memory/flags")
async def list_flagged_proposals(request: Request) -> Dict[str, Any]:
    svc = await get_memory_service(request)
    if not svc:
        return {"count": 0, "flags": {}, "items": []}
    return await svc.get_flagged_proposals()


@router.get("/agents/memory/stats")
async def memory_stats(request: Request) -> Dict[str, Any]:
    svc = await get_memory_service(request)
    if not svc:
        return {}
    return await svc.get_stats()
