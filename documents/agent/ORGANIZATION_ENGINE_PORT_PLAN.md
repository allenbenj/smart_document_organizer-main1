# Organization Engine Port Plan (xAI + DeepSeek Option)

## Goal
Port high-value architecture from `E:\Project\File_Organization\Local-File-Organizer-main` into Smart Document Organizer with:
- index-first organization intelligence
- proposal/review/apply/rollback workflow
- user feedback learning loop
- default xAI remote LLM, optional DeepSeek fallback for cost control

---

## Source-to-Target Port Map

## Source: `file_organizer_v2/smart_organizer.py`
### Reuse Pattern
- Fast scan/index first
- Aggregate signals (entities/patterns/folder stats)
- Ask LLM for batched, contextual decisions

### Target in current app
- `services/taskmaster_service.py` -> extend `analyze_indexed` into `organize_indexed`
- `routes/taskmaster.py` -> expose mode in API
- `mem_db/database.py` -> persist organization proposals + action ledger

---

## Source: `file_organizer_v2/adaptive_organizer.py`
### Reuse Pattern
- User corrections become learning signals
- Pattern/rule refinement loop
- Confidence/performance tracking

### Target in current app
- New routes: `routes/organization.py`
  - `POST /api/organization/feedback`
  - `POST /api/organization/proposals/{id}/approve|reject|edit`
- New service: `services/organization_learning_service.py`
- Unified memory integration for durable preferences

---

## Source: `file_organizer_v2/run_legal_workflow.py`
### Reuse Pattern
- Plan -> preview -> apply
- blocked/allowed actions
- rollback IDs

### Target in current app
- New taskmaster modes:
  - `organize_indexed` (proposal generation only)
  - `organize_apply` (apply approved)
  - `organize_rollback` (undo by action group)
- New tables for action and rollback tracking

---

## DB Schema Additions (in `mem_db/data/documents.db`)

### `organization_proposals`
- id
- run_id
- file_id
- current_path
- proposed_folder
- proposed_filename
- confidence
- rationale
- alternatives_json
- provider
- model
- status (`proposed|approved|rejected|applied|edited`)
- created_at / updated_at

### `organization_feedback`
- id
- proposal_id
- file_id
- action (`accept|edit|reject`)
- original_json
- final_json
- note
- created_at

### `organization_actions`
- id
- proposal_id
- file_id
- action_type (`move|rename|mkdir`)
- from_path
- to_path
- success
- error
- rollback_group
- created_at

---

## LLM Provider Strategy

## Default: xAI
- Provider key: `xai`
- Model from existing env (`LLM_MODEL`)

## Optional low-cost alt: DeepSeek
- Provider key: `deepseek`
- Env vars:
  - `DEEPSEEK_API_KEY`
  - `DEEPSEEK_BASE_URL` (default `https://api.deepseek.com/v1`)
  - `ORGANIZER_LLM_PROVIDER` (`xai|deepseek`)
  - `ORGANIZER_LLM_MODEL`

## Routing rule
- If `ORGANIZER_LLM_PROVIDER` set -> use it for organization decisions
- Else fallback to global `LLM_PROVIDER`

---

## Prompt/Output Contract (strict JSON)

LLM response schema:
- `proposed_folder`: string
- `proposed_filename`: string
- `confidence`: number 0..1
- `rationale`: string (short)
- `alternatives`: array<string>
- `blocked`: boolean
- `blocked_reason`: string|null

All results validated before insert/apply.

---

## Implementation Order

1. DB migration for organization tables
2. Organization proposal service + provider abstraction (xAI/DeepSeek)
3. TaskMaster `organize_indexed`
4. Feedback endpoints + learning service
5. Apply/rollback endpoints and taskmaster modes
6. GUI panel for proposal review and apply

---

## Immediate Sprint Deliverable

- Backend-only MVP:
  - run `organize_indexed`
  - persist proposals
  - approve/reject/edit via API
  - apply approved actions with rollback group
- Keep GUI integration as next step once API behavior is stable.
