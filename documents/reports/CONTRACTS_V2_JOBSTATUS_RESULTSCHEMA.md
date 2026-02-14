# CONTRACTS V2 — JobStatus + ResultSchema
**Date:** 2026-02-14
**Status:** Draft kickoff contract for additive API

## 1) Goals
Define stable v2 contracts for workflow execution and resume-safe polling.

## 2) JobStatus Contract
```json
{
  "success": true,
  "job": {
    "job_id": "wf_20260214_001",
    "workflow": "memory_first_v2",
    "status": "running",
    "current_step": "index_extract",
    "progress": 0.42,
    "draft_state": "dirty",
    "started_at": "2026-02-14T15:30:00Z",
    "updated_at": "2026-02-14T15:35:00Z",
    "completed_at": null,
    "idempotency_key": "6d3f...",
    "webhook": {
      "enabled": true,
      "url": "https://example/callback",
      "last_delivery_status": "ok",
      "last_delivery_at": "2026-02-14T15:34:00Z"
    },
    "stepper": [
      {"name": "sources", "status": "complete", "updated_at": "..."},
      {"name": "index_extract", "status": "running", "updated_at": "..."}
    ],
    "pagination": {
      "events": {"count": 200, "has_more": true, "next_cursor": "evt_123"},
      "results": {"count": 100, "has_more": false, "next_cursor": null}
    },
    "undo": {
      "depth": 5,
      "last_undo_token": "undo_abc"
    },
    "metadata": {
      "source_count": 3,
      "proposal_count": 128
    }
  }
}
```

### Status enums
- `queued | running | waiting_input | completed | failed | cancelled`

### Step enums
- `sources | index_extract | summarize | proposals | review | apply | analytics`

### Draft state enums
- `clean | dirty | saving | failed`

## 3) ResultSchema Contract
```json
{
  "success": true,
  "job_id": "wf_20260214_001",
  "step": "proposals",
  "result": {
    "summary": "Generated 128 proposals",
    "items": [
      {
        "id": "p_001",
        "type": "proposal",
        "status": "proposed",
        "payload": {"from": "...", "to": "..."},
        "version": 3,
        "undo_token": "undo_p_001"
      }
    ],
    "bulk": {
      "supported": true,
      "last_operation": "approve_selected"
    },
    "ontology_edits": {
      "supported": true,
      "granular": true,
      "pending_changes": 4
    },
    "pagination": {
      "count": 100,
      "has_more": true,
      "next_cursor": "res_200"
    }
  },
  "errors": []
}
```

## 4) API Additions (Additive, Non-Breaking)
- `POST /api/workflow/jobs` — create workflow job.
- `GET /api/workflow/jobs/{job_id}/status` — poll status.
- `POST /api/workflow/jobs/{job_id}/steps/{step_name}/execute` — execute/advance step.
- `GET /api/workflow/jobs/{job_id}/results` — paginated step/job results.

## 5) Idempotency Requirements
Mutation endpoints include:
- header: `Idempotency-Key` or body field `idempotency_key`
- duplicate request replay behavior guaranteed for bounded retention window.

## 6) Pagination Requirements
For list endpoints:
- request: `limit`, `offset`, optional `cursor`
- response: `count`, `has_more`, `next_cursor`

## 7) Webhook Callback Event Shape
```json
{
  "event_id": "wf_20260214_001:step.completed:ab12cd34",
  "event_type": "step.completed",
  "job_id": "wf_20260214_001",
  "workflow": "memory_first_v2",
  "status": "running",
  "current_step": "index_extract",
  "payload": {"step": "index_extract", "summary": "...", "count": 1},
  "emitted_at": "2026-02-14T15:40:00Z"
}
```

Headers:
- `X-Workflow-Event: job_callback`
- `X-Workflow-Timestamp: <unix-seconds>`
- `X-Workflow-Signature-Version: v1`
- `X-Workflow-Signature: sha256=<digest>` when secret configured

Retry behavior:
- Retries on network errors, `429`, and `5xx`
- No retries on other `4xx`
- Final failures are persisted to webhook DLQ JSONL

