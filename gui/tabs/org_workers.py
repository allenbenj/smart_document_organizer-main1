"""
Organization Tab Workers

Background workers for long-running organization tasks.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from urllib.parse import quote_plus

from PySide6.QtCore import QThread, Signal
from ..services import api_client
from ..services.organization_service import organization_service, OrgJobType, OrgJobStatus
from .org_utils import get_existing_runtime_roots, get_scope_prefixes

logger = logging.getLogger(__name__)

class LoadProposalsWorker(QThread):
    finished_ok = Signal(list)
    finished_err = Signal(str)

    def __init__(self, job_id: str, root_prefix: Optional[str] = None, status: Optional[str] = None):
        super().__init__()
        self.job_id = job_id
        self.root_prefix = root_prefix
        self.status = status

    def run(self):
        try:
            organization_service.update_job(self.job_id, status=OrgJobStatus.RUNNING, message="Loading proposals...")
            result = api_client.get_organization_proposals(
                root_prefix=self.root_prefix, 
                status=self.status
            )
            
            # ApiClient already normalized this to include 'items'
            items = result.get("items", [])
            
            # Fallback if no proposed found
            if not items and self.status == "proposed":
                organization_service.update_job(self.job_id, message="No pending found, checking all...")
                result = api_client.get_organization_proposals(root_prefix=self.root_prefix)
                items = result.get("items", [])

            organization_service.update_job(self.job_id, status=OrgJobStatus.SUCCESS, results=items)
            self.finished_ok.emit(items)
        except Exception as e:
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=str(e))
            self.finished_err.emit(str(e))

class GenerateProposalsWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)
    progress_update = Signal(str)

    def __init__(self, job_id: str, root: str):
        super().__init__()
        self.job_id = job_id
        self.root = root

    def run(self):
        try:
            organization_service.update_job(self.job_id, status=OrgJobStatus.RUNNING, message="Starting generation...")
            
            # 1. Indexing stabilization (Blocking loop moved to background)
            if self.root:
                self.progress_update.emit("Stabilizing index...")
                self._index_scope_until_stable(self.root)
            
            if self.isInterruptionRequested():
                organization_service.update_job(self.job_id, status=OrgJobStatus.CANCELLED)
                return
                
            # 2. Generate
            self.progress_update.emit("Generating proposals (1-2 min)...")
            out = api_client.generate_organization_proposals(root_prefix=self.root)
            
            organization_service.update_job(self.job_id, status=OrgJobStatus.SUCCESS, results=out)
            self.finished_ok.emit(out)
        except Exception as e:
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=str(e))
            self.finished_err.emit(str(e))

    def _index_scope_until_stable(self, root: str, max_cycles: int = 5) -> None:
        """Helper for background indexing."""
        scan = self._scan_scope_files(root)
        runtime_roots = list(scan.get("runtime_roots") or [])
        if not runtime_roots:
            return

        target_files = int(scan.get("files_with_ext", 0))
        allowed_exts = scan.get("allowed_exts") or None
        max_files = max(int(scan.get("total_files", 0)) + 1000, 20000)

        prev_total = -1
        cycles_run = 0

        while cycles_run < max_cycles:
            if self.isInterruptionRequested(): break
            cycles_run += 1
            self.progress_update.emit(f"Indexing pass {cycles_run}/{max_cycles}...")
            
            payload = {
                "roots": runtime_roots,
                "recursive": True,
                "allowed_exts": allowed_exts,
                "max_files": max_files,
            }
            # Use canonical path
            api_client.post("/files/index?use_taskmaster=false", json=payload, timeout=240.0)
            
            indexed_total = self._count_indexed_for_scope(root)
            if target_files > 0 and indexed_total >= target_files: break
            if indexed_total == prev_total: break
            prev_total = indexed_total

        if not self.isInterruptionRequested():
            api_client.post("/files/refresh?run_watches=false&stale_after_hours=1&use_taskmaster=false", json={}, timeout=180.0)

    def _scan_scope_files(self, root: str) -> dict:
        runtime_roots = get_existing_runtime_roots(root)
        total_files = 0
        files_with_ext = 0
        ext_set = set()
        for scan_root in runtime_roots:
            scan_path = Path(scan_root)
            if not scan_path.exists(): continue
            for _, _, filenames in os.walk(str(scan_path)):
                for name in filenames:
                    total_files += 1
                    ext = Path(name).suffix.lower().strip()
                    if ext:
                        files_with_ext += 1
                        ext_set.add(ext)
        return {"runtime_roots": runtime_roots, "total_files": total_files, "files_with_ext": files_with_ext, "allowed_exts": list(ext_set)}

    def _count_indexed_for_scope(self, root: str) -> int:
        best_total = 0
        for prefix in get_scope_prefixes(root):
            encoded = quote_plus(prefix)
            data = api_client.get(f"/files?limit=1&offset=0&q={encoded}", timeout=20.0)
            best_total = max(best_total, int(data.get("total", 0)))
        return best_total

class ApplyProposalsWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, job_id: str, root: str):
        super().__init__()
        self.job_id = job_id
        self.root = root

    def run(self):
        try:
            organization_service.update_job(self.job_id, status=OrgJobStatus.RUNNING, message="Applying proposals...")
            out = api_client.apply_organization_proposals(root_prefix=self.root)
            
            # Index refresh after apply
            api_client.post("/files/refresh?run_watches=false&stale_after_hours=1&use_taskmaster=false", json={}, timeout=120.0)
            
            organization_service.update_job(self.job_id, status=OrgJobStatus.SUCCESS, results=out)
            self.finished_ok.emit(out)
        except Exception as e:
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=str(e))
            self.finished_err.emit(str(e))

class ClearProposalsWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, job_id: str, root: str):
        super().__init__()
        self.job_id = job_id
        self.root = root

    def run(self):
        try:
            organization_service.update_job(self.job_id, status=OrgJobStatus.RUNNING, message="Clearing proposals...")
            out = api_client.clear_organization_proposals(root_prefix=self.root)
            organization_service.update_job(self.job_id, status=OrgJobStatus.SUCCESS, results=out)
            self.finished_ok.emit(out)
        except Exception as e:
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=str(e))
            self.finished_err.emit(str(e))

class BulkActionWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(
        self,
        job_id: str,
        proposal_ids: List[int],
        action: str,
        note: Optional[str] = None,
        edits_by_id: Optional[Dict[int, Dict[str, Any]]] = None,
    ):
        super().__init__()
        self.job_id = job_id
        self.proposal_ids = proposal_ids
        self.action = action
        self.note = note
        self.edits_by_id = edits_by_id or {}

    def run(self):
        success_count = 0
        fail_count = 0
        errors = []
        total = len(self.proposal_ids)

        organization_service.update_job(self.job_id, status=OrgJobStatus.RUNNING, message=f"Processing {total} items...")

        for idx, pid in enumerate(self.proposal_ids):
            if self.isInterruptionRequested():
                organization_service.update_job(self.job_id, status=OrgJobStatus.CANCELLED)
                return

            try:
                progress = int((idx / total) * 100)
                organization_service.update_job(self.job_id, progress=progress, message=f"Item {idx+1}/{total}...")
                
                if self.action == "approve" and pid in self.edits_by_id:
                    endpoint = f"/organization/proposals/{pid}/edit"
                    payload = dict(self.edits_by_id.get(pid) or {})
                    if self.note and not payload.get("note"):
                        payload["note"] = self.note
                else:
                    endpoint = f"/organization/proposals/{pid}/{self.action}"
                    payload = {"note": self.note} if self.note else {}
                api_client.post(endpoint, payload, timeout=30.0)
                
                success_count += 1
                organization_service.record_item_success(self.job_id, pid)
            except Exception as e:
                fail_count += 1
                err_msg = str(e)
                errors.append(f"#{pid}: {err_msg}")
                organization_service.record_item_failure(self.job_id, pid, err_msg)

        results = {"success": success_count, "failed": fail_count, "errors": errors}
        organization_service.update_job(self.job_id, status=OrgJobStatus.SUCCESS, results=results)
        self.finished_ok.emit(results)
