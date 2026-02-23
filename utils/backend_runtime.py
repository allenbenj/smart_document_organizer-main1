from __future__ import annotations

import os


def backend_base_url() -> str:
    """Canonical backend base URL for local desktop runtime."""
    return (
        os.getenv("SMART_DOC_API_BASE_URL")
        or os.getenv("BACKEND_BASE_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def backend_health_url() -> str:
    """Canonical health URL derived from backend base URL."""
    return f"{backend_base_url()}/api/health"


def launch_health_timeout_seconds(default: int = 120) -> int:
    """Shared startup health timeout (launcher + GUI startup)."""
    raw = (
        os.getenv("LAUNCH_HEALTH_TIMEOUT_SECONDS")
        or os.getenv("GUI_BACKEND_START_TIMEOUT_SECONDS")
        or str(default)
    )
    try:
        return max(15, int(raw))
    except Exception:
        return default
