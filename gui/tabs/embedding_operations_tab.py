"""
Embedding Operations Tab - GUI component for embedding operations

This module provides the UI for text embedding operations including
generation, similarity search, and visualization.
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class EmbeddingOperationsTab(QWidget):
    """Tab for embedding operations."""

    def __init__(self, asyncio_thread):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.worker = None
        self.init_ui()

    def init_ui(self):
        """Initialize the embedding operations tab UI."""
        layout = QVBoxLayout()

        # Title
        title = QLabel("Text Embedding Operations")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Input Group
        input_group = QGroupBox("Text Input")
        input_layout = QVBoxLayout()

        self.text_input = QTextEdit()
        self.text_input.setMaximumHeight(120)
        self.text_input.setPlaceholderText("Enter text to generate embeddings...")
        input_layout.addWidget(self.text_input)
        input_group.setLayout(input_layout)

        # Options Group
        options_group = QGroupBox("Embedding Options")
        options_layout = QVBoxLayout()

        # Model selection
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(
            ["sentence-transformers", "OpenAI", "Legal-BERT", "Custom"]
        )
        model_layout.addWidget(self.model_combo)
        options_layout.addLayout(model_layout)

        # Operation type
        op_layout = QHBoxLayout()
        op_layout.addWidget(QLabel("Operation:"))
        self.operation_combo = QComboBox()
        self.operation_combo.addItems(
            [
                "Generate Embeddings",
                "Similarity Search",
                "Clustering",
                "Dimensionality Reduction",
            ]
        )
        op_layout.addWidget(self.operation_combo)
        options_layout.addLayout(op_layout)

        options_group.setLayout(options_layout)

        # Actions Group
        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout()

        self.process_btn = QPushButton("Process Embeddings")
        self.clear_btn = QPushButton("Clear Results")
        self.visualize_btn = QPushButton("Visualize")

        actions_layout.addWidget(self.process_btn)
        actions_layout.addWidget(self.clear_btn)
        actions_layout.addWidget(self.visualize_btn)
        actions_group.setLayout(actions_layout)

        # Results Group
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout()

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(300)
        results_layout.addWidget(self.results_text)
        results_group.setLayout(results_layout)

        layout.addWidget(input_group)
        layout.addWidget(options_group)
        layout.addWidget(actions_group)
        layout.addWidget(results_group)

        self.setLayout(layout)

        # Connect signals
        self.process_btn.clicked.connect(self.process_embeddings)
        self.clear_btn.clicked.connect(self.clear_results)
        self.visualize_btn.clicked.connect(self.visualize_embeddings)

    def process_embeddings(self):
        """Process text embeddings using the UnifiedEmbeddingAgent."""
        text = self.text_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Warning", "Please enter text to process.")
            return

        # Get selected options
        model_name = self.model_combo.currentText()
        operation = self.operation_combo.currentText()

        try:
            self.results_text.clear()
            self.results_text.append(
                f"Processing {operation.lower()} with {model_name}..."
            )

            # Create worker thread for embedding processing
            self.worker = EmbeddingWorker(
                self.asyncio_thread, text, model_name, operation
            )
            self.worker.result_ready.connect(self.on_embedding_result)
            self.worker.error_occurred.connect(self.on_embedding_error)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.start()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to process embeddings: {str(e)}"
            )

    def clear_results(self):
        """Clear all results and input fields."""
        self.text_input.clear()
        self.results_text.clear()

    def visualize_embeddings(self):
        """Visualize embeddings."""
        QMessageBox.information(self, "Info", "Embedding visualization coming soon.")

    def on_embedding_result(self, result):
        """Handle embedding processing results."""
        self.worker = None
        self.results_text.clear()
        self.results_text.append("Embedding Results:")
        self.results_text.append("-" * 50)

        if isinstance(result, dict):
            for key, value in result.items():
                self.results_text.append(f"{key}: {value}")
        else:
            self.results_text.append(str(result))

    def on_embedding_error(self, error_msg):
        """Handle embedding processing errors."""
        self.worker = None
        self.results_text.clear()
        self.results_text.append(f"Error: {error_msg}")
        QMessageBox.critical(self, "Processing Error", error_msg)


# Import here to avoid circular imports
from .workers import EmbeddingWorker