from __future__ import annotations

from services.heuristic_governance_service import HeuristicGovernanceService


def test_heuristic_collision_detection_tracks_dissent() -> None:
    svc = HeuristicGovernanceService()
    svc.register_heuristic(
        heuristic_id="h-a",
        rule_text="organize legal filings by year and case number",
        owner="expert-1",
    )
    svc.register_heuristic(
        heuristic_id="h-b",
        rule_text="organize legal filings by year and party name",
        owner="expert-2",
    )

    collisions = svc.detect_collisions("h-a")
    assert collisions
    assert collisions[0]["conflicts_with"] == "h-b"

    snapshot = svc.governance_snapshot()
    item = next(x for x in snapshot["items"] if x["heuristic_id"] == "h-a")
    assert "h-b" in item["dissent_from"]
