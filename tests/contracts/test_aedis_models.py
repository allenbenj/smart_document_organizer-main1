from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from services.contracts.aedis_models import (
    AnalysisVersion,
    AuditDelta,
    CanonicalArtifact,
    EvidenceSpan,
    JudgeRun,
    LearningPath,
    LearningStep,
    ProvenanceRecord,
)


_NOW = datetime(2026, 2, 19, 0, 0, tzinfo=UTC)
_SHA = "a" * 64


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(
        source_artifact_row_id=1,
        source_sha256=_SHA,
        captured_at=_NOW,
        extractor="unit-test",
        spans=[
            EvidenceSpan(
                artifact_row_id=1,
                start_char=5,
                end_char=12,
                quote="sample",
            )
        ],
    )


def test_evidence_span_requires_ordered_offsets() -> None:
    with pytest.raises(ValidationError):
        EvidenceSpan(artifact_row_id=1, start_char=8, end_char=8)


def test_canonical_artifact_and_analysis_version_roundtrip() -> None:
    artifact = CanonicalArtifact(
        row_id=1,
        artifact_id="artifact-001",
        sha256=_SHA,
        content_type="text/plain",
        byte_size=100,
        created_at=_NOW,
    )
    analysis = AnalysisVersion(
        analysis_id="analysis-001",
        artifact_row_id=artifact.row_id or 1,
        version=1,
        payload={"summary": "ok"},
        provenance=_provenance(),
        audit_deltas=[
            AuditDelta(
                field_name="summary",
                old_value="before",
                new_value="after",
                rationale="editorial cleanup",
            )
        ],
        created_at=_NOW,
    )

    encoded = analysis.model_dump(mode="json")
    decoded = AnalysisVersion.model_validate(encoded)

    assert decoded.analysis_id == "analysis-001"
    assert decoded.provenance.spans[0].artifact_row_id == 1
    assert decoded.audit_deltas[0].field_name == "summary"


def test_judge_run_verdict_is_strict() -> None:
    with pytest.raises(ValidationError):
        JudgeRun(
            run_id="judge-1",
            planner_run_id="planner-1",
            artifact_row_id=1,
            verdict="MAYBE",
            score=0.5,
            created_at=_NOW,
        )


def test_learning_step_requires_evidence_spans() -> None:
    with pytest.raises(ValidationError):
        LearningStep(
            step_id="step-1",
            title="Do thing",
            instruction="Explain decision",
            objective_id="OBJECTIVE.TEST",
            heuristic_ids=["h1"],
            evidence_spans=[],
            difficulty=1,
        )


def test_learning_path_roundtrip() -> None:
    step = LearningStep(
        step_id="step-1",
        title="Do thing",
        instruction="Explain decision",
        objective_id="OBJECTIVE.TEST",
        heuristic_ids=["h1"],
        evidence_spans=[
            EvidenceSpan(artifact_row_id=1, start_char=0, end_char=3, quote="abc")
        ],
        difficulty=1,
    )
    path = LearningPath(
        path_id="lp-1",
        user_id="user-1",
        objective_id="OBJECTIVE.TEST",
        steps=[step],
        created_at=_NOW,
        updated_at=_NOW,
    )

    encoded = path.model_dump(mode="json")
    decoded = LearningPath.model_validate(encoded)
    assert decoded.steps[0].heuristic_ids == ["h1"]
