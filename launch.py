from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BACKEND_URL = "http://127.0.0.1:8000/api/health"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified launcher for Legal AI UIs.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--modular",
        action="store_true",
        help="Launch Legal AI Modular System (default).",
    )
    mode.add_argument(
        "--platform",
        action="store_true",
        help="Launch Legal AI Platform Manager.",
    )
    parser.add_argument(
        "--backend-mode",
        choices=["sync", "skip", "stop"],
        default="sync",
        help=(
            "Backend lifecycle mode: "
            "'sync' = stop old launcher backend, start backend, wait healthy, stop on exit; "
            "'skip' = do not manage backend; "
            "'stop' = stop launcher backend and exit."
        ),
    )
    return parser


def _pid_file(repo_root: Path) -> Path:
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / "launcher_backend.pid"


def _log_file(repo_root: Path) -> Path:
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / "launcher_backend.log"


def _is_healthy(url: str = BACKEND_URL, timeout_s: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as response:
            return int(getattr(response, "status", 0) or 0) == 200
    except Exception:
        return False


def _wait_for_health(url: str = BACKEND_URL, timeout_s: int = 75) -> bool:
    deadline = time.monotonic() + max(1, int(timeout_s))
    sleep_s = 0.25
    while time.monotonic() < deadline:
        if _is_healthy(url):
            return True
        time.sleep(sleep_s)
        sleep_s = min(2.0, sleep_s * 1.5)
    return False


def _read_pid(pid_path: Path) -> int | None:
    try:
        if not pid_path.exists():
            return None
        payload = json.loads(pid_path.read_text(encoding="utf-8"))
        pid = int(payload.get("pid", 0))
        return pid if pid > 0 else None
    except Exception:
        return None


def _write_pid(pid_path: Path, pid: int) -> None:
    payload = {"pid": pid, "written_at_epoch_s": time.time()}
    pid_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _stop_pid(pid: int, grace_s: float = 4.0) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except Exception:
        return False

    deadline = time.monotonic() + max(0.5, grace_s)
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except Exception:
            pass
        time.sleep(0.1)

    try:
        os.kill(pid, signal.SIGKILL)
    except Exception:
        pass
    return True


def stop_launcher_backend(repo_root: Path) -> bool:
    pid_path = _pid_file(repo_root)
    pid = _read_pid(pid_path)
    if pid is None:
        return True
    ok = _stop_pid(pid)
    try:
        pid_path.unlink(missing_ok=True)
    except Exception:
        pass
    return ok


def start_launcher_backend(repo_root: Path) -> subprocess.Popen[bytes]:
    log_path = _log_file(repo_root)
    log_handle = open(log_path, "ab")
    cmd = [sys.executable, str(repo_root / "Start.py"), "--backend", "--profile", "full"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        stdout=log_handle,
        stderr=log_handle,
    )
    _write_pid(_pid_file(repo_root), proc.pid)
    return proc


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    backend_proc: subprocess.Popen[bytes] | None = None

    if args.backend_mode == "stop":
        stop_launcher_backend(repo_root)
        print("Launcher backend stopped.")
        return 0

    if args.backend_mode == "sync":
        stop_launcher_backend(repo_root)
        backend_proc = start_launcher_backend(repo_root)
        if not _wait_for_health():
            print(
                "Backend failed to become healthy on 127.0.0.1:8000. "
                f"Check logs: {_log_file(repo_root)}",
                file=sys.stderr,
            )
            if backend_proc.poll() is None:
                backend_proc.terminate()
            stop_launcher_backend(repo_root)
            return 1

    target = repo_root / "gui" / "gui_dashboard.py"
    if args.platform:
        target = repo_root / "gui" / "professional_manager.py"

    env = os.environ.copy()
    if args.backend_mode == "sync":
        env["GUI_SKIP_WSL_BACKEND_START"] = "1"

    cmd = [sys.executable, str(target)]
    try:
        return subprocess.call(cmd, cwd=str(repo_root), env=env)
    finally:
        if args.backend_mode == "sync":
            if backend_proc is not None and backend_proc.poll() is None:
                try:
                    backend_proc.terminate()
                    backend_proc.wait(timeout=5)
                except Exception:
                    pass
            stop_launcher_backend(repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
