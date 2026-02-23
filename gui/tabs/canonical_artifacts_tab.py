from __future__ import annotations

import hashlib

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..services import api_client


class CanonicalArtifactsTab(QWidget):
    """GUI connector for immutable canonical artifacts and lineage events."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Canonical Artifacts")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        ingest_group = QGroupBox("Ingest Immutable Artifact")
        ingest_layout = QVBoxLayout(ingest_group)

        artifact_row = QHBoxLayout()
        artifact_row.addWidget(QLabel("Artifact ID:"))
        self.artifact_id_input = QLineEdit()
        self.artifact_id_input.setPlaceholderText("artifact-001")
        artifact_row.addWidget(self.artifact_id_input)
        ingest_layout.addLayout(artifact_row)

        content_row = QHBoxLayout()
        content_row.addWidget(QLabel("Source Text:"))
        self.source_text_input = QLineEdit()
        self.source_text_input.setPlaceholderText("Text used to derive stable SHA-256")
        content_row.addWidget(self.source_text_input)
        ingest_layout.addLayout(content_row)

        self.ingest_button = QPushButton("Ingest Canonical Artifact")
        ingest_layout.addWidget(self.ingest_button)
        layout.addWidget(ingest_group)

        lineage_group = QGroupBox("Lineage")
        lineage_layout = QVBoxLayout(lineage_group)

        id_row = QHBoxLayout()
        id_row.addWidget(QLabel("Artifact Row ID:"))
        self.artifact_row_id_input = QLineEdit()
        self.artifact_row_id_input.setPlaceholderText("1")
        id_row.addWidget(self.artifact_row_id_input)
        lineage_layout.addLayout(id_row)

        event_row = QHBoxLayout()
        event_row.addWidget(QLabel("Event Type:"))
        self.event_type_input = QLineEdit()
        self.event_type_input.setPlaceholderText("lineage_inspected")
        event_row.addWidget(self.event_type_input)
        lineage_layout.addLayout(event_row)

        button_row = QHBoxLayout()
        self.append_lineage_button = QPushButton("Append Event")
        self.load_lineage_button = QPushButton("Load Lineage")
        button_row.addWidget(self.append_lineage_button)
        button_row.addWidget(self.load_lineage_button)
        lineage_layout.addLayout(button_row)

        layout.addWidget(lineage_group)

        self.output = QTextBrowser()
        self.output.setOpenExternalLinks(False)
        layout.addWidget(self.output)

    def _connect_signals(self) -> None:
        self.ingest_button.clicked.connect(self.ingest_canonical_artifact)
        self.append_lineage_button.clicked.connect(self.append_lineage_event)
        self.load_lineage_button.clicked.connect(self.load_lineage)

    def ingest_canonical_artifact(self) -> None:
        artifact_id = self.artifact_id_input.text().strip()
        source_text = self.source_text_input.text().strip()
        if not artifact_id or not source_text:
            QMessageBox.warning(self, "Validation", "Artifact ID and source text are required.")
            return
        sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        try:
            result = api_client.ingest_canonical_artifact(
                artifact_id=artifact_id,
                sha256=sha256,
                source_uri=f"gui://{artifact_id}",
                mime_type="text/plain",
                metadata={"origin": "gui.canonical_tab"},
                content_size_bytes=len(source_text.encode("utf-8")),
            )
            self.output.append(
                f"Ingested artifact {artifact_id} as row "
                f"{result.get('artifact_row_id', '?')}."
            )
        except Exception as e:
            QMessageBox.critical(self, "Canonical Ingest Error", str(e))

    def append_lineage_event(self) -> None:
        try:
            artifact_row_id = int(self.artifact_row_id_input.text().strip())
        except Exception:
            QMessageBox.warning(self, "Validation", "Artifact Row ID must be an integer.")
            return
        event_type = self.event_type_input.text().strip() or "lineage_inspected"
        try:
            result = api_client.append_canonical_lineage_event(
                artifact_row_id=artifact_row_id,
                event_type=event_type,
                event_data={"origin": "gui.canonical_tab"},
            )
            self.output.append(f"Appended event #{result.get('event_row_id', '?')} ({event_type}).")
        except Exception as e:
            QMessageBox.critical(self, "Lineage Error", str(e))

    def load_lineage(self) -> None:
        try:
            artifact_row_id = int(self.artifact_row_id_input.text().strip())
        except Exception:
            QMessageBox.warning(self, "Validation", "Artifact Row ID must be an integer.")
            return
        try:
            result = api_client.get_canonical_lineage(artifact_row_id)
            items = result.get("items", [])
            self.output.append(f"Lineage events ({len(items)}):")
            for item in items:
                self.output.append(
                    f"- {item.get('id', '?')}: {item.get('event_type', '')}"
                )
        except Exception as e:
            QMessageBox.critical(self, "Lineage Fetch Error", str(e))
