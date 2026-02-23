from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mem_db.database import DatabaseManager, get_database_manager
from services.contracts.aedis_models import EvidenceSpan, LearningPath, LearningStep


class LearningPathService:
    """Learning path generation and progression service with DB persistence."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or get_database_manager()

    def generate_path(
        self,
        *,
        path_id: str,
        user_id: str,
        objective_id: str,
        heuristic_ids: list[str],
        evidence_spans: list[dict[str, Any]],
    ) -> LearningPath:
        now = datetime.now(timezone.utc)
        spans = [EvidenceSpan.model_validate(s) for s in evidence_spans]

        steps: list[LearningStep] = []
        if heuristic_ids:
            for idx, heuristic_id in enumerate(heuristic_ids, start=1):
                steps.append(
                    LearningStep(
                        step_id=f"{path_id}::step::{idx}",
                        title=f"Apply heuristic {heuristic_id}",
                        instruction=(
                            "Review the evidence spans and practice applying "
                            f"heuristic `{heuristic_id}` to objective `{objective_id}`."
                        ),
                        objective_id=objective_id,
                        heuristic_ids=[heuristic_id],
                        evidence_spans=spans,
                        difficulty=min(5, idx),
                    )
                )
        else:
            steps.append(
                LearningStep(
                    step_id=f"{path_id}::step::1",
                    title="Baseline analysis step",
                    instruction=(
                        "Review evidence spans and draft a justified conclusion "
                        f"for objective `{objective_id}`."
                    ),
                    objective_id=objective_id,
                    heuristic_ids=[],
                    evidence_spans=spans,
                    difficulty=1,
                )
            )

        path = LearningPath(
            path_id=path_id,
            user_id=user_id,
            objective_id=objective_id,
            status="active",
            steps=steps,
            ontology_version=1,
            heuristic_snapshot=list(heuristic_ids),
            created_at=now,
            updated_at=now,
        )
        self.db.learning_path_upsert(path.model_dump(mode="json"))
        return path

    def get_path(self, path_id: str) -> LearningPath:
        rec = self.db.learning_path_get(path_id)
        if not rec:
            raise KeyError(f"learning path not found: {path_id}")
        return LearningPath.model_validate(rec)

    def update_step_completion(
        self,
        *,
        path_id: str,
        step_id: str,
        completed: bool,
    ) -> LearningPath:
        ok = self.db.learning_path_update_step_completion(
            path_id=path_id,
            step_id=step_id,
            completed=bool(completed),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        if not ok:
            raise KeyError(f"learning step not found: {step_id}")
        return self.get_path(path_id)

    def list_recommended_steps(self, path_id: str) -> list[dict[str, Any]]:
        return self.db.learning_path_list_recommended_steps(path_id)
