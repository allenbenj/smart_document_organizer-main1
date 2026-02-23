from __future__ import annotations

from pathlib import Path

from mem_db.database import DatabaseManager
from services.persona_skill_runtime import PersonaSkillRuntime


def test_persona_skill_runtime_loads_agent_resources_context(tmp_path) -> None:
    db = DatabaseManager(str(tmp_path / "test.db"))

    persona_id = db.persona_upsert(
        name="Legal Reasoning Specialist",
        role="Framework Applier",
        system_prompt="Apply legal reasoning frameworks.",
        activation_rules={"modes": ["analysis"]},
        settings={},
        active=True,
    )
    skill_id = db.skill_upsert(
        name="Legal Finish Agent",
        description="Legal-grade finalization",
        config={
            "enabled": True,
            "source": "agent_resources/skills/legal-finish-agent-skill/SKILL.md",
        },
        enabled=True,
    )
    db.persona_attach_skill(persona_id, skill_id)

    run_id = db.taskmaster_create_run("file_pipeline", payload={"mode": "analysis"})
    runtime = PersonaSkillRuntime(db)
    results = runtime.run(
        run_id=run_id,
        persona_id=persona_id,
        skill_names=["Legal Finish Agent"],
        mode="analysis",
    )

    assert len(results) == 1
    output = results[0]["output"]
    assert output["resource_source"].endswith("legal-finish-agent-skill/SKILL.md")
    assert output["resource_context"]["available"] is True
    assert output["resource_context"]["type"] == "file"
    assert Path(output["resource_context"]["path"]).exists()
