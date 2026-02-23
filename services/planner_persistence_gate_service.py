from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from services.contracts.aedis_models import JudgeRun, PlannerRun


class PlannerPersistenceGateService:
    """Fail-closed persistence gate for planner-driven outputs."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._persisted: dict[str, dict[str, Any]] = {}
        self._blocked: dict[str, dict[str, Any]] = {}

    def persist_planner_output(
        self,
        *,
        planner_run: PlannerRun,
        judge_run: JudgeRun,
        output_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist planner output only when the judge verdict is PASS."""
        with self._lock:
            if judge_run.verdict != "PASS":
                blocked = {
                    "planner_run_id": planner_run.run_id,
                    "judge_run_id": judge_run.run_id,
                    "blocked_at": datetime.now(timezone.utc).isoformat(),
                    "reason": "Judge verdict FAIL blocks persistence",
                    "reasons": list(judge_run.reasons),
                    "remediation": list(judge_run.remediation),
                    "output_preview": dict(output_payload),
                }
                self._blocked[planner_run.run_id] = blocked
                raise PermissionError("Judge verdict FAIL blocks persistence")

            record = {
                "planner_run_id": planner_run.run_id,
                "judge_run_id": judge_run.run_id,
                "artifact_row_id": planner_run.artifact_row_id,
                "objective_id": planner_run.objective_id,
                "persisted_at": datetime.now(timezone.utc).isoformat(),
                "output": dict(output_payload),
            }
            self._persisted[planner_run.run_id] = record
            return record

    def get_persisted(self, planner_run_id: str) -> dict[str, Any]:
        if planner_run_id not in self._persisted:
            raise KeyError(f"persisted output not found: {planner_run_id}")
        return self._persisted[planner_run_id]

    def get_blocked(self, planner_run_id: str) -> dict[str, Any] | None:
        return self._blocked.get(planner_run_id)
