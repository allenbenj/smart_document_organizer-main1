from __future__ import annotations

import pytest

from services.heuristic_governance_service import HeuristicGovernanceService, HeuristicStage


def test_candidate_id_maps_to_heuristic_id_in_candidates() -> None:
    svc = HeuristicGovernanceService()
    svc.register_heuristic(
        heuristic_id="h-map-1",
        rule_text="prefer corroborated factual assertions with source spans",
        owner="expert-a",
    )

    candidates = svc.list_candidates()
    item = next(x for x in candidates if x["heuristic_id"] == "h-map-1")
    assert item["candidate_id"] == item["heuristic_id"]


def test_lifecycle_transitions_and_transition_log_are_explicit() -> None:
    svc = HeuristicGovernanceService()
    svc.register_heuristic(
        heuristic_id="h-life-1",
        rule_text="prefer corroborated factual assertions with source spans",
        owner="expert-a",
    )

    rec = svc.update_evidence(heuristic_id="h-life-1", evidence_count=12, success_rate=0.84)
    assert rec.stage == HeuristicStage.QUALIFIED

    rec = svc.promote_heuristic("h-life-1")
    assert rec.stage == HeuristicStage.ACTIVE

    rec = svc.deprecate_heuristic("h-life-1")
    assert rec.stage == HeuristicStage.DEPRECATED

    record = svc.get_record("h-life-1")
    transitions = record["transition_log"]
    assert len(transitions) >= 4
    assert any(t["to_stage"] == "qualified" for t in transitions)
    assert any(t["to_stage"] == "promoted" for t in transitions)
    assert any(t["to_stage"] == "active" for t in transitions)
    assert any(t["to_stage"] == "deprecated" for t in transitions)


def test_promotion_rejects_invalid_states() -> None:
    svc = HeuristicGovernanceService()
    svc.register_heuristic(
        heuristic_id="h-invalid-1",
        rule_text="prefer concise evidentiary summaries",
        owner="expert-b",
    )

    with pytest.raises(ValueError, match="does not meet promotion threshold"):
        svc.promote_heuristic("h-invalid-1")

    svc.update_evidence(heuristic_id="h-invalid-1", evidence_count=12, success_rate=0.9)
    svc.promote_heuristic("h-invalid-1")
    svc.deprecate_heuristic("h-invalid-1")

    with pytest.raises(ValueError, match="deprecated heuristic cannot be promoted"):
        svc.promote_heuristic("h-invalid-1")


def test_collision_schema_includes_overlap_terms() -> None:
    svc = HeuristicGovernanceService()
    svc.register_heuristic(
        heuristic_id="h-col-a",
        rule_text="organize legal filings by year and case number with source evidence",
        owner="expert-1",
    )
    svc.register_heuristic(
        heuristic_id="h-col-b",
        rule_text="organize legal filings by year and party number with source evidence",
        owner="expert-2",
    )

    collisions = svc.detect_collisions("h-col-a")
    assert collisions
    row = collisions[0]
    assert row["heuristic_id"] == "h-col-a"
    assert row["conflicts_with"] == "h-col-b"
    assert isinstance(row["overlap_terms"], list)
    assert "organize" in row["overlap_terms"]
