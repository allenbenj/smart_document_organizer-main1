"""
Workers and Dialogs for GUI Tabs

This module contains worker threads and dialog classes used by the GUI tabs.
"""

import json
import mimetypes
import os
from typing import Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QDialog, QLabel, QTextEdit, QVBoxLayout, QWidget

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from ..services import api_client


class UploadFileWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):  # noqa: C901
        try:
            if not requests:
                raise RuntimeError("requests not available")
            mt, _ = mimetypes.guess_type(self.path)
            with open(self.path, "rb") as f:
                files = {
                    "file": (
                        os.path.basename(self.path),
                        f,
                        mt or "application/octet-stream",
                    )
                }
                r = requests.post(
                    f"{api_client.base_url}/api/agents/process-document",
                    files=files,
                    timeout=120,
                )
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
            self.finished_ok.emit(r.json())
        except Exception as e:
            self.finished_err.emit(str(e))


class UploadFolderWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):  # noqa: C901
        try:
            if not requests:
                raise RuntimeError("requests not available")
            # Collect all files in folder
            files = []
            for root, _, filenames in os.walk(self.path):
                for filename in filenames:
                    filepath = os.path.join(root, filename)
                    mt, _ = mimetypes.guess_type(filepath)
                    with open(filepath, "rb") as f:
                        files.append(
                            (
                                "files",
                                (
                                    os.path.relpath(filepath, self.path),
                                    f.read(),
                                    mt or "application/octet-stream",
                                ),
                            )
                        )
            if not files:
                raise RuntimeError("No files found in folder")
            r = requests.post(
                f"{api_client.base_url}/api/agents/process-documents",
                files=files,
                timeout=300,
            )
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
            self.finished_ok.emit(r.json())
        except Exception as e:
            self.finished_err.emit(str(e))


class UploadManyFilesWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, paths: list[str], options: Optional[dict] = None):
        super().__init__()
        self.paths = paths
        self.options = options or {}

    def run(self):  # noqa: C901
        try:
            if not requests:
                raise RuntimeError("requests not available")
            files = []
            for path in self.paths:
                mt, _ = mimetypes.guess_type(path)
                with open(path, "rb") as f:
                    files.append(
                        (
                            "files",
                            (
                                os.path.basename(path),
                                f.read(),
                                mt or "application/octet-stream",
                            ),
                        )
                    )
            if not files:
                raise RuntimeError("No files provided")
            r = requests.post(
                f"{api_client.base_url}/api/agents/process-documents",
                files=files,
                data={"options": json.dumps(self.options)} if self.options else None,
                timeout=300,
            )
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
            self.finished_ok.emit(r.json())
        except Exception as e:
            self.finished_err.emit(str(e))


class KGImportFromTextWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def run(self):  # noqa: C901
        try:
            if not requests:
                raise RuntimeError("requests not available")
            r = requests.post(
                f"{api_client.base_url}/api/knowledge/import-text",
                json={"text": self.text},
                timeout=120,
            )
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
            self.finished_ok.emit(r.json())
        except Exception as e:
            self.finished_err.emit(str(e))


class ProcessedDocDetailsDialog(QDialog):
    """Dialog for displaying processed document details."""

    def __init__(self, doc_data: dict, parent=None):
        super().__init__(parent)
        self.doc_data = doc_data
        self.setWindowTitle("Processed Document Details")
        self.setGeometry(200, 200, 600, 400)
        self.init_ui()

    def init_ui(self):
        """Initialize the dialog UI."""
        layout = QVBoxLayout()

        # Document info
        info_label = QLabel(f"Document: {self.doc_data.get('filename', 'Unknown')}")
        layout.addWidget(info_label)

        # Content preview
        content_label = QLabel("Content Preview:")
        layout.addWidget(content_label)

        self.content_text = QTextEdit()
        self.content_text.setPlainText(
            self.doc_data.get("processed_document", {}).get("content", "")
        )
        self.content_text.setReadOnly(True)
        layout.addWidget(self.content_text)

        # Metadata
        metadata_label = QLabel("Metadata:")
        layout.addWidget(metadata_label)

        self.metadata_text = QTextEdit()
        self.metadata_text.setPlainText(
            str(self.doc_data.get("processed_document", {}).get("metadata", {}))
        )
        self.metadata_text.setReadOnly(True)
        layout.addWidget(self.metadata_text)

        self.setLayout(layout)


class LegalReasoningDetailsDialog(QDialog):
    """Dialog for displaying legal reasoning details."""

    def __init__(self, reasoning_data: dict, parent=None):
        super().__init__(parent)
        self.reasoning_data = reasoning_data
        self.setWindowTitle("Legal Reasoning Details")
        self.setGeometry(200, 200, 600, 400)
        self.init_ui()

    def init_ui(self):
        """Initialize the dialog UI."""
        layout = QVBoxLayout()

        # Reasoning info
        info_label = QLabel(f"Case: {self.reasoning_data.get('case_name', 'Unknown')}")
        layout.addWidget(info_label)

        # Reasoning text
        reasoning_label = QLabel("Reasoning:")
        layout.addWidget(reasoning_label)

        self.reasoning_text = QTextEdit()
        self.reasoning_text.setPlainText(
            self.reasoning_data.get("reasoning", "")
        )
        self.reasoning_text.setReadOnly(True)
        layout.addWidget(self.reasoning_text)

        # Conclusion
        conclusion_label = QLabel("Conclusion:")
        layout.addWidget(conclusion_label)

        self.conclusion_text = QTextEdit()
        self.conclusion_text.setPlainText(
            self.reasoning_data.get("conclusion", "")
        )
        self.conclusion_text.setReadOnly(True)
        layout.addWidget(self.conclusion_text)

        self.setLayout(layout)


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
                        f"{api_client.base_url}/api/agents/process-document",
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
                f"{api_client.base_url}/api/agents/semantic",
                json={
                    "text": content,
                    "options": {
                        "analysis_type": self.analysis_type,
                        "include_metadata": self.include_metadata,
                        "deep_analysis": self.deep_analysis,
                    },
                },
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

    def __init__(self, asyncio_thread, file_path, text_input, extraction_type, options: Optional[dict] = None):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.file_path = file_path
        self.text_input = text_input
        self.extraction_type = extraction_type
        self.options = options or {}

    def run(self):  # noqa: C901
        """Execute entity extraction via API."""
        try:
            if not requests:
                raise RuntimeError("requests not available")
            # Determine text to extract from
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
                        f"{api_client.base_url}/api/agents/process-document",
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
            # Call entity extraction endpoint
            resp = requests.post(
                f"{api_client.base_url}/api/agents/entities",
                json={
                    "text": content,
                    "options": {
                        "extraction_type": self.extraction_type,
                        **self.options,
                    },
                },
                timeout=30,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Entities HTTP {resp.status_code}: {resp.text}")
            body = resp.json()
            self.result_ready.emit(body.get("data") or {})
        except Exception as e:
            self.error_occurred.emit(str(e))


class LegalReasoningWorker(QThread):
    """Worker thread for legal reasoning operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, asyncio_thread, file_path, text_input, reasoning_type, options: Optional[dict] = None):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.file_path = file_path
        self.text_input = text_input
        self.reasoning_type = reasoning_type
        self.options = options or {}

    def run(self):  # noqa: C901
        """Execute legal reasoning via API."""
        try:
            if not requests:
                raise RuntimeError("requests not available")
            # Determine text to reason about
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
                        f"{api_client.base_url}/api/agents/process-document",
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
            # Call legal reasoning endpoint
            resp = requests.post(
                f"{api_client.base_url}/api/agents/legal-reasoning",
                json={
                    "text": content,
                    "options": {
                        "reasoning_type": self.reasoning_type,
                        **self.options,
                    },
                },
                timeout=60,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Legal Reasoning HTTP {resp.status_code}: {resp.text}")
            body = resp.json()
            self.result_ready.emit(body.get("data") or {})
        except Exception as e:
            self.error_occurred.emit(str(e))


class EmbeddingWorker(QThread):
    """Worker thread for embedding operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, asyncio_thread, text, model_name, operation):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.text = text
        self.model_name = model_name
        self.operation = operation

    def run(self):  # noqa: C901
        """Execute embedding generation via API."""
        try:
            if not requests:
                raise RuntimeError("requests not available")
            # Call embedding endpoint
            resp = requests.post(
                f"{api_client.base_url}/api/agents/embeddings",
                json={"text": self.text, "options": {"model": self.model_name, "operation": self.operation}},
                timeout=30,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Embeddings HTTP {resp.status_code}: {resp.text}")
            body = resp.json()
            self.result_ready.emit(body.get("data") or {})
        except Exception as e:
            self.error_occurred.emit(str(e))


class DocumentOrganizationWorker(QThread):
    """Worker thread for document organization operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, asyncio_thread, file_path, text_input, organization_type):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.file_path = file_path
        self.text_input = text_input
        self.organization_type = organization_type

    def run(self):  # noqa: C901
        """Execute document organization via API."""
        try:
            if not requests:
                raise RuntimeError("requests not available")
            # Determine text to organize
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
                        f"{api_client.base_url}/api/agents/process-document",
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
                raise RuntimeError("No content to organize")
            # Call document organization endpoint
            resp = requests.post(
                f"{api_client.base_url}/api/agents/organize",
                json={"text": content, "options": {}},
                timeout=30,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Organize HTTP {resp.status_code}: {resp.text}")
            body = resp.json()
            self.result_ready.emit(body.get("data") or {})
        except Exception as e:
            self.error_occurred.emit(str(e))


class VectorIndexWorker(QThread):
    """Worker thread for vector indexing operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, asyncio_thread, file_path, text_input):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.file_path = file_path
        self.text_input = text_input

    def run(self):  # noqa: C901
        """Execute vector indexing via API."""
        try:
            if not requests:
                raise RuntimeError("requests not available")
            # Determine text to index
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
                        f"{api_client.base_url}/api/agents/process-document",
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
                raise RuntimeError("No content to index")
            # Call vector index endpoint
            resp = requests.post(
                f"{api_client.base_url}/api/vector/index",
                json={"text": content, "options": {}},
                timeout=30,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Vector Index HTTP {resp.status_code}: {resp.text}")
            body = resp.json()
            self.result_ready.emit(body.get("data") or {})
        except Exception as e:
            self.error_occurred.emit(str(e))


class KGFromFilesWorker(QThread):
    progress_update = Signal(int, str)
    finished_ok = Signal(str)
    finished_err = Signal(str)

    def __init__(self, files):
        super().__init__()
        self.files = files

    def run(self):
        try:
            for i, file_path in enumerate(self.files):
                self.progress_update.emit(i, "processing")
                # Process file to extract KG
                # Placeholder for KG extraction logic
                self.progress_update.emit(i, "done")
            self.finished_ok.emit("KG extraction completed")
        except Exception as e:
            self.finished_err.emit(str(e))


class PipelineRunnerWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, preset: dict, path: str):
        super().__init__()
        self.preset = preset
        self.path = path

    def run(self):  # noqa: C901
        try:
            if not requests:
                raise RuntimeError("requests not available")
            payload = {
                "steps": self.preset.get("steps", []),
                "context": (
                    {"path": self.path} if self.path else self.preset.get("context", {})
                ),
            }
            r = requests.post(
                f"{api_client.base_url}/api/pipeline/run", json=payload, timeout=120
            )
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
            self.finished_ok.emit(r.json())
        except Exception as e:
            self.finished_err.emit(str(e))