# Workflow v2 Job Monitoring Runbook (API)

This runbook shows how to watch a `memory_first_v2` workflow job live while processing.

Base route prefix: `/api`  
Workflow routes: `routes/workflow.py`

---

## 0) Prerequisites

Set your API base and auth token:

```bash
export BASE_URL="http://localhost:8000/api"
export AUTH_TOKEN="<bearer-token>"
```

Helper for auth header:

```bash
AUTH_HEADER="Authorization: Bearer ${AUTH_TOKEN}"
```

> Note: workflow endpoints are registered as protected routes, so include bearer auth.

---

## 1) Create a workflow job

Endpoint: `POST /workflow/jobs`

```bash
curl -sS -X POST "${BASE_URL}/workflow/jobs" \
  -H "${AUTH_HEADER}" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "memory_first_v2",
    "idempotency_key": "job-create-001",
    "metadata": {
      "operator": "cli",
      "note": "runbook test"
    }
  }'
```

Expected shape:
- `success: true`
- `job.job_id` (example: `wf_abc123...`)
- `job.status` initially `queued`

Capture job id:

```bash
JOB_ID="wf_xxxxxxxxxxxx"
```

---

## 2) Poll job status live

Endpoint: `GET /workflow/jobs/{job_id}/status`

```bash
curl -sS "${BASE_URL}/workflow/jobs/${JOB_ID}/status" \
  -H "${AUTH_HEADER}"
```

Useful fields to watch:
- `job.status` (`queued|running|completed|failed|...`)
- `job.current_step`
- `job.progress` (0.0 → 1.0)
- `job.draft_state`
- `job.stepper[]` per-step statuses

Quick shell poll loop:

```bash
while true; do
  curl -sS "${BASE_URL}/workflow/jobs/${JOB_ID}/status" -H "${AUTH_HEADER}"; echo
  sleep 2
done
```

Or use the helper watcher (prints only status transitions):

```bash
python tools/workflow_watch.py \
  --base-url "${BASE_URL}" \
  --token "${AUTH_TOKEN}" \
  --job-id "${JOB_ID}" \
  --interval 2
```

---

## 3) Execute proposals step

Endpoint: `POST /workflow/jobs/{job_id}/steps/proposals/execute`

```bash
curl -sS -X POST "${BASE_URL}/workflow/jobs/${JOB_ID}/steps/proposals/execute" \
  -H "${AUTH_HEADER}" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "step-proposals-001",
    "payload": {
      "limit": 50,
      "provider": "xai",
      "model": "grok-2-latest",
      "root_prefix": null
    }
  }'
```

Expected shape:
- `success: true`
- `step: "proposals"`
- `result.summary` like `Generated N proposal(s)`

---

## 4) Pull results

Endpoint: `GET /workflow/jobs/{job_id}/results`

### Proposals results

```bash
curl -sS "${BASE_URL}/workflow/jobs/${JOB_ID}/results?step=proposals&limit=100&offset=0" \
  -H "${AUTH_HEADER}"
```

### Summarize artifacts (if summarize step was executed)

```bash
curl -sS "${BASE_URL}/workflow/jobs/${JOB_ID}/results?step=summarize" \
  -H "${AUTH_HEADER}"
```

---

## Optional: proposals mutation endpoints during review

Bulk approve/reject:
- `POST /workflow/jobs/{job_id}/proposals/bulk`

Patch one proposal ontology fields:
- `PATCH /workflow/jobs/{job_id}/proposals/{proposal_id}/ontology`

---

## Operational notes

- Step names are additive contract values from `app/contracts/workflow.py`:
  - `sources`, `index_extract`, `summarize`, `proposals`, `review`, `apply`, `analytics`
- Idempotency is supported for:
  - `POST /workflow/jobs`
  - `POST /workflow/jobs/{job_id}/steps/{step_name}/execute`
  via `idempotency_key` (body or header).
- `GET /workflow/jobs/{job_id}/status` returns a synthetic failed job if not found.
- Results endpoint supports query params:
  - `step` (default `analytics`)
  - `limit` (`1..500`)
  - `offset` (`>=0`)
