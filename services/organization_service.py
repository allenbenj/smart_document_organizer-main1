from __future__ import annotations

import json
import os
import re
import time
import uuid
import difflib
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.llm_providers import LLMManager
from mem_db.database import DatabaseManager
from services.organization_llm import OrganizationLLMPolicy, OrganizationPromptAdapter


class OrganizationService:
    _runtime_provider: Optional[str] = None
    _runtime_model: Optional[str] = None
    _llm_fail_count: int = 0
    _llm_circuit_open_until: float = 0.0

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.llm_manager = LLMManager(
            api_key=os.getenv("XAI_API_KEY", "").strip() or None,
            provider="xai",
            default_model=os.getenv("LLM_MODEL", "grok-4-fast-reasoning"),
            base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
        )

    @classmethod
    def set_runtime_llm(cls, provider: Optional[str] = None, model: Optional[str] = None) -> None:
        cls._runtime_provider = provider.strip().lower() if isinstance(provider, str) and provider.strip() else None
        cls._runtime_model = model.strip() if isinstance(model, str) and model.strip() else None

    @classmethod
    def get_runtime_llm(cls) -> Dict[str, Optional[str]]:
        return {"provider": cls._runtime_provider, "model": cls._runtime_model}

    @classmethod
    def _llm_circuit_is_open(cls) -> bool:
        return time.time() < float(cls._llm_circuit_open_until)

    @classmethod
    def _llm_circuit_record_failure(cls) -> None:
        cls._llm_fail_count += 1
        if cls._llm_fail_count >= 3:
            cls._llm_circuit_open_until = time.time() + 120.0

    @classmethod
    def _llm_circuit_record_success(cls) -> None:
        cls._llm_fail_count = 0
        cls._llm_circuit_open_until = 0.0

    @staticmethod
    def _sanitize_path_parts(folder: str, filename: str) -> tuple[str, str]:
        safe_folder = str(folder or "Inbox/Review").replace("\\", "/").strip().strip("/")
        safe_folder = "/".join(p for p in safe_folder.split("/") if p and p not in {".", ".."})
        if not safe_folder:
            safe_folder = "Inbox/Review"

        safe_name = str(filename or "document").strip().replace("/", "_").replace("\\", "_")
        safe_name = re.sub(r"\s+", " ", safe_name)
        safe_name = re.sub(r"[^A-Za-z0-9._()\- ]+", "", safe_name).strip(" .")
        if not safe_name:
            safe_name = "document"
        return safe_folder, safe_name

    def _llm_suggest(
        self,
        *,
        provider: str,
        model: str,
        file_name: str,
        current_path: str,
        preview: str,
        known_folders: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        prompt = OrganizationPromptAdapter.build_proposal_prompt(
            file_name=file_name,
            current_path=current_path,
            preview=preview,
            known_folders=known_folders or [],
        )

        def _parse_json_maybe(text: str) -> Dict[str, Any]:
            if not text:
                raise RuntimeError("empty_llm_response")
            raw = text.strip()
            try:
                return json.loads(raw)
            except Exception:
                pass
            # Handle fenced code blocks
            if "```" in raw:
                raw = raw.replace("```json", "```")
                parts = raw.split("```")
                for p in parts:
                    p = p.strip()
                    if not p:
                        continue
                    try:
                        return json.loads(p)
                    except Exception:
                        continue
            raise RuntimeError("invalid_llm_json_response")

        if self._llm_circuit_is_open():
            raise RuntimeError("llm_circuit_open")

        try:
            out = self.llm_manager.complete_sync(
                prompt=prompt,
                provider=provider,
                model=model,
                temperature=0.1,
            )
            self._llm_circuit_record_success()
            return _parse_json_maybe(str(out))
        except Exception as exc:
            self._llm_circuit_record_failure()
            raise RuntimeError(f"llm_suggest_failed: {exc}") from exc

    def llm_status(self) -> Dict[str, Any]:
        runtime = self.get_runtime_llm()
        resolved = OrganizationLLMPolicy.resolve(
            runtime_provider=runtime.get("provider"),
            runtime_model=runtime.get("model"),
        )
        return {
            "active": {"provider": resolved.provider, "model": resolved.model},
            "runtime_override": runtime,
            "configured": OrganizationLLMPolicy.configured_status(),
            "base_urls": {
                "xai": os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
                "deepseek": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            },
        }

    def _infer_folder(self, name: str, preview: str = "") -> str:
        corpus = f"{name}\n{preview}".lower()
        rules = [
            ("invoice|billing|receipt|payment", "Finance/Billing"),
            ("contract|agreement|nda|msa", "Legal/Contracts"),
            ("motion|order|pleading|court|case|exhibit", "Legal/Litigation"),
            ("resume|cv|candidate|offer", "HR/Recruiting"),
            ("spec|design|architecture|api", "Engineering/Specs"),
        ]
        for pat, folder in rules:
            if re.search(pat, corpus):
                return folder
        return "Inbox/Review"

    def _infer_filename(self, rec: Dict[str, Any]) -> str:
        ext = (rec.get("ext") or "").strip()
        name = str(rec.get("display_name") or "document").strip()
        stem = Path(name).stem
        stem = re.sub(r"[^A-Za-z0-9 _\-\.]+", "", stem).strip().replace("  ", " ")
        stem = stem[:100] if stem else "document"
        return f"{stem}{ext}"

    @staticmethod
    def _resolve_root_prefix_path(root_prefix: Optional[str]) -> Optional[Path]:
        if not isinstance(root_prefix, str) or not root_prefix.strip():
            return None
        raw = root_prefix.strip().replace("\\", "/")
        win = re.match(r"^([A-Za-z]):/(.*)$", raw)
        if win and os.name != "nt":
            drive = win.group(1).lower()
            rest = win.group(2).lstrip("/")
            return Path(f"/mnt/{drive}/{rest}")
        return Path(raw)

    def _known_folders_from_root(self, root_prefix: Optional[str], max_items: int = 400) -> List[str]:
        root = self._resolve_root_prefix_path(root_prefix)
        if root is None or not root.exists() or not root.is_dir():
            return []
        out: List[str] = []
        seen = set()
        for dirpath, dirnames, _ in os.walk(str(root)):
            rel = Path(dirpath).relative_to(root).as_posix()
            if rel and rel not in seen:
                seen.add(rel)
                out.append(rel)
                if len(out) >= max_items:
                    break
            dirnames.sort()
        return out

    @staticmethod
    def _scope_prefixes(root_prefix: Optional[str]) -> List[str]:
        if not isinstance(root_prefix, str) or not root_prefix.strip():
            return []
        raw = root_prefix.strip().replace("\\", "/")
        prefixes = [raw]
        m = re.match(r"^([A-Za-z]):/(.*)$", raw)
        if m:
            drive = m.group(1).lower()
            rest = m.group(2).lstrip("/")
            prefixes.append(f"/mnt/{drive}/{rest}")
        m2 = re.match(r"^/mnt/([A-Za-z])/(.*)$", raw)
        if m2:
            drive = m2.group(1).upper()
            rest = m2.group(2).lstrip("/")
            prefixes.append(f"{drive}:/{rest}")
        return list(dict.fromkeys(prefixes))

    @staticmethod
    def _rank_known_folder_suggestions(current: str, known_folders: List[str], limit: int = 5) -> List[str]:
        if not known_folders:
            return []
        q = (current or "").strip().lower()
        if not q:
            return known_folders[:limit]
        # Prefer fuzzy-near folders to make alternatives more actionable.
        matches = difflib.get_close_matches(q, [k.lower() for k in known_folders], n=limit, cutoff=0.25)
        by_lower = {k.lower(): k for k in known_folders}
        ranked = [by_lower[m] for m in matches if m in by_lower]
        if len(ranked) < limit:
            for k in known_folders:
                if k not in ranked:
                    ranked.append(k)
                if len(ranked) >= limit:
                    break
        return ranked[:limit]

    def _folder_preference_scores(self) -> Dict[str, int]:
        """Learn simple folder preferences from historical feedback.

        Positive signals:
        - accept -> original/proposed folder
        - edit   -> final folder
        Negative signals:
        - reject -> original/proposed folder
        """
        scores: Dict[str, int] = {}
        feedback = self.db.organization_list_feedback(limit=5000, offset=0)
        for f in feedback:
            action = str(f.get("action") or "").lower()
            original = f.get("original") or {}
            final = f.get("final") or {}

            target_folder = ""
            if action == "edit":
                target_folder = str(final.get("proposed_folder") or "").strip()
            else:
                target_folder = str(original.get("proposed_folder") or "").strip()
            if not target_folder:
                continue

            if action in {"accept", "edit"}:
                scores[target_folder] = scores.get(target_folder, 0) + 1
            elif action == "reject":
                scores[target_folder] = scores.get(target_folder, 0) - 1
        return scores

    def generate_proposals(
        self,
        *,
        run_id: Optional[int] = None,
        limit: int = 200,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        root_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        items = [x for x in self.db.list_all_indexed_files() if str(x.get("status")) == "ready"]
        prefixes = self._scope_prefixes(root_prefix)
        if prefixes:
            items = [
                x
                for x in items
                if any(
                    str(x.get("normalized_path") or "").replace("\\", "/").startswith(pref)
                    for pref in prefixes
                )
            ]
        items = items[: int(limit)]
        created = 0
        rows: List[Dict[str, Any]] = []
        runtime = self.get_runtime_llm()
        resolved = OrganizationLLMPolicy.resolve(
            provider=provider,
            model=model,
            runtime_provider=runtime.get("provider"),
            runtime_model=runtime.get("model"),
        )
        provider_name = resolved.provider
        model_name = resolved.model
        known_folders = self._known_folders_from_root(root_prefix)
        configured_map = OrganizationLLMPolicy.configured_status()
        provider_configured = bool(configured_map.get(provider_name, False))
        if not provider_configured:
            raise RuntimeError(
                f"organization_provider_not_configured: provider={provider_name} model={model_name}"
            )

        folder_pref_scores = self._folder_preference_scores()

        for rec in items:
            name = str(rec.get("display_name") or "")
            meta = rec.get("metadata_json") or {}
            preview = str(meta.get("preview") or "")
            llm = self._llm_suggest(
                provider=provider_name,
                model=model_name,
                file_name=name,
                current_path=str(rec.get("normalized_path") or ""),
                preview=preview,
                known_folders=known_folders,
            )
            if not llm.get("proposed_folder") or not llm.get("proposed_filename"):
                raise RuntimeError(
                    f"organization_invalid_llm_output: missing_folder_or_filename file_id={rec.get('id')}"
                )
            folder, fname = self._sanitize_path_parts(
                str(llm.get("proposed_folder")),
                str(llm.get("proposed_filename")),
            )
            conf = float(llm.get("confidence", 0.75))
            rationale = str(llm.get("rationale") or "LLM proposal")
            alternatives = (
                llm.get("alternatives")
                if isinstance(llm.get("alternatives"), list)
                else ["Inbox/Review"]
            )
            source = "llm"

            # Apply learned confidence adjustment from past folder decisions.
            folder_bias = int(folder_pref_scores.get(folder, 0))
            if folder_bias != 0:
                conf = max(0.05, min(0.99, conf + (0.03 * folder_bias)))
            if known_folders:
                ranked = self._rank_known_folder_suggestions(folder, known_folders, limit=5)
                alternatives = list(dict.fromkeys([*alternatives, *ranked]))


            proposal = {
                "run_id": run_id,
                "file_id": rec.get("id"),
                "current_path": rec.get("normalized_path"),
                "proposed_folder": folder,
                "proposed_filename": fname,
                "confidence": conf,
                "rationale": rationale,
                "alternatives": alternatives,
                "provider": provider_name,
                "model": model_name,
                "status": "proposed",
                "metadata": {
                    "source": "organize_indexed",
                    "decision_source": source,
                    "folder_preference_bias": folder_bias,
                    "known_folders_count": len(known_folders),
                },
            }
            pid = self.db.organization_add_proposal(proposal)
            proposal["id"] = pid
            rows.append(proposal)
            created += 1

        return {
            "success": True,
            "created": created,
            "items": rows,
            "requested_provider": resolved.provider,
            "active_provider": provider_name,
        }

    def list_proposals(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
        root_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Scope first, then apply paging to avoid cross-root bleed in first page.
        if root_prefix and root_prefix.strip():
            items = self.db.organization_list_proposals(status=status, limit=100000, offset=0)
            prefixes = self._scope_prefixes(root_prefix)
            if prefixes:
                items = [
                    x
                    for x in items
                    if any(
                        str(x.get("current_path") or "").replace("\\", "/").startswith(pref)
                        for pref in prefixes
                    )
                ]
            start = max(0, int(offset))
            end = start + max(1, int(limit))
            items = items[start:end]
        else:
            items = self.db.organization_list_proposals(status=status, limit=limit, offset=offset)
        return {"success": True, "total": len(items), "items": items}

    def clear_proposals(
        self,
        *,
        status: Optional[str] = "proposed",
        root_prefix: Optional[str] = None,
        note: Optional[str] = "bulk_clear",
    ) -> Dict[str, Any]:
        items = self.db.organization_list_proposals(status=status, limit=100000, offset=0)
        prefixes = self._scope_prefixes(root_prefix)
        if prefixes:
            items = [
                x
                for x in items
                if any(
                    str(x.get("current_path") or "").replace("\\", "/").startswith(pref)
                    for pref in prefixes
                )
            ]

        cleared = 0
        ids: List[int] = []
        for p in items:
            pid = int(p.get("id")) if p.get("id") is not None else None
            if not pid:
                continue
            out = self.reject_proposal(pid, note=note)
            if out.get("success"):
                cleared += 1
                ids.append(pid)
        return {"success": True, "cleared": cleared, "ids": ids[:100], "status": status, "root_prefix": root_prefix}

    def list_feedback(self, *, limit: int = 200, offset: int = 0) -> Dict[str, Any]:
        items = self.db.organization_list_feedback(limit=limit, offset=offset)
        return {"success": True, "total": len(items), "items": items}

    def list_actions(self, *, limit: int = 200, offset: int = 0) -> Dict[str, Any]:
        items = self.db.organization_list_actions(limit=limit, offset=offset)
        return {"success": True, "total": len(items), "items": items}

    def stats(self) -> Dict[str, Any]:
        return {"success": True, **self.db.organization_stats()}

    def approve_proposal(self, proposal_id: int) -> Dict[str, Any]:
        p = self.db.organization_get_proposal(proposal_id)
        if not p:
            return {"success": False, "error": "proposal_not_found"}
        self.db.organization_update_proposal(proposal_id, status="approved")
        self.db.organization_add_feedback(
            {
                "proposal_id": proposal_id,
                "file_id": p.get("file_id"),
                "action": "accept",
                "original": p,
                "final": p,
                "note": None,
            }
        )
        return {"success": True, "proposal_id": proposal_id, "status": "approved"}

    def reject_proposal(self, proposal_id: int, note: Optional[str] = None) -> Dict[str, Any]:
        p = self.db.organization_get_proposal(proposal_id)
        if not p:
            return {"success": False, "error": "proposal_not_found"}
        self.db.organization_update_proposal(proposal_id, status="rejected")
        self.db.organization_add_feedback(
            {
                "proposal_id": proposal_id,
                "file_id": p.get("file_id"),
                "action": "reject",
                "original": p,
                "final": {},
                "note": note,
            }
        )
        return {"success": True, "proposal_id": proposal_id, "status": "rejected"}

    def edit_proposal(self, proposal_id: int, *, proposed_folder: str, proposed_filename: str, note: Optional[str] = None) -> Dict[str, Any]:
        return self.edit_proposal_fields(
            proposal_id,
            proposed_folder=proposed_folder,
            proposed_filename=proposed_filename,
            confidence=0.99,
            rationale="User edited and approved",
            note=note,
            auto_approve=True,
        )

    def edit_proposal_fields(
        self,
        proposal_id: int,
        *,
        proposed_folder: Optional[str] = None,
        proposed_filename: Optional[str] = None,
        confidence: Optional[float] = None,
        rationale: Optional[str] = None,
        note: Optional[str] = None,
        auto_approve: bool = True,
    ) -> Dict[str, Any]:
        p = self.db.organization_get_proposal(proposal_id)
        if not p:
            return {"success": False, "error": "proposal_not_found"}

        next_folder = proposed_folder if proposed_folder is not None else str(p.get("proposed_folder") or "Inbox/Review")
        next_filename = proposed_filename if proposed_filename is not None else str(p.get("proposed_filename") or "document")
        safe_folder, safe_name = self._sanitize_path_parts(next_folder, next_filename)

        self.db.organization_update_proposal(
            proposal_id,
            status="approved" if auto_approve else None,
            proposed_folder=safe_folder,
            proposed_filename=safe_name,
            confidence=confidence,
            rationale=rationale,
        )

        updated = self.db.organization_get_proposal(proposal_id) or {}
        self.db.organization_add_feedback(
            {
                "proposal_id": proposal_id,
                "file_id": p.get("file_id"),
                "action": "edit",
                "original": p,
                "final": updated,
                "note": note,
            }
        )
        return {
            "success": True,
            "proposal_id": proposal_id,
            "status": str(updated.get("status") or ("approved" if auto_approve else "proposed")),
            "item": updated,
        }

    def apply_approved(
        self,
        *,
        limit: int = 200,
        dry_run: bool = True,
        root_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        items = self.db.organization_list_proposals(status="approved", limit=limit, offset=0)
        prefixes = self._scope_prefixes(root_prefix)
        if prefixes:
            items = [
                p
                for p in items
                if any(
                    str(p.get("current_path") or "").replace("\\", "/").startswith(pref)
                    for pref in prefixes
                )
            ]
        rollback_group = uuid.uuid4().hex
        applied = 0
        failed = 0
        results = []
        for p in items:
            src = str(p.get("current_path") or "")
            if not src:
                continue
            src_path = Path(src)
            safe_folder, safe_name = self._sanitize_path_parts(
                str(p.get("proposed_folder") or "Inbox/Review"),
                str(p.get("proposed_filename") or src_path.name),
            )
            root_path = self._resolve_root_prefix_path(root_prefix)
            if root_path is not None:
                dst_dir = root_path / safe_folder
            else:
                dst_dir = src_path.parent / safe_folder
            dst_name = safe_name
            dst = dst_dir / dst_name
            ok = True
            err = None
            if not dry_run:
                try:
                    dst_dir.mkdir(parents=True, exist_ok=True)
                    src_path.rename(dst)
                except Exception as e:
                    ok = False
                    err = str(e)
            self.db.organization_add_action(
                {
                    "proposal_id": p.get("id"),
                    "file_id": p.get("file_id"),
                    "action_type": "move",
                    "from_path": str(src_path),
                    "to_path": str(dst),
                    "success": ok,
                    "error": err,
                    "rollback_group": rollback_group,
                }
            )
            if ok:
                applied += 1
                if not dry_run:
                    self.db.organization_update_proposal(int(p.get("id")), status="applied")
            else:
                failed += 1
            results.append({"proposal_id": p.get("id"), "ok": ok, "from": str(src_path), "to": str(dst), "error": err})

        return {
            "success": failed == 0,
            "dry_run": dry_run,
            "rollback_group": rollback_group,
            "applied": applied,
            "failed": failed,
            "results": results,
            "root_prefix": root_prefix,
        }
