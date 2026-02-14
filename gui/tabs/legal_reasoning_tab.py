"""
Legal Reasoning Tab - GUI component for legal reasoning operations

This tab provides the interface for legal reasoning and analysis
using the legal AI agents.
"""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import PySide6.QtWidgets as _QtWidgets  # noqa: F401
    import PySide6.QtCore as _QtCore        # noqa: F401
    import PySide6.QtGui as _QtGui          # noqa: F401

try:
    from PySide6.QtWidgets import (  # noqa: E402
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QTextEdit,
        QPushButton,
        QComboBox,
        QGroupBox,
        QProgressBar,
        QSplitter,
        QTextBrowser,
        QMessageBox,
        QCheckBox,
    )
    from PySide6.QtCore import Qt, Signal, QThread  # noqa: E402
    from PySide6.QtGui import QFont, QPalette, QColor  # noqa: E402
except ImportError:
    # Fallback for systems without PySide6
    QWidget = object
    QVBoxLayout = QHBoxLayout = QLabel = QTextEdit = QPushButton = object
    QComboBox = QGroupBox = QProgressBar = QSplitter = QTextBrowser = object
    QMessageBox = QCheckBox = object
    Qt = QThread = Signal = object
    QFont = QPalette = QColor = object

from .status_presenter import TabStatusPresenter  # noqa: E402
from ..ui import JobStatusWidget, ResultsSummaryBox  # noqa: E402
from .workers import LegalReasoningWorker, LegalReasoningDetailsDialog  # noqa: E402


class LegalReasoningTab(QWidget):
    """Tab for legal reasoning operations."""

    # Signals
    reasoning_completed = Signal(dict)
    reasoning_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.current_results = None
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Legal Reasoning")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left panel - Input
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Input group
        input_group = QGroupBox("Legal Query")
        input_layout = QVBoxLayout(input_group)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Enter legal question or scenario to analyze...")
        input_layout.addWidget(self.input_text)

        # Reasoning options
        options_layout = QVBoxLayout()

        # Reasoning type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Reasoning Type:"))

        self.reasoning_type_combo = QComboBox()
        self.reasoning_type_combo.addItems([
            "General Analysis",
            "Case Law Analysis",
            "Statutory Interpretation",
            "Contract Analysis",
            "Precedent Analysis",
            "Legal Risk Assessment"
        ])
        type_layout.addWidget(self.reasoning_type_combo)
        type_layout.addStretch()
        options_layout.addLayout(type_layout)

        # Options checkboxes
        self.include_precedents = QCheckBox("Include Precedents")
        self.include_precedents.setChecked(True)
        options_layout.addWidget(self.include_precedents)

        self.include_statutes = QCheckBox("Include Statutes")
        self.include_statutes.setChecked(True)
        options_layout.addWidget(self.include_statutes)

        self.deep_analysis = QCheckBox("Deep Analysis")
        options_layout.addWidget(self.deep_analysis)

        input_layout.addLayout(options_layout)
        left_layout.addWidget(input_group)

        # Control buttons
        button_layout = QHBoxLayout()

        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        button_layout.addWidget(self.analyze_button)

        self.clear_button = QPushButton("Clear")
        button_layout.addWidget(self.clear_button)

        button_layout.addStretch()
        left_layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        left_layout.addWidget(self.status_label)
        self.status = TabStatusPresenter(self, self.status_label, source="Legal Reasoning")
        self.job_status = JobStatusWidget("Legal Reasoning Job")
        left_layout.addWidget(self.job_status)

        self.results_summary = ResultsSummaryBox()
        left_layout.addWidget(self.results_summary)

        splitter.addWidget(left_widget)

        # Right panel - Results
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Results group
        results_group = QGroupBox("Legal Analysis Results")
        results_layout = QVBoxLayout(results_group)

        self.results_browser = QTextBrowser()
        self.results_browser.setOpenExternalLinks(True)
        results_layout.addWidget(self.results_browser)

        right_layout.addWidget(results_group)

        # Export buttons
        export_layout = QHBoxLayout()

        self.export_json_button = QPushButton("Export JSON")
        self.export_json_button.setEnabled(False)
        export_layout.addWidget(self.export_json_button)

        self.export_html_button = QPushButton("Export HTML")
        self.export_html_button.setEnabled(False)
        export_layout.addWidget(self.export_html_button)

        export_layout.addStretch()
        right_layout.addLayout(export_layout)

        splitter.addWidget(right_widget)

        # Set splitter proportions
        splitter.setSizes([400, 400])

    def connect_signals(self):
        """Connect UI signals to handlers."""
        self.analyze_button.clicked.connect(self.start_reasoning)
        self.clear_button.clicked.connect(self.clear_results)
        self.export_json_button.clicked.connect(self.export_json)
        self.export_html_button.clicked.connect(self.export_html)

    def start_reasoning(self):
        """Start legal reasoning process."""
        text = self.input_text.toPlainText().strip()
        if not text:
            self.status.warn("Please enter a legal question or scenario to analyze.")
            return

        # Get reasoning options
        options = {
            "reasoning_type": self.reasoning_type_combo.currentText(),
            "include_precedents": self.include_precedents.isChecked(),
            "include_statutes": self.include_statutes.isChecked(),
            "deep_analysis": self.deep_analysis.isChecked(),
        }

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.analyze_button.setEnabled(False)
        self.analyze_button.setText("Analyzing...")

        # Start worker thread
        self.job_status.set_status("running", "Analysis in progress")
        self.status.loading("Running legal analysis...")
        self.worker = LegalReasoningWorker(
            asyncio_thread=None,
            file_path="",
            text_input=text,
            reasoning_type=options.get("reasoning_type", "General Analysis"),
            options=options,
        )
        self.worker.result_ready.connect(self.on_reasoning_finished)
        self.worker.error_occurred.connect(self.on_reasoning_error)
        self.worker.start()

    def on_reasoning_finished(self, results):
        """Handle successful reasoning completion."""
        self.current_results = results
        self.display_results(results)
        self.cleanup_worker()

        self.job_status.set_status("success", "Completed")
        self.results_summary.set_summary(
            "Legal reasoning completed successfully",
            "Displayed in Legal Analysis Results (export JSON/HTML optional)",
            "Run Console",
        )
        self.status.success("Legal reasoning complete")

        # Emit signal
        self.reasoning_completed.emit(results)

    def on_reasoning_error(self, error_msg):
        """Handle reasoning error."""
        self.job_status.set_status("failed", "Analysis failed")
        self.results_summary.set_summary(
            f"Legal reasoning failed: {error_msg}",
            "No output generated",
            "Run Console",
        )
        self.status.error(f"Failed to perform legal analysis: {error_msg}")
        self.cleanup_worker()

        # Emit signal
        self.reasoning_error.emit(error_msg)

    def cleanup_worker(self):
        """Clean up worker thread."""
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

        self.progress_bar.setVisible(False)
        self.analyze_button.setEnabled(True)
        self.analyze_button.setText("Analyze")

    def display_results(self, results):
        """Display reasoning results."""
        # Format results as HTML for better display
        html_content = self.format_results_html(results)
        self.results_browser.setHtml(html_content)

        # Enable export buttons
        self.export_json_button.setEnabled(True)
        self.export_html_button.setEnabled(True)

    def format_results_html(self, results):  # noqa: C901
        """Format results as HTML for display."""
        html = ["<html><body>"]

        # Analysis summary
        if "analysis" in results:
            analysis = results["analysis"]
            html.append("<h2>Legal Analysis</h2>")
            html.append(f"<p><strong>Conclusion:</strong> {analysis.get('conclusion', 'N/A')}</p>")

            if "confidence" in analysis:
                html.append(f"<p><strong>Confidence:</strong> {analysis['confidence']:.2f}</p>")

            if "reasoning" in analysis:
                html.append("<h3>Reasoning</h3>")
                html.append(f"<p>{analysis['reasoning']}</p>")

        # Supporting evidence
        if "evidence" in results:
            evidence = results["evidence"]
            html.append("<h2>Supporting Evidence</h2>")

            if "precedents" in evidence and evidence["precedents"]:
                html.append("<h3>Relevant Precedents</h3><ul>")
                for precedent in evidence["precedents"]:
                    html.append(f"<li>{precedent}</li>")
                html.append("</ul>")

            if "statutes" in evidence and evidence["statutes"]:
                html.append("<h3>Relevant Statutes</h3><ul>")
                for statute in evidence["statutes"]:
                    html.append(f"<li>{statute}</li>")
                html.append("</ul>")

        # Recommendations
        if "recommendations" in results:
            html.append("<h2>Recommendations</h2><ul>")
            for rec in results["recommendations"]:
                html.append(f"<li>{rec}</li>")
            html.append("</ul>")

        # Risks
        if "risks" in results:
            html.append("<h2>Risks Identified</h2><ul>")
            for risk in results["risks"]:
                html.append(f"<li>{risk}</li>")
            html.append("</ul>")

        html.append("</body></html>")
        return "\n".join(html)

    def clear_results(self):
        """Clear all results and input."""
        self.input_text.clear()
        self.results_browser.clear()
        self.export_json_button.setEnabled(False)
        self.export_html_button.setEnabled(False)
        self.current_results = None
        self.job_status.reset()
        self.results_summary.set_summary("No run yet", "N/A", "Run Console")

    def export_json(self):
        """Export results to JSON file."""
        if not self.current_results:
            return

        try:
            from PySide6.QtWidgets import QFileDialog  # noqa: E402
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save JSON", "", "JSON files (*.json)"
            )
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_results, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "Export Successful", "Results exported to JSON.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export JSON: {e}")

    def export_html(self):
        """Export results to HTML file."""
        if not self.current_results:
            return

        try:
            from PySide6.QtWidgets import QFileDialog  # noqa: E402
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save HTML", "", "HTML files (*.html)"
            )
            if file_path:
                html_content = self.format_results_html(self.current_results)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                QMessageBox.information(self, "Export Successful", "Results exported to HTML.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export HTML: {e}")
