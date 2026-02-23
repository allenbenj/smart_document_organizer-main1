from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from services.contracts.aedis_models import JudgeRun, PlannerRun


class PlannerJudgeService:
    """Deterministic planner/judge core with versioned rulesets."""

    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self._planner_runs: dict[str, PlannerRun] = {}
        self._judge_runs: dict[str, JudgeRun] = {}
        self._rulesets: dict[int, dict[str, Any]] = {
            1: {
                "version": 1,
                "name": "baseline",
                "required_keys": ["goal", "steps"],
                "created_at": now.isoformat(),
            }
        }
        self._active_ruleset_version = 1

    @property
    def active_ruleset_version(self) -> int:
        return self._active_ruleset_version

    def create_ruleset(self, *, name: str, required_keys: list[str]) -> dict[str, Any]:
        version = max(self._rulesets) + 1
        ruleset = {
            "version": version,
            "name": name,
            "required_keys": list(required_keys),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._rulesets[version] = ruleset
        return ruleset

    def activate_ruleset(self, version: int) -> dict[str, Any]:
        if version not in self._rulesets:
            raise KeyError(f"ruleset version not found: {version}")
        self._active_ruleset_version = int(version)
        return self._rulesets[version]

    def get_ruleset(self, version: int | None = None) -> dict[str, Any]:
        v = self._active_ruleset_version if version is None else int(version)
        if v not in self._rulesets:
            raise KeyError(f"ruleset version not found: {v}")
        return self._rulesets[v]

    def create_plan(
        self,
        *,
        run_id: str,
        objective_id: str,
        artifact_row_id: int,
        heuristic_ids: list[str],
        strategy: dict[str, Any],
    ) -> PlannerRun:
        run = PlannerRun(
            run_id=run_id,
            objective_id=objective_id,
            artifact_row_id=artifact_row_id,
            heuristic_ids=list(heuristic_ids),
            strategy=dict(strategy),
            created_at=datetime.now(timezone.utc),
        )
        self._planner_runs[run_id] = run
        return run

    def judge_plan(self, planner_run_id: str) -> JudgeRun:
        if planner_run_id not in self._planner_runs:
            raise KeyError(f"planner run not found: {planner_run_id}")

        run = self._planner_runs[planner_run_id]
        ruleset = self.get_ruleset()
        strategy = run.strategy or {}
        missing = [k for k in ruleset["required_keys"] if k not in strategy]
        deterministic_blob = json.dumps(strategy, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(deterministic_blob.encode("utf-8")).hexdigest()
        # Deterministic score based on strategy hash + ruleset outcome.
        base_score = int(digest[:8], 16) / 0xFFFFFFFF
        score = round(base_score if not missing else min(base_score, 0.49), 6)

        verdict = "PASS" if not missing else "FAIL"
        reasons = [] if not missing else [f"missing required key: {key}" for key in missing]
        remediation = [] if not missing else [f"add strategy.{key}" for key in missing]

        judge_id = f"judge::{planner_run_id}::v{ruleset['version']}"
        judge = JudgeRun(
            run_id=judge_id,
            planner_run_id=planner_run_id,
            artifact_row_id=run.artifact_row_id,
            verdict=verdict,
            score=score,
            reasons=reasons,
            remediation=remediation,
            created_at=datetime.now(timezone.utc),
        )
        self._judge_runs[judge_id] = judge
        return judge

    def get_planner_run(self, run_id: str) -> PlannerRun:
        if run_id not in self._planner_runs:
            raise KeyError(f"planner run not found: {run_id}")
        return self._planner_runs[run_id]

    def get_judge_run(self, run_id: str) -> JudgeRun:
        if run_id not in self._judge_runs:
            raise KeyError(f"judge run not found: {run_id}")
        return self._judge_runs[run_id]

    def get_latest_judge_for_planner(self, planner_run_id: str) -> JudgeRun:
        candidates = [
            run
            for run in self._judge_runs.values()
            if run.planner_run_id == planner_run_id
        ]
        if not candidates:
            raise KeyError(f"judge run not found for planner run: {planner_run_id}")
        candidates.sort(key=lambda item: item.created_at)
        return candidates[-1]
