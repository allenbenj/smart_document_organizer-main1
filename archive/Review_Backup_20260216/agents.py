from fastapi import APIRouter, HTTPException, Request
from fastapi import UploadFile, File
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import uuid

from agents import get_agent_manager, list_agent_types
from mem_db.memory.memory_interfaces import MemoryType, MemoryRecord
from mem_db.memory import proposals_db

router = APIRouter()
logger = logging.getLogger(__name__)


class TextPayload(BaseModel):
    text: str
    options: Optional[Dict[str, Any]] = None


@router.get("/agents")
async def get_agents() -> Dict[str, Any]:
    """List available agent types and discovered modules."""
    try:
        base = Path(__file__).resolve().parents[1] / "agents"
        files: List[str] = []
        try:
            for p in base.rglob("*.py"):
                if p.name == "__init__.py":
                    continue
                files.append(str(p.relative_to(base)))
        except Exception:
            pass
        return {"agents": list_agent_types(), "modules": sorted(files)}
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list agents")


@router.get("/agents/health")
async def get_agents_health() -> Dict[str, Any]:
    """Get overall agent system health (production or fallback)."""
    try:
        manager = get_agent_manager()
        health = await manager.get_system_health()
        return {"health": health}
    except Exception as e:
        logger.error(f"Error getting agent health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent health")


class LegalAnalysisPayload(BaseModel):
    text: str
    options: Optional[Dict[str, Any]] = None


@router.post("/agents/legal")
async def analyze_legal(payload: LegalAnalysisPayload) -> Dict[str, Any]:
    """Run comprehensive legal analysis with explainability and KG hints."""
    try:
        manager = get_agent_manager()
        opts = payload.options or {}
        # Provide a conservative default timeout if caller doesn't specify
        opts.setdefault("timeout", 5.0)
        result = await manager.analyze_legal_reasoning(payload.text, **opts)
        out = {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "processing_time": result.processing_time,
            "agent_type": result.agent_type,
            "metadata": result.metadata,
        }
        try:
            # Propose memory for human review (legal reasoning)
            _memory_proposals.append({
                "id": len(_memory_proposals) + 1,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "namespace": "legal_analysis",
                "key": f"{result.metadata.get('document_id','unknown')}_legal",
                "content": json.dumps(result.data or {}),
                "memory_type": "analysis",
                "confidence_score": float(result.metadata.get("confidence", 0.5)),
                "importance_score": 0.6,
            })
        except Exception:
            pass
        if not result.success:
            deg = (result.metadata or {}).get("degradation") if result.metadata else None
            raise HTTPException(status_code=503, detail={"error": result.error or "unavailable", "degradation": deg})
        return out
    except Exception as e:
        logger.error(f"Legal analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Legal analysis failed")


class FeedbackPayload(BaseModel):
    analysis_id: str
    agent: str
    rating: int
    comments: Optional[str] = None
    tags: Optional[List[str]] = None
    suggested_corrections: Optional[Dict[str, Any]] = None


@router.post("/agents/feedback")
async def submit_feedback(payload: FeedbackPayload) -> Dict[str, Any]:
    """Submit user feedback to improve analysis quality over time."""
    try:
        manager = get_agent_manager()
        stored = await manager.submit_feedback(
            analysis_id=payload.analysis_id,
            agent=payload.agent,
            rating=payload.rating,
            comments=payload.comments,
            tags=payload.tags or [],
            suggested_corrections=payload.suggested_corrections or {},
        )
        return {"success": True, "stored": stored}
    except Exception as e:
        logger.error(f"Submitting feedback failed: {e}")
        raise HTTPException(status_code=500, detail="Feedback submission failed")


# ---------------- Memory Proposal & Review (NEW) ----------------

_memory_proposals: List[Dict[str, Any]] = []  # legacy in-memory (kept for compatibility)
_memory_proposal_seq = 0
_approved_index: Dict[str, str] = {}

# Simple sensitive terms and patterns for auto-flagging
SENSITIVE_TERMS = [
    "privileged", "confidential", "attorney-client", "sealed",
    "SSN", "social security", "medical", "HIPAA",
    "trade secret", "proprietary",
]


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


@router.get("/agents/memory/proposals")
async def list_memory_proposals() -> Dict[str, Any]:
    try:
        items = proposals_db.list_proposals(limit=500, offset=0)
        return {"proposals": items}
    except Exception:
        return {"proposals": _memory_proposals}


async def _get_config(request: Request) -> Optional[Any]:
    try:
        services = getattr(request.app.state, "services", None)
        if services and hasattr(services, "get_service"):
            return await services.get_service("config_manager")
    except Exception:
        return None
    return None


async def _get_memory_manager(request: Request) -> Optional[Any]:
    try:
        services = getattr(request.app.state, "services", None)
        if services and hasattr(services, "get_service"):
            return await services.get_service("memory_manager")
    except Exception:
        return None
    return None


def _to_memory_type(name: str) -> MemoryType:
    try:
        return MemoryType(name)
    except Exception:
        return MemoryType.ANALYSIS


async def _store_memory(mm: Any, payload: MemoryProposalPayload) -> Optional[str]:
    try:
        rec = MemoryRecord(
            record_id=str(uuid.uuid4()),
            namespace=payload.namespace,
            key=payload.key,
            content=payload.content,
            memory_type=_to_memory_type(payload.memory_type),
            agent_id=payload.agent_id,
            document_id=payload.document_id,
            metadata=payload.metadata or {},
            importance_score=float(payload.importance_score),
            confidence_score=float(payload.confidence_score),
        )
        rid = await mm.store(rec)
        return rid
    except Exception:
        return None


def _norm_key(namespace: str, key: str) -> str:
    return f"{namespace}::{key}"


def _normalize_content(content: str) -> str:
    return (content or "").strip().lower()


def _auto_flags(payload: MemoryProposalPayload) -> List[str]:
    flags: List[str] = []
    # Low confidence
    try:
        if float(payload.confidence_score) < 0.5:
            flags.append("low_confidence")
    except Exception:
        pass
    # High impact heuristic
    try:
        if float(payload.importance_score) >= 0.85:
            flags.append("high_impact")
    except Exception:
        pass
    # Sensitive content
    content_l = _normalize_content(payload.content)
    if any(term in content_l for term in (t.lower() for t in SENSITIVE_TERMS)):
        flags.append("sensitive")
    # Conflict with approved index
    nk = _norm_key(payload.namespace, payload.key)
    prev = _approved_index.get(nk)
    if prev is not None and prev != content_l:
        flags.append("conflict")
    return flags


@router.post("/agents/memory/proposals")
async def propose_memory_entry(payload: MemoryProposalPayload, request: Request) -> Dict[str, Any]:
    """Propose a memory record for human review.

    If confidence >= threshold (config `memory.approval_threshold`, default 0.7),
    auto-approve and store directly.
    """
    global _memory_proposal_seq
    threshold = 0.7
    cfg = await _get_config(request)
    try:
        if cfg is not None:
            threshold = float(getattr(cfg, "get_float", lambda *a, **k: threshold)("memory.approval_threshold", threshold))
    except Exception:
        pass

    proposal = payload.model_dump()
    _memory_proposal_seq += 1
    proposal_id = _memory_proposal_seq
    proposal.update({
        "id": proposal_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    })
    proposal["flags"] = _auto_flags(payload)

    stored_record_id: Optional[str] = None
    if payload.confidence_score >= threshold:
        mm = await _get_memory_manager(request)
        if mm is not None:
            rid = await _store_memory(mm, payload)
            if rid:
                stored_record_id = rid
                proposal["status"] = "approved"
                proposal["stored_record_id"] = rid
                # Update approved index
                _approved_index[_norm_key(payload.namespace, payload.key)] = _normalize_content(payload.content)
    try:
        proposals_db.init_schema()
        db_id = proposals_db.add_proposal({
            **proposal,
            "confidence_score": payload.confidence_score,
            "importance_score": payload.importance_score,
        })
        proposal_id = db_id
    except Exception:
        _memory_proposals.append(proposal)
    return {"id": proposal_id, "status": proposal["status"], "stored_record_id": stored_record_id}


@router.post("/agents/memory/proposals/approve")
async def approve_memory_proposal(decision: MemoryDecisionPayload, request: Request) -> Dict[str, Any]:
    for p in _memory_proposals:
        if p.get("id") == decision.proposal_id:
            if p.get("status") == "approved":
                return {"id": p["id"], "status": p["status"], "stored_record_id": p.get("stored_record_id")}
            payload = MemoryProposalPayload(**{k: p[k] for k in [
                "namespace","key","content","memory_type","agent_id","document_id","metadata","confidence_score","importance_score"
            ]})
            # Apply corrections before store
            if decision.corrections:
                for k, v in decision.corrections.items():
                    if hasattr(payload, k):
                        setattr(payload, k, v)
            mm = await _get_memory_manager(request)
            if mm is None:
                raise HTTPException(status_code=500, detail="Memory manager unavailable")
            rid = await _store_memory(mm, payload)
            if not rid:
                raise HTTPException(status_code=500, detail="Failed to store memory")
            p["status"] = "approved"
            p["stored_record_id"] = rid
            p["approved_at"] = datetime.now().isoformat()
            # Update approved index
            _approved_index[_norm_key(payload.namespace, payload.key)] = _normalize_content(payload.content)
            try:
                proposals_db.approve_proposal(p["id"], rid, p["approved_at"])
            except Exception:
                pass
            return {"id": p.get("id"), "status": p.get("status"), "stored_record_id": rid}
    raise HTTPException(status_code=404, detail="Proposal not found")


@router.post("/agents/memory/proposals/reject")
async def reject_memory_proposal(decision: MemoryDecisionPayload) -> Dict[str, Any]:
    for p in _memory_proposals:
        if p.get("id") == decision.proposal_id:
            p["status"] = "rejected"
            p["rejected_at"] = datetime.now().isoformat()
            try:
                proposals_db.reject_proposal(p["id"], p["rejected_at"])
            except Exception:
                pass
            return {"id": p.get("id"), "status": p.get("status")}
    raise HTTPException(status_code=404, detail="Proposal not found")


class MemoryCorrectionPayload(BaseModel):
    record_id: str
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    importance_score: Optional[float] = None
    confidence_score: Optional[float] = None


@router.post("/agents/memory/correct")
async def correct_memory_record(payload: MemoryCorrectionPayload, request: Request) -> Dict[str, Any]:
    mm = await _get_memory_manager(request)
    if mm is None:
        raise HTTPException(status_code=500, detail="Memory manager unavailable")
    rec = await mm.retrieve(payload.record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    if payload.content is not None:
        rec.content = payload.content
    if payload.metadata is not None:
        rec.metadata.update(payload.metadata)
    if payload.importance_score is not None:
        rec.importance_score = float(payload.importance_score)
    if payload.confidence_score is not None:
        rec.confidence_score = float(payload.confidence_score)
    ok = await mm.update(rec)
    return {"updated": bool(ok)}


class MemoryDeletePayload(BaseModel):
    record_id: str


@router.post("/agents/memory/delete")
async def delete_memory_record(payload: MemoryDeletePayload, request: Request) -> Dict[str, Any]:
    mm = await _get_memory_manager(request)
    if mm is None:
        raise HTTPException(status_code=500, detail="Memory manager unavailable")
    ok = await mm.delete(payload.record_id)
    return {"deleted": bool(ok)}


@router.get("/agents/memory/flags")
async def list_flagged_proposals() -> Dict[str, Any]:
    try:
        items = proposals_db.list_proposals(limit=500, offset=0)
        flagged = [p for p in items if p.get("flags")]
        counts: Dict[str, int] = {}
        for p in flagged:
            for f in p.get("flags", []):
                counts[f] = counts.get(f, 0) + 1
        return {"count": len(flagged), "flags": counts, "items": flagged}
    except Exception:
        flagged = [p for p in _memory_proposals if p.get("flags")]
        counts: Dict[str, int] = {}
        for p in flagged:
            for f in p.get("flags", []):
                counts[f] = counts.get(f, 0) + 1
        return {"count": len(flagged), "flags": counts, "items": flagged}


@router.get("/agents/memory/stats")
async def memory_stats() -> Dict[str, Any]:
    try:
        s = proposals_db.stats()
    except Exception:
        total = len(_memory_proposals)
        by_status: Dict[str, int] = {}
        for p in _memory_proposals:
            st = p.get("status", "pending")
            by_status[st] = by_status.get(st, 0) + 1
        s = {"total": total, "by_status": by_status, "flags": {}}
    return {
        "proposals_total": s.get("total", 0),
        "by_status": s.get("by_status", {}),
        "flags": s.get("flags", {}),
        "approved_index_size": len(_approved_index),
    }


@router.get("/agents/status/{agent_type}")
async def get_agent_status(agent_type: str) -> Dict[str, Any]:
    """Get status for a single agent type."""
    try:
        manager = get_agent_manager()
        # Use production AgentType
        try:
            from agents.production_agent_manager import AgentType as PAgentType
            AgentType = PAgentType
        except Exception:
            AgentType = None

        if AgentType is None:
            raise ValueError("AgentType enum unavailable")

        # Normalize string to enum
        enum_val = None
        for t in AgentType:
            if t.value == agent_type:
                enum_val = t
                break
        if enum_val is None:
            raise HTTPException(status_code=400, detail=f"Unknown agent type: {agent_type}")

        status = await manager.get_agent_status(enum_val)
        return {"agent": agent_type, "status": status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for {agent_type}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent status")


@router.post("/agents/irac")
async def analyze_irac(payload: TextPayload) -> Dict[str, Any]:
    """Run IRAC analysis via the active agent manager."""
    try:
        manager = get_agent_manager()
        options = payload.options or {}
        result = await manager.analyze_irac(payload.text, **options)
        out = {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "processing_time": result.processing_time,
            "agent_type": result.agent_type,
            "metadata": result.metadata,
        }
        try:
            _memory_proposals.append({
                "id": len(_memory_proposals) + 1,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "namespace": "legal_analysis",
                "key": f"{result.metadata.get('document_id','unknown')}_irac",
                "content": json.dumps(result.data or {}),
                "memory_type": "analysis",
                "confidence_score": float(result.metadata.get("confidence", 0.5)),
                "importance_score": 0.7,
            })
        except Exception:
            pass
        if not result.success:
            deg = (result.metadata or {}).get("degradation") if result.metadata else None
            raise HTTPException(status_code=503, detail={"error": result.error or "unavailable", "degradation": deg})
        return out
    except Exception as e:
        logger.error(f"IRAC analysis failed: {e}")
        raise HTTPException(status_code=500, detail="IRAC analysis failed")


@router.post("/agents/toulmin")
async def analyze_toulmin(payload: TextPayload) -> Dict[str, Any]:
    """Run Toulmin analysis via the active agent manager."""
    try:
        manager = get_agent_manager()
        options = payload.options or {}
        result = await manager.analyze_toulmin(payload.text, **options)
        out = {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "processing_time": result.processing_time,
            "agent_type": result.agent_type,
            "metadata": result.metadata,
        }
        try:
            _memory_proposals.append({
                "id": len(_memory_proposals) + 1,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "namespace": "legal_analysis",
                "key": f"{result.metadata.get('document_id','unknown')}_toulmin",
                "content": json.dumps(result.data or {}),
                "memory_type": "analysis",
                "confidence_score": float(result.metadata.get("confidence", 0.5)),
                "importance_score": 0.6,
            })
        except Exception:
            pass
        if not result.success:
            deg = (result.metadata or {}).get("degradation") if result.metadata else None
            raise HTTPException(status_code=503, detail={"error": result.error or "unavailable", "degradation": deg})
        return out
    except Exception as e:
        logger.error(f"Toulmin analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Toulmin analysis failed")


@router.post("/agents/entities")
async def extract_entities(payload: TextPayload) -> Dict[str, Any]:
    try:
        manager = get_agent_manager()
        result = await manager.extract_entities(payload.text, **(payload.options or {}))
        return {"success": result.success, "data": result.data, "error": result.error}
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        raise HTTPException(status_code=500, detail="Entity extraction failed")


@router.post("/agents/semantic")
async def semantic_analysis(payload: TextPayload) -> Dict[str, Any]:
    try:
        manager = get_agent_manager()
        result = await manager.analyze_semantic(payload.text, **(payload.options or {}))
        if not result.success:
            deg = (result.metadata or {}).get("degradation") if result.metadata else None
            raise HTTPException(status_code=503, detail={"error": result.error or "unavailable", "degradation": deg})
        out = {"success": True, "data": result.data, "error": None}
        try:
            _memory_proposals.append({
                "id": len(_memory_proposals) + 1,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "namespace": "legal_analysis",
                "key": f"semantic_{len(_memory_proposals)+1}",
                "content": json.dumps(result.data or {}),
                "memory_type": "analysis",
                "confidence_score": 0.6,
                "importance_score": 0.6,
            })
        except Exception:
            pass
        return out
    except Exception as e:
        logger.error(f"Semantic analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Semantic analysis failed")


@router.post("/agents/contradictions")
async def contradictions(payload: TextPayload) -> Dict[str, Any]:
    try:
        manager = get_agent_manager()
        result = await manager.analyze_contradictions(payload.text, **(payload.options or {}))
        if not result.success:
            deg = (result.metadata or {}).get("degradation") if result.metadata else None
            raise HTTPException(status_code=503, detail={"error": result.error or "unavailable", "degradation": deg})
        return {"success": True, "data": result.data, "error": None}
    except Exception as e:
        logger.error(f"Contradiction detection failed: {e}")
        raise HTTPException(status_code=500, detail="Contradiction detection failed")


@router.post("/agents/violations")
async def violations(payload: TextPayload) -> Dict[str, Any]:
    try:
        manager = get_agent_manager()
        result = await manager.analyze_violations(payload.text, **(payload.options or {}))
        if not result.success:
            deg = (result.metadata or {}).get("degradation") if result.metadata else None
            raise HTTPException(status_code=503, detail={"error": result.error or "unavailable", "degradation": deg})
        return {"success": True, "data": result.data, "error": None}
    except Exception as e:
        logger.error(f"Violation review failed: {e}")
        raise HTTPException(status_code=500, detail="Violation review failed")


class EmbedPayload(BaseModel):
    texts: List[str]
    options: Optional[Dict[str, Any]] = None


@router.post("/agents/embed")
async def embed(payload: EmbedPayload) -> Dict[str, Any]:
    try:
        manager = get_agent_manager()
        result = await manager.embed_texts(payload.texts, **(payload.options or {}))
        return {"success": result.success, "data": result.data, "error": result.error}
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(status_code=500, detail="Embedding failed")


@router.post("/agents/orchestrate")
async def orchestrate(payload: TextPayload) -> Dict[str, Any]:
    try:
        manager = get_agent_manager()
        result = await manager.orchestrate(payload.text, **(payload.options or {}))
        return {"success": result.success, "data": result.data, "error": result.error}
    except Exception as e:
        logger.error(f"Orchestration failed: {e}")
        raise HTTPException(status_code=500, detail="Orchestration failed")


class ClassifyPayload(BaseModel):
    text: str
    options: Optional[Dict[str, Any]] = None


@router.post("/agents/classify")
async def classify(payload: ClassifyPayload) -> Dict[str, Any]:
    try:
        manager = get_agent_manager()
        result = await manager.classify_text(payload.text, **(payload.options or {}))
        return {"success": result.success, "data": result.data, "error": result.error}
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(status_code=500, detail="Classification failed")


@router.post("/agents/process-document")
async def process_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Process an uploaded document using the production document processor.

    Saves to a temporary file, invokes the agent manager, and returns the
    processed document payload with content/chunks/metadata.
    """
    import tempfile, os
    try:
        manager = get_agent_manager()
        # Save to temp file
        suffix = os.path.splitext(file.filename or "")[1] or ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            blob = await file.read()
            tmp.write(blob)
            tmp_path = tmp.name
        try:
            result = await manager.process_document(tmp_path)
            return {
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "processing_time": result.processing_time,
                "agent_type": result.agent_type,
                "metadata": result.metadata,
            }
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Process document failed: {e}")
        raise HTTPException(status_code=500, detail="Process document failed")
