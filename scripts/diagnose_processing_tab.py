from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path
from typing import Any

import requests


SUPPORTED_EXTS = {
    ".pdf",
    ".docx",
    ".doc",
    ".txt",
    ".html",
    ".htm",
    ".rtf",
    ".md",
    ".xlsx",
    ".xls",
    ".csv",
    ".pptx",
    ".ppt",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".bmp",
    ".mp4",
    ".mov",
    ".avi",
    ".mp3",
    ".wav",
    ".eml",
}


def collect_files(root: Path, max_files: int) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SUPPORTED_EXTS:
            continue
        out.append(p)
        if len(out) >= max_files:
            break
    return out


def normalize_batch(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"files": [], "processed": 0, "failed": 0, "raw_type": type(payload).__name__}
    items = payload.get("results")
    if not isinstance(items, list):
        items = payload.get("files")
    if not isinstance(items, list):
        items = payload.get("items")
    if not isinstance(items, list):
        items = []
    ok = 0
    bad = 0
    for item in items:
        if isinstance(item, dict) and bool(item.get("success", True)) and not item.get("error"):
            ok += 1
        else:
            bad += 1
    return {"files": items, "processed": ok, "failed": bad}


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose Processing-tab batch pipeline.")
    parser.add_argument("--root", required=True, help="Root folder for sample files.")
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="Backend base URL.")
    parser.add_argument("--max-files", type=int, default=10, help="How many files to send.")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists() or not root.is_dir():
        print(f"[ERR] invalid root: {root}")
        return 2

    base = args.base.rstrip("/")
    health_url = f"{base}/api/health"
    batch_url = f"{base}/api/agents/process-documents"

    try:
        hr = requests.get(health_url, timeout=10)
        print(f"[OK] health status={hr.status_code}")
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] health request failed: {e}")
        return 2

    files = collect_files(root, max(1, int(args.max_files)))
    print(f"[INFO] root={root}")
    print(f"[INFO] collected_files={len(files)}")
    if not files:
        print("[ERR] no supported files found under root")
        return 2

    handles = []
    files_payload = []
    try:
        for p in files:
            mt, _ = mimetypes.guess_type(str(p))
            fh = open(p, "rb")
            handles.append(fh)
            files_payload.append(("files", (p.name, fh, mt or "application/octet-stream")))

        resp = requests.post(batch_url, files=files_payload, timeout=300)
        print(f"[INFO] batch_http_status={resp.status_code}")
        text = resp.text[:1200]
        payload = None
        try:
            payload = resp.json()
        except Exception:
            print(f"[ERR] non-json response: {text}")
            return 1

        if not isinstance(payload, dict):
            print(f"[ERR] unexpected payload type: {type(payload).__name__}")
            print(text)
            return 1

        print(f"[INFO] payload_keys={sorted(payload.keys())}")
        if "error" in payload:
            print(f"[INFO] payload_error={payload.get('error')}")

        norm = normalize_batch(payload)
        print(
            "[RESULT] "
            f"processed={norm['processed']} failed={norm['failed']} total={len(norm['files'])}"
        )
        if norm["failed"] > 0:
            sample_errors = []
            for it in norm["files"]:
                if isinstance(it, dict) and (it.get("error") or not it.get("success", True)):
                    sample_errors.append(
                        {
                            "filename": it.get("filename"),
                            "error": it.get("error"),
                            "success": it.get("success"),
                        }
                    )
                if len(sample_errors) >= 5:
                    break
            print(f"[RESULT] sample_failures={sample_errors}")
        return 0
    finally:
        for h in handles:
            try:
                h.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
