"""
Organization Orchestration Service

This service manages the organization proposal lifecycle, including folder
scoping, indexing stabilization, proposal generation, and bulk approval/rejection.
It abstracts the complex workflow from the GUI and provides a stable API.
"""

import os
import uuid
import asyncio
import logging
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from . import api_client

logger = logging.getLogger(__name__)

class OrgJobType(Enum):
    LOAD = "load"
    GENERATE = "generate"
    INDEX = "index"
    CLEAR = "clear"
    APPLY = "apply"
    BULK_APPROVE = "bulk_approve"
    BULK_REJECT = "bulk_reject"

class OrgJobStatus(Enum):
    IDLE = "idle"
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class OrganizationJob:
    """Represents a single organization workflow job with transaction tracking."""
    id: str
    type: OrgJobType
    status: OrgJobStatus = OrgJobStatus.IDLE
    progress: int = 0
    message: str = ""
    results: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)
    # Transaction tracking for bulk operations
    completed_ids: List[int] = field(default_factory=list)
    failed_ids: Dict[int, str] = field(default_factory=dict)

class OrganizationService:
    """
    Orchestration service for document organization.
    Owned by the application lifecycle, surviving UI tab destructions.
    """
    
    def __init__(self):
        self._active_jobs: Dict[str, OrganizationJob] = {}
        self._active_workers: Dict[str, Any] = {} # Job ID -> QThread
        self._observers: List[Callable[[OrganizationJob], None]] = []
        self._proposals_cache: List[Dict[str, Any]] = []

    def subscribe(self, callback: Callable[[OrganizationJob], None]):
        """Subscribe to job status updates."""
        self._observers.append(callback)

    def _notify(self, job: OrganizationJob):
        """Notify all observers of a job update."""
        for callback in self._observers:
            try:
                callback(job)
            except Exception as e:
                logger.error(f"[OrgService] Observer error: {e}")

    def register_worker(self, job_id: str, worker: Any):
        """Register a worker thread to be managed by the service."""
        self._active_workers[job_id] = worker
        worker.finished.connect(lambda: self._cleanup_worker(job_id))

    def _cleanup_worker(self, job_id: str):
        """Remove worker from tracking once finished."""
        if job_id in self._active_workers:
            del self._active_workers[job_id]

    def cancel_job(self, job_id: str):
        """Safely request cancellation of an active job."""
        if job_id in self._active_workers:
            worker = self._active_workers[job_id]
            if hasattr(worker, "requestInterruption"):
                worker.requestInterruption()
            self.update_job(job_id, status=OrgJobStatus.CANCELLED, message="Cancellation requested")

    def shutdown(self):
        """Shut down all active jobs and workers."""
        for job_id in list(self._active_workers.keys()):
            self.cancel_job(job_id)

    def create_job(self, job_type: OrgJobType, context: Optional[Dict] = None) -> str:
        """Create and track a new job."""
        job_id = str(uuid.uuid4())
        job = OrganizationJob(
            id=job_id,
            type=job_type,
            status=OrgJobStatus.PENDING,
            started_at=datetime.now(),
            context=context or {}
        )
        self._active_jobs[job_id] = job
        self._notify(job)
        return job_id

    def record_item_success(self, job_id: str, item_id: int):
        """Record a single successful item in a bulk job."""
        if job_id in self._active_jobs:
            self._active_jobs[job_id].completed_ids.append(item_id)

    def record_item_failure(self, job_id: str, item_id: int, error: str):
        """Record a single failed item in a bulk job."""
        if job_id in self._active_jobs:
            self._active_jobs[job_id].failed_ids[item_id] = error

    def update_job(self, job_id: str, status: Optional[OrgJobStatus] = None, 
                   progress: Optional[int] = None, message: Optional[str] = None,
                   results: Any = None, error: Optional[str] = None):
        """Update job state and notify observers."""
        if job_id in self._active_jobs:
            job = self._active_jobs[job_id]
            if status: job.status = status
            if progress is not None: job.progress = progress
            if message: job.message = message
            if results is not None: job.results = results
            if error: job.error = error
            
            if status in [OrgJobStatus.SUCCESS, OrgJobStatus.FAILED, OrgJobStatus.CANCELLED]:
                job.ended_at = datetime.now()
            
            self._notify(job)

    def get_job(self, job_id: str) -> Optional[OrganizationJob]:
        return self._active_jobs.get(job_id)

# Global service instance
organization_service = OrganizationService()
