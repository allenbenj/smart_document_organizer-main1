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
from .default_paths import get_default_dialog_dir  # noqa: E402


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
        self.browse_btn = QPushButton("Browse File")
        self.browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(QLabel("File:"))
        file_layout.addWidget(self.file_path)
        file_layout.addWidget(self.browse_btn)
        input_layout.addLayout(file_layout)

        # Folder selection
        folder_layout = QHBoxLayout()
        self.folder_path = QLineEdit()
        self.folder_path.setPlaceholderText("Or select folder...")
        self.browse_folder_btn = QPushButton("Browse Folder")
        self.browse_folder_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(QLabel("Folder:"))
        folder_layout.addWidget(self.folder_path)
        folder_layout.addWidget(self.browse_folder_btn)
        input_layout.addLayout(folder_layout)

        # Text input
        input_layout.addWidget(QLabel("Or enter text directly:"))
        self.text_input = QTextEdit()
        self.text_input.setMaximumHeight(100)
        self.text_input.setPlaceholderText("Enter document text for analysis...")
        input_layout.addWidget(self.text_input)

        input_group.setLayout(input_layout)

        # Analysis Options Group
        options_group = QGroupBox("Strategic Analysis Settings")
        options_layout = QVBoxLayout()

        # Analysis type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Core Engine:"))
        self.analysis_combo = QComboBox()
        self.analysis_combo.addItems(
            [
                "Strategic Clustering", 
                "Summarization",
                "Topic Identification",
                "Sentiment Analysis",
                "Key Phrases",
            ]
        )
        type_layout.addWidget(self.analysis_combo)
        options_layout.addLayout(type_layout)

        # Strategic Refinements (New Intelligence Layer)
        refinement_label = QLabel("Intelligence Refinements:")
        refinement_label.setStyleSheet("font-weight: bold; color: #4dabf7; margin-top: 10px;")
        options_layout.addWidget(refinement_label)

        self.auto_label_themes = QCheckBox("Auto-Label Themes (Knowledge Graph Prep)")
        self.auto_label_themes.setToolTip("Uses LLM to name clusters based on legal theory (e.g., 'Discovery Abuse').")
        self.auto_label_themes.setChecked(True)
        options_layout.addWidget(self.auto_label_themes)

        self.outlier_detection = QCheckBox("Smoking Gun Detection (Outlier Analysis)")
        self.outlier_detection.setToolTip("Flags sentences that don't fit any theme—often where the unique evidence is hidden.")
        options_layout.addWidget(self.outlier_detection)

        self.pattern_finder = QCheckBox("Cross-Document Pattern Finder")
        self.pattern_finder.setToolTip("Extracts cluster vectors for searching similar misconduct patterns in other cases.")
        options_layout.addWidget(self.pattern_finder)

        self.denoise_boilerplate = QCheckBox("Boilerplate De-noising")
        self.denoise_boilerplate.setToolTip("Automatically identifies and suppresses administrative/procedural filler.")
        options_layout.addWidget(self.denoise_boilerplate)

        # Advanced options
        self.deep_analysis = QCheckBox("Enable deep semantic analysis (High-Res)")
        options_layout.addWidget(self.deep_analysis)

        options_group.setLayout(options_layout)

        # Actions Group
        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout()

        self.analyze_btn = QPushButton("Analyze Document")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.clear_btn = QPushButton("Clear Results")
        self.export_btn = QPushButton("Export Results")
        
        # New: Expert Review Bridge
        self.verify_btn = QPushButton("Verify Findings in Knowledge Graph")
        self.verify_btn.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.verify_btn.setEnabled(False)
        self.verify_btn.clicked.connect(self.open_memory_review)

        actions_layout.addWidget(self.analyze_btn)
        actions_layout.addWidget(self.cancel_btn)
        actions_layout.addWidget(self.verify_btn)
        actions_layout.addWidget(self.clear_btn)
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
        self.cancel_btn.clicked.connect(self.cancel_analysis)
        self.clear_btn.clicked.connect(self.clear_results)
        self.export_btn.clicked.connect(self.export_results)

    def browse_file(self):
        """Browse for document file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Document",
            get_default_dialog_dir(self.folder_path.text() or self.file_path.text()),
            "All Files (*);;Text Files (*.txt);;PDF Files (*.pdf);;Word Files (*.docx);;Markdown (*.md)",
        )
        if file_path:
            self.file_path.setText(file_path)
            self.folder_path.clear()

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
        options = {
            "deep_analysis": self.deep_analysis.isChecked(),
            "auto_label": self.auto_label_themes.isChecked(),
            "outlier_detection": self.outlier_detection.isChecked(),
            "pattern_finder": self.pattern_finder.isChecked(),
            "denoise": self.denoise_boilerplate.isChecked(),
        }

        try:
            if self.worker is not None and self.worker.isRunning():
                self.status.warn("Analysis already running. Please wait for completion.")
                return

            self.results_text.clear()
            self.results_text.append(f"Starting {analysis_type.lower()}...")
            self.job_status.set_status("running", f"{analysis_type} in progress")
            self.status.loading(f"Running {analysis_type.lower()}...")
            self.cancel_btn.setEnabled(True)

            # Create worker thread
            self.worker = SemanticAnalysisWorker(
                self.asyncio_thread,
                file_path,
                text_input,
                analysis_type,
                options
            )
            self.worker.result_ready.connect(self.on_analysis_result)
            self.worker.error_occurred.connect(self.on_analysis_error)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.start()

        except Exception as e:
            self.cancel_btn.setEnabled(False)
            self.job_status.set_status("failed", "Failed to start")
            self.results_summary.set_summary(
                "Failed to start semantic analysis",
                "No output generated",
                "See Run Console / status line",
            )
            self.status.error(f"Failed to start analysis: {str(e)}")

    def clear_results(self):
        """Clear all results and inputs."""
        self.cancel_btn.setEnabled(False)
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

    def cancel_analysis(self):
        """Cancel the ongoing analysis."""
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.status.warn("Analysis cancelled")
            self.cancel_btn.setEnabled(False)

    def on_analysis_result(self, result):
        """Handle analysis results with support for thematic clustering and auto-labeling."""
        self.worker = None
        self.cancel_btn.setEnabled(False)
        self.results_text.clear()
        
        # Check for clustering specific result (Formal Discovery Service format)
        if isinstance(result, dict) and result.get("type") == "strategic_discovery":
            self.results_text.append("AEDIS STRATEGIC INTELLIGENCE: DISCOVERY PROPOSALS")
            self.results_text.append("=" * 60)
            data = result.get("data", {})
            themes = data.get("results", [])
            
            for theme in themes:
                self.results_text.append(f"\n[PROPOSAL: {theme.get('theme_label').upper()}]")
                self.results_text.append(f"Linked Evidence: {theme.get('evidence_count')} Items")
                self.results_text.append(f"Key Identifiers: {', '.join(theme.get('key_identifiers', []))}")
                self.results_text.append("-" * 40)
                self.results_text.append(f"Summary: {theme.get('summary')}")
            
            # Enable Human-in-the-Loop Review
            self.verify_btn.setEnabled(True)
            self.status.success("Discovery complete - Ready for Expert Verification")
        else:
            # Fallback for standard analysis
            if isinstance(result, dict) and "clusters" in result:
                self.results_text.append("AEDIS STRATEGIC INTELLIGENCE: THEMATIC CLUSTERS")
                self.results_text.append("=" * 60)
                clusters = result["clusters"]
                for theme, items in clusters.items():
                    header = f"\n[THEME: {theme.upper()}]" if not str(theme).isdigit() else f"\n[THEME {int(theme) + 1}]"
                    self.results_text.append(header)
                    self.results_text.append(f"Linked Evidence: {len(items)} Items")
                    self.results_text.append("-" * 40)
                    for item in items:
                        self.results_text.append(f" • {item}")
            else:
                self.results_text.append("Analysis Results:")
                self.results_text.append("-" * 50)
                if isinstance(result, dict):
                    for key, value in result.items():
                        self.results_text.append(f"{key}: {value}")
                else:
                    self.results_text.append(str(result))
                
        self.job_status.set_status("success", "Completed")

    def open_memory_review(self):
        """Bridge to the Memory Review tab for expert verification."""
        # Find the main window and switch tabs if possible
        parent = self.window()
        if hasattr(parent, "tab_widget"):
            # Search for 'Memory Review' tab
            for i in range(parent.tab_widget.count()):
                if parent.tab_widget.tabText(i) == "Memory Review":
                    parent.tab_widget.setCurrentIndex(i)
                    self.status.info("Switched to Memory Review for expert verification.")
                    return
        
        QMessageBox.information(self, "Expert Review", "Findings saved to database. Please open the 'Memory Review' tab to finalize.")
        self.results_summary.set_summary(
            "Semantic analysis completed successfully",
            "Visible in Analysis Results (use Export Results to save)",
            "Run Console",
        )
        self.status.success("Semantic analysis complete")

    def on_analysis_error(self, error_msg):
        """Handle analysis errors."""
        self.worker = None
        self.cancel_btn.setEnabled(False)
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
