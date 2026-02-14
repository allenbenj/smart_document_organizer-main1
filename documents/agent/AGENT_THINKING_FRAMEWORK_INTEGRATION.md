# Agent Thinking Framework Integration Guide

This document translates **Agent Thinking Frameworks.txt** into concrete runtime behavior for Smart Document Organizer agents.

## Purpose

Use the framework as a **reasoning contract** across all analyzers so outputs are:
- structured
- explainable
- auditable
- resilient under partial failure

---

## 1) Canonical Reasoning Stack (Execution Order)

For each document/case, agents should execute this order:

1. **Legal Principles**
   - Identify statutes/regulations/case-law doctrines relevant to the matter.
2. **Factual Scenarios**
   - Extract and normalize material facts.
3. **Application of Law to Facts**
   - Explicitly map each principle to specific facts.
4. **Conclusion**
   - Produce bounded conclusion with confidence + uncertainty notes.
5. **Counterarguments / Ambiguities**
   - Identify alternate interpretations and unresolved conflicts.

This should be treated as required structure in legal reasoning and IRAC outputs.

---

## 2) Toulmin Integration (Argument Quality Layer)

Run Toulmin analysis as a quality gate over legal reasoning output:

Required components:
- **Claim**
- **Data (Evidence)**
- **Warrant**
- **Backing**
- **Qualifier**
- **Rebuttal**

### Scoring recommendation
For each component, score:
- `present` (true/false)
- `quality` (0-1)
- `evidence_refs` (source snippets/citations)

Then compute:
- `toulmin_completeness_score`
- `toulmin_strength_score`

If missing components are detected, produce machine-actionable remediation guidance.

---

## 3) Mapping to Existing Analyzers

## A) `legal_reasoning`
Must output:
- principles identified
- facts extracted
- law-to-fact mapping
- conclusion
- uncertainty/counterargument section

## B) `irac_analyzer`
Map framework directly:
- Issue → factual/legal conflict
- Rule → legal principles
- Application → law-to-fact mapping
- Conclusion → bounded legal outcome

Add required fields:
- `ambiguities`
- `alternative_interpretations`
- `confidence`

## C) `toulmin_analyzer`
Treat as validator + enhancer:
- detect missing argument components
- propose explicit fixes
- emit structured feedback usable by downstream UI/reporting

## D) `precedent_analyzer` + `citation`
Back the **Warrant/Backing** fields with:
- precedent matches
- citation strength
- jurisdiction fit
- recency/authority weighting

## E) `compliance`
Operationalize qualifiers/rebuttals as risk conditions and exceptions.

---

## 4) ADA / DA Perspective Requirement

From the framework note: when an ADA/DA perspective appears relevant, perform a targeted pass.

Implementation policy:
1. Detect prosecution-oriented framing markers (e.g., burden, probable cause, elements of offense, charging logic).
2. Run a dedicated perspective check:
   - Was the perspective method explicitly used in the document?
   - If yes, evaluate and **refute/support with document-grounded facts**.
3. Include explicit section in output:
   - `ada_da_perspective_detected`
   - `ada_da_method_employed`
   - `ada_da_fact_refutation`

If terminology is jurisdiction-specific/ambiguous, mark as uncertain and provide alternatives.

---

## 5) Standard Output Schema Additions

Add these fields to legal-analysis payloads:

- `reasoning_framework`: `"deductive_legal" | "irac" | "toulmin" | "hybrid"`
- `legal_principles`: `[]`
- `factual_scenarios`: `[]`
- `application_map`: `[{principle, facts, rationale}]`
- `conclusion`: `{text, confidence}`
- `uncertainties`: `[]`
- `counterarguments`: `[]`
- `toulmin`: `{claim,data,warrant,backing,qualifier,rebuttal,completeness,strength}`
- `ada_da_review`: `{detected, employed, analysis, refutation}`

---

## 6) Pipeline Integration Points

In TaskMaster/full-folder runs, enforce stage checks:

1. **Extraction Stage**
   - Facts and legal references available
2. **Reasoning Stage**
   - Legal Principles/Facts/Application/Conclusion present
3. **Toulmin Stage**
   - 6 components evaluated, missing elements flagged
4. **Precedent/Citation Stage**
   - Warrant/backing support quality measured
5. **Report Stage**
   - Aggregate framework completeness metrics

Suggested new report metrics:
- `framework_complete_ok`
- `toulmin_complete_ok`
- `law_fact_mapping_ok`
- `uncertainty_declared_ok`
- `ada_da_review_ok`

---

## 7) Memory Integration

Store only high-value framework artifacts:
- normalized legal principles
- key law→fact mappings
- strongest/weakest Toulmin components
- reusable rebuttal patterns

Memory key examples:
- `principle:<domain>:<jurisdiction>:<topic>`
- `mapping:<document_id>:<issue_id>`
- `toulmin_gap:<document_id>:<component>`

---

## 8) Governance Rules

- Never present conclusions without showing law-to-fact trace.
- If legal support is weak, lower confidence and mark explicitly.
- If rebuttals are missing, do not mark argument as robust.
- If ADA/DA check triggered, include explicit factual support/refutation.

---

## 9) Quick Adoption Plan

1. Update legal/IRAC result schemas with framework fields.
2. Add Toulmin completeness scoring to analyzer output.
3. Add ADA/DA perspective pass in legal reasoning stage.
4. Extend TaskMaster report with framework metrics.
5. Add Memory Review panel filters for framework artifacts.

---

This integration makes the framework operational: not just conceptual guidance, but a repeatable reasoning protocol across agents and pipelines.