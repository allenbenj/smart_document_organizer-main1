"""GUI path resolution helpers for portability across Windows/WSL/Linux."""

from __future__ import annotations

import os
from pathlib import Path


def project_root_path() -> Path:
    """Return repository root path resolved from this module location."""
    return Path(__file__).resolve().parents[2]


def _windows_to_wsl(path: str) -> str:
    """Translate `C:\\...` to `/mnt/c/...` when possible."""
    if len(path) >= 3 and path[1:3] == ":\\":
        drive = path[0].lower()
        rest = path[3:].replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    return path.replace("\\", "/")


def default_wsl_project_path() -> str:
    """Return WSL project path with env override and portable fallback."""
    override = (os.getenv("WSL_PROJECT_PATH") or "").strip()
    if override:
        return override

    root = project_root_path()
    root_str = str(root)
    # If currently on Windows-style path, convert to /mnt/<drive>/...
    if len(root_str) >= 3 and root_str[1:3] == ":\\":
        return _windows_to_wsl(root_str)
    return root_str.replace("\\", "/")


def default_dialog_candidates(current_value: str | None = None) -> list[str]:
    """Provide prioritized folder candidates for file dialogs."""
    current = (current_value or "").strip()
    env_default = (os.getenv("SMART_DOC_DEFAULT_DIR") or "").strip()
    env_docs = (os.getenv("SMART_DOC_DOCUMENTS_DIR") or "").strip()
    root = project_root_path()
    return [
        current,
        env_default,
        env_docs,
        str(root / "documents"),
        str(root),
        str(Path.home() / "Documents"),
        str(Path.home()),
        os.getcwd(),
    ]


def resolve_local_model_path(
    *,
    env_var: str,
    relative_path: str,
    legacy_windows_path: str | None = None,
) -> str:
    """Resolve model path from env, repo-relative fallback, and legacy fallback."""
    env_value = (os.getenv(env_var) or "").strip()
    if env_value and os.path.exists(env_value):
        return env_value

    repo_relative = project_root_path() / relative_path
    if repo_relative.exists():
        return str(repo_relative)

    if legacy_windows_path and os.path.exists(legacy_windows_path):
        return legacy_windows_path

    # Return a stable fallback path even if missing so callers can report clearly.
    return str(repo_relative)


__all__ = [
    "default_dialog_candidates",
    "default_wsl_project_path",
    "project_root_path",
    "resolve_local_model_path",
]
