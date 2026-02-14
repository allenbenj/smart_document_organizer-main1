# Agent Result Schemas (v1 + v2)

- Legacy spec (human-readable): this file (v1)
- New machine-readable JSON Schema (v2): `agent_result_schema_v2.json`

v2 adds reasoning framework integration fields from `AGENT_THINKING_FRAMEWORK_INTEGRATION.md` including:
- `reasoning_framework`, `legal_principles`, `factual_scenarios`, `application_map`
- `uncertainties`, `counterarguments`
- `toulmin` scoring (`completeness`, `strength`)
- `ada_da_review`

This document defines stable, versioned result shapes returned by agent endpoints. All responses share a common envelope and include explainability fields where relevant.

## Common Envelope
- success: boolean
- data: object (agent-specific payload)
- error: string | null
- processing_time: number (seconds)
- agent_type: string
- metadata: object (diagnostics; may include cache_hit, timeout, prompt, analysis_id)

## Entities (POST /api/agents/entities)
- data.entities: list of objects
  - text: string
  - type: string
  - start: number
  - end: number
  - confidence: number (0–1)
  - context: string
- data.total_entities: number

## Legal Analysis (POST /api/agents/legal)
- data.issue: string
- data.confidence: number
- data.legal_issues: list of { issue_id, description, confidence }
- data.legal_arguments: list of { argument_id, claim, confidence }
- data.compliance_checks: list of { check_id, regulation, status, confidence }
- data.matched_signals: list of { signal, label, confidence }
- data.reasoning_trace: list of { step, evidence, score }
- data.knowledge_graph.triples: list of [head, relation, tail]
- data.analysis_type: string
- data.analysis_id: string

## IRAC (POST /api/agents/irac)
- data.analysis.issue: { content, confidence }
- data.analysis.rule: { content, confidence }
- data.analysis.application: { content, confidence }
- data.analysis.conclusion: { content, confidence }
- Optional convenience: data.issue, data.confidence

## Toulmin (POST /api/agents/toulmin)
- data.claim: string
- data.data: string
- data.warrant: string
- data.backing: string
- data.qualifier: string
- data.rebuttal: string
- Optional: data.confidence

## Semantic (POST /api/agents/semantic)
- data.summary: string
- data.topics: string[]
- data.key_phrases: string[]

## Embed (POST /api/agents/embed)
- data.embeddings: number[][] (normalized vectors)
- metadata.dim: number (when known)

## Classify (POST /api/agents/classify)
- data.labels: list of { label, confidence }
- data.primary: { label, confidence } (optional)
- data.used_ml_model: boolean

## Orchestrate (POST /api/agents/orchestrate)
- data.entities: Entities payload
- data.semantic: Semantic payload
- data.violations: { violations: list }

Notes
- Version: v1. Any breaking changes will increment to v2 in a new document.
- Clients should defensively check for optional fields and fall back gracefully.
