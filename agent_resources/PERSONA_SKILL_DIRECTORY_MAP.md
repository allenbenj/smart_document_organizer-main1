# PERSONA_SKILL_DIRECTORY_MAP.md

Purpose
- Define the full persona profile set and skill catalog mapped to `agent_resources/` as seed material for runtime DB tables (`manager_personas`, `manager_skills`, `manager_persona_skills`).

## Directories

- Personas source:
  - `agent_resources/chatAgents/AIAgentExpert.agent.md`
  - `agent_resources/chatAgents/DataAnalysisExpert.agent.md`
- Skill source:
  - `agent_resources/skills/agent-workflow-builder_ai_toolkit/SKILL.md`
  - `agent_resources/skills/legal-finish-agent-skill/SKILL.md`
- Provider templates:
  - `agent_resources/provider/*`
- Evaluation guidance:
  - `agent_resources/eval/*`

## Persona Profiles (canonical names)

1. AIAgentExpert
- Role: Agent Lifecycle Architect
- Modes: analysis, strategy, diagnostics
- Content types: agent_spec, workflow, system_report
- Source: `agent_resources/chatAgents/AIAgentExpert.agent.md`

2. DataAnalysisExpert
- Role: Data Inspection Specialist
- Modes: analysis, verify, summary
- Content types: csv, jsonl, table, metrics
- Source: `agent_resources/chatAgents/DataAnalysisExpert.agent.md`

3. Diagnostician
- Role: System Auditor
- Modes: diagnostics, recovery
- Content types: system_report, meta

4. Recovery Coordinator
- Role: Fix Planner
- Modes: recovery, watch_refresh
- Content types: system_report

5. Legal Reasoning Specialist
- Role: Framework Applier
- Modes: analysis
- Content types: legal_doc, brief, motion

6. Critical Thinker
- Role: Bias & Fallacy Detector
- Modes: analysis, verify
- Content types: legal_doc, argument

7. Strategic Analyst
- Role: Issue Tree Builder
- Modes: strategy, analysis
- Content types: legal_doc, project

8. Questioner
- Role: Clarification Generator
- Modes: index, refresh, watch_refresh
- Content types: any

9. Summarizer
- Role: Reporting
- Modes: report, summary
- Content types: any

## Skill Catalog

- Framework Detector & Mapper (internal)
- Argument Structure Parser (internal)
- Fallacy & Bias Scanner (internal)
- Issue Tree & MECE Builder (internal)
- Salvageability & Fix Planner (internal)
- Self-Referential Analyzer (internal)
- Strategic Simulation (internal)
- Perspective Switcher (internal)
- Summarization Formatter (internal)
- Agent Workflow Builder (source: `agent_resources/skills/agent-workflow-builder_ai_toolkit/SKILL.md`)
- Legal Finish Agent (source: `agent_resources/skills/legal-finish-agent-skill/SKILL.md`)
- Provider Template Selector (source: `agent_resources/provider/*`)
- Evaluation Harness Planner (source: `agent_resources/eval/*`)

## Persona -> Skill Mapping

- AIAgentExpert
  - Agent Workflow Builder
  - Provider Template Selector
  - Evaluation Harness Planner
  - Self-Referential Analyzer

- DataAnalysisExpert
  - Evaluation Harness Planner
  - Fallacy & Bias Scanner
  - Summarization Formatter

- Diagnostician
  - Self-Referential Analyzer
  - Salvageability & Fix Planner
  - Fallacy & Bias Scanner

- Recovery Coordinator
  - Salvageability & Fix Planner
  - Issue Tree & MECE Builder
  - Strategic Simulation

- Legal Reasoning Specialist
  - Framework Detector & Mapper
  - Argument Structure Parser
  - Perspective Switcher
  - Legal Finish Agent

- Critical Thinker
  - Fallacy & Bias Scanner
  - Argument Structure Parser
  - Perspective Switcher

- Strategic Analyst
  - Issue Tree & MECE Builder
  - Strategic Simulation
  - Framework Detector & Mapper

- Questioner
  - Framework Detector & Mapper
  - Self-Referential Analyzer

- Summarizer
  - Framework Detector & Mapper
  - Perspective Switcher
  - Summarization Formatter

## Runtime Notes

- Seed endpoint: `POST /api/personas/seed-defaults`
- DB targets:
  - `manager_personas`
  - `manager_skills`
  - `manager_persona_skills`
- Skill execution output:
  - `manager_skill_results`
