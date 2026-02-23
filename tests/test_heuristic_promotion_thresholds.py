from __future__ import annotations

from services.heuristic_governance_service import HeuristicGovernanceService, HeuristicStage


def test_heuristic_promotion_thresholds() -> None:
    svc = HeuristicGovernanceService()
    svc.register_heuristic(
        heuristic_id="h-1",
        rule_text="prefer specific folder path for filings",
        owner="expert-a",
    )

    rec = svc.update_evidence(heuristic_id="h-1", evidence_count=12, success_rate=0.82)
    assert rec.stage == HeuristicStage.QUALIFIED

    rec = svc.update_evidence(heuristic_id="h-1", evidence_count=21, success_rate=0.91)
    assert rec.stage == HeuristicStage.PROMOTED

    active = svc.activate_heuristic("h-1")
    assert active.stage == HeuristicStage.ACTIVE
