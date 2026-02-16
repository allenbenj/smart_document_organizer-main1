#!/usr/bin/env python3
"""Poll workflow job status and print status transitions.

Usage:
  python tools/workflow_watch.py --base-url http://localhost:8000/api --token "$AUTH_TOKEN" --job-id wf_123
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, Optional


def _utc_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def fetch_status(base_url: str, token: str, job_id: str, timeout: float) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/workflow/jobs/{job_id}/status"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body)


def summarize(job: Dict[str, Any]) -> str:
    stepper = job.get("stepper") or []
    step_counts: Dict[str, int] = {}
    for s in stepper:
        st = str(s.get("status") or "unknown")
        step_counts[st] = step_counts.get(st, 0) + 1

    parts = [
        f"status={job.get('status')}",
        f"current_step={job.get('current_step')}",
        f"progress={job.get('progress')}",
        f"draft_state={job.get('draft_state')}",
        f"steps={step_counts}",
    ]
    return " | ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Watch workflow job status transitions")
    ap.add_argument("--base-url", required=True, help="API base, e.g. http://localhost:8000/api")
    ap.add_argument("--token", required=True, help="Bearer token")
    ap.add_argument("--job-id", required=True, help="Workflow job id (wf_...) ")
    ap.add_argument("--interval", type=float, default=2.0, help="Poll interval seconds (default: 2)")
    ap.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds (default: 10)")
    ap.add_argument("--max-errors", type=int, default=5, help="Stop after this many consecutive errors")
    args = ap.parse_args()

    last_line: Optional[str] = None
    consecutive_errors = 0

    while True:
        try:
            data = fetch_status(args.base_url, args.token, args.job_id, args.timeout)
            job = data.get("job") or {}
            line = summarize(job)

            if line != last_line:
                print(f"[{_utc_now()}Z] {line}", flush=True)
                last_line = line

            consecutive_errors = 0
            if str(job.get("status")) in {"completed", "failed", "cancelled"}:
                print(f"[{_utc_now()}Z] terminal status reached", flush=True)
                return 0

            time.sleep(max(args.interval, 0.2))

        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            return 130
        except urllib.error.HTTPError as e:
            consecutive_errors += 1
            print(f"[{_utc_now()}Z] HTTP error: {e.code} {e.reason}", file=sys.stderr, flush=True)
        except urllib.error.URLError as e:
            consecutive_errors += 1
            print(f"[{_utc_now()}Z] Network error: {e}", file=sys.stderr, flush=True)
        except Exception as e:  # pragma: no cover
            consecutive_errors += 1
            print(f"[{_utc_now()}Z] Unexpected error: {e}", file=sys.stderr, flush=True)

        if consecutive_errors >= max(args.max_errors, 1):
            print(f"[{_utc_now()}Z] too many consecutive errors; stopping", file=sys.stderr, flush=True)
            return 1

        time.sleep(max(args.interval, 0.2))


if __name__ == "__main__":
    raise SystemExit(main())
