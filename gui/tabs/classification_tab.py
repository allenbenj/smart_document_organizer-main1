"""
Classification Tab - GUI component for text classification operations

This module provides the UI for text classification operations using
various models and custom labels.
"""

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
)

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from ..services import api_client


class ClassificationTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("Text Classification")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        input_group = QGroupBox("Text Input")
        input_layout = QVBoxLayout()
        self.text = QTextEdit()
        self.text.setPlaceholderText("Enter text to classify...")
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

        layout.addWidget(input_group)
        layout.addWidget(actions_group)
        layout.addWidget(results_group)
        self.setLayout(layout)

        self.run_btn.clicked.connect(self.do_classify)
        self.clear_btn.clicked.connect(
            lambda: (self.text.clear(), self.table.setRowCount(0))
        )

    def do_classify(self):
        t = self.text.toPlainText().strip()
        if not t:
            QMessageBox.warning(self, "Warning", "Please enter text.")
            return
        try:
            if not requests:
                raise RuntimeError("requests not available")
            opts = {
                "quality_gate": self.quality_gate.isChecked(),
                "model_name": self.model_combo.currentText(),
            }
            labels = [
                s.strip()
                for s in (self.labels_edit.text() or "").split(",")
                if s.strip()
            ]
            if labels:
                opts["labels"] = labels
            r = requests.post(
                f"{api_client.base_url}/api/agents/classify",
                json={"text": t, "options": opts},
                timeout=30,
            )
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
            labels = r.json().get("data", {}).get("labels", [])
            self.table.setRowCount(len(labels))
            for i, item in enumerate(labels):
                self.table.setItem(i, 0, QTableWidgetItem(str(item.get("label", ""))))
                self.table.setItem(
                    i, 1, QTableWidgetItem(f"{item.get('confidence', 0):.2f}")
                )
        except Exception as e:
            QMessageBox.critical(self, "Classification Error", str(e))