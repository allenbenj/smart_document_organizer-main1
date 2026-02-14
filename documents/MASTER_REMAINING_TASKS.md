# Master Remaining Tasks (Consolidated)

_Last consolidated: 2026-02-12_

This file combines unfinished work previously spread across:
- `remediation_tasks.md`
- `AGENT_MIGRATION_PLAN.md`
- `combined_project_plan.md`
- `ORGANIZATION_PLAN.md`
- `agent_development_plan.md`
- `plans/RECOVERY_PLAN.md`

## A) Runtime Validation + Stability Completion

- [ ] Add endpoint-level counters/observability for schema validation failures.
- [ ] Decide strictness policy by environment (`AGENT_SCHEMA_ENFORCE` in dev/stage/prod).
- [ ] Add a small schema health endpoint (optional) to expose validator status.
- [ ] Ensure all remaining agent routes are normalized to the v2 envelope consistently.

## B) Agent Contract & Migration Cleanup

- [ ] Finalize v2 contract rollout notes for clients still consuming v1 payload assumptions.
- [ ] Add contract tests for `legal`, `irac`, `toulmin`, `entities`, `document_processor` responses.
- [ ] Add GUI-side compatibility checks for new/normalized fields (`schema_version`, `warnings`, `fallback_used`).

## C) End-to-End Verification (Definition of Done)

- [ ] Backend starts cleanly (`python Start.py` or uvicorn path used by team).
- [ ] Health endpoint green (`GET /api/health`).
- [ ] GUI launches and runs document flows without thread/shutdown crashes.
- [ ] Full-folder run passes with current target corpus.
- [ ] Test suite baseline passes (or documented expected failures with reasons).
- [ ] No unresolved import/runtime warnings in standard startup and task execution paths.

## D) Memory System Finalization

- [ ] Validate Memory Review endpoints end-to-end against the persistent manager path.
- [ ] Add tests for memory store/search/retrieve via routes and agent mixins.
- [ ] Confirm expected behavior when optional vector backend is unavailable.

## E) Analyzer Quality Improvements

- [ ] Improve Toulmin completion rate across full-folder dataset.
- [ ] Reduce remaining enhancement-path 400 errors (xAI enhancement paths).
- [ ] Add benchmark snapshots for entities/legal/IRAC/Toulmin/precedents quality deltas.

## F) Packaging & Documentation Hygiene

- [ ] Keep one source-of-truth checklist here; archive superseded planning docs.
- [ ] Maintain one architecture summary + one runbook for operators.
- [ ] Keep skill files linted (valid frontmatter, runtime-aligned tool references, concise scope).

## G) Organization Engine Port (NEW)

- [ ] Add DB tables: `organization_proposals`, `organization_feedback`, `organization_actions`.
- [ ] Add provider abstraction for organization LLM calls (default xAI, optional DeepSeek).
- [ ] Implement TaskMaster mode: `organize_indexed` (proposal generation only).
- [ ] Add organization feedback endpoints (accept/edit/reject) and learning persistence.
- [ ] Implement `organize_apply` + rollback action groups.
- [ ] Add GUI review/apply panel for organization proposals.

## H) Optional Nice-to-Haves

- [ ] Add CI check for SKILL frontmatter + markdown fence validity.
- [ ] Add CI check for schema file presence/validity and route-level response schema tests.

---

## Notes

- Completed historical items remain in archived planning docs for traceability.
- Use this file as the active execution checklist going forward.
