"""
Vector Search Tab - GUI component for vector search operations

This module provides the UI for vector search operations including
embedding generation and similarity search.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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


class VectorSearchTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self._refresh_status_banner()

    def init_ui(self):
        layout = QVBoxLayout()
        self.status_banner = QLabel("")
        self.status_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_banner.setStyleSheet("QLabel { color: #c0392b; margin: 6px; }")
        layout.addWidget(self.status_banner)
        title = QLabel("Vector Search")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        input_group = QGroupBox("Query Text")
        input_layout = QVBoxLayout()
        self.query_text = QTextEdit()
        self.query_text.setPlaceholderText("Enter text to embed and search...")
        input_layout.addWidget(self.query_text)
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Embed Model:"))
        self.search_model_combo = QComboBox()
        self.search_model_combo.addItems(
            ["fallback", "sentence-transformers", "OpenAI", "Legal-BERT"]
        )
        model_row.addWidget(self.search_model_combo)
        input_layout.addLayout(model_row)
        input_group.setLayout(input_layout)

        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout()
        self.search_btn = QPushButton("Embed + Search")
        self.clear_btn = QPushButton("Clear")
        actions_layout.addWidget(self.search_btn)
        actions_layout.addWidget(self.clear_btn)
        actions_group.setLayout(actions_layout)

        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout()
        self.results_table = QTableWidget(0, 3)
        self.results_table.setHorizontalHeaderLabels(["ID", "Score", "Type"])
        results_layout.addWidget(self.results_table)
        results_group.setLayout(results_layout)

        layout.addWidget(input_group)
        layout.addWidget(actions_group)
        layout.addWidget(results_group)
        self.setLayout(layout)

    def _refresh_status_banner(self):
        try:
            data = api_client.get_vector_status()
            if not data.get("available"):
                deg = data.get("degradation") or {}
                lost = (
                    ", ".join(deg.get("lost_features", [])) or "vector features"
                )
                self.status_banner.setText(
                    f"Vector Store Unavailable — Lost: {lost} — See Memory menu for guidance"
                )
                self.status_banner.show()
                return
        except Exception:
            pass
        self.status_banner.setText("")
        self.status_banner.hide()

        self.search_btn.clicked.connect(self.do_search)
        self.clear_btn.clicked.connect(
            lambda: (self.query_text.clear(), self.results_table.setRowCount(0))
        )

    def do_search(self):
        text = self.query_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Warning", "Please enter query text.")
            return
        try:
            embed_result = api_client.embed_texts([text], {"model": self.search_model_combo.currentText()})
            emb = embed_result.get("data", {}).get("embeddings", [])
            if not emb:
                raise RuntimeError("No embedding returned")
            search_result = api_client.vector_search(emb[0], top_k=5)
            data = search_result.get("results", [])
            self.results_table.setRowCount(len(data))
            for i, item in enumerate(data):
                self.results_table.setItem(
                    i, 0, QTableWidgetItem(str(item.get("id", "")))
                )
                self.results_table.setItem(
                    i, 1, QTableWidgetItem(f"{item.get('score', 0):.3f}")
                )
                self.results_table.setItem(
                    i, 2, QTableWidgetItem(str(item.get("document_type", "")))
                )
        except Exception as e:
            QMessageBox.critical(self, "Search Error", str(e))