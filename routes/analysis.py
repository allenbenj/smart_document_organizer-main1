from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.agent_service import AgentService
from services.dependencies import get_agent_manager_strict_dep
from services.response_schema_validator import enforce_agent_response

router = APIRouter()


class AnalysisRequest(BaseModel):
    text: str
    options: Dict[str, Any] = {}


@router.post("/semantic")
async def run_semantic_analysis(
    request: AnalysisRequest,
    manager=Depends(get_agent_manager_strict_dep),
) -> Dict[str, Any]:
    service = AgentService(manager)
    result = await service.dispatch_task(
        "analyze_semantic",
        {"text": request.text, "options": request.options or {}},
    )

    if isinstance(result, dict):
        out = {
            "success": bool(result.get("success", False)),
            "data": result.get("data", {}),
            "error": result.get("error"),
            "processing_time": result.get("processing_time", 0.0),
            "agent_type": result.get("agent_type", "semantic"),
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

    return enforce_agent_response("semantic", out)
