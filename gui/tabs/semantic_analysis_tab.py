"""
Semantic Analysis Tab - GUI component for document semantic analysis

This module provides the UI for semantic analysis operations including
document summarization, topic identification, and content analysis.
"""


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import PySide6.QtWidgets as _QtWidgets  # noqa: F401
    import PySide6.QtCore as _QtCore        # noqa: F401
    import PySide6.QtGui as _QtGui          # noqa: F401

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
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
    QWidget,
)


class SemanticAnalysisTab(QWidget):
    """Tab for semantic analysis operations."""

    def __init__(self, asyncio_thread=None, parent=None):
        super().__init__(parent)
        self.asyncio_thread = asyncio_thread
        self.worker = None
        self.init_ui()

    def init_ui(self):
        """Initialize the semantic analysis tab UI."""
        layout = QVBoxLayout()

        # Title
        title = QLabel("Semantic Analysis")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Input Group
        input_group = QGroupBox("Document Input")
        input_layout = QVBoxLayout()

        # File selection
        file_layout = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("Select document file...")
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(QLabel("File:"))
        file_layout.addWidget(self.file_path)
        file_layout.addWidget(self.browse_btn)
        input_layout.addLayout(file_layout)

        # Text input
        input_layout.addWidget(QLabel("Or enter text directly:"))
        self.text_input = QTextEdit()
        self.text_input.setMaximumHeight(100)
        self.text_input.setPlaceholderText("Enter document text for analysis...")
        input_layout.addWidget(self.text_input)

        input_group.setLayout(input_layout)

        # Analysis Options Group
        options_group = QGroupBox("Analysis Options")
        options_layout = QVBoxLayout()

        # Analysis type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Analysis Type:"))
        self.analysis_combo = QComboBox()
        self.analysis_combo.addItems(
            [
                "Summarization",
                "Topic Identification",
                "Sentiment Analysis",
                "Key Phrases",
            ]
        )
        type_layout.addWidget(self.analysis_combo)
        options_layout.addLayout(type_layout)

        # Advanced options
        self.include_metadata = QCheckBox("Include metadata analysis")
        self.deep_analysis = QCheckBox("Enable deep semantic analysis")
        options_layout.addWidget(self.include_metadata)
        options_layout.addWidget(self.deep_analysis)

        options_group.setLayout(options_layout)

        # Actions Group
        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout()

        self.analyze_btn = QPushButton("Analyze Document")
        self.clear_btn = QPushButton("Clear Results")
        self.export_btn = QPushButton("Export Results")

        actions_layout.addWidget(self.analyze_btn)
        actions_layout.addWidget(self.clear_btn)
        actions_layout.addWidget(self.export_btn)
        actions_group.setLayout(actions_layout)

        # Feedback/status label
        self.status_label = QLabel("")
        self.status = TabStatusPresenter(self, self.status_label, source="Semantic Analysis")
        self.status.info("Ready")

        self.job_status = JobStatusWidget("Semantic Analysis Job")
        self.results_summary = ResultsSummaryBox()

        # Results Group
        results_group = QGroupBox("Analysis Results")
        results_layout = QVBoxLayout()

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(300)
        results_layout.addWidget(self.results_text)
        results_group.setLayout(results_layout)

        layout.addWidget(input_group)
        layout.addWidget(options_group)
        layout.addWidget(actions_group)
        layout.addWidget(self.status_label)
        layout.addWidget(self.job_status)
        layout.addWidget(self.results_summary)
        layout.addWidget(results_group)

        self.setLayout(layout)

        # Connect signals
        self.analyze_btn.clicked.connect(self.analyze_document)
        self.clear_btn.clicked.connect(self.clear_results)
        self.export_btn.clicked.connect(self.export_results)

    def browse_file(self):
        """Browse for document file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Document",
            "",
            "All Files (*);;Text Files (*.txt);;PDF Files (*.pdf);;Word Files (*.docx)",
        )
        if file_path:
            self.file_path.setText(file_path)

    def analyze_document(self):
        """Analyze document using semantic analyzer."""
        # Get input
        file_path = self.file_path.text().strip()
        text_input = self.text_input.toPlainText().strip()

        if not file_path and not text_input:
            self.status.warn("Please provide a file or text input.")
            return

        # Get options
        analysis_type = self.analysis_combo.currentText()
        include_metadata = self.include_metadata.isChecked()
        deep_analysis = self.deep_analysis.isChecked()

        try:
            self.results_text.clear()
            self.results_text.append(f"Starting {analysis_type.lower()}...")
            self.job_status.set_status("running", f"{analysis_type} in progress")
            self.status.loading(f"Running {analysis_type.lower()}...")

            # Create worker thread (store on self to avoid premature GC/thread destruction)
            self.worker = SemanticAnalysisWorker(
                self.asyncio_thread,
                file_path,
                text_input,
                analysis_type,
                include_metadata,
                deep_analysis,
            )
            self.worker.result_ready.connect(self.on_analysis_result)
            self.worker.error_occurred.connect(self.on_analysis_error)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.start()

        except Exception as e:
            self.job_status.set_status("failed", "Failed to start")
            self.results_summary.set_summary(
                "Failed to start semantic analysis",
                "No output generated",
                "See Run Console / status line",
            )
            self.status.error(f"Failed to start analysis: {str(e)}")

    def clear_results(self):
        """Clear all results and inputs."""
        self.results_text.clear()
        self.text_input.clear()
        self.file_path.clear()

    def export_results(self):
        """Export analysis results."""
        if not self.results_text.toPlainText():
            QMessageBox.warning(self, "Warning", "No results to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "analysis_results.txt", "Text Files (*.txt)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.results_text.toPlainText())
                QMessageBox.information(
                    self, "Success", "Results exported successfully."
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to export results: {str(e)}"
                )

    def on_analysis_result(self, result):
        """Handle analysis results."""
        self.worker = None
        self.results_text.clear()
        self.results_text.append("Analysis Results:")
        self.results_text.append("-" * 50)

        if isinstance(result, dict):
            for key, value in result.items():
                self.results_text.append(f"{key}: {value}")
        else:
            self.results_text.append(str(result))
        self.job_status.set_status("success", "Completed")
        self.results_summary.set_summary(
            "Semantic analysis completed successfully",
            "Visible in Analysis Results (use Export Results to save)",
            "Run Console",
        )
        self.status.success("Semantic analysis complete")

    def on_analysis_error(self, error_msg):
        """Handle analysis errors."""
        self.worker = None
        self.results_text.clear()
        self.results_text.append(f"Error: {error_msg}")
        self.job_status.set_status("failed", "Analysis failed")
        self.results_summary.set_summary(
            f"Semantic analysis failed: {error_msg}",
            "No output generated",
            "Run Console",
        )
        self.status.error(f"Analysis error: {error_msg}")


# Import here to avoid circular imports
from .status_presenter import TabStatusPresenter  # noqa: E402
from ..ui import JobStatusWidget, ResultsSummaryBox  # noqa: E402
from .workers import SemanticAnalysisWorker  # noqa: E402
