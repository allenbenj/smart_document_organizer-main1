import logging
from typing import Any, Dict, List, Optional  # noqa: E402

from fastapi import APIRouter, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from pipelines.presets import get_presets  # noqa: E402
from pipelines.runner import Pipeline, Step, run_pipeline  # noqa: E402

router = APIRouter()
logger = logging.getLogger(__name__)


class StepModel(BaseModel):
    name: str
    options: Optional[Dict[str, Any]] = None


class PipelineModel(BaseModel):
    steps: List[StepModel]
    context: Optional[Dict[str, Any]] = None


@router.post("/pipeline/run")
async def pipeline_run(p: PipelineModel) -> Dict[str, Any]:
    try:
        pl = Pipeline(
            steps=[Step(name=s.name, options=s.options or {}) for s in p.steps]
        )
        result = await run_pipeline(pl, p.context or {})
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Pipeline run failed: {e}")
        raise HTTPException(status_code=500, detail="Pipeline run failed")


@router.get("/pipeline/presets")
@router.get("/pipeline-presets")
@router.get("/presets")
async def pipeline_presets() -> Dict[str, Any]:
    return {"items": get_presets(), "count": len(get_presets())}
