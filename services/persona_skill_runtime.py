from __future__ import annotations

import re
from typing import Any, Dict, List

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

    def run(self, *, run_id: int, persona_id: int | None, skill_names: List[str], mode: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        corpus = self._sample_corpus()

        for skill in skill_names:
            out: Dict[str, Any]
            s = skill.lower()
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
            else:
                out = {"note": "Skill recognized but no runtime handler yet", "skill": skill}

            self.db.skill_result_add(run_id=run_id, persona_id=persona_id, skill_name=skill, output=out)
            results.append({"skill": skill, "output": out})

        return results
