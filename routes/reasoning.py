from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from services.agent_service import AgentService
from services.dependencies import get_agent_manager_strict_dep
from services.response_schema_validator import enforce_agent_response

router = APIRouter()


class ReasoningRequest(BaseModel):
    text: str
    options: Dict[str, Any] = Field(default_factory=dict)


@router.post("/legal")
async def run_legal_reasoning(
    request: ReasoningRequest,
    manager=Depends(get_agent_manager_strict_dep),
) -> Dict[str, Any]:
    service = AgentService(manager)
    result = await service.dispatch_task(
        "analyze_legal",
        {"text": request.text, "context": request.options or {}},
    )

    if isinstance(result, dict):
        out = {
            "success": bool(result.get("success", False)),
            "data": result.get("data", {}),
            "error": result.get("error"),
            "processing_time": result.get("processing_time", 0.0),
            "agent_type": result.get("agent_type", "legal_reasoning"),
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

    return enforce_agent_response("legal_reasoning", out)
