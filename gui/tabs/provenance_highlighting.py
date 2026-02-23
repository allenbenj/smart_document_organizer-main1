"""
Provenance Highlighting Tab - Evidence chain visualization

Provides the interface for inspecting provenance records and visualizing
evidence spans directly within the source document text.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from PySide6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QGroupBox,
        QSplitter,
        QTextBrowser,
        QListWidget,
        QListWidgetItem,
        QLineEdit,
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore

from .status_presenter import TabStatusPresenter
from services.provenance_service import get_provenance_service
from services.contracts.aedis_models import ProvenanceRecord

logger = logging.getLogger(__name__)


def build_highlight_segments(
    text: str,
    spans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build contiguous highlighted/non-highlighted segments from character spans."""
    if not text:
        return []

    merged: list[tuple[int, int]] = []
    for raw in spans:
        try:
            start = max(0, int(raw.get("start_char", 0)))
            end = min(len(text), int(raw.get("end_char", 0)))
        except Exception:
            continue
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            prev_start, prev_end = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end))

    if not merged:
        return [{"text": text, "highlight": False}]

    cursor = 0
    out: list[dict[str, Any]] = []
    for start, end in merged:
        if start > cursor:
            out.append({"text": text[cursor:start], "highlight": False})
        out.append({"text": text[start:end], "highlight": True})
        cursor = end
    if cursor < len(text):
        out.append({"text": text[cursor:], "highlight": False})
    return out


class ProvenanceHighlightingTab(QWidget):  # type: ignore[misc]
    """
    Tab for visualizing provenance and character-level evidence spans.
    Fulfills AEDIS Phase 3 'GUI-Integrated' mandate.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_text = ""
        self.current_records: list[ProvenanceRecord] = []
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Provenance & Evidence Visualization")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "Inspect evidence-backed claims and visualize character-level provenance "
            "chains from generation back to canonical truth anchors."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; padding: 5px 0;")
        layout.addWidget(desc)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left panel - Search & List
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Search Group
        search_group = QGroupBox("Find Artifact Provenance")
        search_layout = QVBoxLayout(search_group)
        
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target ID:"))
        self.target_id_input = QLineEdit()
        self.target_id_input.setPlaceholderText("e.g., proposal_123")
        target_row.addWidget(self.target_id_input)
        search_layout.addLayout(target_row)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Target Type:"))
        self.target_type_input = QLineEdit()
        self.target_type_input.setText("organization_proposal")
        type_row.addWidget(self.target_type_input)
        search_layout.addLayout(type_row)

        self.fetch_button = QPushButton("🔍 Fetch Provenance")
        self.fetch_button.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        search_layout.addWidget(self.fetch_button)

        left_layout.addWidget(search_group)

        # Records List
        self.record_list = QListWidget()
        left_layout.addWidget(QLabel("Evidence Chains:"))
        left_layout.addWidget(self.record_list)

        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f5f5f5; border-radius: 3px;")
        left_layout.addWidget(self.status_label)
        self.status = TabStatusPresenter(self, self.status_label, source="Provenance")

        splitter.addWidget(left_widget)

        # Right panel - Text Visualization
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        self.text_display = QTextBrowser()
        self.text_display.setPlaceholderText("Document text will appear here with provenance highlights...")
        self.text_display.setFont(QFont("Courier New", 10))
        right_layout.addWidget(self.text_display)

        splitter.addWidget(right_widget)
        splitter.setSizes([300, 500])

    def connect_signals(self):
        """Connect UI signals."""
        self.fetch_button.clicked.connect(self.load_provenance)
        self.record_list.itemSelectionChanged.connect(self.highlight_selected_record)

    def load_provenance(self):
        """Fetch provenance for the given target ID and type."""
        t_id = self.target_id_input.text().strip()
        t_type = self.target_type_input.text().strip()
        
        if not t_id or not t_type:
            self.status.error("Please provide both Target ID and Type")
            return

        self.status.loading(f"Fetching provenance for {t_id}...")
        try:
            service = get_provenance_service()
            record = service.get_provenance_for_artifact(t_type, t_id)
            if not record:
                self.status.warn("No provenance record found for this artifact")
                return

            self.current_records = [record]
            self.update_record_list()
            self.status.success(f"Loaded provenance for {t_id}")
        except Exception as e:
            self.status.error(f"Failed to load provenance: {e}")

    def update_record_list(self):
        """Populate the record list widget."""
        self.record_list.clear()
        for rec in self.current_records:
            item = QListWidgetItem(f"Chain: {rec.extractor}")
            item.setToolTip(f"Captured: {rec.captured_at.isoformat()}")
            item.setData(Qt.UserRole, rec)
            self.record_list.addItem(item)

    def highlight_selected_record(self):
        """Highlight evidence spans in the text browser."""
        selected_items = self.record_list.selectedItems()
        if not selected_items:
            return

        record: ProvenanceRecord = selected_items[0].data(Qt.UserRole)
        
        # Clear existing formatting
        cursor = self.text_display.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(QTextCharFormat())
        
        # Apply highlight for each span
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor("#fff176")) # Light yellow
        highlight_format.setFontWeight(QFont.Bold)

        for span in record.spans:
            cursor.setPosition(span.start_char)
            cursor.setPosition(span.end_char, QTextCursor.KeepAnchor)
            cursor.setCharFormat(highlight_format)
            
            # Scroll to first span
            if span == record.spans[0]:
                self.text_display.setTextCursor(cursor)
                self.text_display.ensureCursorVisible()

    def set_document_text(self, text: str):
        """Externally set the text to be highlighted."""
        self.current_text = text
        self.text_display.setPlainText(text)
