# TaskMaster Organization Runbook (Deterministic)

Purpose: keep organization workflow predictable and safe.

## Hard Rules

- Never create helper scripts/files.
- Never write debug/output files for logs, summaries, or checkpoints.
- Never move/rename/delete files unless explicitly approved by user.
- Never apply proposals automatically.
- Work one target root at a time unless user explicitly asks for multi-root.
- Prefer GUI actions when available; API fallback only when GUI lacks control.
- Do not improvise alternate workflows when output appears empty; switch to compact JSON console output only.
- Do not silently broaden scope (no corpus-wide proposal edits when user asked for one folder).
- When uncertain about endpoint shape, discover/read route docs first, then proceed.
- Print action/command intent before execution.

## Workflow State Machine

1. **Scope**
2. **Preflight**
3. **Index**
4. **Propose**
5. **Review**
6. **User Decision**
7. **Apply (optional, user-approved)**

Do not skip states.

---

## 1) Scope

Collect and confirm exactly one target root (example):

`E:\01_General_Files\Lukas\Final Products`

Normalize to runtime path when needed:

`/mnt/e/01_General_Files/Lukas/Final Products`

## 2) Preflight

Check:
- API healthy.
- Startup report available.
- Organization routes available.

If organization routes return 503/service container unavailable:
- Stop and report startup/DI issue.
- Do not attempt workaround scripts.

## 3) Index

Run index for target root only.

Interpretation guidance:
- `indexed > 0` => new/updated files indexed.
- `indexed = 0` with `scanned = 0` can still be valid when files are already indexed and unchanged.

If uncertain, verify indexed entries contain target-root paths before proceeding.

## 4) Propose

Generate proposals after confirming target-root files are indexed.

Then immediately filter to target root only:
- Keep proposals where `current_path` starts with target runtime root.
- Ignore unrelated proposals from older runs.

## 5) Review

Summarize for user:
- total proposals generated
- proposals in target root
- 10 sample rows: id, current_path, proposed_folder, proposed_filename, confidence

## 6) User Decision (Required)

Ask this exact question before any mutation of proposal set or file moves:

**"I found proposals for this folder. Do you want me to clean up proposals first (e.g., clear/reject low-quality or stale ones) before applying anything?"**

Provide options:
- **A)** Keep as-is and review manually
- **B)** Cleanup proposals first (recommended)
- **C)** Regenerate with stricter filters (higher confidence / scoped taxonomy)
- **D)** Stop here

If user chooses **B** or **C**, run a **dry-run summary first** and ask confirmation before mutating proposals.

## 7) Apply (Optional, Explicit Approval)

Only proceed if user clearly approves.

Always do dry-run first and report:
- affected file count
- source->destination samples
- failures/conflicts

Then ask final confirmation before real apply.

---

## Universal Confirmation Gates (applies across situations)

Before any **state mutation** (proposal reject/edit/clear, schedule changes, apply/move, restart/control actions), require:

1. **Intent summary** (what will change).
2. **Impact summary** (counts + representative samples/IDs).
3. **Explicit user confirmation** (`yes`, selected option, or equivalent clear approval).

If user approval is ambiguous, stop and ask a clarifying question.

---

## Cleanup Policy (when user chooses B)

Cleanup may include:
- Reject stale proposals not in target root.
- Reject low-confidence fallback proposals (example: `Inbox/Review` + low confidence).
- Keep high-confidence, root-matching proposals.

Never delete files during proposal cleanup.

### Mandatory Dry-Run Output Format (before any reject/edit/apply)

Print one JSON object to console with keys:
- `total_proposals`
- `in_target`
- `reject_not_in_target`
- `reject_low_conf_inbox`
- `keep_count`
- `sample_reject_ids` (up to 10)
- `sample_keep_ids` (up to 10)

Do not mutate proposals until user confirms after seeing this summary.

## Failure Handling

If any step fails:
- Stop at that step.
- Report exact step + error.
- Offer one next action only (retry, diagnose, or stop).

If console output looks empty or malformed:
- Do not create files.
- Print compact JSON diagnostics only:
  - `status_code`
  - `content_type`
  - `content_length`
  - `text_len`
  - `text_preview` (first 300 chars)
  - `bytes_preview` (repr of first 80 bytes)

## Forbidden Workarounds

- No ad-hoc file scripts.
- No local output files for logging/debug.
- No silent proposal apply.
- No unscoped corpus-wide proposal actions when user asked for one folder.
