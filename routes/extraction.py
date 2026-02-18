from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from services.agent_service import AgentService
from services.dependencies import get_agent_manager_strict_dep
from services.response_schema_validator import enforce_agent_response

router = APIRouter()


class ExtractionRequest(BaseModel):
    text: str
    extraction_type: str = "ner"
    options: Dict[str, Any] = {}


@router.post("/run")
async def run_entity_extraction(
    request: ExtractionRequest,
    manager=Depends(get_agent_manager_strict_dep),
):
    service = AgentService(manager)
    payload = {
        "text": request.text,
        "options": {**(request.options or {}), "extraction_type": request.extraction_type},
    }
    result = await service.dispatch_task("extract_entities", payload)

    if isinstance(result, dict):
        out = {
            "success": bool(result.get("success", False)),
            "data": result.get("data", {}),
            "error": result.get("error"),
            "processing_time": result.get("processing_time", 0.0),
            "agent_type": result.get("agent_type", "entity_extractor"),
            "metadata": result.get("metadata", {}),
        }
    else:
        out = {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "processing_time": result.processing_time,
            "agent_type": result.agent_type,
            "metadata": result.metadata,
        }

    return enforce_agent_response("entity_extractor", out)


@router.get("/{doc_id}/entities")
async def get_document_entities(doc_id: str = Path(..., title="The ID of the document")):
    raise HTTPException(
        status_code=501,
        detail=(
            "Entity retrieval by document id is not implemented in production routes. "
            "Use POST /api/extraction/run with document text."
        ),
    )
