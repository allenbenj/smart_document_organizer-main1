from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.agent_service import AgentService
from services.dependencies import get_agent_manager_strict_dep
from services.response_schema_validator import enforce_agent_response

router = APIRouter()


class ClassificationRequest(BaseModel):
    text: str
    options: Dict[str, Any] = {}


@router.post("/run")
async def run_classification(
    request: ClassificationRequest,
    manager=Depends(get_agent_manager_strict_dep),
) -> Dict[str, Any]:
    service = AgentService(manager)
    result = await service.dispatch_task(
        "classify_text",
        {"text": request.text, "options": request.options or {}},
    )

    if isinstance(result, dict):
        out = {
            "success": bool(result.get("success", False)),
            "data": result.get("data", {}),
            "error": result.get("error"),
            "processing_time": result.get("processing_time", 0.0),
            "agent_type": result.get("agent_type", "classify"),
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

    return enforce_agent_response("classify", out)
