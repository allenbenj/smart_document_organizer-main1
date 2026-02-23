from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from services.agent_service import AgentService
from services.dependencies import get_agent_manager_strict_dep
from services.response_schema_validator import enforce_agent_response

router = APIRouter()


class ExtractionRequest(BaseModel):
    text: str
    extraction_type: str = "ner"
    options: Dict[str, Any] = Field(default_factory=dict)


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
        raw_data = result.get("data", {})
        success = bool(result.get("success", False))
        error = result.get("error")
        processing_time = result.get("processing_time", 0.0)
        agent_type = result.get("agent_type", "entity_extractor")
        metadata = result.get("metadata", {})
    else:
        raw_data = result.data
        success = bool(result.success)
        error = result.error
        processing_time = result.processing_time
        agent_type = result.agent_type
        metadata = result.metadata

    if not isinstance(raw_data, dict):
        raw_data = {}

    extraction_result = (
        raw_data.get("extraction_result")
        if isinstance(raw_data.get("extraction_result"), dict)
        else raw_data
    )
    if not isinstance(extraction_result, dict):
        extraction_result = {}

    entities = (
        extraction_result.get("entities")
        if isinstance(extraction_result.get("entities"), list)
        else []
    )
    relationships = (
        extraction_result.get("relationships")
        if isinstance(extraction_result.get("relationships"), list)
        else []
    )
    extraction_stats = (
        extraction_result.get("extraction_stats")
        if isinstance(extraction_result.get("extraction_stats"), dict)
        else {}
    )
    extraction_methods_used = (
        extraction_result.get("extraction_methods_used")
        if isinstance(extraction_result.get("extraction_methods_used"), list)
        else []
    )
    validation_results = (
        extraction_result.get("validation_results")
        if isinstance(extraction_result.get("validation_results"), dict)
        else {}
    )
    if not extraction_stats:
        extraction_stats = {
            "entity_count": len(entities),
            "relationship_count": len(relationships),
        }

    out = {
        "success": success,
        "data": {
            **raw_data,
            "entities": entities,
            "relationships": relationships,
            "extraction_stats": extraction_stats,
            "extraction_methods_used": extraction_methods_used,
            "validation_results": validation_results,
        },
        "error": error,
        "processing_time": processing_time,
        "agent_type": agent_type,
        "metadata": metadata,
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
