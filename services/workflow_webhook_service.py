from __future__ import annotations

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
from typing import Any, Dict


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
        body = json.dumps(payload, default=str).encode("utf-8")
        retries = self.max_retries if self.enable_retries else 0
        total_attempts = max(1, retries + 1)

        for attempt in range(1, total_attempts + 1):
            self._record_retry(event_id, url=url, attempt=attempt)
            status, err = self._send_once(url, body)
            if status is not None and 200 <= status < 300:
                self._record_retry(event_id, url=url, attempt=attempt, last_status=status, done=True)
                return {"ok": True, "status": status, "attempt": attempt}

            self._record_retry(event_id, url=url, attempt=attempt, last_status=status, last_error=err)
            if attempt < total_attempts and self.retry_backoff_seconds > 0:
                time.sleep(self.retry_backoff_seconds * attempt)

        dlq_entry = {
            "event_id": event_id,
            "url": url,
            "failed_at": datetime.utcnow().isoformat(),
            "payload": payload,
            "attempts": total_attempts,
            "last_state": self._retry_state.get(event_id, {}),
        }
        self._append_dlq(dlq_entry)
        return {"ok": False, "status": None, "attempt": total_attempts}

    def _send_once(self, url: str, body: bytes) -> tuple[int | None, str | None]:
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("X-Workflow-Event", "job_callback")
        request.add_header("X-Workflow-Timestamp", str(int(time.time())))

        if self.secret:
            signature = hmac.new(self.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            request.add_header("X-Workflow-Signature", f"sha256={signature}")

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
