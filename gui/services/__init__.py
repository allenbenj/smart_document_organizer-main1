"""
GUI Services - API client and data management for the Legal AI GUI

This module provides centralized API communication and data handling
to keep the GUI components clean and focused on UI logic.
"""

import os
from typing import Any, Dict, Optional

try:
    import requests  # noqa: E402
except ImportError:
    requests = None


class ApiClient:
    """Centralized API client for GUI operations."""

    def __init__(self, base_url: Optional[str] = None):
        resolved = (base_url or os.getenv("SMART_DOC_API_BASE_URL") or "http://127.0.0.1:8000").strip()
        self.base_url = resolved.rstrip("/")
        self.session = requests.Session() if requests else None

    @property
    def api_base_url(self) -> str:
        """Return API root URL (base + /api)."""
        return f"{self.base_url}/api"

    def api_url(self, path: str) -> str:
        """Build full URL from either '/api/..' or '/..' path."""
        if not path:
            return self.base_url
        if path.startswith("/api/"):
            return f"{self.base_url}{path}"
        if path.startswith("/"):
            return f"{self.api_base_url}{path}"
        return f"{self.api_base_url}/{path}"

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling."""
        if not self.session:
            raise RuntimeError("requests not available")

        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            status = None
            body = ""
            try:
                resp = getattr(e, "response", None) or locals().get("response")
                if resp is not None:
                    status = resp.status_code
                    body = (resp.text or "")[:500]
            except Exception:
                pass
            if status is not None:
                raise RuntimeError(
                    f"API request failed [{method} {endpoint}] HTTP {status}: {body or str(e)}"
                )
            raise RuntimeError(f"API request failed [{method} {endpoint}]: {e}")

    def get_health(self) -> Dict[str, Any]:
        """Get system health status."""
        return self._make_request("GET", "/api/health")

    def analyze_semantic(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Perform semantic analysis."""
        data = {"text": text, "options": options or {}}
        return self._make_request("POST", "/api/agents/semantic", json=data)

    def extract_entities(self, text: str, entity_types: Optional[list] = None) -> Dict[str, Any]:
        """Extract entities from text."""
        data = {"text": text}
        if entity_types:
            data["entity_types"] = entity_types
        return self._make_request("POST", "/api/agents/entities", json=data)

    def process_document(self, file_path: str) -> Dict[str, Any]:
        """Process document file."""
        import mimetypes  # noqa: E402
        import os  # noqa: E402

        mt, _ = mimetypes.guess_type(file_path)
        with open(file_path, "rb") as f:
            files = {
                "file": (
                    os.path.basename(file_path),
                    f,
                    mt or "application/octet-stream",
                )
            }
            return self._make_request("POST", "/api/agents/process-document", files=files)


# Global API client instance
api_client = ApiClient()
