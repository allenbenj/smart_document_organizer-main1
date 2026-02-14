from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

WorkflowStatus = Literal["queued", "running", "waiting_input", "completed", "failed", "cancelled"]
StepName = Literal["sources", "index_extract", "summarize", "proposals", "review", "apply", "analytics"]
StepStatus = Literal["not_started", "in_progress", "blocked", "complete", "failed"]
DraftState = Literal["clean", "dirty", "saving", "failed"]


class PaginationMeta(BaseModel):
    count: int = 0
    has_more: bool = False
    next_cursor: Optional[str] = None


class StepStatusItem(BaseModel):
    name: StepName
    status: StepStatus = "not_started"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WebhookStatus(BaseModel):
    enabled: bool = False
    url: Optional[str] = None
    last_delivery_status: Optional[str] = None
    last_delivery_at: Optional[datetime] = None


class UndoMeta(BaseModel):
    depth: int = 0
    last_undo_token: Optional[str] = None


class JobStatus(BaseModel):
    job_id: str
    workflow: str = "memory_first_v2"
    status: WorkflowStatus = "queued"
    current_step: StepName = "sources"
    progress: float = 0.0
    draft_state: DraftState = "clean"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    webhook: WebhookStatus = Field(default_factory=WebhookStatus)
    stepper: List[StepStatusItem] = Field(default_factory=list)
    pagination: Dict[str, PaginationMeta] = Field(default_factory=dict)
    undo: UndoMeta = Field(default_factory=UndoMeta)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResultItem(BaseModel):
    id: str
    type: str = "proposal"
    status: str = "proposed"
    payload: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    undo_token: Optional[str] = None


class ResultSchema(BaseModel):
    summary: Optional[str] = None
    items: List[ResultItem] = Field(default_factory=list)
    bulk: Dict[str, Any] = Field(default_factory=dict)
    ontology_edits: Dict[str, Any] = Field(default_factory=dict)
    pagination: PaginationMeta = Field(default_factory=PaginationMeta)


class JobStatusResponse(BaseModel):
    success: bool = True
    job: JobStatus


class ResultResponse(BaseModel):
    success: bool = True
    job_id: str
    step: StepName
    result: ResultSchema
    errors: List[str] = Field(default_factory=list)


class ExecuteStepRequest(BaseModel):
    idempotency_key: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class CreateJobRequest(BaseModel):
    workflow: str = "memory_first_v2"
    idempotency_key: Optional[str] = None
    webhook_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowBulkActionRequest(BaseModel):
    proposal_ids: List[int] = Field(default_factory=list)
    action: Literal["approve", "reject"]
    note: Optional[str] = None


class WorkflowOntologyEditRequest(BaseModel):
    proposed_folder: Optional[str] = None
    proposed_filename: Optional[str] = None
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    note: Optional[str] = None


class WorkflowMutationResponse(BaseModel):
    success: bool = True
    job_id: str
    step: StepName = "proposals"
    applied: int = 0
    failed: int = 0
    items: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
