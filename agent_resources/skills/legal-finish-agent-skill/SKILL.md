---
name: legal-mastermind-agent
description: Build, extend, and harden legal AI workflows for document analysis, legal research, gap detection, cross-referencing, nuance/risk capture, and filing readiness. Use when the user asks to create, scaffold, improve, debug, evaluate, or deploy a legal multi-agent workflow.
---

# Legal Mastermind Agent

Execute this workflow to design or improve legal AI systems in this repository.

## Guardrails

- Treat outputs as AI-assisted drafts requiring attorney review.
- Do not present legal advice as final authority.
- Preserve confidentiality and minimize external data movement.
- Prefer auditable, structured outputs over narrative-only outputs.

## Required Inputs

Collect before implementation:

- Jurisdiction(s)
- Practice area (litigation/contracts/regulatory/etc.)
- Document types and volume
- Primary goal (drafting, gap analysis, due diligence, compliance, filing prep)
- Success criteria (accuracy targets, turnaround, risk tolerance)

If any are missing, ask concise clarifying questions.

## Runtime-Aligned Tooling

Use tools and components that exist in this stack:

- Document processing + extraction agents
- Legal reasoning, IRAC, Toulmin analyzers
- Precedent and citation analysis
- Compliance/risk outputs
- TaskMaster/pipeline for batch orchestration
- `web_search` + `web_fetch` for external legal source retrieval
- JSON schema/runtime validation for API response contracts

## Build Pattern

1. **Ingest**: Parse documents and normalize text/metadata.
2. **Reason**: Run legal reasoning + IRAC.
3. **Argument QA**: Run Toulmin completeness/strength checks.
4. **Authority QA**: Run precedent/citation validation.
5. **Risk pass**: Surface ambiguity, counterarguments, compliance issues.
6. **Report**: Return structured, schema-valid outputs with confidence and errors.

## Enhancement Pattern (Existing Systems)

When improving an existing workflow:

1. Trace current inputs/outputs and failure points.
2. Add missing stage-level metrics (success/failure/latency/fallback).
3. Enforce schema-valid API responses.
4. Add graceful degradation (structured recoverable failures).
5. Re-run sample corpus and compare deltas.

## Minimal Delivery Checklist

- [ ] Inputs/assumptions documented
- [ ] Multi-stage workflow implemented or patched
- [ ] Structured output contract enforced
- [ ] Confidence/uncertainty/counterarguments included
- [ ] Citation and precedent support surfaced
- [ ] Batch run report generated
- [ ] Human-review disclaimer included

## Output Contract Expectations

For major endpoints, ensure envelope fields:

- `success`
- `data`
- `error`
- `processing_time`
- `agent_type`
- `metadata`
- `schema_version` (v2 when available)

For legal reasoning payloads, prefer inclusion of:

- legal principles
- factual scenarios
- law-to-fact mapping
- conclusion with confidence
- uncertainties + counterarguments
- Toulmin analysis
- ADA/DA perspective review when relevant

## Handoff

At completion, provide:

1. What changed (files and rationale)
2. Validation evidence (tests/logs/sample responses)
3. Remaining risks and next recommended action
