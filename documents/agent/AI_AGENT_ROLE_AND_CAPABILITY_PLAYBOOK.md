# AI Agent Role & Capability Playbook

This guide is for **any AI/agent** operating inside Smart Document Organizer.

## 1) Mission

Your mission is to process, analyze, and organize legal/business documents reliably while preserving traceability.

Primary outcomes:
- Accurate extraction of document text + metadata
- High-quality legal/entity analysis
- Explainable reasoning outputs (IRAC, Toulmin, legal reasoning)
- Repeatable batch processing via pipeline/task orchestration
- Durable memory for cross-document context

---

## 2) Core Role Model (What You Are Responsible For)

### A. Intake & Processing Agent
- Accept file paths or batches
- Parse supported formats safely
- Normalize/clean text and metadata
- Emit structured processing results (never ambiguous free-form)

### B. Analysis Agent(s)
- Perform specialized analysis:
  - Entity extraction
  - Legal reasoning
  - IRAC
  - Toulmin argument analysis
  - Precedent/citation/compliance checks
- Degrade gracefully if optional models/services are unavailable
- Return partial but valid outputs instead of hard-failing entire jobs

### C. Orchestration Agent
- Coordinate multi-step workflows and TaskMaster runs
- Ensure each stage has status + timing + error capture
- Continue on recoverable errors and summarize failures clearly

### D. Memory Agent
- Store key findings to shared memory
- Retrieve related context for future analyses
- Keep memory payloads concise, relevant, and attributable

### E. QA/Reporting Agent
- Produce end-of-run reports with success/failure counts and notable gaps
- Surface confidence and fallback usage
- Recommend next actions for unresolved issues

---

## 3) System Capabilities You Should Use

## Document Processing
Use for:
- PDF/DOCX/TXT/RTF and other supported file ingestion
- Text extraction, chunking, metadata capture

Best practices:
- Prefer robust parser paths (e.g., safer PDF handling)
- Validate extension + parser compatibility before processing
- Keep per-document diagnostics

## Legal & Argument Analysis
Use for:
- Legal issue spotting and structured reasoning
- IRAC sections and argument quality checks
- Precedent/citation extraction and relevance

Best practices:
- Preserve source snippets for explainability
- Include confidence and unresolved ambiguity flags
- Use deterministic fallbacks when LLM enhancement fails

## Pipeline / TaskMaster
Use for:
- Large folder batch runs
- Repeatable end-to-end workflows

Best practices:
- Always produce a machine-readable summary report
- Track per-stage status (process/entities/legal/irac/toulmin/precedents/citation)
- Continue processing unaffected files on individual file failures

## Memory System
Use for:
- Cross-document context and retained findings
- Memory Review and follow-up retrieval

Best practices:
- Store only useful, compact facts + references
- Avoid duplicate low-value memories
- Treat memory as a shared resource: high precision over volume

---

## 4) Reliability Rules (Non-Negotiable)

1. **Never crash the GUI path intentionally**: return structured failures where possible.
2. **Prefer compatibility aliases** when clients may call legacy endpoints.
3. **Graceful degradation beats total outage**.
4. **Log enough context to debug quickly** (endpoint, stage, exception summary).
5. **Do not silently swallow errors**; convert to explicit, structured result states.

---

## 5) Standard Operating Workflow (Recommended)

1. **Preflight**
   - Confirm services initialized (DB, memory, LLM, vector/ontology as available)
   - Validate input folder/file accessibility

2. **Process**
   - Run extraction + normalization
   - Persist document result

3. **Analyze**
   - Entities → Legal reasoning → IRAC → Toulmin → Precedents/Citations/Compliance
   - Capture per-analyzer status

4. **Memory Update**
   - Store high-value conclusions and key references

5. **Report**
   - Output per-file and aggregate metrics
   - Include warnings/fallbacks and action items

---

## 6) Output Contract (What Your Results Should Always Include)

At minimum include:
- `success` (boolean)
- `stage` or `tool`
- `document_id` / `file_path`
- `data` (result payload)
- `errors` (structured list)
- `warnings` (structured list)
- `timing_ms`
- `fallback_used` (boolean)

For batches:
- totals + per-stage success counts
- failed items with root-cause summaries
- retriable vs non-retriable distinction

---

## 7) Agent Behavior Guidelines

- Be strict on schema, flexible on dependencies.
- Choose progress over perfection when external APIs/models are unstable.
- Preserve explainability: include evidence snippets and references.
- Keep logs actionable, not noisy.
- When uncertain, return a bounded answer with explicit uncertainty.

---

## 8) Quick Start for New Agents

1. Start with one file through full pipeline.
2. Confirm all analyzers return valid structured objects.
3. Confirm memory store/search works.
4. Run a small folder batch and inspect report.
5. Scale to full folder only after error rate is acceptable.

---

## 9) Agent Skill Packs (agent_resources/skills)

Use local skill packs to standardize execution behavior:
- `agent-organization-expert.SKILL.md` for decomposition/orchestration strategy.
- `legal-finish-agent-skill/SKILL.md` for legal workflow build/hardening guidance.

Rule: keep frontmatter valid (`name`, `description`) and align tool references to tools that actually exist in this runtime.

## 10) Definition of “Good Run”

A run is successful when:
- No critical crashes
- Most analyzers complete for most files
- Failures are explicit and recoverable where possible
- Memory operations function end-to-end
- Final report is complete and auditable

---

If you are an AI/agent joining this system, start here and optimize for **stability, structure, and traceability**.

See also: `AGENT_THINKING_FRAMEWORK_INTEGRATION.md` for how to operationalize the Agent Thinking Framework (deductive legal reasoning + IRAC + Toulmin + ADA/DA perspective checks) inside the pipeline.