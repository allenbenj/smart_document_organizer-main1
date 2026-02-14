from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


SIGNATURE_VERSION = "v1"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    try:
        return max(int(os.getenv(name, str(default))), minimum)
    except Exception:
        return default


def _env_float(name: str, default: float, *, minimum: float = 0.0) -> float:
    try:
        return max(float(os.getenv(name, str(default))), minimum)
    except Exception:
        return default


class WorkflowWebhookService:
    """Best-effort workflow callback delivery with signing, retries, and DLQ."""

    _lock = threading.Lock()
    _retry_state: Dict[str, Dict[str, Any]] = {}

    def __init__(self) -> None:
        self.secret = str(os.getenv("WORKFLOW_WEBHOOK_SECRET", "") or "")
        self.timeout_seconds = _env_float("WORKFLOW_WEBHOOK_TIMEOUT_SECONDS", 5.0, minimum=0.5)
        self.max_retries = _env_int("WORKFLOW_WEBHOOK_MAX_RETRIES", 2, minimum=0)
        self.retry_backoff_seconds = _env_float("WORKFLOW_WEBHOOK_RETRY_BACKOFF_SECONDS", 0.5, minimum=0.0)
        self.enable_retries = _env_bool("WORKFLOW_WEBHOOK_ENABLE_RETRIES", True)
        self.dlq_path = Path(os.getenv("WORKFLOW_WEBHOOK_DLQ_PATH", "logs/workflow_webhook_dlq.jsonl"))

    def deliver(self, *, url: str, payload: Dict[str, Any], event_id: str) -> Dict[str, Any]:
        body = json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")
        retries = self.max_retries if self.enable_retries else 0
        total_attempts = max(1, retries + 1)

        final_status: int | None = None
        final_error: str | None = None
        attempt_records: List[Dict[str, Any]] = []

        for attempt in range(1, total_attempts + 1):
            timestamp = str(int(time.time()))
            headers = {
                "Content-Type": "application/json",
                "X-Workflow-Event": "job_callback",
                "X-Workflow-Timestamp": timestamp,
                "X-Workflow-Signature-Version": SIGNATURE_VERSION,
            }
            if self.secret:
                headers["X-Workflow-Signature"] = self._sign(body=body, timestamp=timestamp)

            self._record_retry(event_id, url=url, attempt=attempt)
            status, err = self._send_once(url, body, headers=headers)

            retryable = self._is_retryable(status, err)
            final_status = status
            final_error = err
            attempt_records.append(
                {
                    "attempt": attempt,
                    "status": status,
                    "error": err,
                    "retryable": retryable,
                    "at": datetime.utcnow().isoformat(),
                }
            )

            if status is not None and 200 <= status < 300:
                self._record_retry(event_id, url=url, attempt=attempt, last_status=status, done=True)
                return {
                    "ok": True,
                    "status": status,
                    "attempt": attempt,
                    "event_id": event_id,
                    "signature_version": SIGNATURE_VERSION,
                    "last_error": None,
                    "retryable": False,
                    "attempts_detail": attempt_records,
                }

            self._record_retry(event_id, url=url, attempt=attempt, last_status=status, last_error=err)
            should_retry = attempt < total_attempts and retryable
            if should_retry and self.retry_backoff_seconds > 0:
                time.sleep(self.retry_backoff_seconds * attempt)
            if not should_retry:
                break

        dlq_entry = {
            "event_id": event_id,
            "url": url,
            "failed_at": datetime.utcnow().isoformat(),
            "payload": payload,
            "attempts": len(attempt_records),
            "attempts_detail": attempt_records,
            "last_state": self._retry_state.get(event_id, {}),
            "replay": {
                "method": "POST",
                "url": url,
                "headers": {
                    "Content-Type": "application/json",
                    "X-Workflow-Event": "job_callback",
                    "X-Workflow-Signature-Version": SIGNATURE_VERSION,
                },
                "body_base64": base64.b64encode(body).decode("ascii"),
                "encoding": "utf-8",
            },
        }
        self._append_dlq(dlq_entry)
        return {
            "ok": False,
            "status": final_status,
            "attempt": len(attempt_records),
            "event_id": event_id,
            "signature_version": SIGNATURE_VERSION,
            "last_error": final_error,
            "retryable": self._is_retryable(final_status, final_error),
            "attempts_detail": attempt_records,
            "dlq_path": str(self.dlq_path),
        }

    @staticmethod
    def _is_retryable(status: int | None, err: str | None) -> bool:
        if status is None:
            return True
        if status == 429:
            return True
        if 500 <= status <= 599:
            return True
        return False

    def _sign(self, *, body: bytes, timestamp: str) -> str:
        signed = f"{timestamp}.".encode("utf-8") + body
        digest = hmac.new(self.secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def _send_once(self, url: str, body: bytes, *, headers: Dict[str, str]) -> tuple[int | None, str | None]:
        request = urllib.request.Request(url, data=body, method="POST")
        for k, v in headers.items():
            request.add_header(k, v)

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
                return int(resp.status), None
        except urllib.error.HTTPError as e:
            return int(e.code), str(e)
        except Exception as e:
            return None, str(e)

    @classmethod
    def _record_retry(
        cls,
        event_id: str,
        *,
        url: str,
        attempt: int,
        last_status: int | None = None,
        last_error: str | None = None,
        done: bool = False,
    ) -> None:
        with cls._lock:
            cls._retry_state[event_id] = {
                "event_id": event_id,
                "url": url,
                "attempt": attempt,
                "last_status": last_status,
                "last_error": last_error,
                "done": done,
                "updated_at": datetime.utcnow().isoformat(),
            }

    def _append_dlq(self, payload: Dict[str, Any]) -> None:
        self.dlq_path.parent.mkdir(parents=True, exist_ok=True)
        with self.dlq_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")

    @classmethod
    def get_retry_state(cls, event_id: str) -> Dict[str, Any] | None:
        with cls._lock:
            state = cls._retry_state.get(event_id)
            return dict(state) if state else None

    def read_dlq(self, *, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.dlq_path.exists():
            return []

        rows: List[Dict[str, Any]] = []
        with self.dlq_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue

        if limit <= 0:
            return rows
        return rows[-limit:]
