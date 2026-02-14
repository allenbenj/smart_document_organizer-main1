from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from agents.base.enhanced_agent_factory import AgentTemplate, EnhancedAgentFactory
from mem_db.database import DatabaseManager


class _NullServiceContainer:
    def get_service(self, _name: str):
        return None


@dataclass
class _PersonaSeed:
    name: str
    role: str
    system_prompt: str
    activation_rules: Dict[str, Any]
    settings: Dict[str, Any]


class FactoryCapabilityMapper:
    """Sync EnhancedAgentFactory templates/capabilities into DB-backed personas/skills."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.factory = EnhancedAgentFactory(service_container=_NullServiceContainer())

    @staticmethod
    def _template_to_persona(template: AgentTemplate) -> _PersonaSeed:
        t = template.value
        role = t.replace("_", " ").title()
        mode_map = {
            "document_processor": ["index", "analysis"],
            "legal_analyzer": ["analysis", "strategy"],
            "entity_extractor": ["analysis", "verify"],
            "citation_analyzer": ["verify", "analysis"],
            "precedent_matcher": ["analysis", "strategy"],
            "compliance_checker": ["verify", "diagnostics"],
            "semantic_analyzer": ["analysis", "summary"],
            "memory_manager": ["index", "refresh", "watch_refresh"],
            "workflow_coordinator": ["watch_refresh", "recovery"],
            "production_semantic_analyzer": ["analysis", "summary"],
            "production_precedent_analyzer": ["analysis", "strategy"],
            "production_entity_extractor": ["analysis", "verify"],
            "production_embedding_agent": ["index", "analysis"],
        }
        content_map = {
            "document_processor": ["pdf", "docx", "txt", "html"],
            "legal_analyzer": ["legal_doc", "brief", "motion"],
            "entity_extractor": ["legal_doc", "text"],
            "citation_analyzer": ["brief", "case_law"],
            "precedent_matcher": ["case_law", "brief"],
            "compliance_checker": ["policy", "contract", "regulation"],
            "semantic_analyzer": ["legal_doc", "text"],
            "memory_manager": ["any"],
            "workflow_coordinator": ["any"],
            "production_semantic_analyzer": ["brief", "motion", "complaint", "contract"],
            "production_precedent_analyzer": ["case_law", "brief", "motion", "opinion"],
            "production_entity_extractor": ["complaint", "contract", "brief", "motion", "judgment"],
            "production_embedding_agent": ["any"],
        }
        return _PersonaSeed(
            name=f"Factory::{t}",
            role=role,
            system_prompt=f"Execute {t} tasks using EnhancedAgentFactory semantics and capability contracts.",
            activation_rules={"modes": mode_map.get(t, ["analysis"]), "content_types": content_map.get(t, ["any"]), "template": t},
            settings={"temperature": 0.1, "source": "agents/base/enhanced_agent_factory.py"},
        )

    @staticmethod
    def _capability_to_skill(capability: Any) -> Dict[str, Any]:
        c = getattr(capability, "value", str(capability))
        name = f"Factory Capability::{c}"
        return {
            "name": name,
            "description": f"Capability imported from EnhancedAgentFactory: {c}",
            "config": {"enabled": True, "source": "agents/base/enhanced_agent_factory.py", "capability": c},
        }

    def sync(self) -> Dict[str, Any]:
        persona_count = 0
        skill_count = 0
        attachment_count = 0

        for template, cfg in self.factory.agent_templates.items():
            persona = self._template_to_persona(template)
            pid = self.db.persona_upsert(
                name=persona.name,
                role=persona.role,
                system_prompt=persona.system_prompt,
                activation_rules=persona.activation_rules,
                settings=persona.settings,
                active=True,
            )
            persona_count += 1

            caps: List[Any] = cfg.get("capabilities", [])
            for cap in caps:
                skill = self._capability_to_skill(cap)
                sid = self.db.skill_upsert(
                    name=skill["name"],
                    description=skill.get("description"),
                    config=skill.get("config") or {},
                    enabled=True,
                )
                skill_count += 1
                self.db.persona_attach_skill(pid, sid)
                attachment_count += 1

        return {
            "success": True,
            "templates_mapped": len(self.factory.agent_templates),
            "personas_upserted": persona_count,
            "skills_upserted": skill_count,
            "attachments_upserted": attachment_count,
        }
