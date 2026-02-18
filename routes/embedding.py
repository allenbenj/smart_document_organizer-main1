from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.agent_service import AgentService
from services.dependencies import get_agent_manager_strict_dep
from services.response_schema_validator import enforce_agent_response

router = APIRouter()


class EmbeddingRequest(BaseModel):
    text: str
    model_name: str = ""
    operation: str = "embed"
    options: Dict[str, Any] = {}


def _to_response(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        return {
            "success": bool(result.get("success", False)),
            "data": result.get("data", {}),
            "error": result.get("error"),
            "processing_time": result.get("processing_time", 0.0),
            "agent_type": result.get("agent_type", "embed"),
            "metadata": result.get("metadata", {}),
        }
    return {
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "processing_time": result.processing_time,
        "agent_type": result.agent_type,
        "metadata": result.metadata,
    }


async def _dispatch_embed(
    request: EmbeddingRequest,
    manager: Any,
) -> Dict[str, Any]:
    service = AgentService(manager)
    payload = {
        "texts": [request.text],
        "options": {
            **(request.options or {}),
            "model_name": request.model_name,
            "operation": request.operation,
        },
    }
    result = await service.dispatch_task("embed_texts", payload)
    return enforce_agent_response("embed", _to_response(result))


@router.post("/run_operation")
async def run_embedding_operation(
    request: EmbeddingRequest,
    manager=Depends(get_agent_manager_strict_dep),
) -> Dict[str, Any]:
    return await _dispatch_embed(request, manager)


@router.post("/")
async def get_embeddings(
    request: EmbeddingRequest,
    manager=Depends(get_agent_manager_strict_dep),
) -> Dict[str, Any]:
    return await _dispatch_embed(request, manager)
