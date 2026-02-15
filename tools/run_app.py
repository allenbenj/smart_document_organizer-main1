import argparse
import importlib.util
import json
import os  # noqa: E402
from pathlib import Path
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import webbrowser


def missing_modules(module_names: list[str]) -> list[str]:
    """Return dependency modules missing from the active Python environment."""
    return [name for name in module_names if importlib.util.find_spec(name) is None]


def install_requirements(
    py_exe: str, project_root: Path, include_optional: bool, full: bool
) -> bool:
    """Install dependencies for launcher.

    full=False installs requirements-core.txt when available (safer/faster bootstrap).
    full=True installs requirements.txt.
    """
    required = (
        project_root / ("requirements.txt" if full else "requirements-core.txt")
    )
    optional = project_root / "requirements-optional.txt"

    if not required.exists():
        print(f"[!] Missing dependency file: {required}")
        return False

    commands = [[py_exe, "-m", "pip", "install", "-r", str(required)]]
    if include_optional and optional.exists():
        commands.append([py_exe, "-m", "pip", "install", "-r", str(optional)])

    for cmd in commands:
        print(f"[+] Running: {' '.join(cmd)}")
        try:
            subprocess.check_call(cmd, cwd=str(project_root))
        except subprocess.CalledProcessError as exc:
            print(f"[!] Dependency install failed with exit code {exc.returncode}")
            return False
    return True


def print_install_help(py_exe: str) -> None:
    print("[!] Required dependencies are missing.")
    print("    You can install them with either:")
    print("    1) python tools/run_app.py --install           # core deps")
    print("    1b) python tools/run_app.py --install --full-install  # full deps")
    print("    2) python -m pip install -r requirements.txt")
    print("    If your system Python is managed (PEP 668), create a virtualenv first:")
    print(f"      {py_exe} -m venv .venv")
    if os.name == "nt":
        print(r"      .venv\Scripts\python tools\run_app.py --install")
    else:
        print("      .venv/bin/python tools/run_app.py --install")


def check_backend_health(
    url: str = "http://127.0.0.1:8000/api/health", retries: int = 30, delay: float = 0.5
) -> bool:
    """Return True once API responds with HTTP 200.

    For local/dev startup we treat both `healthy` and `degraded` as boot-success,
    so strict optional-service gates do not block the launcher UX.
    """
    try:
        import urllib.request  # noqa: E402

        for _ in range(retries):
            try:
                with urllib.request.urlopen(url, timeout=1.5) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                pass
            time.sleep(delay)
    except Exception:
        return False
    return False


def _is_headless() -> bool:
    if os.name == "nt":
        return False
    return not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Smart Document Organizer backend API and GUI"
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install dependencies before launch",
    )
    parser.add_argument(
        "--full-install",
        action="store_true",
        help="Install full requirements.txt (includes heavier ML deps)",
    )
    parser.add_argument(
        "--optional",
        action="store_true",
        help="Also install requirements-optional.txt (used with --install)",
    )
    parser.add_argument(
        "--backend-only",
        action="store_true",
        help="Start API only; skip desktop GUI",
    )
    parser.add_argument(
        "--with-gui",
        action="store_true",
        help="Force GUI launch even in headless environments",
    )
    args = parser.parse_args()

    py = sys.executable
    project_root = Path(__file__).resolve().parent.parent

    launch_gui = not args.backend_only
    if _is_headless() and not args.with_gui:
        launch_gui = False

    required_modules = ["fastapi", "uvicorn", "requests"]

    missing = missing_modules(required_modules)

    if missing and args.install:
        if not install_requirements(py, project_root, args.optional, args.full_install):
            return 1
        missing = missing_modules(required_modules)

    if missing:
        print(f"[!] Missing Python modules: {', '.join(missing)}")
        print_install_help(py)
        return 1

    env = os.environ.copy()
    # Default to permissive local-dev startup unless the caller explicitly sets values.
    env.setdefault("STRICT_PRODUCTION_STARTUP", "0")
    env.setdefault("API_KEY", "")
    env.setdefault("RATE_LIMIT_REQUESTS_PER_MINUTE", "0")
    env.setdefault("REQUIRED_PRODUCTION_AGENTS", "")

    pyside_available = importlib.util.find_spec("PySide6") is not None

    print("[+] Starting backend API (uvicorn Start:app) ...")
    print("[i] Launcher defaults: permissive local mode (strict startup off, API key off, rate limit off)")
    backend = subprocess.Popen(
        [py, "-m", "uvicorn", "Start:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(project_root),
        env=env,
    )

    org_console = None
    try:
        print(
            "[+] Waiting for backend to become healthy on http://127.0.0.1:8000/api/health ..."
        )
        if not check_backend_health():
            print(
                "[!] Backend did not become healthy in time. Check console output for errors."
            )
        else:
            print("[+] Backend is healthy.")

        if launch_gui:
            print("[+] Starting Organization Console (http://127.0.0.1:8010) ...")
            org_console = subprocess.Popen(
                [py, os.path.join("tools", "org_console", "app.py")],
                cwd=str(project_root),
                env=env,
            )
            time.sleep(0.8)
            try:
                webbrowser.open("http://127.0.0.1:8010")
            except Exception:
                pass

            if pyside_available:
                print("[+] Launching desktop GUI (gui/gui_dashboard.py) ...")
                gui_rc = subprocess.call(
                    [py, os.path.join("gui", "gui_dashboard.py")],
                    cwd=str(project_root),
                    env=env,
                )
                print(f"[+] GUI exited with code {gui_rc}")
                return 0 if gui_rc == 0 else gui_rc

            print("[!] PySide6 not available. Using Organization Console only at http://127.0.0.1:8010")

        print("[+] Backend-only mode active. API is running; press Ctrl+C to stop.")
        while backend.poll() is None:
            time.sleep(0.5)
        return backend.returncode or 0
    finally:
        if org_console and org_console.poll() is None:
            print("[+] Shutting down Organization Console ...")
            try:
                org_console.terminate()
                org_console.wait(timeout=3)
            except Exception:
                try:
                    org_console.kill()
                except Exception:
                    pass
        if backend and backend.poll() is None:
            print("[+] Shutting down backend API ...")
            try:
                backend.terminate()
                backend.wait(timeout=5)
            except Exception:
                try:
                    backend.kill()
                except Exception:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
