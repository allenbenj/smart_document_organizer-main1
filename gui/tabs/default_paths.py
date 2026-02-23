"""Shared default path helpers for GUI tab file/folder pickers."""

from __future__ import annotations

import os

from gui.core.path_config import default_dialog_candidates


def get_default_dialog_dir(current_value: str | None = None) -> str:
    """Return the best available directory for file/folder dialogs."""
    candidates = default_dialog_candidates(current_value)

    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate
    return ""
