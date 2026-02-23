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
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(
        self,
        job_id: str,
        root_prefix: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ):
        super().__init__()
        self.job_id = job_id
        self.root_prefix = root_prefix
        self.status = status
        self.limit = max(1, int(limit))
        self.offset = max(0, int(offset))

    def run(self):
        try:
            organization_service.update_job(self.job_id, status=OrgJobStatus.RUNNING, message="Loading proposals...")
            result = api_client.get_organization_proposals(
                root_prefix=self.root_prefix, 
                status=self.status,
                limit=self.limit,
                offset=self.offset,
            )
            
            # ApiClient already normalized this to include 'items'
            items = result.get("items", [])
            
            # Fallback if no proposed found
            if not items and self.status == "proposed":
                organization_service.update_job(self.job_id, message="No pending found, checking all...")
                result = api_client.get_organization_proposals(
                    root_prefix=self.root_prefix,
                    limit=self.limit,
                    offset=self.offset,
                )
                items = result.get("items", [])

            payload = {
                "items": items,
                "total": int(result.get("total", len(items)) or 0),
                "limit": int(result.get("limit", self.limit) or self.limit),
                "offset": int(result.get("offset", self.offset) or self.offset),
            }
            organization_service.update_job(self.job_id, status=OrgJobStatus.SUCCESS, results=payload)
            self.finished_ok.emit(payload)
        except requests.exceptions.RequestException as e:
            error_msg = f"API connection error loading proposals: {e}"
            logger.error(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Invalid API response loading proposals: {e}"
            logger.error(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
        except RuntimeError as e:
            error_msg = f"Runtime error loading proposals: {e}"
            logger.error(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred loading proposals: {e}"
            logger.exception(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
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
                try:
                    self._index_scope_until_stable(self.root)
                except Exception as e:
                    logger.error(f"Error during index stabilization: {e}")
                    raise # Re-raise to be caught by the outer block

            if self.isInterruptionRequested():
                organization_service.update_job(self.job_id, status=OrgJobStatus.CANCELLED)
                return
                
            # 2. Generate
            self.progress_update.emit("Generating proposals (1-2 min)...")
            out = api_client.generate_organization_proposals(root_prefix=self.root)
            
            organization_service.update_job(self.job_id, status=OrgJobStatus.SUCCESS, results=out)
            self.finished_ok.emit(out)
        except requests.exceptions.RequestException as e:
            error_msg = f"API connection error generating proposals: {e}"
            logger.error(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Invalid API response generating proposals: {e}"
            logger.error(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
        except RuntimeError as e:
            error_msg = f"Runtime error generating proposals: {e}"
            logger.error(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred generating proposals: {e}"
            logger.exception(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
    def _index_scope_until_stable(self, root: str, max_cycles: int = 5) -> None:
        """Helper for background indexing."""
        scan = self._scan_scope_files(root)
        runtime_roots = list(scan.get("runtime_roots") or [])
        if not runtime_roots:
            return

        target_files = int(scan.get("files_with_ext", 0))
        allowed_exts = scan.get("allowed_exts") or None
        scanned_all = bool(scan.get("scanned_all", True))
        # For very large folders, avoid unbounded pre-scan costs and index in bounded passes.
        if scanned_all:
            max_files = max(int(scan.get("total_files", 0)) + 1000, 20000)
        else:
            max_files = 120000
            target_files = 0
            max_cycles = min(max_cycles, 3)

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

    def _scan_scope_files(
        self,
        root: str,
        max_scan_files: int = 20000,
        max_scan_dirs: int = 5000,
    ) -> dict:
        runtime_roots = get_existing_runtime_roots(root)
        total_files = 0
        files_with_ext = 0
        ext_set = set()
        scanned_all = True
        for scan_root in runtime_roots:
            scan_path = Path(scan_root)
            if not scan_path.exists():
                continue

            stack = [scan_path]
            scanned_dirs = 0
            while stack:
                if scanned_dirs >= max_scan_dirs or total_files >= max_scan_files:
                    scanned_all = False
                    break
                current = stack.pop()
                scanned_dirs += 1
                try:
                    with os.scandir(current) as it:
                        subdirs: list[Path] = []
                        for entry in it:
                            if entry.is_dir(follow_symlinks=False):
                                subdirs.append(Path(entry.path))
                                continue
                            if not entry.is_file(follow_symlinks=False):
                                continue
                            total_files += 1
                            ext = Path(entry.name).suffix.lower().strip()
                            if ext:
                                files_with_ext += 1
                                ext_set.add(ext)
                            if total_files >= max_scan_files:
                                scanned_all = False
                                break
                        subdirs.sort(key=lambda p: p.name.lower(), reverse=True)
                        stack.extend(subdirs)
                except (OSError, IOError) as e:
                    logger.warning(f"File system error during scanning '{current}': {e}")
                    continue
                except Exception as e:
                    logger.exception(f"An unexpected error occurred during scanning '{current}': {e}")
                    continue

        return {
            "runtime_roots": runtime_roots,
            "total_files": total_files,
            "files_with_ext": files_with_ext,
            "allowed_exts": list(ext_set),
            "scanned_all": scanned_all,
        }
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
            try:
                api_client.post("/files/refresh?run_watches=false&stale_after_hours=1&use_taskmaster=false", json={}, timeout=120.0)
            except requests.exceptions.RequestException as e:
                logger.warning(f"Failed to refresh index after applying proposals: {e}")
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid API response during index refresh after applying proposals: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error during index refresh after applying proposals: {e}")

            organization_service.update_job(self.job_id, status=OrgJobStatus.SUCCESS, results=out)
            self.finished_ok.emit(out)
        except requests.exceptions.RequestException as e:
            error_msg = f"API connection error applying proposals: {e}"
            logger.error(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Invalid API response applying proposals: {e}"
            logger.error(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
        except RuntimeError as e:
            error_msg = f"Runtime error applying proposals: {e}"
            logger.error(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred applying proposals: {e}"
            logger.exception(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
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
        except requests.exceptions.RequestException as e:
            error_msg = f"API connection error clearing proposals: {e}"
            logger.error(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Invalid API response clearing proposals: {e}"
            logger.error(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
        except RuntimeError as e:
            error_msg = f"Runtime error clearing proposals: {e}"
            logger.error(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred clearing proposals: {e}"
            logger.exception(error_msg)
            organization_service.update_job(self.job_id, status=OrgJobStatus.FAILED, error=error_msg)
            self.finished_err.emit(error_msg)

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
            except requests.exceptions.RequestException as e:
                fail_count += 1
                err_msg = f"API connection error for proposal #{pid}: {e}"
                logger.error(err_msg)
                errors.append(err_msg)
                organization_service.record_item_failure(self.job_id, pid, err_msg)
            except json.JSONDecodeError as e:
                fail_count += 1
                err_msg = f"Invalid API response for proposal #{pid}: {e}"
                logger.error(err_msg)
                errors.append(err_msg)
                organization_service.record_item_failure(self.job_id, pid, err_msg)
            except RuntimeError as e:
                fail_count += 1
                err_msg = f"Runtime error for proposal #{pid}: {e}"
                logger.error(err_msg)
                errors.append(err_msg)
                organization_service.record_item_failure(self.job_id, pid, err_msg)
            except Exception as e:
                fail_count += 1
                err_msg = f"An unexpected error occurred for proposal #{pid}: {e}"
                logger.exception(err_msg)
                errors.append(err_msg)
                organization_service.record_item_failure(self.job_id, pid, err_msg)

        results = {"success": success_count, "failed": fail_count, "errors": errors}
        organization_service.update_job(self.job_id, status=OrgJobStatus.SUCCESS, results=results)
        self.finished_ok.emit(results)
