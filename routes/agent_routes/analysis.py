"""Agent analysis endpoints."""

import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, Depends
from pydantic import BaseModel

from services.agent_service import AgentService
from services.response_schema_validator import enforce_agent_response
from .common import (
    get_agent_service,
    get_memory_service,
)
from services.dependencies import get_database_manager_strict_dep

router = APIRouter()
logger = logging.getLogger(__name__)


def _v(agent_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return enforce_agent_response(agent_type, payload)


class TextPayload(BaseModel):
    text: str
    options: Optional[Dict[str, Any]] = None


class LegalAnalysisPayload(BaseModel):
    text: str
    options: Optional[Dict[str, Any]] = None


class FeedbackPayload(BaseModel):
    analysis_id: str
    agent: str
    rating: int
    comments: Optional[str] = None
    tags: Optional[List[str]] = None
    suggested_corrections: Optional[Dict[str, Any]] = None


class EmbedPayload(BaseModel):
    texts: List[str]
    options: Optional[Dict[str, Any]] = None


class ClassifyPayload(BaseModel):
    text: str
    options: Optional[Dict[str, Any]] = None

@router.post("/agents/legal")
@router.post("/agents/legal-reasoning")
async def analyze_legal(
    request: Request, 
    payload: LegalAnalysisPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        opts = payload.options or {}
        opts.setdefault("timeout", 5.0)
        
        # Dispatch via service
        result = await service.dispatch_task("analyze_legal", {
            "text": payload.text,
            "context": opts
        })
        
        # Result from dispatch_task might be the AgentResult object or a dict if failed
        # AgentService returns whatever manager returns. Manager returns AgentResult usually.
        # But dispatch_task also wraps exceptions in a dict {success: False...} if it catches exception.
        # However, manager calls inside dispatch_task might return AgentResult.
        
        # Let's assume result follows the same contract as manager today for now
        # but handled better.
        
        # If AgentService.dispatch_task returns a dict, we need to handle it.
        # The current implementation of dispatch_task returns:
        # 1. Manager result (AgentResult) on success
        # 2. Dict on Exception {success: False, error: ...}
        
        if isinstance(result, dict) and not result.get("success", True):
            return _v("legal_reasoning", {
                "success": False,
                "data": result.get("data", {}),
                "error": result.get("error", "Task failed"),
                "processing_time": result.get("processing_time"),
                "agent_type": result.get("agent_type", "legal_reasoning"),
                "metadata": result.get("metadata", {"recoverable": True}),
            })

        # Access attributes of AgentResult
        out = {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "processing_time": result.processing_time,
            "agent_type": result.agent_type,
            "metadata": result.metadata,
        }

        svc = await get_memory_service(request)
        if svc:
            try:
                await svc.create_proposal(
                    {
                        "namespace": "legal_analysis",
                        "key": f"{(result.metadata or {}).get('document_id','unknown')}_legal",
                        "content": json.dumps(result.data or {}),
                        "memory_type": "analysis",
                        "confidence_score": float((result.metadata or {}).get("confidence", 0.5)),
                        "importance_score": 0.6,
                        "metadata": result.metadata,
                    }
                )
            except Exception as e:
                logger.error(f"Failed to create memory proposal: {e}")
                out.setdefault("metadata", {})["memory_write"] = "failed"
        else:
            out.setdefault("metadata", {})["memory_write"] = "unavailable"
        if not result.success:
            deg = ((result.metadata or {}).get("degradation") if result.metadata else None)
            out["metadata"] = out.get("metadata") or {}
            out["metadata"]["degradation"] = deg
            return _v("legal_reasoning", out)
        return _v("legal_reasoning", out)
    except HTTPException as e:
        return _v("legal_reasoning", {
            "success": False,
            "data": {},
            "error": str(e.detail) if hasattr(e, "detail") else "Legal analysis failed",
            "processing_time": None,
            "agent_type": "legal_reasoning",
            "metadata": {"recoverable": True},
        })
    except Exception as e:
        logger.error(f"Legal analysis failed: {e}")
        return _v("legal_reasoning", {
            "success": False,
            "data": {},
            "error": f"Legal analysis failed: {e}",
            "processing_time": None,
            "agent_type": "legal_reasoning",
            "metadata": {"recoverable": True},
        })


@router.post("/agents/feedback")
async def submit_feedback(
    payload: FeedbackPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        stored = await service.dispatch_task("submit_feedback", {
            "analysis_id": payload.analysis_id,
            "agent": payload.agent,
            "rating": payload.rating,
            "comments": payload.comments,
            "tags": payload.tags or [],
            "suggested_corrections": payload.suggested_corrections or {}
        })
        return {"success": True, "stored": stored}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submitting feedback failed: {e}")
        raise HTTPException(status_code=500, detail="Feedback submission failed")


@router.post("/agents/irac")
async def analyze_irac(
    payload: TextPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        result = await service.dispatch_task("analyze_irac", {
            "text": payload.text,
            "options": payload.options
        })
        
        if isinstance(result, dict) and not result.get("success", True):
            raise HTTPException(status_code=503, detail=result.get("error", "unavailable"))
             
        out = {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "processing_time": result.processing_time,
            "agent_type": result.agent_type,
            "metadata": result.metadata,
        }
        if not result.success:
            deg = ((result.metadata or {}).get("degradation") if result.metadata else None)
            raise HTTPException(status_code=503, detail={"error": result.error or "unavailable", "degradation": deg})
        return _v("irac_analyzer", out)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"IRAC analysis failed: {e}")
        raise HTTPException(status_code=500, detail="IRAC analysis failed")


@router.post("/agents/toulmin")
async def analyze_toulmin(
    payload: TextPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        result = await service.dispatch_task("analyze_toulmin", {
            "text": payload.text,
            "options": payload.options
        })

        if isinstance(result, dict) and not result.get("success", True):
            raise HTTPException(status_code=503, detail=result.get("error", "unavailable"))

        out = {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "processing_time": result.processing_time,
            "agent_type": result.agent_type,
            "metadata": result.metadata,
        }
        if not result.success:
            deg = ((result.metadata or {}).get("degradation") if result.metadata else None)
            raise HTTPException(status_code=503, detail={"error": result.error or "unavailable", "degradation": deg})
        return _v("toulmin_analyzer", out)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Toulmin analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Toulmin analysis failed")


@router.post("/agents/entities")
async def extract_entities(
    payload: TextPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        result = await service.dispatch_task("extract_entities", {"text": payload.text})

        if isinstance(result, dict):
            if not result.get("success", True):
                return _v("entity_extractor", {
                    "success": False,
                    "data": result.get("data", {}),
                    "error": result.get("error", "Entity extraction failed"),
                    "metadata": {"recoverable": True},
                })
            return _v("entity_extractor", {
                "success": True,
                "data": result.get("data", {}),
                "error": None,
                "metadata": result.get("metadata", {}),
            })

        return _v("entity_extractor", {
            "success": bool(getattr(result, "success", False)),
            "data": getattr(result, "data", {}),
            "error": getattr(result, "error", None),
            "metadata": getattr(result, "metadata", {}),
        })
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        return _v("entity_extractor", {
            "success": False,
            "data": {},
            "error": f"Entity extraction failed: {e}",
            "metadata": {"recoverable": True},
        })


@router.post("/agents/semantic")
async def semantic_analysis(
    payload: TextPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        result = await service.dispatch_task("analyze_semantic", {
            "text": payload.text,
            "options": payload.options
        })

        # Keep HTTP 200 and return structured payload for GUI resilience.
        if isinstance(result, dict):
            if not result.get("success", True):
                return _v("semantic", {
                    "success": False,
                    "data": result.get("data", {}),
                    "error": result.get("error", "unavailable"),
                    "metadata": {
                        "degradation": result.get("degradation")
                        or result.get("metadata", {}).get("degradation"),
                        "recoverable": True,
                    },
                })
            return _v("semantic", {
                "success": True,
                "data": result.get("data", {}),
                "error": None,
                "metadata": result.get("metadata", {}),
            })

        if hasattr(result, "success") and not result.success:
            deg = ((result.metadata or {}).get("degradation") if result.metadata else None)
            return _v("semantic", {
                "success": False,
                "data": result.data or {},
                "error": result.error or "unavailable",
                "metadata": {"degradation": deg, "recoverable": True},
            })

        return _v("semantic", {
            "success": True,
            "data": (result.data if hasattr(result, "data") else {}),
            "error": None,
            "metadata": (result.metadata if hasattr(result, "metadata") else {}),
        })
    except Exception as e:
        logger.error(f"Semantic analysis failed: {e}")
        return _v("semantic", {
            "success": False,
            "data": {},
            "error": f"Semantic analysis failed: {e}",
            "metadata": {"recoverable": True},
        })


@router.post("/agents/contradictions")
async def contradictions(
    payload: TextPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        result = await service.dispatch_task("analyze_contradictions", {
            "text": payload.text,
            "options": payload.options
        })
        
        if isinstance(result, dict) and not result.get("success", True):
            raise HTTPException(status_code=503, detail={"error": result.get("error", "unavailable")})

        if hasattr(result, "success") and not result.success:
            deg = ((result.metadata or {}).get("degradation") if result.metadata else None)
            raise HTTPException(status_code=503, detail={"error": result.error or "unavailable", "degradation": deg})

        return {"success": True, "data": result.data, "error": None}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contradiction detection failed: {e}")
        raise HTTPException(status_code=500, detail="Contradiction detection failed")


@router.post("/agents/violations")
async def violations(
    payload: TextPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        result = await service.dispatch_task("analyze_violations", {
            "text": payload.text,
            "options": payload.options
        })
        
        if isinstance(result, dict) and not result.get("success", True):
            raise HTTPException(status_code=503, detail={"error": result.get("error", "unavailable")})

        if hasattr(result, "success") and not result.success:
            deg = ((result.metadata or {}).get("degradation") if result.metadata else None)
            raise HTTPException(status_code=503, detail={"error": result.error or "unavailable", "degradation": deg})

        return {"success": True, "data": result.data, "error": None}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Violation review failed: {e}")
        raise HTTPException(status_code=500, detail="Violation review failed")


@router.post("/agents/contract")
async def analyze_contract(
    payload: TextPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        result = await service.dispatch_task("analyze_contract", {
            "text": payload.text,
            "options": payload.options
        })

        if isinstance(result, dict) and not result.get("success", True):
            return _v("contract_analyzer", {
                "success": False,
                "data": result.get("data", {}),
                "error": result.get("error", "unavailable"),
                "metadata": {"recoverable": True},
            })

        return _v("contract_analyzer", {
            "success": bool(getattr(result, "success", False)),
            "data": getattr(result, "data", {}),
            "error": getattr(result, "error", None),
            "processing_time": getattr(result, "processing_time", None),
            "agent_type": getattr(result, "agent_type", "contract_analyzer"),
            "metadata": getattr(result, "metadata", {}),
        })
    except Exception as e:
        logger.error(f"Contract analysis failed: {e}")
        return _v("contract_analyzer", {
            "success": False,
            "data": {},
            "error": f"Contract analysis failed: {e}",
            "metadata": {"recoverable": True},
        })


@router.post("/agents/compliance")
async def check_compliance(
    payload: TextPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        result = await service.dispatch_task("check_compliance", {
            "text": payload.text,
            "options": payload.options
        })

        if isinstance(result, dict) and not result.get("success", True):
            return _v("compliance_checker", {
                "success": False,
                "data": result.get("data", {}),
                "error": result.get("error", "unavailable"),
                "metadata": {"recoverable": True},
            })

        return _v("compliance_checker", {
            "success": bool(getattr(result, "success", False)),
            "data": getattr(result, "data", {}),
            "error": getattr(result, "error", None),
            "processing_time": getattr(result, "processing_time", None),
            "agent_type": getattr(result, "agent_type", "compliance_checker"),
            "metadata": getattr(result, "metadata", {}),
        })
    except Exception as e:
        logger.error(f"Compliance check failed: {e}")
        return _v("compliance_checker", {
            "success": False,
            "data": {},
            "error": f"Compliance check failed: {e}",
            "metadata": {"recoverable": True},
        })


@router.post("/agents/embed")
@router.post("/agents/embedding")
@router.post("/agents/embeddings")
async def embed(
    payload: EmbedPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        result = await service.dispatch_task("embed_texts", {
            "texts": payload.texts,
            "options": payload.options
        })
        if isinstance(result, dict) and not result.get("success", True):
            raise HTTPException(status_code=500, detail=result.get("error", "Embedding failed"))

        return _v("embed", {"success": result.success, "data": result.data, "error": result.error})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(status_code=500, detail="Embedding failed")


@router.post("/agents/orchestrate")
async def orchestrate(
    payload: TextPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        result = await service.dispatch_task("orchestrate_task", {
            "text": payload.text,
            "options": payload.options
        })
        if isinstance(result, dict) and not result.get("success", True):
            raise HTTPException(status_code=500, detail=result.get("error", "Orchestration failed"))

        return _v("orchestrate", {"success": result.success, "data": result.data, "error": result.error})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Orchestration failed: {e}")
        raise HTTPException(status_code=500, detail="Orchestration failed")


@router.post("/agents/classify")
async def classify(
    payload: ClassifyPayload,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        result = await service.dispatch_task("classify_text", {
            "text": payload.text,
            "options": payload.options
        })
        if isinstance(result, dict) and not result.get("success", True):
            raise HTTPException(status_code=500, detail=result.get("error", "Classification failed"))

        return _v("classify", {"success": result.success, "data": result.data, "error": result.error})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(status_code=500, detail="Classification failed")


@router.post("/agents/process-document")
async def process_document(
    file: UploadFile | None = File(default=None),
    file_id: int | None = Form(default=None),
    service: AgentService = Depends(get_agent_service),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        if file_id is not None:
            rec = db.get_indexed_file(file_id)
            if not rec:
                raise HTTPException(status_code=404, detail=f"Indexed file not found: {file_id}")
            if rec.get("status") != "ready":
                raise HTTPException(status_code=400, detail={"error": "indexed_file_not_ready", "status": rec.get("status"), "last_error": rec.get("last_error")})
            result = await service.dispatch_task("process_document", {"file_path": rec.get("normalized_path")})
        else:
            if file is None:
                raise HTTPException(status_code=400, detail="Provide either file upload or file_id")
            suffix = os.path.splitext(file.filename or "")[1] or ""
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                blob = await file.read()
                tmp.write(blob)
                tmp_path = tmp.name
            try:
                result = await service.dispatch_task("process_document", {"file_path": tmp_path})
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        if result is None:
            return _v("document_processor", {
                "success": False,
                "error": "Processing failed: empty result",
                "data": {},
                "agent_type": "document_processor",
                "metadata": {"recoverable": True},
            })

        if isinstance(result, dict):
            # Return structured failure payloads with 200 so GUI clients that call
            # response.raise_for_status() do not crash the whole app flow.
            if not result.get("success", True):
                result.setdefault("data", {})
                result.setdefault("agent_type", "document_processor")
                result.setdefault("metadata", {"recoverable": True})
            return _v("document_processor", result)

        if not hasattr(result, "success"):
            return _v("document_processor", {
                "success": False,
                "error": f"Processing failed: unexpected result type {type(result).__name__}",
                "data": {},
                "agent_type": "document_processor",
                "metadata": {"recoverable": True},
            })

        return _v("document_processor", {
            "success": bool(result.success),
            "data": result.data,
            "error": result.error,
            "processing_time": result.processing_time,
            "agent_type": result.agent_type,
            "metadata": result.metadata,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Process document failed: {e}")
        raise HTTPException(status_code=500, detail="Process document failed")


@router.post("/agents/process-documents")
async def process_documents(
    files: List[UploadFile] = File(default_factory=list),
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """Batch document processing endpoint used by GUI folder/multi-file workers."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    results: List[Dict[str, Any]] = []

    for up in files:
        suffix = os.path.splitext(up.filename or "")[1] or ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            blob = await up.read()
            tmp.write(blob)
            tmp_path = tmp.name

        try:
            result = await service.dispatch_task(
                "process_document", {"file_path": tmp_path}
            )
            if result is None:
                result = {
                    "success": False,
                    "error": "Processing failed: empty result",
                    "data": {},
                    "agent_type": "document_processor",
                    "metadata": {"recoverable": True},
                }
            elif not isinstance(result, dict):
                result = {
                    "success": bool(getattr(result, "success", False)),
                    "data": getattr(result, "data", {}),
                    "error": getattr(result, "error", None),
                    "processing_time": getattr(result, "processing_time", None),
                    "agent_type": getattr(result, "agent_type", "document_processor"),
                    "metadata": getattr(result, "metadata", {}),
                }

            validated = _v("document_processor", result)
            results.append({"filename": up.filename, **validated})
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    success_count = sum(1 for r in results if r.get("success"))
    return {
        "success": success_count == len(results),
        "processed": success_count,
        "failed": len(results) - success_count,
        "results": results,
    }
