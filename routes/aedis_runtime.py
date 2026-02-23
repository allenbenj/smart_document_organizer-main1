from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from services.contracts.aedis_models import ProvenanceRecord
from services.heuristic_governance_service import HeuristicGovernanceService
from services.learning_path_service import LearningPathService
from services.planner_persistence_gate_service import PlannerPersistenceGateService
from services.planner_judge_service import PlannerJudgeService
from services.provenance_service import get_provenance_service

router = APIRouter()

planner_judge_service = PlannerJudgeService()
heuristic_governance_service = HeuristicGovernanceService()
planner_persistence_gate_service = PlannerPersistenceGateService()
learning_path_service = LearningPathService()


class PlannerJudgeRunPayload(BaseModel):
    objective_id: str = Field(..., min_length=1, max_length=200)
    artifact_row_id: int = Field(..., gt=0)
    strategy: dict[str, Any] = Field(default_factory=dict)
    heuristic_ids: list[str] = Field(default_factory=list)
    run_id: str | None = Field(default=None, max_length=200)


class HeuristicRegisterPayload(BaseModel):
    heuristic_id: str = Field(..., min_length=1, max_length=200)
    rule_text: str = Field(..., min_length=1, max_length=8000)
    owner: str = Field(..., min_length=1, max_length=200)


class HeuristicEvidencePayload(BaseModel):
    evidence_count: int = Field(..., ge=0)
    success_rate: float = Field(..., ge=0.0, le=1.0)


class HeuristicPromotePayload(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


class LearningPathGeneratePayload(BaseModel):
    path_id: str = Field(..., min_length=1, max_length=200)
    user_id: str = Field(..., min_length=1, max_length=200)
    objective_id: str = Field(..., min_length=1, max_length=200)
    heuristic_ids: list[str] = Field(default_factory=list)
    evidence_spans: list[dict[str, Any]] = Field(default_factory=list)


class LearningPathStepUpdatePayload(BaseModel):
    completed: bool


class PlannerPersistPayload(BaseModel):
    planner_run_id: str = Field(..., min_length=1, max_length=200)
    output: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


def _new_run_id(payload: PlannerJudgeRunPayload) -> str:
    raw = json.dumps(
        {
            "objective_id": payload.objective_id,
            "artifact_row_id": payload.artifact_row_id,
            "strategy": payload.strategy,
            "heuristic_ids": payload.heuristic_ids,
            "ts": datetime.now(timezone.utc).isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    suffix = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"planner::{payload.objective_id}::{suffix}"


@router.post("/planner-judge/run")
async def run_planner_judge(payload: PlannerJudgeRunPayload) -> dict[str, Any]:
    started = time.perf_counter()
    run_id = payload.run_id or _new_run_id(payload)

    try:
        planner_run = planner_judge_service.create_plan(
            run_id=run_id,
            objective_id=payload.objective_id,
            artifact_row_id=payload.artifact_row_id,
            heuristic_ids=list(payload.heuristic_ids),
            strategy=dict(payload.strategy),
        )
        judge_run = planner_judge_service.judge_plan(run_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    elapsed = round(time.perf_counter() - started, 6)
    return {
        "success": True,
        "planner_run": planner_run.model_dump(mode="json"),
        "judge_run": judge_run.model_dump(mode="json"),
        "processing_time": elapsed,
        "error": None,
    }


@router.get("/planner/run/{run_id}")
async def get_planner_run(
    run_id: str = Path(..., min_length=1, max_length=200),
) -> dict[str, Any]:
    try:
        item = planner_judge_service.get_planner_run(run_id)
        return {"success": True, "item": item.model_dump(mode="json")}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/judge/failures/{run_id}")
async def get_judge_failures(
    run_id: str = Path(..., min_length=1, max_length=200),
) -> dict[str, Any]:
    try:
        try:
            judge = planner_judge_service.get_judge_run(run_id)
        except KeyError:
            judge = planner_judge_service.get_latest_judge_for_planner(run_id)

        return {
            "success": True,
            "run_id": judge.run_id,
            "planner_run_id": judge.planner_run_id,
            "verdict": judge.verdict,
            "score": judge.score,
            "reasons": list(judge.reasons),
            "remediation": list(judge.remediation),
            "failed": judge.verdict == "FAIL",
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/planner-judge/persist")
async def persist_planner_output(payload: PlannerPersistPayload) -> dict[str, Any]:
    try:
        planner_run = planner_judge_service.get_planner_run(payload.planner_run_id)
        judge_run = planner_judge_service.get_latest_judge_for_planner(payload.planner_run_id)
        provenance_record = ProvenanceRecord.model_validate(payload.provenance)
        provenance_service = get_provenance_service()
        provenance_id: int | None
        provenance_status = "persisted"
        try:
            provenance_id = provenance_service.record_provenance(
                provenance_record,
                target_type="planner_persisted_output",
                target_id=payload.planner_run_id,
            )
        except RuntimeError:
            # Fail closed on invalid provenance, but tolerate unavailable backing tables.
            provenance_id = None
            provenance_status = "validated_only"
        record = planner_persistence_gate_service.persist_planner_output(
            planner_run=planner_run,
            judge_run=judge_run,
            output_payload=payload.output,
        )
        record["provenance_id"] = provenance_id
        record["provenance_status"] = provenance_status
        return {"success": True, "item": record}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        blocked = planner_persistence_gate_service.get_blocked(payload.planner_run_id) or {}
        return {
            "success": False,
            "error": str(exc),
            "blocked": True,
            "failure_artifact": blocked,
        }


@router.get("/planner-judge/persisted/{planner_run_id}")
async def get_persisted_planner_output(
    planner_run_id: str = Path(..., min_length=1, max_length=200),
) -> dict[str, Any]:
    try:
        item = planner_persistence_gate_service.get_persisted(planner_run_id)
        return {"success": True, "item": item}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/learning-paths/generate")
async def generate_learning_path(payload: LearningPathGeneratePayload) -> dict[str, Any]:
    try:
        item = learning_path_service.generate_path(
            path_id=payload.path_id,
            user_id=payload.user_id,
            objective_id=payload.objective_id,
            heuristic_ids=payload.heuristic_ids,
            evidence_spans=payload.evidence_spans,
        )
        return {"success": True, "item": item.model_dump(mode="json")}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/learning-paths/{path_id}")
async def get_learning_path(path_id: str = Path(..., min_length=1, max_length=200)) -> dict[str, Any]:
    try:
        item = learning_path_service.get_path(path_id)
        return {"success": True, "item": item.model_dump(mode="json")}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/learning-paths/{path_id}/steps/{step_id}")
async def update_learning_step(
    path_id: str,
    step_id: str,
    payload: LearningPathStepUpdatePayload,
) -> dict[str, Any]:
    try:
        item = learning_path_service.update_step_completion(
            path_id=path_id,
            step_id=step_id,
            completed=payload.completed,
        )
        return {"success": True, "item": item.model_dump(mode="json")}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/learning-paths/{path_id}/recommendations")
async def get_learning_recommendations(path_id: str) -> dict[str, Any]:
    try:
        items = learning_path_service.list_recommended_steps(path_id)
        return {"success": True, "items": items, "count": len(items)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/provenance/{target_type}/{target_id}")
async def get_provenance_for_target(
    target_type: str = Path(..., min_length=1, max_length=120),
    target_id: str = Path(..., min_length=1, max_length=300),
) -> dict[str, Any]:
    service = get_provenance_service()
    record = service.get_provenance_for_artifact(target_type=target_type, target_id=target_id)
    if record is None:
        raise HTTPException(status_code=404, detail="provenance not found")
    return {"success": True, "item": record.model_dump(mode="json")}


@router.get("/heuristics/candidates")
async def list_heuristic_candidates() -> dict[str, Any]:
    items = heuristic_governance_service.list_candidates()
    return {"success": True, "items": items, "count": len(items)}


@router.get("/heuristics/governance")
async def get_heuristic_governance_snapshot() -> dict[str, Any]:
    snapshot = heuristic_governance_service.governance_snapshot()
    return {"success": True, **snapshot}


@router.get("/heuristics/{heuristic_id}/collisions")
async def detect_heuristic_collisions(
    heuristic_id: str = Path(..., min_length=1, max_length=200),
) -> dict[str, Any]:
    try:
        collisions = heuristic_governance_service.detect_collisions(heuristic_id)
        return {
            "success": True,
            "heuristic_id": heuristic_id,
            "collisions": collisions,
            "count": len(collisions),
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/heuristics/candidates/{candidate_id}/promote")
async def promote_heuristic_candidate(
    candidate_id: str,
    payload: HeuristicPromotePayload,
) -> dict[str, Any]:
    try:
        provenance_record = ProvenanceRecord.model_validate(payload.provenance)
        provenance_service = get_provenance_service()
        provenance_id: int | None
        provenance_status = "persisted"
        try:
            provenance_id = provenance_service.record_provenance(
                provenance_record,
                target_type="heuristic_promotion",
                target_id=candidate_id,
            )
        except RuntimeError:
            provenance_id = None
            provenance_status = "validated_only"

        item = heuristic_governance_service.promote_heuristic(candidate_id)
        return {
            "success": True,
            "item": heuristic_governance_service.get_record(item.heuristic_id),
            "metadata": payload.metadata,
            "provenance_id": provenance_id,
            "provenance_status": provenance_status,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/heuristics/{heuristic_id}/deprecate")
async def deprecate_heuristic(
    heuristic_id: str,
) -> dict[str, Any]:
    try:
        item = heuristic_governance_service.deprecate_heuristic(heuristic_id)
        return {
            "success": True,
            "item": heuristic_governance_service.get_record(item.heuristic_id),
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/heuristics/register")
async def register_heuristic(payload: HeuristicRegisterPayload) -> dict[str, Any]:
    rec = heuristic_governance_service.register_heuristic(
        heuristic_id=payload.heuristic_id,
        rule_text=payload.rule_text,
        owner=payload.owner,
    )
    return {
        "success": True,
        "item": heuristic_governance_service.get_record(rec.heuristic_id),
    }


@router.post("/heuristics/{heuristic_id}/evidence")
async def update_heuristic_evidence(
    heuristic_id: str,
    payload: HeuristicEvidencePayload,
) -> dict[str, Any]:
    try:
        rec = heuristic_governance_service.update_evidence(
            heuristic_id=heuristic_id,
            evidence_count=payload.evidence_count,
            success_rate=payload.success_rate,
        )
        return {
            "success": True,
            "item": heuristic_governance_service.get_record(rec.heuristic_id),
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
