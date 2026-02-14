from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .base import BaseRepository


class PersonaRepository(BaseRepository):
    def upsert(
        self,
        *,
        name: str,
        role: Optional[str] = None,
        system_prompt: Optional[str] = None,
        activation_rules: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        active: bool = True,
    ) -> int:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO manager_personas (name, role, system_prompt, activation_rules_json, settings_json, active, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    role=excluded.role,
                    system_prompt=excluded.system_prompt,
                    activation_rules_json=excluded.activation_rules_json,
                    settings_json=excluded.settings_json,
                    active=excluded.active,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (name, role, system_prompt, json.dumps(activation_rules or {}), json.dumps(settings or {}), 1 if active else 0),
            )
            row = conn.execute("SELECT id FROM manager_personas WHERE name = ?", (name,)).fetchone()
            conn.commit()
            return int(row[0]) if row else 0

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM manager_personas WHERE name = ?", (name,)).fetchone()
            if not row:
                return None
            item = dict(row)
            for k in ("activation_rules_json", "settings_json"):
                try:
                    item[k] = json.loads(item.get(k) or "{}")
                except Exception:
                    item[k] = {}
            item["active"] = bool(item.get("active"))
            return item

    def list(self, active_only: bool = False) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            where = "WHERE active = 1" if active_only else ""
            rows = conn.execute(f"SELECT * FROM manager_personas {where} ORDER BY name").fetchall()
            out: List[Dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                for k in ("activation_rules_json", "settings_json"):
                    try:
                        item[k] = json.loads(item.get(k) or "{}")
                    except Exception:
                        item[k] = {}
                item["active"] = bool(item.get("active"))
                out.append(item)
            return out

    def skill_upsert(self, *, name: str, description: Optional[str] = None, config: Optional[Dict[str, Any]] = None, enabled: bool = True) -> int:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO manager_skills (name, description, config_json, enabled, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    description=excluded.description,
                    config_json=excluded.config_json,
                    enabled=excluded.enabled,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (name, description, json.dumps(config or {}), 1 if enabled else 0),
            )
            row = conn.execute("SELECT id FROM manager_skills WHERE name = ?", (name,)).fetchone()
            conn.commit()
            return int(row[0]) if row else 0

    def skill_list(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            where = "WHERE enabled = 1" if enabled_only else ""
            rows = conn.execute(f"SELECT * FROM manager_skills {where} ORDER BY name").fetchall()
            out: List[Dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                try:
                    item["config_json"] = json.loads(item.get("config_json") or "{}")
                except Exception:
                    item["config_json"] = {}
                item["enabled"] = bool(item.get("enabled"))
                out.append(item)
            return out

    def attach_skill(self, persona_id: int, skill_id: int) -> bool:
        with self.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO manager_persona_skills (persona_id, skill_id) VALUES (?, ?)",
                (persona_id, skill_id),
            )
            conn.commit()
            return True

    def persona_skills(self, persona_id: int) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT s.* FROM manager_skills s
                JOIN manager_persona_skills ps ON ps.skill_id = s.id
                WHERE ps.persona_id = ?
                ORDER BY s.name
                """,
                (persona_id,),
            ).fetchall()
            out = []
            for r in rows:
                item = dict(r)
                try:
                    item["config_json"] = json.loads(item.get("config_json") or "{}")
                except Exception:
                    item["config_json"] = {}
                out.append(item)
            return out

    def resolve(self, *, mode: Optional[str] = None, content_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        candidates = self.list(active_only=True)
        for p in candidates:
            rules = p.get("activation_rules_json") or {}
            modes = set((rules.get("modes") or []))
            types = set((rules.get("content_types") or []))
            if mode and modes and mode in modes:
                return p
            if content_type and types and content_type in types:
                return p
        return candidates[0] if candidates else None

    def skill_result_add(self, *, run_id: int, skill_name: str, output: Dict[str, Any], persona_id: Optional[int] = None) -> int:
        with self.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO manager_skill_results (run_id, persona_id, skill_name, output_json)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, persona_id, skill_name, json.dumps(output or {})),
            )
            conn.commit()
            return int(cur.lastrowid)

    def skill_result_list(self, run_id: int) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM manager_skill_results WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                try:
                    item["output_json"] = json.loads(item.get("output_json") or "{}")
                except Exception:
                    item["output_json"] = {}
                out.append(item)
            return out
