from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class HeuristicStage(str, Enum):
    CANDIDATE = "candidate"
    QUALIFIED = "qualified"
    PROMOTED = "promoted"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


@dataclass
class HeuristicRecord:
    heuristic_id: str
    rule_text: str
    owner: str
    created_at: str
    stage: HeuristicStage = HeuristicStage.CANDIDATE
    evidence_count: int = 0
    success_rate: float = 0.0
    dissent_from: list[str] = field(default_factory=list)


class HeuristicGovernanceService:
    """Lifecycle governance for heuristic promotion and dissent tracking."""

    def __init__(self) -> None:
        self._records: dict[str, HeuristicRecord] = {}
        self._active_ids: set[str] = set()

    def register_heuristic(self, *, heuristic_id: str, rule_text: str, owner: str) -> HeuristicRecord:
        rec = HeuristicRecord(
            heuristic_id=heuristic_id,
            rule_text=rule_text,
            owner=owner,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._records[heuristic_id] = rec
        return rec

    def update_evidence(self, *, heuristic_id: str, evidence_count: int, success_rate: float) -> HeuristicRecord:
        rec = self._require(heuristic_id)
        rec.evidence_count = int(evidence_count)
        rec.success_rate = float(success_rate)
        rec.stage = self._evaluate_stage(rec)
        return rec

    def activate_heuristic(self, heuristic_id: str) -> HeuristicRecord:
        rec = self._require(heuristic_id)
        if rec.stage not in {HeuristicStage.PROMOTED, HeuristicStage.ACTIVE}:
            raise ValueError("heuristic must be promoted before activation")
        rec.stage = HeuristicStage.ACTIVE
        self._active_ids.add(heuristic_id)
        return rec

    def deprecate_heuristic(self, heuristic_id: str) -> HeuristicRecord:
        rec = self._require(heuristic_id)
        rec.stage = HeuristicStage.DEPRECATED
        self._active_ids.discard(heuristic_id)
        return rec

    def detect_collisions(self, heuristic_id: str) -> list[dict[str, Any]]:
        target = self._require(heuristic_id)
        collisions: list[dict[str, Any]] = []
        target_tokens = set(target.rule_text.lower().split())
        for other in self._records.values():
            if other.heuristic_id == heuristic_id:
                continue
            overlap = target_tokens.intersection(set(other.rule_text.lower().split()))
            if len(overlap) >= 4:
                target.dissent_from.append(other.heuristic_id)
                collisions.append(
                    {
                        "heuristic_id": heuristic_id,
                        "conflicts_with": other.heuristic_id,
                        "overlap_terms": sorted(overlap),
                    }
                )
        # de-duplicate dissent IDs while preserving order
        seen = set()
        deduped: list[str] = []
        for hid in target.dissent_from:
            if hid not in seen:
                seen.add(hid)
                deduped.append(hid)
        target.dissent_from = deduped
        return collisions

    def governance_snapshot(self) -> dict[str, Any]:
        return {
            "items": [
                {
                    "heuristic_id": r.heuristic_id,
                    "stage": r.stage.value,
                    "evidence_count": r.evidence_count,
                    "success_rate": r.success_rate,
                    "dissent_from": list(r.dissent_from),
                }
                for r in self._records.values()
            ],
            "active": sorted(self._active_ids),
        }

    def _require(self, heuristic_id: str) -> HeuristicRecord:
        if heuristic_id not in self._records:
            raise KeyError(f"heuristic not found: {heuristic_id}")
        return self._records[heuristic_id]

    @staticmethod
    def _evaluate_stage(rec: HeuristicRecord) -> HeuristicStage:
        # Threshold policy for promotion lifecycle.
        if rec.evidence_count >= 20 and rec.success_rate >= 0.90:
            return HeuristicStage.PROMOTED
        if rec.evidence_count >= 10 and rec.success_rate >= 0.80:
            return HeuristicStage.QUALIFIED
        return HeuristicStage.CANDIDATE
