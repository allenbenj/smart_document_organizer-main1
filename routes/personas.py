from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from services.dependencies import get_database_manager_strict_dep
from services.factory_capability_mapper import FactoryCapabilityMapper

router = APIRouter()


DEFAULT_PERSONAS = [
    {
        "name": "AIAgentExpert",
        "role": "Agent Lifecycle Architect",
        "system_prompt": "Design, debug, evaluate, and productionize agent/workflow systems with strong run-fix discipline.",
        "activation_rules": {"modes": ["analysis", "strategy", "diagnostics"], "content_types": ["agent_spec", "workflow", "system_report"]},
        "settings": {"temperature": 0.2, "source": "agent_resources/chatAgents/AIAgentExpert.agent.md"},
    },
    {
        "name": "DataAnalysisExpert",
        "role": "Data Inspection Specialist",
        "system_prompt": "Inspect structured data, compare slices, summarize schema-level findings, and flag anomalies.",
        "activation_rules": {"modes": ["analysis", "verify", "summary"], "content_types": ["csv", "jsonl", "table", "metrics"]},
        "settings": {"temperature": 0.1, "source": "agent_resources/chatAgents/DataAnalysisExpert.agent.md"},
    },
    {
        "name": "Diagnostician",
        "role": "System Auditor",
        "system_prompt": "Analyze system health, failures, and recovery plans. Rank severity and propose phased remediation.",
        "activation_rules": {"modes": ["diagnostics", "recovery"], "content_types": ["system_report", "meta"]},
        "settings": {"temperature": 0.1},
    },
    {
        "name": "Recovery Coordinator",
        "role": "Fix Planner",
        "system_prompt": "Convert diagnostics into executable recovery steps with dependencies and verification points.",
        "activation_rules": {"modes": ["recovery", "watch_refresh"], "content_types": ["system_report"]},
        "settings": {"temperature": 0.2},
    },
    {
        "name": "Legal Reasoning Specialist",
        "role": "Framework Applier",
        "system_prompt": "Apply legal reasoning frameworks (IRAC/Toulmin) and structure arguments clearly.",
        "activation_rules": {"modes": ["analysis"], "content_types": ["legal_doc", "brief", "motion"]},
        "settings": {"temperature": 0.2},
    },
    {
        "name": "Critical Thinker",
        "role": "Bias & Fallacy Detector",
        "system_prompt": "Identify fallacies, hidden assumptions, contradictory evidence, and bias from multiple perspectives.",
        "activation_rules": {"modes": ["analysis", "verify"], "content_types": ["legal_doc", "argument"]},
        "settings": {"temperature": 0.1},
    },
    {
        "name": "Strategic Analyst",
        "role": "Issue Tree Builder",
        "system_prompt": "Build issue trees, SWOTs, causal chains, and prioritize recommendations using MECE principles.",
        "activation_rules": {"modes": ["strategy", "analysis"], "content_types": ["legal_doc", "project"]},
        "settings": {"temperature": 0.2},
    },
    {
        "name": "Questioner",
        "role": "Clarification Generator",
        "system_prompt": "Generate targeted, context-aware questions when confidence is low or entities are ambiguous.",
        "activation_rules": {"modes": ["index", "refresh", "watch_refresh"], "content_types": ["any"]},
        "settings": {"temperature": 0.2},
    },
    {
        "name": "Summarizer",
        "role": "Reporting",
        "system_prompt": "Produce concise, faithful summaries and key findings using verified context first.",
        "activation_rules": {"modes": ["report", "summary"], "content_types": ["any"]},
        "settings": {"temperature": 0.2},
    },
]

DEFAULT_SKILLS = [
    {"name": "Framework Detector & Mapper", "description": "Detect IRAC/Toulmin/SWOT/issue-tree patterns", "config": {"enabled": True, "source": "internal"}},
    {"name": "Argument Structure Parser", "description": "Break arguments into claim/data/warrant/backing/qualifier/rebuttal", "config": {"enabled": True, "source": "internal"}},
    {"name": "Fallacy & Bias Scanner", "description": "Detect logical fallacies, assumption gaps, and bias", "config": {"enabled": True, "source": "internal"}},
    {"name": "Issue Tree & MECE Builder", "description": "Generate hierarchical, MECE issue trees", "config": {"enabled": True, "source": "internal"}},
    {"name": "Salvageability & Fix Planner", "description": "Rank what works and plan phased fixes", "config": {"enabled": True, "source": "internal"}},
    {"name": "Self-Referential Analyzer", "description": "Route meta/system docs to diagnostics and recovery", "config": {"enabled": True, "source": "internal"}},
    {"name": "Strategic Simulation", "description": "Run scenario analysis via SWOT/cost-benefit/causal chains", "config": {"enabled": True, "source": "internal"}},
    {"name": "Perspective Switcher", "description": "Generate prosecution/defense (or opposing) perspectives", "config": {"enabled": True, "source": "internal"}},
    {"name": "Agent Workflow Builder", "description": "Build and refine agents/workflows with plan->implement->verify discipline", "config": {"enabled": True, "source": "agent_resources/skills/agent-workflow-builder_ai_toolkit/SKILL.md"}},
    {"name": "Legal Finish Agent", "description": "Perform legal-grade gap detection, cross-reference, and risk-aware finalization", "config": {"enabled": True, "source": "agent_resources/skills/legal-finish-agent-skill/SKILL.md"}},
    {"name": "Provider Template Selector", "description": "Select provider/language starter templates from agent_resources/provider", "config": {"enabled": True, "source": "agent_resources/provider"}},
    {"name": "Evaluation Harness Planner", "description": "Build evaluation datasets and quality gates from eval playbooks", "config": {"enabled": True, "source": "agent_resources/eval"}},
    {"name": "Summarization Formatter", "description": "Produce concise, faithful output frames for reports and dashboards", "config": {"enabled": True, "source": "internal"}},
]


class PersonaPayload(BaseModel):
    name: str
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    activation_rules: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None
    active: bool = True


class SkillPayload(BaseModel):
    name: str
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    enabled: bool = True


class AttachSkillPayload(BaseModel):
    persona_id: int
    skill_id: int


@router.post("/personas")
async def upsert_persona(payload: PersonaPayload, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    pid = db.persona_upsert(
        name=payload.name,
        role=payload.role,
        system_prompt=payload.system_prompt,
        activation_rules=payload.activation_rules,
        settings=payload.settings,
        active=payload.active,
    )
    return {"success": True, "id": pid}


@router.get("/personas")
async def list_personas(active_only: bool = Query(False), db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    items = db.persona_list(active_only=active_only)
    return {"success": True, "total": len(items), "items": items}


@router.post("/personas/skills")
async def upsert_skill(payload: SkillPayload, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    sid = db.skill_upsert(name=payload.name, description=payload.description, config=payload.config, enabled=payload.enabled)
    return {"success": True, "id": sid}


@router.get("/personas/skills")
async def list_skills(enabled_only: bool = Query(False), db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    items = db.skill_list(enabled_only=enabled_only)
    return {"success": True, "total": len(items), "items": items}


@router.post("/personas/attach-skill")
async def attach_skill(payload: AttachSkillPayload, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    ok = db.persona_attach_skill(payload.persona_id, payload.skill_id)
    if not ok:
        raise HTTPException(status_code=400, detail="attach_failed")
    return {"success": True}


@router.get("/personas/{persona_id}/skills")
async def persona_skills(persona_id: int, db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    items = db.persona_skills(persona_id)
    return {"success": True, "total": len(items), "items": items}


@router.get("/personas/resolve")
async def resolve_persona(
    mode: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    p = db.persona_resolve(mode=mode, content_type=content_type)
    if not p:
        return {"success": True, "persona": None}
    p["skills"] = db.persona_skills(int(p["id"]))
    return {"success": True, "persona": p}


@router.post("/personas/sync-from-enhanced-factory")
async def sync_from_enhanced_factory(db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    mapper = FactoryCapabilityMapper(db)
    return mapper.sync()


@router.post("/personas/seed-defaults")
async def seed_defaults(db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    persona_ids: Dict[str, int] = {}
    skill_ids: Dict[str, int] = {}

    for p in DEFAULT_PERSONAS:
        pid = db.persona_upsert(
            name=p["name"],
            role=p.get("role"),
            system_prompt=p.get("system_prompt"),
            activation_rules=p.get("activation_rules") or {},
            settings=p.get("settings") or {},
            active=True,
        )
        persona_ids[p["name"]] = pid

    for s in DEFAULT_SKILLS:
        sid = db.skill_upsert(
            name=s["name"],
            description=s.get("description"),
            config=s.get("config") or {},
            enabled=True,
        )
        skill_ids[s["name"]] = sid

    # Baseline mappings
    attach_map = {
        "AIAgentExpert": [
            "Agent Workflow Builder",
            "Provider Template Selector",
            "Evaluation Harness Planner",
            "Self-Referential Analyzer",
        ],
        "DataAnalysisExpert": [
            "Evaluation Harness Planner",
            "Fallacy & Bias Scanner",
            "Summarization Formatter",
        ],
        "Diagnostician": [
            "Self-Referential Analyzer",
            "Salvageability & Fix Planner",
            "Fallacy & Bias Scanner",
        ],
        "Recovery Coordinator": [
            "Salvageability & Fix Planner",
            "Issue Tree & MECE Builder",
            "Strategic Simulation",
        ],
        "Legal Reasoning Specialist": [
            "Framework Detector & Mapper",
            "Argument Structure Parser",
            "Perspective Switcher",
            "Legal Finish Agent",
        ],
        "Critical Thinker": [
            "Fallacy & Bias Scanner",
            "Argument Structure Parser",
            "Perspective Switcher",
        ],
        "Strategic Analyst": [
            "Issue Tree & MECE Builder",
            "Strategic Simulation",
            "Framework Detector & Mapper",
        ],
        "Questioner": [
            "Framework Detector & Mapper",
            "Self-Referential Analyzer",
        ],
        "Summarizer": [
            "Framework Detector & Mapper",
            "Perspective Switcher",
            "Summarization Formatter",
        ],
    }

    attached = 0
    for persona_name, skill_names in attach_map.items():
        pid = persona_ids.get(persona_name)
        if not pid:
            continue
        for skill_name in skill_names:
            sid = skill_ids.get(skill_name)
            if not sid:
                continue
            db.persona_attach_skill(pid, sid)
            attached += 1

    return {
        "success": True,
        "personas_seeded": len(persona_ids),
        "skills_seeded": len(skill_ids),
        "attachments": attached,
    }
