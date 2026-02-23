from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from mem_db.database import DatabaseManager


class PersonaSkillRuntime:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def _sample_corpus(self, max_files: int = 80) -> str:
        rows = self.db.list_all_indexed_files()[:max_files]
        parts: List[str] = []
        for r in rows:
            if str(r.get("status")) != "ready":
                continue
            meta = r.get("metadata_json") or {}
            parts.append(str(r.get("display_name") or ""))
            parts.append(str(meta.get("preview") or ""))
        return "\n".join(parts)

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[1]

    def _resolve_source_path(self, source: str) -> Optional[Path]:
        raw = str(source or "").strip()
        if not raw:
            return None
        p = Path(raw)
        if p.is_absolute() and p.exists():
            return p
        rel = self._project_root() / raw
        if rel.exists():
            return rel
        return None

    def _load_skill_source_context(self, source: str) -> Dict[str, Any]:
        """Load lightweight context from a skill source path for runtime use."""
        if not source or source == "internal":
            return {"available": False, "source": source or "internal"}

        p = self._resolve_source_path(source)
        if p is None:
            return {"available": False, "source": source, "error": "source_not_found"}

        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                return {
                    "available": False,
                    "source": source,
                    "path": str(p),
                    "error": str(exc),
                }
            headings = re.findall(r"^##\s+(.+)$", text, flags=re.MULTILINE)[:8]
            return {
                "available": True,
                "source": source,
                "path": str(p),
                "type": "file",
                "headings": headings,
                "excerpt": text[:1200],
            }

        if p.is_dir():
            skill_md = p / "SKILL.md"
            excerpt = ""
            headings: List[str] = []
            if skill_md.exists():
                txt = skill_md.read_text(encoding="utf-8", errors="ignore")
                headings = re.findall(r"^##\s+(.+)$", txt, flags=re.MULTILINE)[:8]
                excerpt = txt[:1200]
            templates = sorted([x.name for x in p.glob("*.tpl")])[:20]
            files = sorted([x.name for x in p.iterdir() if x.is_file()])[:30]
            return {
                "available": True,
                "source": source,
                "path": str(p),
                "type": "directory",
                "files": files,
                "templates": templates,
                "headings": headings,
                "excerpt": excerpt,
            }

        return {"available": False, "source": source, "error": "unsupported_path_type"}

    def _skill_source_map(self, persona_id: Optional[int]) -> Dict[str, Dict[str, Any]]:
        if not persona_id:
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for s in self.db.persona_skills(int(persona_id)):
            name = str(s.get("name") or "").strip()
            cfg = s.get("config_json") if isinstance(s.get("config_json"), dict) else {}
            out[name] = cfg or {}
        return out

    def run(self, *, run_id: int, persona_id: int | None, skill_names: List[str], mode: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        corpus = self._sample_corpus()
        source_by_skill = self._skill_source_map(persona_id)

        for skill in skill_names:
            out: Dict[str, Any]
            s = skill.lower()
            source = str((source_by_skill.get(skill) or {}).get("source") or "internal")
            source_ctx = self._load_skill_source_context(source)

            if "legal finish agent" in s:
                found = []
                for key in [
                    "jurisdiction",
                    "practice area",
                    "document type",
                    "success criteria",
                ]:
                    if key in corpus.lower():
                        found.append(key)
                out = {
                    "workflow": [
                        "ingest",
                        "reason",
                        "argument_qa",
                        "authority_qa",
                        "risk_pass",
                        "report",
                    ],
                    "required_inputs_seen": found,
                    "resource_source": source,
                    "resource_context": source_ctx,
                }
            elif "agent workflow builder" in s:
                out = {
                    "delivery_checklist": [
                        "inputs_assumptions_documented",
                        "workflow_implemented_or_patched",
                        "structured_contract_enforced",
                        "confidence_uncertainty_included",
                    ],
                    "resource_source": source,
                    "resource_context": source_ctx,
                }
            elif "provider template selector" in s:
                providers: List[str] = []
                p = self._resolve_source_path(source)
                if p and p.is_dir():
                    providers = sorted(
                        [x.stem for x in p.glob("*.yml")] + [x.stem for x in p.glob("*.yaml")],
                    )
                out = {
                    "providers_available": providers,
                    "resource_source": source,
                    "resource_context": source_ctx,
                }
            elif "evaluation harness planner" in s:
                out = {
                    "evaluation_tasks": [
                        "define_queries",
                        "define_expected_outcomes",
                        "select_metrics",
                        "run_regression_suite",
                    ],
                    "resource_source": source,
                    "resource_context": source_ctx,
                }
            if "framework detector" in s:
                found = []
                for k in ["irac", "toulmin", "swot", "mece", "issue tree"]:
                    if k in corpus.lower():
                        found.append(k.upper())
                out = {"detected_frameworks": found, "mode": mode}
            elif "fallacy" in s or "bias" in s:
                cues = []
                for pat in ["always", "never", "obviously", "everyone knows"]:
                    if pat in corpus.lower():
                        cues.append(pat)
                out = {"bias_cues": cues, "count": len(cues)}
            elif "perspective switcher" in s:
                out = {
                    "perspectives": {
                        "prosecution": "Focus on policy, statutory compliance, and strongest inculpatory facts.",
                        "defense": "Focus on ambiguity, burden of proof, and alternative explanations.",
                    }
                }
            elif "issue tree" in s:
                out = {"issue_tree": [{"issue": "Document quality", "children": ["missing context", "weak evidence", "incomplete metadata"]}]}
            elif "salvageability" in s:
                out = {"plan": ["stabilize indexing", "validate entities", "close acceptance tests"], "priority": "high"}
            elif "self-referential analyzer" in s:
                meta_terms = re.findall(r"\b(start\.py|taskmaster|agent manager|truth_report)\b", corpus.lower())
                out = {"meta_mentions": sorted(set(meta_terms))}
            elif "legal finish agent" in s or "agent workflow builder" in s or "provider template selector" in s or "evaluation harness planner" in s:
                # Already handled above with resource-aware outputs.
                pass
            else:
                out = {"note": "Skill recognized but no runtime handler yet", "skill": skill}

            out.setdefault("resource_source", source)
            if "resource_context" not in out:
                out["resource_context"] = source_ctx
            self.db.skill_result_add(run_id=run_id, persona_id=persona_id, skill_name=skill, output=out)
            results.append({"skill": skill, "output": out})

        return results
