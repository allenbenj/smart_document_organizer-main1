from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _to_alt_paths(root: str) -> list[str]:
    raw = root.strip().replace("\\", "/")
    out = [raw]

    m_win = re.match(r"^([A-Za-z]):/(.*)$", raw)
    if m_win:
        drive = m_win.group(1).lower()
        rest = m_win.group(2).lstrip("/")
        out.append(f"/mnt/{drive}/{rest}")

    m_wsl = re.match(r"^/mnt/([A-Za-z])/(.*)$", raw)
    if m_wsl:
        drive = m_wsl.group(1).upper()
        rest = m_wsl.group(2).lstrip("/")
        out.append(f"{drive}:/{rest}")

    seen: set[str] = set()
    unique: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def _http_json(method: str, url: str, body: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    data = None
    headers: dict[str, str] = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        if not raw.strip():
            return {}
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
        return {"_raw": obj}


def _safe_call(label: str, fn):
    try:
        out = fn()
        return {"ok": True, "label": label, "data": out}
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "label": label, "error": f"http {e.code}", "detail": text[:800]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "label": label, "error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose organization scope pipeline end-to-end.")
    parser.add_argument("--root", required=True, help="Scope root path (Windows or /mnt style).")
    parser.add_argument("--base", default="http://127.0.0.1:8000/api", help="API base URL.")
    parser.add_argument("--limit", type=int, default=500, help="Generate limit.")
    parser.add_argument("--skip-index", action="store_true", help="Skip index/refresh steps.")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    root = args.root.strip().replace("\\", "/")
    roots = _to_alt_paths(root)

    print("=== Organization Scope Diagnostics ===")
    print(f"base={base}")
    print(f"root={root}")
    print(f"root_variants={roots}")
    print("")

    calls: list[dict[str, Any]] = []
    calls.append(_safe_call("health", lambda: _http_json("GET", f"{base}/health", None, 10.0)))

    for variant in roots:
        q = urllib.parse.quote_plus(variant)
        calls.append(
            _safe_call(
                f"files_query[{variant}]",
                lambda v=q: _http_json("GET", f"{base}/files?limit=1&offset=0&q={v}", None, 20.0),
            )
        )

    if not args.skip_index:
        existing_roots = [p for p in roots if os.path.isdir(p)]
        payload_roots = existing_roots or [root]
        calls.append(
            _safe_call(
                "files_index",
                lambda: _http_json(
                    "POST",
                    f"{base}/files/index?use_taskmaster=false",
                    {"roots": payload_roots, "recursive": True, "max_files": 20000},
                    300.0,
                ),
            )
        )
        calls.append(
            _safe_call(
                "files_refresh",
                lambda: _http_json(
                    "POST",
                    f"{base}/files/refresh?run_watches=false&stale_after_hours=1&use_taskmaster=false",
                    {},
                    180.0,
                ),
            )
        )

    calls.append(
        _safe_call(
            "org_generate",
            lambda: _http_json(
                "POST",
                f"{base}/organization/proposals/generate",
                {"limit": int(args.limit), "root_prefix": root},
                240.0,
            ),
        )
    )

    status_counts: dict[str, int] = {}
    for status in ["all", "proposed", "approved", "rejected", "applied"]:
        if status == "all":
            url = f"{base}/organization/proposals?limit=10000&offset=0&root_prefix={urllib.parse.quote_plus(root)}"
        else:
            url = (
                f"{base}/organization/proposals?status={status}&limit=10000&offset=0"
                f"&root_prefix={urllib.parse.quote_plus(root)}"
            )
        result = _safe_call(f"org_list[{status}]", lambda u=url: _http_json("GET", u, None, 60.0))
        calls.append(result)
        if result.get("ok") and isinstance(result.get("data"), dict):
            items = result["data"].get("items", [])
            status_counts[status] = len(items) if isinstance(items, list) else 0

    for c in calls:
        if c.get("ok"):
            d = c.get("data")
            if isinstance(d, dict):
                keys = ["success", "indexed", "errors", "created", "total"]
                preview = {k: d.get(k) for k in keys if k in d}
                if c["label"].startswith("org_generate"):
                    for k in [
                        "fallback_mode",
                        "seeded_indexed_count",
                        "scoped_indexed_count",
                        "scoped_ready_count",
                    ]:
                        if k in d:
                            preview[k] = d.get(k)
                print(f"[OK] {c['label']}: {preview}")
            else:
                print(f"[OK] {c['label']}")
        else:
            print(f"[ERR] {c['label']}: {c.get('error')}")

    print("")
    print(f"status_counts={status_counts}")

    generate = next((c for c in calls if c.get("label") == "org_generate"), None)
    if generate and generate.get("ok") and isinstance(generate.get("data"), dict):
        gd = generate["data"]
        created = int(gd.get("created", 0))
        scoped_indexed = int(gd.get("scoped_indexed_count", 0))
        scoped_ready = int(gd.get("scoped_ready_count", 0))
        seeded = int(gd.get("seeded_indexed_count", 0))
        fallback = bool(gd.get("fallback_mode"))
        all_count = int(status_counts.get("all", 0))
        proposed_count = int(status_counts.get("proposed", 0))

        print("=== Diagnosis ===")
        if created > 0 or proposed_count > 0 or all_count > 0:
            print("Pipeline produced proposals. UI empty-state is likely frontend state/filter related.")
        elif scoped_indexed == 0 and seeded == 0:
            print(
                "Scoped root is not visible to backend index/generation in current runtime. "
                "Likely root path/runtime mismatch or inaccessible folder."
            )
        elif scoped_indexed > 0 and scoped_ready == 0 and not fallback:
            print(
                "Scoped files are indexed but none are ready, and fallback did not trigger. "
                "Backend build likely stale; restart required."
            )
        elif scoped_indexed > 0 and created == 0:
            print(
                "Scoped files found but generation returned zero. "
                "Likely provider/output validation or insert constraint issue."
            )
        else:
            print("Unknown gate failure. Check org_generate payload and list responses above.")
    else:
        print("=== Diagnosis ===")
        print("Generation call failed before proposal creation. Fix transport/startup first.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
