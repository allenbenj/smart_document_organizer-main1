# Workflow Webhooks (v2)

This documents the hardened webhook behavior used by `/api/workflow/jobs` callbacks.

## Delivery behavior

- Method: `POST`
- Content type: `application/json`
- Event headers:
  - `X-Workflow-Event: job_callback`
  - `X-Workflow-Timestamp: <unix-seconds>`
  - `X-Workflow-Signature-Version: v1`
  - `X-Workflow-Signature: sha256=<hex>` (only when `WORKFLOW_WEBHOOK_SECRET` is set)

## Signing behavior (v1)

When `WORKFLOW_WEBHOOK_SECRET` is configured, signature input is:

`<timestamp> + "." + <raw request body bytes>`

HMAC algorithm: `SHA-256`

Consumers should verify:
1. Timestamp freshness.
2. Signature exact match using the same secret and canonical payload bytes.

## Retry semantics

Retries are attempted only for retryable failures:
- network/transport errors
- HTTP `429`
- HTTP `5xx`

No retries for non-retryable client errors (`4xx` except `429`).

Backoff is linear: `retry_backoff_seconds * attempt_index`.

Config:
- `WORKFLOW_WEBHOOK_ENABLE_RETRIES` (default: true)
- `WORKFLOW_WEBHOOK_MAX_RETRIES` (default: 2)
- `WORKFLOW_WEBHOOK_RETRY_BACKOFF_SECONDS` (default: 0.5)
- `WORKFLOW_WEBHOOK_TIMEOUT_SECONDS` (default: 5.0)

## DLQ behavior

Failed deliveries are appended as JSON lines to:
- `WORKFLOW_WEBHOOK_DLQ_PATH` (default: `logs/workflow_webhook_dlq.jsonl`)

Each entry includes:
- event metadata (`event_id`, `url`, `attempts`, `attempts_detail`)
- original payload
- replay envelope (`replay.method`, `replay.url`, `replay.headers`, `replay.body_base64`)

Replay utilities:
- `services.workflow_webhook_dlq.read_webhook_dlq(...)`
- `services.workflow_webhook_dlq.as_replay_requests(...)`

## Job status persistence

For each callback, the job record persists delivery outcome metadata under:

`job.metadata.webhook`

including a rolling delivery history (`deliveries`, capped) and `last_delivery` summary.
