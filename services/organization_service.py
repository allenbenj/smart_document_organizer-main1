from __future__ import annotations

import json
import os
import re
import time
import uuid
import difflib
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.llm_providers import LLMManager
from mem_db.database import DatabaseManager
from services.organization_llm import OrganizationLLMPolicy, OrganizationPromptAdapter
from services.organization_naming_rules import OrganizationNamingRules
from services.provenance_service import ProvenanceGateError, get_provenance_service
from services.contracts.aedis_models import ProvenanceRecord, EvidenceSpan

logger = logging.getLogger(__name__)


class OrganizationService:
    _runtime_provider: Optional[str] = None
    _runtime_model: Optional[str] = None
    _llm_fail_count: int = 0
    _llm_circuit_open_until: float = 0.0

    def __init__(self, db: DatabaseManager, provenance_service: Optional[ProvenanceService] = None):
        self.db = db
        self.naming_rules = OrganizationNamingRules()
        self.provenance_service = provenance_service or get_provenance_service() # New service
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

    def _sanitize_path_parts(self, folder: str, filename: str) -> tuple[str, str]:
        safe_folder = str(folder or "Inbox/Review").replace("\\", "/").strip().strip("/")
        safe_folder = "/".join(p for p in safe_folder.split("/") if p and p not in {".", ".."})
        if not safe_folder:
            safe_folder = "Inbox/Review"

        safe_name = str(filename or "document").strip().replace("/", "_").replace("\\", "_")
        safe_name = re.sub(r"\s+", " ", safe_name)
        safe_name = re.sub(r"[^A-Za-z0-9._()\- ]+", "", safe_name).strip(" .")
        if not safe_name:
            safe_name = "document"
        return self._normalize_naming_rules(safe_folder, safe_name)

    @staticmethod
    def _validate_source_sha256(rec: Dict[str, Any]) -> str:
        raw = str(rec.get("sha256") or "").strip().lower()
        file_id = rec.get("id")
        if not raw:
            raise RuntimeError(
                f"organization_missing_source_sha256: file_id={file_id}"
            )
        if not re.fullmatch(r"[a-f0-9]{64}", raw):
            raise RuntimeError(
                f"organization_invalid_source_sha256: file_id={file_id}"
            )
        return raw

    def _normalize_naming_rules(self, folder: str, filename: str) -> tuple[str, str]:
        """Apply configurable global naming policy for folder + filename."""
        try:
            return self.naming_rules.apply(folder, filename)
        except Exception:
            return folder, filename

    def _llm_suggest(
        self,
        *,
        provider: str,
        model: str,
        file_name: str,
        current_path: str,
        preview: str,
        known_folders: Optional[List[str]] = None,
        semantic_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prompt = OrganizationPromptAdapter.build_proposal_prompt(
            file_name=file_name,
            current_path=current_path,
            preview=preview,
            known_folders=known_folders or [],
            semantic_summary=semantic_summary,
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
    def _path_matches_prefixes(path_value: Optional[str], prefixes: List[str]) -> bool:
        """Case-insensitive prefix match across Windows/WSL path variants."""
        if not prefixes:
            return True
        path_norm = str(path_value or "").replace("\\", "/").strip().lower()
        if not path_norm:
            return False
        for pref in prefixes:
            pref_norm = str(pref or "").replace("\\", "/").strip().lower()
            if pref_norm and path_norm.startswith(pref_norm):
                return True
        return False

    def _seed_index_from_root(self, root_prefix: Optional[str], max_items: int = 3000) -> int:
        """Best-effort index seeding from filesystem for scoped generation."""
        root = self._resolve_root_prefix_path(root_prefix)
        if root is None or not root.exists() or not root.is_dir():
            return 0

        allowed_exts = {
            ".txt", ".md", ".doc", ".docx", ".pdf", ".rtf",
            ".xls", ".xlsx", ".csv", ".ppt", ".pptx",
            ".eml", ".msg", ".json", ".xml", ".html", ".htm",
            ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif",
            ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".m4a",
            ".log",
        }
        seeded = 0
        for dirpath, _, filenames in os.walk(str(root)):
            for name in filenames:
                ext = Path(name).suffix.lower()
                if ext not in allowed_exts:
                    continue
                p = Path(dirpath) / name
                try:
                    st = p.stat()
                    self.db.upsert_indexed_file(
                        display_name=p.name,
                        original_path=str(p),
                        normalized_path=str(p),
                        file_size=int(st.st_size),
                        mtime=float(st.st_mtime),
                        mime_type=None,
                        mime_source=None,
                        sha256=None,
                        ext=ext,
                        status="indexed",
                        last_error=None,
                        metadata={"seeded_by": "organization_service", "root_prefix": root_prefix},
                    )
                    seeded += 1
                except Exception:
                    continue
                if seeded >= max_items:
                    return seeded
        return seeded

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

    @staticmethod
    def _normalize_alternatives(values: Any) -> List[str]:
        """Normalize LLM alternatives into a deduplicated list of folder strings."""
        if not isinstance(values, list):
            return []
        out: List[str] = []
        seen = set()
        for item in values:
            candidate = ""
            if isinstance(item, str):
                candidate = item
            elif isinstance(item, dict):
                candidate = str(
                    item.get("folder")
                    or item.get("path")
                    or item.get("name")
                    or ""
                )
            else:
                candidate = str(item or "")
            candidate = candidate.strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            out.append(candidate)
        return out

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

    @staticmethod
    def _path_signature(path_value: Optional[str]) -> str:
        """Stable key for matching near-identical documents across runs."""
        name = Path(str(path_value or "")).name.strip().lower()
        if not name:
            return ""
        stem = Path(name).stem
        return re.sub(r"[^a-z0-9]+", "", stem)

    def _historical_folder_corrections(self, min_votes: int = 1) -> Dict[str, str]:
        """Build signature -> preferred folder mapping from user edit feedback."""
        votes: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        feedback = self.db.organization_list_feedback(limit=5000, offset=0)
        for f in feedback:
            action = str(f.get("action") or "").strip().lower()
            if action != "edit":
                continue
            original = f.get("original") or {}
            final = f.get("final") or {}
            sig = self._path_signature(original.get("current_path"))
            folder = str(final.get("proposed_folder") or "").strip()
            if not sig or not folder:
                continue
            votes[sig][folder] += 1

        out: Dict[str, str] = {}
        threshold = max(1, int(min_votes))
        for sig, folder_counts in votes.items():
            best_folder = ""
            best_votes = 0
            for folder, count in folder_counts.items():
                if count > best_votes:
                    best_folder = folder
                    best_votes = count
            if best_folder and best_votes >= threshold:
                out[sig] = best_folder
        return out

    def _historical_filename_corrections(self, min_votes: int = 1) -> Dict[str, str]:
        """Build signature -> preferred filename mapping from user edit feedback."""
        votes: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        feedback = self.db.organization_list_feedback(limit=5000, offset=0)
        for f in feedback:
            action = str(f.get("action") or "").strip().lower()
            if action != "edit":
                continue
            original = f.get("original") or {}
            final = f.get("final") or {}
            sig = self._path_signature(original.get("current_path"))
            filename = str(final.get("proposed_filename") or "").strip()
            if not sig or not filename:
                continue
            votes[sig][filename] += 1

        out: Dict[str, str] = {}
        threshold = max(1, int(min_votes))
        for sig, name_counts in votes.items():
            best_name = ""
            best_votes = 0
            for name, count in name_counts.items():
                if count > best_votes:
                    best_name = name
                    best_votes = count
            if best_name and best_votes >= threshold:
                out[sig] = best_name
        return out

    def _auto_correct_existing_proposals(
        self,
        *,
        root_prefix: Optional[str] = None,
        min_votes: int = 1,
        limit: int = 2000,
    ) -> int:
        """Auto-correct existing proposed items using learned edit history."""
        learned_folders = self._historical_folder_corrections(min_votes=min_votes)
        learned_filenames = self._historical_filename_corrections(min_votes=min_votes)
        if not learned_folders and not learned_filenames:
            return 0

        proposals = self.db.organization_list_proposals(
            status="proposed",
            limit=limit,
            offset=0,
        )
        prefixes = self._scope_prefixes(root_prefix)
        if prefixes:
            proposals = [
                p
                for p in proposals
                if self._path_matches_prefixes(p.get("current_path"), prefixes)
            ]

        corrected = 0
        for p in proposals:
            sig = self._path_signature(p.get("current_path"))
            target_folder = learned_folders.get(sig)
            target_filename = learned_filenames.get(sig)
            if not target_folder and not target_filename:
                continue
            current_folder = str(p.get("proposed_folder") or "").strip()
            current_filename = str(p.get("proposed_filename") or "").strip()

            next_folder = target_folder or current_folder
            next_filename = target_filename or current_filename
            if current_folder == next_folder and current_filename == next_filename:
                continue

            safe_folder, safe_name = self._sanitize_path_parts(
                next_folder,
                next_filename or "document",
            )
            pid = int(p.get("id"))
            self.db.organization_update_proposal(
                pid,
                proposed_folder=safe_folder,
                proposed_filename=safe_name,
                confidence=max(float(p.get("confidence") or 0.0), 0.98),
                rationale="Auto-corrected from historical user edits",
            )
            self.db.organization_add_feedback(
                {
                    "proposal_id": pid,
                    "file_id": p.get("file_id"),
                    "action": "auto_correct",
                    "original": p,
                    "final": self.db.organization_get_proposal(pid) or {},
                    "note": "auto-corrected_from_historical_feedback",
                }
            )
            corrected += 1
        return corrected

    def generate_proposals(
        self,
        *,
        run_id: Optional[int] = None,
        limit: int = 200,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        root_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        auto_corrected_existing = self._auto_correct_existing_proposals(
            root_prefix=root_prefix,
        )
        # Always seed scoped index view from filesystem first when scope is provided.
        seeded_count = 0
        if root_prefix and root_prefix.strip():
            seeded_count = self._seed_index_from_root(
                root_prefix,
                max_items=max(int(limit) * 20, 4000),
            )

        scoped_items = list(self.db.list_all_indexed_files())
        prefixes = self._scope_prefixes(root_prefix)
        if prefixes:
            scoped_items = [
                x
                for x in scoped_items
                if self._path_matches_prefixes(x.get("normalized_path"), prefixes)
            ]
        ready_items = [
            x for x in scoped_items if str(x.get("status") or "").strip().lower() == "ready"
        ]
        candidate_items = [
            x
            for x in scoped_items
            if str(x.get("status") or "").strip().lower() not in {"missing"}
        ]
        items = candidate_items[: int(limit)]
        active_generation_mode = True

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
        learned_folders = self._historical_folder_corrections(min_votes=1)
        learned_filenames = self._historical_filename_corrections(min_votes=1)

        for rec in items:
            name = str(rec.get("display_name") or "")
            meta = rec.get("metadata_json") or {}
            preview = str(meta.get("preview") or "")
            row_status = str(rec.get("status") or "").strip().lower()
            source_sha256 = self._validate_source_sha256(rec)
            llm = self._llm_suggest(
                provider=provider_name,
                model=model_name,
                file_name=name,
                current_path=str(rec.get("normalized_path") or ""),
                preview=preview,
                known_folders=known_folders,
                semantic_summary=rec.get("metadata_json", {}).get("semantic_analysis_summary", None),
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
            used_provider = provider_name
            used_model = model_name

            sig = self._path_signature(rec.get("normalized_path"))
            learned_folder = learned_folders.get(sig)
            learned_filename = learned_filenames.get(sig)
            if learned_folder or learned_filename:
                folder, fname = self._sanitize_path_parts(
                    learned_folder or folder,
                    learned_filename or fname,
                )
                source = "historical_edit_feedback"
                rationale = "Auto-adjusted from historical user edits"
                conf = max(conf, 0.98)

            # Apply learned confidence adjustment from past folder decisions.
            folder_bias = int(folder_pref_scores.get(folder, 0))
            if folder_bias != 0:
                conf = max(0.05, min(0.99, conf + (0.03 * folder_bias)))
            if known_folders:
                ranked = self._rank_known_folder_suggestions(folder, known_folders, limit=5)
                alternatives = self._normalize_alternatives([*alternatives, *ranked])


            proposal = {
                "run_id": run_id,
                "file_id": rec.get("id"),
                "current_path": rec.get("normalized_path"),
                "proposed_folder": folder,
                "proposed_filename": fname,
                "confidence": conf,
                "rationale": rationale,
                "alternatives": alternatives,
                "provider": used_provider,
                "model": used_model,
                "status": "proposed",
                "metadata": {
                    "source": "organize_indexed",
                    "decision_source": source,
                    "folder_preference_bias": folder_bias,
                    "known_folders_count": len(known_folders),
                    "file_status": row_status or "unknown",
                },
            }
            pid = self.db.organization_add_proposal(proposal)
            proposal["id"] = pid

            # Phase 3: Record Provenance
            try:
                # Capture spans from LLM response
                raw_spans = llm.get("evidence_spans", [])
                spans = []
                for s in raw_spans:
                    try:
                        spans.append(EvidenceSpan(
                            artifact_row_id=int(rec.get("id")),
                            start_char=int(s.get("start_char")),
                            end_char=int(s.get("end_char")),
                            quote=s.get("quote")
                        ))
                    except (ValueError, TypeError):
                        continue
                
                # If no spans provided by LLM, require deterministic contextual evidence.
                if not spans:
                    fallback_text = preview.strip() or name.strip() or str(
                        rec.get("normalized_path") or ""
                    ).strip()
                    if not fallback_text:
                        raise RuntimeError(
                            f"organization_missing_evidence_context: file_id={rec.get('id')}"
                        )
                    spans.append(EvidenceSpan(
                        artifact_row_id=int(rec.get("id")),
                        start_char=0,
                        end_char=len(fallback_text),
                        quote=(
                            f"{fallback_text[:100]}..."
                            if len(fallback_text) > 100
                            else fallback_text
                        ),
                    ))

                prov_record = ProvenanceRecord(
                    source_artifact_row_id=int(rec.get("id")),
                    source_sha256=source_sha256,
                    captured_at=datetime.now(timezone.utc),
                    extractor=f"organizer:{provider_name}:{model_name}",
                    spans=spans,
                    notes=f"Auto-generated proposal for {name}"
                )
                
                prov_id = get_provenance_service().record_provenance(
                    prov_record, 
                    target_type="organization_proposal", 
                    target_id=str(pid)
                )
                proposal["metadata"]["provenance_id"] = prov_id
            except (ProvenanceGateError, RuntimeError) as prov_err:
                logger.error(f"Provenance gate failed for proposal {pid}: {prov_err}. Deleting proposal.")
                self.db.organization_delete_proposal(pid) # Delete the proposal if provenance fails
                raise # Re-raise to fail the generation for this proposal
            except Exception as prov_err:
                logger.exception(f"An unexpected error occurred while recording provenance for proposal {pid}: {prov_err}. Deleting proposal.")
                self.db.organization_delete_proposal(pid) # Delete the proposal if provenance fails
                raise # Re-raise to fail the generation for this proposal

            rows.append(proposal)
            created += 1

        return {
            "success": True,
            "created": created,
            "items": rows,
            "auto_corrected_existing": auto_corrected_existing,
            "requested_provider": resolved.provider,
            "active_provider": provider_name,
            "active_generation_mode": active_generation_mode,
            "seeded_indexed_count": seeded_count,
            "scoped_indexed_count": len(scoped_items),
            "scoped_candidate_count": len(candidate_items),
            "scoped_ready_count": len(ready_items),
        }

    def list_proposals(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
        root_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        auto_corrected_existing = 0
        if status is None or str(status).strip().lower() == "proposed":
            auto_corrected_existing = self._auto_correct_existing_proposals(
                root_prefix=root_prefix,
            )
        # Scope first, then apply paging to avoid cross-root bleed in first page.
        if root_prefix and root_prefix.strip():
            items = self.db.organization_list_proposals(status=status, limit=100000, offset=0)
            prefixes = self._scope_prefixes(root_prefix)
            if prefixes:
                items = [
                    x
                    for x in items
                    if self._path_matches_prefixes(x.get("current_path"), prefixes)
                ]
            start = max(0, int(offset))
            end = start + max(1, int(limit))
            items = items[start:end]
        else:
            items = self.db.organization_list_proposals(status=status, limit=limit, offset=offset)
        return {
            "success": True,
            "total": len(items),
            "items": items,
            "auto_corrected_existing": auto_corrected_existing,
        }

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
                if self._path_matches_prefixes(x.get("current_path"), prefixes)
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
                if self._path_matches_prefixes(p.get("current_path"), prefixes)
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
