from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from services.contracts.aedis_models import (
    AnalysisVersion,
    CanonicalArtifact,
    HeuristicEntry,
    JudgeRun,
    PlannerRun,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _normalize_to_model(model_cls: type[ModelT], payload: dict[str, Any] | ModelT) -> ModelT:
    if isinstance(payload, model_cls):
        return payload
    return model_cls.model_validate(payload)


def canonical_artifact_from_api(payload: dict[str, Any] | CanonicalArtifact) -> CanonicalArtifact:
    return _normalize_to_model(CanonicalArtifact, payload)


def analysis_version_from_api(payload: dict[str, Any] | AnalysisVersion) -> AnalysisVersion:
    return _normalize_to_model(AnalysisVersion, payload)


def heuristic_entry_from_api(payload: dict[str, Any] | HeuristicEntry) -> HeuristicEntry:
    return _normalize_to_model(HeuristicEntry, payload)


def planner_run_from_api(payload: dict[str, Any] | PlannerRun) -> PlannerRun:
    return _normalize_to_model(PlannerRun, payload)


def judge_run_from_api(payload: dict[str, Any] | JudgeRun) -> JudgeRun:
    return _normalize_to_model(JudgeRun, payload)


def to_api_payload(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
