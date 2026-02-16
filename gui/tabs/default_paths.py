"""Shared default path helpers for GUI tab file/folder pickers."""

from __future__ import annotations

import os
from pathlib import Path


_LEGACY_INTERVIEWS_PATH = r"E:\Organization_Folder\02_Working_Folder\02_Analysis\08_Interviews"
_LEGACY_ORG_ROOT = r"E:\Organization_Folder"


def get_default_dialog_dir(current_value: str | None = None) -> str:
    """Return the best available directory for file/folder dialogs."""
    candidates = [
        (current_value or "").strip(),
        os.getenv("SMART_DOC_DEFAULT_DIR", "").strip(),
        _LEGACY_INTERVIEWS_PATH,
        _LEGACY_ORG_ROOT,
        str(Path.home() / "Documents"),
        str(Path.home()),
        os.getcwd(),
    ]

    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate
    return ""
