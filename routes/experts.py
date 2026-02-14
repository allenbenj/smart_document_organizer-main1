import logging
from typing import Dict  # noqa: E402

from fastapi import APIRouter, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from agents.utils.context_builder import AgentContextBuilder  # noqa: E402

router = APIRouter()
logger = logging.getLogger(__name__)


class ExpertPromptPayload(BaseModel):
    agent_name: str
    task_type: str
    task_data: str


@router.post("/experts/prompt")
async def build_expert_prompt(payload: ExpertPromptPayload) -> Dict[str, str]:
    try:
        builder = AgentContextBuilder()
        prompt = builder.generate_expert_prompt(
            payload.agent_name, payload.task_type, payload.task_data
        )
        return {"prompt": prompt}
    except Exception as e:
        logger.error(f"Expert prompt build failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to build expert prompt")
