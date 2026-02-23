from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


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
    transition_log: list[dict[str, Any]] = field(default_factory=list)


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
        rec.transition_log.append(
            {
                "from_stage": None,
                "to_stage": HeuristicStage.CANDIDATE.value,
                "reason": "registration",
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._records[heuristic_id] = rec
        logger.info("heuristic registered: heuristic_id=%s stage=%s", heuristic_id, rec.stage.value)
        return rec

    def update_evidence(self, *, heuristic_id: str, evidence_count: int, success_rate: float) -> HeuristicRecord:
        rec = self._require(heuristic_id)
        rec.evidence_count = int(evidence_count)
        rec.success_rate = float(success_rate)
        evaluated = self._evaluate_stage(rec)
        self._transition(
            rec,
            evaluated,
            reason=f"evidence_update:{rec.evidence_count}:{rec.success_rate:.3f}",
        )
        return rec

    def activate_heuristic(self, heuristic_id: str) -> HeuristicRecord:
        rec = self._require(heuristic_id)
        if rec.stage not in {HeuristicStage.PROMOTED, HeuristicStage.ACTIVE}:
            raise ValueError("heuristic must be promoted before activation")
        self._transition(rec, HeuristicStage.ACTIVE, reason="manual_activate")
        self._active_ids.add(heuristic_id)
        return rec

    def promote_heuristic(self, heuristic_id: str) -> HeuristicRecord:
        rec = self._require(heuristic_id)
        if rec.stage == HeuristicStage.DEPRECATED:
            raise ValueError("deprecated heuristic cannot be promoted")
        if rec.stage == HeuristicStage.CANDIDATE:
            raise ValueError("heuristic does not meet promotion threshold")
        if rec.stage in {HeuristicStage.QUALIFIED, HeuristicStage.PROMOTED}:
            self._transition(rec, HeuristicStage.PROMOTED, reason="promotion")
        if rec.stage == HeuristicStage.ACTIVE:
            return rec
        return self.activate_heuristic(heuristic_id)

    def deprecate_heuristic(self, heuristic_id: str) -> HeuristicRecord:
        rec = self._require(heuristic_id)
        self._transition(rec, HeuristicStage.DEPRECATED, reason="deprecation")
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

    def list_candidates(self) -> list[dict[str, Any]]:
        candidate_stages = {
            HeuristicStage.CANDIDATE,
            HeuristicStage.QUALIFIED,
            HeuristicStage.PROMOTED,
        }
        return [
            {
                "candidate_id": r.heuristic_id,
                "heuristic_id": r.heuristic_id,
                "stage": r.stage.value,
                "evidence_count": r.evidence_count,
                "success_rate": r.success_rate,
                "rule_text": r.rule_text,
                "owner": r.owner,
            }
            for r in self._records.values()
            if r.stage in candidate_stages
        ]

    def get_record(self, heuristic_id: str) -> dict[str, Any]:
        rec = self._require(heuristic_id)
        return {
            "heuristic_id": rec.heuristic_id,
            "rule_text": rec.rule_text,
            "owner": rec.owner,
            "created_at": rec.created_at,
            "stage": rec.stage.value,
            "evidence_count": rec.evidence_count,
            "success_rate": rec.success_rate,
            "dissent_from": list(rec.dissent_from),
            "transition_log": list(rec.transition_log),
        }

    def governance_snapshot(self) -> dict[str, Any]:
        return {
            "items": [
                {
                    "heuristic_id": r.heuristic_id,
                    "rule_text": r.rule_text,
                    "owner": r.owner,
                    "stage": r.stage.value,
                    "evidence_count": r.evidence_count,
                    "success_rate": r.success_rate,
                    "dissent_from": list(r.dissent_from),
                    "transition_log": list(r.transition_log),
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

    def _transition(
        self,
        rec: HeuristicRecord,
        to_stage: HeuristicStage,
        *,
        reason: str,
    ) -> None:
        from_stage = rec.stage
        if from_stage == to_stage:
            return
        rec.stage = to_stage
        event = {
            "from_stage": from_stage.value if from_stage else None,
            "to_stage": to_stage.value,
            "reason": reason,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        rec.transition_log.append(event)
        logger.info(
            "heuristic stage transition: heuristic_id=%s from=%s to=%s reason=%s",
            rec.heuristic_id,
            event["from_stage"],
            event["to_stage"],
            reason,
        )
