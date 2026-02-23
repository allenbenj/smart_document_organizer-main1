"""
Classification Tab - GUI component for text classification operations

This module provides the UI for text classification operations using
various models and custom labels.
"""

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from ..services import api_client
from .default_paths import get_default_dialog_dir
from gui.core.base_tab import BaseTab


class ClassificationTab(BaseTab):
    def __init__(self, asyncio_thread: Optional[Any] = None, parent=None):
        super().__init__("Classification", asyncio_thread, parent)
        self.setup_ui()

    def setup_ui(self):
        title = QLabel("Text Classification")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        input_group = QGroupBox("Text Input")
        input_layout = QVBoxLayout()
        
        # File/Folder Selection
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("File:"))
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("Select a file...")
        file_row.addWidget(self.file_path)
        self.browse_file_btn = QPushButton("Browse File")
        self.browse_file_btn.clicked.connect(self.browse_file)
        file_row.addWidget(self.browse_file_btn)
        input_layout.addLayout(file_row)
        
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Folder:"))
        self.folder_path = QLineEdit()
        self.folder_path.setPlaceholderText("Or select a folder...")
        folder_row.addWidget(self.folder_path)
        self.browse_folder_btn = QPushButton("Browse Folder")
        self.browse_folder_btn.clicked.connect(self.browse_folder)
        folder_row.addWidget(self.browse_folder_btn)
        input_layout.addLayout(folder_row)
        
        input_layout.addWidget(QLabel("Or enter text directly:"))
        self.text = QTextEdit()
        self.text.setPlaceholderText("Enter text to classify...")
        self.text.setMaximumHeight(100)
        input_layout.addWidget(self.text)
        options_row = QHBoxLayout()
        self.quality_gate = QCheckBox("Quality gate")
        options_row.addWidget(self.quality_gate)
        options_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(
            [
                "typeform/distilbert-base-uncased-mnli",  # Speed
                "roberta-large-mnli",  # Balanced
                "facebook/bart-large-mnli",  # Accuracy
                "MoritzLaurer/deberta-v3-large-zeroshot-v2",
            ]
        )
        options_row.addWidget(self.model_combo)
        input_layout.addLayout(options_row)
        # Optional custom labels
        self.labels_edit = QLineEdit()
        self.labels_edit.setPlaceholderText(
            "Custom labels (comma-separated), leave blank for defaults"
        )
        input_layout.addWidget(self.labels_edit)
        input_group.setLayout(input_layout)

        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout()
        self.run_btn = QPushButton("Classify")
        self.clear_btn = QPushButton("Clear")
        actions_layout.addWidget(self.run_btn)
        actions_layout.addWidget(self.clear_btn)
        actions_group.setLayout(actions_layout)

        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout()
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Label", "Confidence"])
        results_layout.addWidget(self.table)
        results_group.setLayout(results_layout)

        self.main_layout.addWidget(input_group)
        self.main_layout.addWidget(actions_group)
        self.main_layout.addWidget(results_group)

        self.run_btn.clicked.connect(self.do_classify)
        self.clear_btn.clicked.connect(self.clear_all)

    def browse_file(self):
        """Browse for a single file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Document",
            get_default_dialog_dir(self.folder_path.text() or self.file_path.text()),
            "All Files (*);;Text Files (*.txt);;PDF Files (*.pdf);;Word Files (*.docx);;Markdown (*.md)",
        )
        if file_path:
            self.file_path.setText(file_path)
            self.folder_path.clear()
            self.text.clear()

    def browse_folder(self):
        """Browse for a folder."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            get_default_dialog_dir(self.folder_path.text() or self.file_path.text()),
        )
        if folder_path:
            self.folder_path.setText(folder_path)
            self.file_path.clear()
            self.text.clear()

    def clear_all(self):
        """Clear all inputs and results."""
        self.text.clear()
        self.file_path.clear()
        self.folder_path.clear()
        self.table.setRowCount(0)

    def do_classify(self):
        t = self.text.toPlainText().strip()
        if not t:
            QMessageBox.warning(self, "Warning", "Please enter text.")
            return
        try:
            opts = {
                "quality_gate": self.quality_gate.isChecked(),
                "model_name": self.model_combo.currentText(),
            }
            labels_list = [
                s.strip()
                for s in (self.labels_edit.text() or "").split(",")
                if s.strip()
            ]
            if labels_list:
                opts["labels"] = labels_list
            result = api_client.classify_text(t, opts)
            labels = result.get("data", {}).get("labels", [])
            self.table.setRowCount(len(labels))
            for i, item in enumerate(labels):
                self.table.setItem(i, 0, QTableWidgetItem(str(item.get("label", ""))))
                self.table.setItem(
                    i, 1, QTableWidgetItem(f"{item.get('confidence', 0):.2f}")
                )
        except Exception as e:
            QMessageBox.critical(self, "Classification Error", str(e))
