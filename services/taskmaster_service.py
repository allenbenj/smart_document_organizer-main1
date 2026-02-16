"""MVP TaskMaster orchestrator for scanner workflows."""

from __future__ import annotations

import asyncio
import re
import threading
from typing import Any, Dict, Optional

from mem_db.database import DatabaseManager
from services.file_index_service import FileIndexService
from services.persona_skill_runtime import PersonaSkillRuntime


class TaskMasterService:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.file_index = FileIndexService(db)
        self.skill_runtime = PersonaSkillRuntime(db)

    @staticmethod
    def _run_coro_sync(coro):
        """Run async coroutine from sync context, even if an event loop is already running."""
        out = {"result": None, "error": None}

        def _worker():
            try:
                out["result"] = asyncio.run(coro)
            except Exception as e:
                out["error"] = e

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join()
        if out["error"] is not None:
            raise out["error"]
        return out["result"]

    @staticmethod
    def _extract_text_from_processed(process_data: Dict[str, Any]) -> str:
        for key in ["content", "text", "document_text", "extracted_text", "full_text"]:
            v = process_data.get(key)
            if isinstance(v, str) and v.strip():
                return v
        doc = process_data.get("document") if isinstance(process_data.get("document"), dict) else {}
        for key in ["content", "text", "document_text", "extracted_text", "full_text"]:
            v = doc.get(key)
            if isinstance(v, str) and v.strip():
                return v
        return ""

    @staticmethod
    def _has_skill(skill_names: list[str], target: str) -> bool:
        t = target.strip().lower()
        return any(str(s).strip().lower() == t for s in skill_names)

    def _extract_candidate_terms(self, text: str) -> list[str]:
        terms = set()
        for m in re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text or ""):
            terms.add(m.strip())
        return sorted(terms)[:20]

    def _generate_knowledge_questions(self, run_id: int) -> int:
        created = 0
        files = self.db.list_all_indexed_files()
        for f in files[:300]:
            if str(f.get("status")) != "ready":
                continue
            meta = f.get("metadata_json") or {}
            sample = " ".join(
                [
                    str(f.get("display_name") or ""),
                    str(meta.get("preview") or ""),
                    " ".join([h.get("title", "") for h in (meta.get("headings") or []) if isinstance(h, dict)]),
                ]
            )
            for term in self._extract_candidate_terms(sample):
                if not self.db.knowledge_has_term(term):
                    qid = self.db.knowledge_add_question(
                        question=f"What is '{term}' in this case context?",
                        context={"file_id": f.get("id"), "file": f.get("display_name")},
                        linked_term=term,
                        asked_by="taskmaster",
                    )
                    self._emit(
                        run_id,
                        level="info",
                        event_type="knowledge_question_created",
                        message=f"Knowledge question created for unknown term: {term}",
                        data={"question_id": qid, "term": term, "file_id": f.get("id")},
                        code="TM_KQ_CREATE",
                        category="knowledge",
                    )
                    created += 1
                    if created >= 25:
                        return created
        return created

    def _emit(
        self,
        run_id: int,
        *,
        level: str,
        event_type: str,
        message: str,
        task_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
        category: Optional[str] = None,
    ) -> None:
        payload = dict(data or {})
        if code:
            payload.setdefault("code", code)
        if category:
            payload.setdefault("category", category)
        self.db.taskmaster_add_event(
            run_id,
            task_id=task_id,
            level=level,
            event_type=event_type,
            message=message,
            data=payload,
        )

    def run_file_pipeline(
        self,
        *,
        mode: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        requested_persona_name = payload.get("persona_name")
        resolved_persona = (
            self.db.persona_get_by_name(str(requested_persona_name))
            if requested_persona_name
            else self.db.persona_resolve(mode=mode, content_type=payload.get("content_type"))
        )
        effective_payload = {"mode": mode, **payload}
        persona_skills: list[str] = []
        if resolved_persona:
            persona_skills = self.db.persona_skill_names(int(resolved_persona.get("id")))
            effective_payload["persona"] = {
                "id": resolved_persona.get("id"),
                "name": resolved_persona.get("name"),
                "role": resolved_persona.get("role"),
                "skills": persona_skills,
                "requested": requested_persona_name,
            }

        run_id = self.db.taskmaster_create_run("file_pipeline", payload=effective_payload)
        self._emit(
            run_id,
            level="info",
            event_type="run_started",
            message=f"TaskMaster run started: {mode}",
            data=effective_payload,
            code="TM_RUN_START",
            category="lifecycle",
        )
        if resolved_persona:
            self._emit(
                run_id,
                level="info",
                event_type="persona_activated",
                message=f"Persona activated: {resolved_persona.get('name')}",
                data={"persona_id": resolved_persona.get("id"), "persona_name": resolved_persona.get("name"), "skills": persona_skills},
                code="TM_PERSONA_ACTIVE",
                category="persona",
            )

        required_skill_by_mode = {
            "analysis": "Framework Detector & Mapper",
            "strategy": "Issue Tree & MECE Builder",
            "diagnostics": "Self-Referential Analyzer",
            "recovery": "Salvageability & Fix Planner",
        }
        required = required_skill_by_mode.get(mode)
        if required and resolved_persona and not self._has_skill(persona_skills, required):
            self._emit(
                run_id,
                level="warning",
                event_type="persona_skill_mismatch",
                message=f"Persona missing recommended skill for mode '{mode}'",
                data={"required_skill": required, "persona": resolved_persona.get("name"), "skills": persona_skills},
                code="TM_SKILL_MISMATCH",
                category="persona",
            )

        # Start a TaskMaster tracing span (best-effort)
        try:
            from opentelemetry import trace as _otel_trace  # type: ignore
            _tm_tracer = _otel_trace.get_tracer(__name__)
            _tm_span_ctx = _tm_tracer.start_as_current_span("taskmaster.run_file_pipeline", attributes={"mode": mode, "requested_persona": requested_persona_name})
            _tm_span_ctx.__enter__()
        except Exception:
            _tm_span_ctx = None

        try:
            if mode == "index":
                task_id = self.db.taskmaster_create_task(run_id, "index_roots", payload=payload)
                self._emit(run_id, task_id=task_id, level="info", event_type="task_started", message="Index roots started", code="TM_TASK_START", category="task")
                res = self.file_index.index_roots(
                    payload.get("roots", []),
                    recursive=bool(payload.get("recursive", True)),
                    allowed_exts=set(payload.get("allowed_exts", []) or []) or None,
                    include_paths=payload.get("include_paths"),
                    exclude_paths=payload.get("exclude_paths"),
                    min_size_bytes=payload.get("min_size_bytes"),
                    max_size_bytes=payload.get("max_size_bytes"),
                    modified_after_ts=payload.get("modified_after_ts"),
                    max_files=int(payload.get("max_files", 5000)),
                    max_depth=payload.get("max_depth"),
                    max_runtime_seconds=payload.get("max_runtime_seconds"),
                    follow_symlinks=bool(payload.get("follow_symlinks", False)),
                    progress_cb=lambda p: self._emit(run_id, task_id=task_id, level="info", event_type="task_progress", message="Indexing progress", data=p, code="TM_PROGRESS", category="progress"),
                    should_stop=lambda: self.db.taskmaster_get_run_status(run_id) == "cancelled",
                )
                if res.get("cancelled"):
                    self.db.taskmaster_update_task(task_id, status="cancelled", progress=100, result=res, done=True)
                    self.db.taskmaster_complete_run(run_id, status="cancelled", summary={"mode": mode, "result": res})
                    self._emit(run_id, task_id=task_id, level="warning", event_type="task_cancelled", message="Index roots cancelled", data=res, code="TM_TASK_CANCELLED", category="task")
                    return {"success": False, "error": "cancelled", "run": self.db.taskmaster_get_run(run_id)}
                self.db.taskmaster_update_task(task_id, status="completed", progress=100, result=res, done=True)
                self._emit(run_id, task_id=task_id, level="info", event_type="task_completed", message="Index roots completed", data=res, code="TM_TASK_COMPLETE", category="task")
                can_question = (not resolved_persona) or self._has_skill(persona_skills, "Self-Referential Analyzer") or str((resolved_persona or {}).get("name", "")).lower() == "questioner"
                kq = self._generate_knowledge_questions(run_id) if can_question else 0
                summary = {"mode": mode, "result": res, "knowledge_questions_created": kq}

            elif mode == "refresh":
                task_id = self.db.taskmaster_create_task(run_id, "refresh_index", payload=payload)
                self._emit(run_id, task_id=task_id, level="info", event_type="task_started", message="Refresh index started", code="TM_TASK_START", category="task")
                res = self.file_index.refresh_index(
                    stale_after_hours=int(payload.get("stale_after_hours", 24)),
                    progress_cb=lambda p: self._emit(run_id, task_id=task_id, level="info", event_type="task_progress", message="Refresh progress", data=p, code="TM_PROGRESS", category="progress"),
                    should_stop=lambda: self.db.taskmaster_get_run_status(run_id) == "cancelled",
                )
                if res.get("cancelled"):
                    self.db.taskmaster_update_task(task_id, status="cancelled", progress=100, result=res, done=True)
                    self.db.taskmaster_complete_run(run_id, status="cancelled", summary={"mode": mode, "result": res})
                    self._emit(run_id, task_id=task_id, level="warning", event_type="task_cancelled", message="Refresh cancelled", data=res, code="TM_TASK_CANCELLED", category="task")
                    return {"success": False, "error": "cancelled", "run": self.db.taskmaster_get_run(run_id)}
                self.db.taskmaster_update_task(task_id, status="completed", progress=100, result=res, done=True)
                self._emit(run_id, task_id=task_id, level="info", event_type="task_completed", message="Refresh index completed", data=res, code="TM_TASK_COMPLETE", category="task")
                summary = {"mode": mode, "result": res}

            elif mode == "watch_refresh":
                t1 = self.db.taskmaster_create_task(run_id, "run_watches", payload=payload)
                self.db.taskmaster_add_event(run_id, task_id=t1, level="info", event_type="task_started", message="Watched indexing started")
                r1 = self.file_index.run_watched_index(max_files_per_watch=int(payload.get("max_files_per_watch", 5000)))
                self.db.taskmaster_update_task(t1, status="completed", progress=100, result=r1, done=True)
                self.db.taskmaster_add_event(run_id, task_id=t1, level="info", event_type="task_completed", message="Watched indexing completed", data=r1)

                t2 = self.db.taskmaster_create_task(run_id, "refresh_index", payload=payload)
                self.db.taskmaster_add_event(run_id, task_id=t2, level="info", event_type="task_started", message="Refresh index started")
                r2 = self.file_index.refresh_index(stale_after_hours=int(payload.get("stale_after_hours", 24)))
                self.db.taskmaster_update_task(t2, status="completed", progress=100, result=r2, done=True)
                self.db.taskmaster_add_event(run_id, task_id=t2, level="info", event_type="task_completed", message="Refresh index completed", data=r2)
                can_question = (not resolved_persona) or self._has_skill(persona_skills, "Self-Referential Analyzer") or str((resolved_persona or {}).get("name", "")).lower() == "questioner"
                kq = self._generate_knowledge_questions(run_id) if can_question else 0
                summary = {"mode": mode, "watch": r1, "refresh": r2, "knowledge_questions_created": kq}

            elif mode == "analyze_indexed":
                t = self.db.taskmaster_create_task(run_id, "analyze_indexed", payload=payload)
                self._emit(run_id, task_id=t, level="info", event_type="task_started", message="Indexed analysis started", code="TM_TASK_START", category="task")

                from agents import get_agent_manager

                mgr = get_agent_manager()
                self._run_coro_sync(mgr.initialize())

                items = [x for x in self.db.list_all_indexed_files() if str(x.get("status")) == "ready"]
                max_files = int(payload.get("max_files_analyze", 200))
                items = items[:max_files]

                counts = {
                    "process_ok": 0,
                    "entities_ok": 0,
                    "legal_ok": 0,
                    "irac_ok": 0,
                    "toulmin_ok": 0,
                    "precedents_ok": 0,
                    "contract_ok": 0,
                    "compliance_ok": 0,
                    "ontology_hits": 0,
                }
                per_file = []

                for i, rec in enumerate(items, start=1):
                    path = rec.get("normalized_path")
                    if not path:
                        continue

                    p = self._run_coro_sync(mgr.process_document(path))
                    process_ok = bool(getattr(p, "success", False))
                    pdata = (getattr(p, "data", {}) or {}) if process_ok else {}
                    text = self._extract_text_from_processed(pdata)
                    if not text:
                        text = str((rec.get("metadata_json") or {}).get("preview") or "")

                    e = self._run_coro_sync(mgr.extract_entities(text))
                    l = self._run_coro_sync(mgr.analyze_legal_reasoning(text))
                    ir = self._run_coro_sync(mgr.analyze_irac(text))
                    to = self._run_coro_sync(mgr.analyze_toulmin(text))
                    co = self._run_coro_sync(mgr.analyze_contract(text))
                    cm = self._run_coro_sync(mgr.check_compliance(text))

                    citations = []
                    import re as _re

                    for m in _re.findall(r"\b\d+\s+[A-Z][A-Za-z\.\s]*\s+\d+\b", text or ""):
                        citations.append(m)
                    pr = self._run_coro_sync(mgr.analyze_precedents(citations))

                    try:
                        ents = self.db.get_file_entities(rec.get("id")) or []
                        ontology_hits = len(ents)
                    except Exception:
                        ontology_hits = 0

                    row = {
                        "file_id": rec.get("id"),
                        "file": rec.get("display_name"),
                        "process_ok": bool(getattr(p, "success", False)),
                        "entities_ok": bool(getattr(e, "success", False)),
                        "legal_ok": bool(getattr(l, "success", False)),
                        "irac_ok": bool(getattr(ir, "success", False)),
                        "toulmin_ok": bool(getattr(to, "success", False)),
                        "precedents_ok": bool(getattr(pr, "success", False)),
                        "contract_ok": bool(getattr(co, "success", False)),
                        "compliance_ok": bool(getattr(cm, "success", False)),
                        "ontology_hits": ontology_hits,
                    }
                    per_file.append(row)

                    for k in ["process_ok", "entities_ok", "legal_ok", "irac_ok", "toulmin_ok", "precedents_ok", "contract_ok", "compliance_ok"]:
                        if row[k]:
                            counts[k] += 1
                    counts["ontology_hits"] += ontology_hits

                    if i % 10 == 0:
                        self._emit(run_id, task_id=t, level="info", event_type="task_progress", message="Analyze indexed progress", data={"done": i, "total": len(items)}, code="TM_PROGRESS", category="progress")

                res = {"files_total": len(items), "counts": counts, "files": per_file}
                self.db.taskmaster_update_task(t, status="completed", progress=100, result=res, done=True)
                self._emit(run_id, task_id=t, level="info", event_type="task_completed", message="Indexed analysis completed", data={"files_total": len(items), "counts": counts}, code="TM_TASK_COMPLETE", category="task")
                summary = {"mode": mode, "analysis": {"files_total": len(items), **counts}}

            elif mode == "organize_indexed":
                t = self.db.taskmaster_create_task(run_id, "organize_indexed", payload=payload)
                self._emit(run_id, task_id=t, level="info", event_type="task_started", message="Organization proposal generation started", code="TM_TASK_START", category="task")
                from services.organization_service import OrganizationService

                org = OrganizationService(self.db)
                out = org.generate_proposals(
                    run_id=run_id,
                    limit=int(payload.get("max_files_organize", payload.get("max_files_analyze", 200))),
                    provider=payload.get("provider"),
                    model=payload.get("model"),
                )
                self.db.taskmaster_update_task(t, status="completed", progress=100, result=out, done=True)
                self._emit(run_id, task_id=t, level="info", event_type="task_completed", message="Organization proposal generation completed", data={"created": out.get("created", 0)}, code="TM_TASK_COMPLETE", category="task")
                summary = {"mode": mode, "organization": {"created": out.get("created", 0)}}

            else:
                raise ValueError(f"Unsupported mode: {mode}")

            skill_results = []
            if resolved_persona and persona_skills:
                skill_results = self.skill_runtime.run(
                    run_id=run_id,
                    persona_id=int(resolved_persona.get("id")),
                    skill_names=persona_skills,
                    mode=mode,
                )
                self._emit(
                    run_id,
                    level="info",
                    event_type="skills_executed",
                    message=f"Executed {len(skill_results)} persona skills",
                    data={"count": len(skill_results), "skills": [s.get("skill") for s in skill_results]},
                    code="TM_SKILLS_EXECUTED",
                    category="persona",
                )
                summary["skill_results_count"] = len(skill_results)

            self.db.taskmaster_complete_run(run_id, status="completed", summary=summary)
            self._emit(run_id, level="info", event_type="run_completed", message="TaskMaster run completed", data=summary, code="TM_RUN_COMPLETE", category="lifecycle")
            run = self.db.taskmaster_get_run(run_id)
            return {"success": True, "run": run}

        except Exception as e:
            self._emit(run_id, level="error", event_type="run_failed", message=str(e), data={"error": str(e)}, code="TM_RUN_FAILED", category="error")
            self.db.taskmaster_complete_run(run_id, status="failed", summary={"error": str(e)})
            run = self.db.taskmaster_get_run(run_id)
            return {"success": False, "error": str(e), "run": run}
        finally:
            # Ensure TaskMaster span is closed (best-effort)
            try:
                if _tm_span_ctx is not None:
                    _tm_span_ctx.__exit__(None, None, None)
            except Exception:
                pass

    def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        run_type: Optional[str] = None,
        started_after: Optional[str] = None,
        started_before: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "items": self.db.taskmaster_list_runs(
                limit=limit,
                offset=offset,
                status=status,
                run_type=run_type,
                started_after=started_after,
                started_before=started_before,
            ),
        }

    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        return self.db.taskmaster_get_run(run_id)

    def get_events(
        self,
        run_id: int,
        limit: int = 500,
        level: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "items": self.db.taskmaster_list_events(
                run_id,
                limit=limit,
                level=level,
                event_type=event_type,
            ),
        }

    def cancel_run(self, run_id: int) -> Dict[str, Any]:
        ok = self.db.taskmaster_cancel_run(run_id)
        if ok:
            self.db.taskmaster_add_event(
                run_id,
                level="warning",
                event_type="run_cancelled",
                message="Run cancelled by user",
            )
        return {"success": ok, "run": self.db.taskmaster_get_run(run_id)}

    def retry_run(self, run_id: int) -> Dict[str, Any]:
        run = self.db.taskmaster_get_run(run_id)
        if not run:
            return {"success": False, "error": "run_not_found"}

        payload = run.get("payload_json") or {}
        mode = payload.get("mode")
        if not mode:
            return {"success": False, "error": "run_payload_missing_mode"}

        return self.run_file_pipeline(mode=mode, payload=payload)

    def enqueue_file_pipeline(
        self,
        *,
        mode: str,
        payload: Optional[Dict[str, Any]] = None,
        max_retries: int = 2,
        max_queue_depth: int = 200,
    ) -> Dict[str, Any]:
        depth = self.db.taskmaster_queue_depth(include_running=False)
        if depth >= int(max_queue_depth):
            return {
                "success": False,
                "error": "backpressure_queue_full",
                "queue_depth": depth,
                "max_queue_depth": int(max_queue_depth),
            }
        job_id = self.db.taskmaster_queue_enqueue(
            mode=mode,
            payload=payload or {},
            max_retries=int(max_retries),
        )
        return {"success": True, "queue_job_id": job_id, "queue_depth": depth + 1}

    def run_worker_once(self, *, worker_name: str = "taskmaster-worker-1") -> Dict[str, Any]:
        job = self.db.taskmaster_queue_claim_next(worker_name=worker_name)
        if not job:
            return {"success": True, "idle": True}

        job_id = int(job.get("id"))
        mode = str(job.get("mode"))
        payload = dict(job.get("payload_json") or {})
        try:
            out = self.run_file_pipeline(mode=mode, payload=payload)
            if out.get("success"):
                self.db.taskmaster_queue_mark_completed(job_id)
                return {"success": True, "idle": False, "queue_job_id": job_id, "status": "completed", "run": out.get("run")}

            action = self.db.taskmaster_queue_mark_retry_or_dead_letter(
                job_id,
                error_message=str(out.get("error") or "taskmaster run failed"),
            )
            return {"success": False, "idle": False, "queue_job_id": job_id, "status": action, "error": out.get("error")}
        except Exception as e:
            action = self.db.taskmaster_queue_mark_retry_or_dead_letter(job_id, error_message=str(e))
            return {"success": False, "idle": False, "queue_job_id": job_id, "status": action, "error": str(e)}

    def queue_status(self) -> Dict[str, Any]:
        return {
            "success": True,
            "queued": self.db.taskmaster_queue_depth(include_running=False),
            "inflight": self.db.taskmaster_queue_depth(include_running=True),
            "dead_letters": len(self.db.taskmaster_dead_letters(limit=1000)),
        }

    def create_schedule(
        self,
        *,
        name: Optional[str],
        mode: str,
        payload: Optional[Dict[str, Any]],
        every_minutes: int,
        active: bool = True,
    ) -> Dict[str, Any]:
        sid = self.db.schedule_upsert(
            name=name,
            mode=mode,
            payload=payload,
            every_minutes=every_minutes,
            active=active,
        )
        return {"success": True, "id": sid}

    def list_schedules(self, active_only: bool = False) -> Dict[str, Any]:
        items = self.db.schedule_list(active_only=active_only)
        return {"success": True, "total": len(items), "items": items}

    def run_due_schedules(self, *, max_due: int = 2) -> Dict[str, Any]:
        # Keep scheduler ticks bounded to avoid long-running lock pressure from bulk schedule runs.
        due = self.db.schedule_due()[: max(1, int(max_due))]
        runs = []
        for s in due:
            mode = str(s.get("mode"))
            payload = dict(s.get("payload_json") or {})
            out = self.run_file_pipeline(mode=mode, payload=payload)
            runs.append({"schedule_id": s.get("id"), "result": out})
            self.db.schedule_mark_ran(int(s.get("id")), int(s.get("every_minutes") or 60))
        return {"success": True, "due": len(due), "runs": runs, "max_due": max(1, int(max_due))}

    def get_skill_results(self, run_id: int) -> Dict[str, Any]:
        items = self.db.skill_result_list(run_id)
        return {"success": True, "total": len(items), "items": items}

    def dashboard(self) -> Dict[str, Any]:
        runs = self.db.taskmaster_list_runs(limit=200)
        active = [r for r in runs if r.get("status") == "running"]
        completed = [r for r in runs if r.get("status") == "completed"]
        failed = [r for r in runs if r.get("status") == "failed"]
        cancelled = [r for r in runs if r.get("status") == "cancelled"]
        return {
            "success": True,
            "kpis": {
                "total_recent_runs": len(runs),
                "active_runs": len(active),
                "completed_runs": len(completed),
                "failed_runs": len(failed),
                "cancelled_runs": len(cancelled),
            },
            "active": active[:20],
        }
