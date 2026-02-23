"""
Embedding Operations Tab - GUI component for embedding operations

This module provides the UI for text embedding operations including
generation, similarity search, and visualization.
"""

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ..services.model_capability_registry import ModelCapabilityRegistry
from .default_paths import get_default_dialog_dir
from .workers import EmbeddingWorker
from gui.core.base_tab import BaseTab

class EmbeddingOperationsTab(BaseTab):
    """Tab for embedding operations."""

    def __init__(self, asyncio_thread: Optional[Any] = None, parent=None):
        super().__init__("Embedding Operations", asyncio_thread, parent)
        self.setup_ui()

    def setup_ui(self):
        """Initialize the embedding operations tab UI."""
        self.registry = ModelCapabilityRegistry("models")

        # Title
        title = QLabel("Text Embedding Operations")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        # Input Group
        input_group = QGroupBox("Text Input")
        input_layout = QVBoxLayout()

        file_row = QHBoxLayout()
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("Optional: select one file...")
        file_row.addWidget(self.file_path_input)
        self.browse_file_btn = QPushButton("File...")
        file_row.addWidget(self.browse_file_btn)
        input_layout.addLayout(file_row)

        folder_row = QHBoxLayout()
        self.folder_path_input = QLineEdit()
        self.folder_path_input.setPlaceholderText(
            "Optional: select a folder to embed all supported files..."
        )
        folder_row.addWidget(self.folder_path_input)
        self.browse_folder_btn = QPushButton("Folder...")
        folder_row.addWidget(self.browse_folder_btn)
        input_layout.addLayout(folder_row)

        self.text_input = QTextEdit()
        self.text_input.setMaximumHeight(120)
        self.text_input.setPlaceholderText(
            "Enter text to generate embeddings (or leave empty to use file/folder)."
        )
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
            [
                "Nomic v1.5 (High-Fidelity)",
                "MiniLM-L6 (Local-Fast)",
                "Legal-BERT",
                "OpenAI",
                "Custom",
            ]
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

        strategic_group = QGroupBox("Strategic Clustering Refinements")
        strategic_layout = QVBoxLayout()
        self.auto_label_themes = QCheckBox("Auto-Label Themes")
        self.auto_label_themes.setChecked(True)
        self.auto_label_themes.setToolTip(
            "Use LLM naming to label clusters with legal themes."
        )
        strategic_layout.addWidget(self.auto_label_themes)

        self.smoking_gun_detection = QCheckBox("Smoking Gun Detection")
        self.smoking_gun_detection.setToolTip(
            "Flag semantic outliers that do not fit major cluster narratives."
        )
        strategic_layout.addWidget(self.smoking_gun_detection)

        self.pattern_finder = QCheckBox("Pattern Finder")
        self.pattern_finder.setToolTip(
            "Preserve cluster center vectors for cross-document pattern searches."
        )
        strategic_layout.addWidget(self.pattern_finder)

        self.boilerplate_denoising = QCheckBox("Boilerplate De-noising")
        self.boilerplate_denoising.setToolTip(
            "Tag probable procedural filler clusters for optional suppression."
        )
        strategic_layout.addWidget(self.boilerplate_denoising)
        strategic_group.setLayout(strategic_layout)
        options_layout.addWidget(strategic_group)

        options_group.setLayout(options_layout)

        # Actions Group
        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout()

        self.process_btn = QPushButton("Process Embeddings")
        self.clear_btn = QPushButton("Clear Output")
        self.visualize_btn = QPushButton("Visualize")

        actions_layout.addWidget(self.process_btn)
        actions_layout.addWidget(self.clear_btn)
        actions_layout.addWidget(self.visualize_btn)
        self.refresh_registry_btn = QPushButton("Refresh Registry")
        actions_layout.addWidget(self.refresh_registry_btn)
        actions_group.setLayout(actions_layout)

        # Results Group
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout()

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(300)
        results_layout.addWidget(self.results_text)

        self.registry_text = QTextEdit()
        self.registry_text.setReadOnly(True)
        self.registry_text.setMinimumHeight(240)
        results_layout.addWidget(self.registry_text)
        results_group.setLayout(results_layout)

        self.main_layout.addWidget(input_group)
        self.main_layout.addWidget(options_group)
        self.main_layout.addWidget(actions_group)
        self.main_layout.addWidget(results_group)

        # Connect signals
        self.process_btn.clicked.connect(self.process_embeddings)
        self.clear_btn.clicked.connect(self.clear_results)
        self.visualize_btn.clicked.connect(self.visualize_embeddings)
        self.refresh_registry_btn.clicked.connect(self.refresh_model_registry)
        self.browse_file_btn.clicked.connect(self.select_file)
        self.browse_folder_btn.clicked.connect(self.select_folder)
        self.refresh_model_registry()

    def process_embeddings(self):
        """Process text embeddings using the UnifiedEmbeddingAgent."""
        text = self.text_input.toPlainText().strip()
        file_path = self.file_path_input.text().strip()
        folder_path = self.folder_path_input.text().strip()
        if not text and not file_path and not folder_path:
            QMessageBox.warning(
                self,
                "Warning",
                "Provide text input, a file path, or a folder path to process.",
            )
            return

        # Get selected options
        model_name = self.model_combo.currentText()
        operation = self.operation_combo.currentText()

        try:
            self.results_text.clear()
            self.results_text.append(
                f"Processing {operation.lower()} with {model_name}..."
            )
            self.results_text.append(
                "Strategic options: "
                f"auto_label={self.auto_label_themes.isChecked()}, "
                f"smoking_gun={self.smoking_gun_detection.isChecked()}, "
                f"pattern_finder={self.pattern_finder.isChecked()}, "
                f"denoise={self.boilerplate_denoising.isChecked()}"
            )

            strategic_options = {
                "auto_label_themes": self.auto_label_themes.isChecked(),
                "smoking_gun_detection": self.smoking_gun_detection.isChecked(),
                "pattern_finder": self.pattern_finder.isChecked(),
                "boilerplate_denoising": self.boilerplate_denoising.isChecked(),
            }

            # Create worker thread for embedding processing
            worker_instance = EmbeddingWorker(
                self.asyncio_thread,
                text,
                model_name,
                operation,
                strategic_options,
                file_path=file_path,
                folder_path=folder_path,
            )
            worker_instance.result_ready.connect(self.on_embedding_result)
            # BaseTab handles error_occurred and finished, so no need to connect directly
            self.start_worker(worker_instance) # Use BaseTab's start_worker

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to process embeddings: {str(e)}"
            )

    def clear_results(self):
        """Clear all results and input fields."""
        self.text_input.clear()
        self.file_path_input.clear()
        self.folder_path_input.clear()
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



    def select_file(self):
        """Select one file to embed."""
        default_dir = get_default_dialog_dir(self.file_path_input.text())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Embed",
            default_dir,
            "All Files (*)",
        )
        if path:
            self.file_path_input.setText(path)

    def select_folder(self):
        """Select a folder to embed recursively."""
        default_dir = get_default_dialog_dir(self.folder_path_input.text())
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Embed",
            default_dir,
        )
        if folder:
            self.folder_path_input.setText(folder)

    def refresh_model_registry(self):
        """Rebuild and display local model capability registry."""
        try:
            payload = self.registry.build()
            summary = payload.get("summary", {})
            items = payload.get("items", [])
            lines = [
                "MODEL CAPABILITY REGISTRY",
                "=" * 80,
                f"Models directory: {payload.get('models_dir', 'models')}",
                (
                    "Summary: "
                    f"cataloged={summary.get('total_cataloged', 0)}, "
                    f"present={summary.get('present', 0)}, "
                    f"ready={summary.get('ready', 0)}, "
                    f"degraded_or_missing={summary.get('degraded_or_missing', 0)}"
                ),
                "",
            ]
            for item in items:
                lines.append(
                    f"[{item.get('display_name', item.get('id', 'unknown')).upper()}]"
                )
                lines.append(
                    f"status={item.get('status', 'unknown')} "
                    f"category={item.get('category', 'unknown')}"
                )
                lines.append(f"path={item.get('path', '')}")
                lines.append(
                    "capabilities: "
                    + "; ".join(item.get("capabilities", []) or ["none"])
                )
                lines.append(
                    "in-app uses: " + "; ".join(item.get("app_uses", []) or ["none"])
                )
                lines.append(
                    "strategic plays: "
                    + "; ".join(item.get("strategic_plays", []) or ["none"])
                )
                lines.append("")

            self.registry_text.setPlainText("\n".join(lines))
        except Exception as exc:
            self.registry_text.setPlainText(f"Failed to build model registry: {exc}")

