"""
Document Processing Orchestration Service

This service owns the document processing lifecycle, including initialization,
batch management, retry logic, and state tracking. It provides a clean API
for GUI components to observe and control processing jobs.
"""

import os
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from . import api_client

class JobStatus(Enum):
    """Explicit runtime state machine for processing jobs."""
    IDLE = "idle"
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DEGRADED = "degraded"
    CANCELLED = "cancelled"

@dataclass
class ProcessingJob:
    """Represents a single document processing job."""
    id: str
    files: List[str]
    options: Dict[str, Any]
    status: JobStatus = JobStatus.IDLE
    progress: int = 0
    total_files: int = 0
    results: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

class DocumentProcessingService:
    """
    Orchestration service that owns document processing policy.
    
    Responsibilities:
    - Manage active processing jobs
    - Implement retry/fallback logic
    - Provide state updates to observers
    - Abstract API communication
    """
    
    def __init__(self):
        self._active_jobs: Dict[str, ProcessingJob] = {}
        self._observers: List[Callable[[ProcessingJob], None]] = []

    def subscribe(self, callback: Callable[[ProcessingJob], None]):
        """Subscribe to job status updates."""
        self._observers.append(callback)

    def _notify(self, job: ProcessingJob):
        """Notify all observers of a job update."""
        for callback in self._observers:
            try:
                callback(job)
            except Exception as e:
                print(f"[ProcessingService] Observer error: {e}")

    async def run_batch(self, files: List[str], options: Optional[Dict] = None) -> str:
        """
        Start a new document processing batch.
        
        This is a non-blocking call that returns a job ID.
        """
        import uuid
        job_id = str(uuid.uuid4())
        
        # Filter and validate files
        valid_files = [f for f in files if os.path.exists(f)]
        if not valid_files:
            raise ValueError("No valid files provided for processing")
            
        job = ProcessingJob(
            id=job_id,
            files=valid_files,
            options=options or {},
            status=JobStatus.PENDING,
            total_files=len(valid_files),
            started_at=datetime.now()
        )
        
        self._active_jobs[job_id] = job
        self._notify(job)
        
        # In a real implementation, this would trigger a background task
        # For now, it returns the ID so the GUI can track it via the worker
        return job_id

    def update_job_progress(self, job_id: str, progress: int, status: Optional[JobStatus] = None):
        """Update the status of an active job."""
        if job_id in self._active_jobs:
            job = self._active_jobs[job_id]
            job.progress = progress
            if status:
                job.status = status
            if status in [JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED]:
                job.ended_at = datetime.now()
            self._notify(job)

    def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        """Retrieve a job by ID."""
        return self._active_jobs.get(job_id)

# Global service instance
processing_service = DocumentProcessingService()
