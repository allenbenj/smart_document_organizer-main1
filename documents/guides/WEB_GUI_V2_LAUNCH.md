# Web GUI v2 Launch (Phase C)

## Legacy Note
The existing PySide GUI remains available as **legacy fallback** during migration.
Do not remove it in this phase.

## Backend (FastAPI)
From repo root:

```bash
python3 Start.py
```

## Frontend (React + Vite)
From repo root:

```bash
cd frontend
npm install
npm run dev
```

Vite default: `http://127.0.0.1:5173`

## Optional build check
```bash
cd frontend
npm run build
```

## v2 API routes currently implemented (additive)
Core workflow:
- `POST /api/workflow/jobs`
- `GET /api/workflow/jobs/{job_id}/status`
- `POST /api/workflow/jobs/{job_id}/steps/{step_name}/execute`
- `GET /api/workflow/jobs/{job_id}/results?step=<step>&limit=<n>&offset=<n>`

Proposal review mutations used by web UI:
- `POST /api/workflow/jobs/{job_id}/proposals/bulk` (approve/reject)
- `PATCH /api/workflow/jobs/{job_id}/proposals/{proposal_id}/ontology` (inline proposal field patch + auto-approve)

These are additive v2 routes and do not replace existing taskmaster/organization routes.

## Webhook behavior reference
Webhook delivery hardening details are documented in:
- `documents/guides/WORKFLOW_WEBHOOKS.md`

Implementation notes reflected there:
- signed callbacks when `WORKFLOW_WEBHOOK_SECRET` is set
- retries for transport errors/`429`/`5xx`
- no retries for other `4xx`
- linear retry backoff
- DLQ JSONL persistence for terminal failures

## Phase C smoke checks
From repo root:

```bash
pytest -q \
  tests/test_workflow_routes_v2.py \
  tests/test_workflow_bulk_ontology_api.py \
  tests/test_workflow_webhooks.py \
  tests/test_org_console_static_and_proxy.py \
  tests/test_pyside_import_safety.py
```

Expected: all pass with PySide remaining a legacy fallback path.
