from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mem_db.database import DatabaseManager  # noqa: E402
from services.taskmaster_service import TaskMasterService  # noqa: E402


MODES = [
    "index",
    "refresh",
    "watch_refresh",
    "analyze_indexed",
    "organize_indexed",
]


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def _ask_int(prompt: str, default: int) -> int:
    raw = _ask(prompt, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def _ask_bool(prompt: str, default: bool = True) -> bool:
    default_label = "y" if default else "n"
    raw = _ask(f"{prompt} (y/n)", default_label).lower()
    if raw in {"y", "yes", "1", "true"}:
        return True
    if raw in {"n", "no", "0", "false"}:
        return False
    return default


def _normalize_exts(raw: str) -> list[str]:
    out: list[str] = []
    for part in raw.split(","):
        ext = part.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        out.append(ext)
    return out


def _build_payload(db: DatabaseManager, mode: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    personas = db.persona_list(active_only=True)
    if personas:
        print("\nAvailable personas:")
        for p in personas:
            print(f"- {p.get('name')}")
        persona_name = _ask("Persona name (blank=auto resolve)", "")
        if persona_name:
            payload["persona_name"] = persona_name

    if mode == "index":
        default_root = str(REPO_ROOT / "documents")
        root = _ask("Root folder to index", default_root)
        payload["roots"] = [root]
        payload["recursive"] = _ask_bool("Recursive scan", True)
        payload["max_files"] = _ask_int("Max files", 5000)
        allowed = _ask("Allowed extensions CSV (blank=all)", "")
        exts = _normalize_exts(allowed)
        if exts:
            payload["allowed_exts"] = exts
    elif mode in {"refresh", "watch_refresh"}:
        payload["stale_after_hours"] = _ask_int("Stale-after hours", 24)
        if mode == "watch_refresh":
            payload["max_files_per_watch"] = _ask_int("Max files per watch", 5000)
    elif mode == "analyze_indexed":
        payload["max_files_analyze"] = _ask_int("Max indexed files to analyze", 200)
        payload["content_type"] = _ask("Content type hint", "legal_doc")
    elif mode == "organize_indexed":
        payload["max_files_organize"] = _ask_int("Max indexed files to organize", 200)
        payload["provider"] = _ask("Provider (blank=default)", "")
        payload["model"] = _ask("Model (blank=default)", "")
        if not payload["provider"]:
            payload.pop("provider", None)
        if not payload["model"]:
            payload.pop("model", None)

    return payload


def run_launcher(db_path: str | None = None, mode_arg: str | None = None) -> int:
    db = DatabaseManager(db_path)
    svc = TaskMasterService(db)

    print("TaskMaster Control Launcher")
    print("TaskMaster is in control for this run.")
    print()

    mode = mode_arg or _ask(
        f"Run mode ({', '.join(MODES)})",
        "index",
    )
    if mode not in MODES:
        print(f"Invalid mode: {mode}")
        return 2

    payload = _build_payload(db, mode)
    print("\nPlanned request:")
    print(json.dumps({"mode": mode, "payload": payload}, indent=2))

    if not _ask_bool("Run now", True):
        print("Cancelled.")
        return 0

    out = svc.run_file_pipeline(mode=mode, payload=payload)
    if not out.get("success"):
        print(f"\nRun failed: {out.get('error', 'unknown_error')}")
        run = out.get("run") or {}
        if run:
            print(f"Run ID: {run.get('id')} status={run.get('status')}")
        return 1

    run = out.get("run") or {}
    run_id = int(run.get("id", 0) or 0)
    print(f"\nRun completed. run_id={run_id} status={run.get('status')}")
    print("Summary:")
    print(json.dumps(run.get("summary_json") or {}, indent=2))

    if run_id > 0:
        skill_out = svc.get_skill_results(run_id)
        items = skill_out.get("items") if isinstance(skill_out, dict) else []
        if items:
            print(f"\nPersona skill outputs ({len(items)}):")
            for item in items[:10]:
                skill = item.get("skill_name", "unknown")
                output = item.get("output_json", {})
                print(f"- {skill}: {json.dumps(output)[:240]}")

    print("\nDone.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interactive launcher that runs TaskMaster pipelines directly.",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Optional database path override.",
    )
    parser.add_argument(
        "--mode",
        default=None,
        choices=MODES,
        help="Pipeline mode. If omitted, launcher asks interactively.",
    )
    args = parser.parse_args()
    return run_launcher(db_path=args.db_path, mode_arg=args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
