from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceSpan(BaseModel):
    """Character-level evidence location inside a source artifact."""

    model_config = ConfigDict(extra="forbid")

    artifact_row_id: int = Field(..., gt=0)
    start_char: int = Field(..., ge=0)
    end_char: int = Field(..., gt=0)
    quote: str | None = Field(default=None, max_length=2000)

    @field_validator("end_char")
    @classmethod
    def _validate_offsets(cls, value: int, info: Any) -> int:
        start = info.data.get("start_char")
        if isinstance(start, int) and value <= start:
            raise ValueError("end_char must be greater than start_char")
        return value


class AuditDelta(BaseModel):
    """Expert-reviewed change trace between prior and current analysis versions."""

    model_config = ConfigDict(extra="forbid")

    field_name: str = Field(..., min_length=1, max_length=200)
    old_value: str | None = Field(default=None, max_length=4000)
    new_value: str | None = Field(default=None, max_length=4000)
    rationale: str | None = Field(default=None, max_length=2000)


class ProvenanceRecord(BaseModel):
    """Mandatory provenance envelope for generated outputs."""

    model_config = ConfigDict(extra="forbid")

    source_artifact_row_id: int = Field(..., gt=0)
    source_sha256: str = Field(..., min_length=64, max_length=64)
    captured_at: datetime
    extractor: str = Field(..., min_length=1, max_length=100)
    spans: list[EvidenceSpan] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)


class CanonicalArtifact(BaseModel):
    """Immutable canonical artifact anchored by content hash."""

    model_config = ConfigDict(extra="forbid")

    row_id: int | None = Field(default=None, gt=0)
    artifact_id: str = Field(..., min_length=1, max_length=200)
    sha256: str = Field(..., min_length=64, max_length=64)
    content_type: str = Field(..., min_length=1, max_length=120)
    byte_size: int = Field(..., ge=0)
    created_at: datetime


class AnalysisVersion(BaseModel):
    """Mutable analysis layer snapshot linked to canonical truth."""

    model_config = ConfigDict(extra="forbid")

    analysis_id: str = Field(..., min_length=1, max_length=200)
    artifact_row_id: int = Field(..., gt=0)
    version: int = Field(..., ge=1)
    parent_version: int | None = Field(default=None, ge=1)
    status: str = Field(default="draft", min_length=1, max_length=40)
    payload: dict[str, Any] = Field(default_factory=dict)
    provenance: ProvenanceRecord
    audit_deltas: list[AuditDelta] = Field(default_factory=list)
    created_at: datetime


class HeuristicEntry(BaseModel):
    """Tacit knowledge heuristic with lifecycle metadata and dissent support."""

    model_config = ConfigDict(extra="forbid")

    heuristic_id: str = Field(..., min_length=1, max_length=200)
    version: int = Field(..., ge=1)
    status: str = Field(..., min_length=1, max_length=40)
    owner: str = Field(..., min_length=1, max_length=200)
    rule_text: str = Field(..., min_length=1, max_length=8000)
    conflicts_with: list[str] = Field(default_factory=list)
    created_at: datetime


class PlannerRun(BaseModel):
    """Planner strategy composition run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., min_length=1, max_length=200)
    objective_id: str = Field(..., min_length=1, max_length=200)
    artifact_row_id: int = Field(..., gt=0)
    heuristic_ids: list[str] = Field(default_factory=list)
    strategy: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class JudgeRun(BaseModel):
    """Deterministic judgment outcome for planner outputs."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., min_length=1, max_length=200)
    planner_run_id: str = Field(..., min_length=1, max_length=200)
    artifact_row_id: int = Field(..., gt=0)
    verdict: str = Field(..., pattern="^(PASS|FAIL)$")
    score: float = Field(..., ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    remediation: list[str] = Field(default_factory=list)
    created_at: datetime


class OntologyRecord(BaseModel):
    """Versioned ontology registry record for a single ontology type/version."""

    model_config = ConfigDict(extra="forbid")

    ontology_type: str = Field(..., min_length=1, max_length=40)
    version: int = Field(..., ge=1)
    status: str = Field(..., min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=500)
    created_at: datetime
