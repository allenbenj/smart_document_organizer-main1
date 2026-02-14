"""
GUI Workers - Background processing threads for the Legal AI GUI

This module contains QThread subclasses that handle long-running operations
in the background to keep the GUI responsive.
"""

import mimetypes
import os  # noqa: E402
from typing import Optional  # noqa: E402

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import PySide6.QtWidgets as _QtWidgets  # noqa: F401
    import PySide6.QtCore as _QtCore        # noqa: F401
    import PySide6.QtGui as _QtGui          # noqa: F401

from PySide6.QtCore import QThread, Signal  # noqa: E402

try:
    import requests  # noqa: E402
except ImportError:
    requests = None


class SemanticAnalysisWorker(QThread):
    """Worker thread for semantic analysis operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(
        self,
        asyncio_thread,
        file_path,
        text_input,
        analysis_type,
        include_metadata,
        deep_analysis,
    ):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.file_path = file_path
        self.text_input = text_input
        self.analysis_type = analysis_type
        self.include_metadata = include_metadata
        self.deep_analysis = deep_analysis

    def run(self):  # noqa: C901
        """Execute semantic analysis via API (and document processor when needed)."""
        try:
            if not requests:
                raise RuntimeError("requests not available")
            # Determine text to analyze
            content = self.text_input.strip()
            if not content and self.file_path:
                # Upload the file to get content
                mt, _ = mimetypes.guess_type(self.file_path)
                with open(self.file_path, "rb") as f:
                    files = {
                        "file": (
                            os.path.basename(self.file_path),
                            f,
                            mt or "application/octet-stream",
                        )
                    }
                    r = requests.post(
                        "http://127.0.0.1:8000/api/agents/process-document",
                        files=files,
                        timeout=120,
                    )
                if r.status_code != 200:
                    raise RuntimeError(f"Process HTTP {r.status_code}: {r.text}")
                content = (
                    (r.json().get("data") or {})
                    .get("processed_document", {})
                    .get("content", "")
                )
            if not content:
                raise RuntimeError("No content to analyze")
            # Call semantic endpoint
            resp = requests.post(
                "http://127.0.0.1:8000/api/agents/semantic",
                json={"text": content, "options": {}},
                timeout=30,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Semantic HTTP {resp.status_code}: {resp.text}")
            body = resp.json()
            self.result_ready.emit(body.get("data") or {})
        except Exception as e:
            self.error_occurred.emit(str(e))


class EntityExtractionWorker(QThread):
    """Worker thread for entity extraction operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, text: str, entity_types: Optional[list] = None):
        super().__init__()
        self.text = text
        self.entity_types = entity_types

    def run(self):  # noqa: C901
        """Execute entity extraction via API."""
        try:
            if not requests:
                raise RuntimeError("requests not available")

            # Prepare request data
            data = {"text": self.text}
            if self.entity_types:
                data["entity_types"] = self.entity_types

            # Call entity extraction endpoint
            resp = requests.post(
                "http://127.0.0.1:8000/api/agents/entities",
                json=data,
                timeout=30,
            )

            if resp.status_code != 200:
                raise RuntimeError(f"Entity extraction HTTP {resp.status_code}: {resp.text}")

            body = resp.json()
            self.result_ready.emit(body.get("data") or {})

        except Exception as e:
            self.error_occurred.emit(str(e))


class LegalReasoningWorker(QThread):
    """Worker thread for legal reasoning operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, text: str, options: Optional[dict] = None):
        super().__init__()
        self.text = text
        self.options = options or {}

    def run(self):  # noqa: C901
        """Execute legal reasoning via API."""
        try:
            if not requests:
                raise RuntimeError("requests not available")

            # Prepare request data
            data = {
                "text": self.text,
                "options": self.options
            }

            # Call legal reasoning endpoint
            resp = requests.post(
                "http://127.0.0.1:8000/api/agents/legal-reasoning",
                json=data,
                timeout=60,  # Legal reasoning can take longer
            )

            if resp.status_code != 200:
                raise RuntimeError(f"Legal reasoning HTTP {resp.status_code}: {resp.text}")

            body = resp.json()
            self.result_ready.emit(body.get("data") or {})

        except Exception as e:
            self.error_occurred.emit(str(e))


class DocumentProcessingWorker(QThread):
    """Worker thread for document processing operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, files: list, options: dict):
        super().__init__()
        self.files = files
        self.options = options

    def run(self):  # noqa: C901
        """Execute document processing via API."""
        try:
            if not requests:
                raise RuntimeError("requests not available")

            # For each file, process
            results = []
            for file_path in self.files:
                mt, _ = mimetypes.guess_type(file_path)
                with open(file_path, "rb") as f:
                    files = {
                        "file": (
                            os.path.basename(file_path),
                            f,
                            mt or "application/octet-stream",
                        )
                    }
                    r = requests.post(
                        "http://127.0.0.1:8000/api/agents/process-document",
                        files=files,
                        timeout=120,
                    )
                if r.status_code != 200:
                    raise RuntimeError(f"Process HTTP {r.status_code}: {r.text}")
                results.append(r.json().get("data") or {})

            self.result_ready.emit({"results": results})

        except Exception as e:
            self.error_occurred.emit(str(e))
