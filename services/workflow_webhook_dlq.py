from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, List


def read_webhook_dlq(path: str | Path, *, limit: int = 100) -> List[Dict[str, Any]]:
    dlq_path = Path(path)
    if not dlq_path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with dlq_path.open("r", encoding="utf-8") as f:
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


def as_replay_requests(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Produce replay-ready request envelopes from DLQ entries.

    Output shape (stable):
    {
      "event_id": str,
      "method": "POST",
      "url": str,
      "headers": {...},
      "body": str,  # decoded utf-8 JSON payload
      "body_base64": str,
    }
    """

    out: List[Dict[str, Any]] = []
    for entry in entries:
        replay = dict(entry.get("replay") or {})
        body_b64 = str(replay.get("body_base64") or "")
        try:
            body = base64.b64decode(body_b64.encode("ascii")).decode(replay.get("encoding") or "utf-8")
        except Exception:
            body = ""

        out.append(
            {
                "event_id": entry.get("event_id"),
                "method": replay.get("method") or "POST",
                "url": replay.get("url") or entry.get("url"),
                "headers": replay.get("headers") or {"Content-Type": "application/json"},
                "body": body,
                "body_base64": body_b64,
            }
        )
    return out
