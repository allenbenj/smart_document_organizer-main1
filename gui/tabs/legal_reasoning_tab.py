"""
Legal Reasoning Tab - GUI component for legal reasoning operations

This tab provides the interface for legal reasoning and analysis
using the legal AI agents.
"""

import json
from html import escape
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
        QCheckBox,
        QGroupBox,
        QProgressBar,
        QSplitter,
        QTextBrowser,
        QMessageBox,
        QFileDialog,
        QLineEdit,
    )
    from PySide6.QtCore import Qt, Signal, QThread  # noqa: E402
    from PySide6.QtGui import QFont, QPalette, QColor  # noqa: E402
except ImportError:
    # Fallback for systems without PySide6
    QWidget = object
    QVBoxLayout = QHBoxLayout = QLabel = QTextEdit = QPushButton = object
    QComboBox = QCheckBox = QGroupBox = QProgressBar = QSplitter = QTextBrowser = object
    QMessageBox = QFileDialog = QLineEdit = object
    Qt = QThread = Signal = object
    QFont = QPalette = QColor = object

from .status_presenter import TabStatusPresenter  # noqa: E402
from ..ui import JobStatusWidget, ResultsSummaryBox  # noqa: E402
from .default_paths import get_default_dialog_dir  # noqa: E402
from .workers import LegalReasoningWorker  # noqa: E402


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
        title = QLabel("Legal Reasoning & Analysis")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)

        # Main splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(self.main_splitter)

        # Left panel - Input
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # File Selection
        file_group = QGroupBox("Target Document")
        file_layout = QVBoxLayout(file_group)
        
        file_row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("Select file...")
        file_row.addWidget(self.file_path)
        self.browse_file_btn = QPushButton("...")
        self.browse_file_btn.setMaximumWidth(40)
        self.browse_file_btn.clicked.connect(self.browse_file)
        file_row.addWidget(self.browse_file_btn)
        file_layout.addLayout(file_row)
        left_layout.addWidget(file_group)

        # Input group
        input_group = QGroupBox("Query Context")
        input_layout = QVBoxLayout(input_group)
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Enter legal scenario...")
        self.input_text.setMinimumHeight(200)
        input_layout.addWidget(self.input_text)
        left_layout.addWidget(input_group)

        # Options
        options_group = QGroupBox("Analysis Mode")
        options_layout = QVBoxLayout(options_group)
        self.reasoning_type_combo = QComboBox()
        self.reasoning_type_combo.addItems([
            "General Analysis", 
            "Case Law Analysis", 
            "Statutory Interpretation", 
            "Contract Analysis", 
            "Precedent Analysis", 
            "Legal Risk Assessment"
        ])
        options_layout.addWidget(self.reasoning_type_combo)
        
        self.deep_analysis = QCheckBox("Deep Analysis")
        options_layout.addWidget(self.deep_analysis)
        left_layout.addWidget(options_group)

        self.analyze_button = QPushButton("⚡ RUN ANALYSIS")
        self.analyze_button.setStyleSheet("""
            QPushButton {
                background-color: #0e639c; 
                color: white; 
                font-weight: bold; 
                padding: 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        left_layout.addWidget(self.analyze_button)
        
        left_layout.addStretch()
        
        # Wrap left widget in a scroll area for small windows
        from PySide6.QtWidgets import QScrollArea
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_widget)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.main_splitter.addWidget(left_scroll)

        # Right panel - Results
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.results_browser = QTextBrowser()
        self.results_browser.setOpenExternalLinks(True)
        right_layout.addWidget(self.results_browser)
        
        # Status & Summary area
        self.status_label = QLabel("Ready")
        right_layout.addWidget(self.status_label)
        self.status = TabStatusPresenter(self, self.status_label, source="Legal Reasoning")
        
        self.job_status = JobStatusWidget("Legal Reasoning Job")
        right_layout.addWidget(self.job_status)

        self.results_summary = ResultsSummaryBox()
        right_layout.addWidget(self.results_summary)

        self.main_splitter.addWidget(right_widget)
        
        # Proportions: 35% left, 65% right
        self.main_splitter.setSizes([450, 850])

    def connect_signals(self):
        """Connect UI signals to handlers."""
        self.analyze_button.clicked.connect(self.start_reasoning)
        self.file_path.textChanged.connect(self.clear_results_on_input)
        self.input_text.textChanged.connect(self.clear_results_on_input)

    def clear_results_on_input(self):
        """Partially clear results when input changes to avoid confusion."""
        if self.current_results:
            self.status.info("Input changed - ready for new analysis")

    def browse_file(self):
        """Browse for a single file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Document",
            get_default_dialog_dir(self.file_path.text()),
            "Legal Documents (*.pdf *.docx *.txt *.md);;All Files (*)",
        )
        if file_path:
            self.file_path.setText(file_path)
            self.input_text.clear()

    def start_reasoning(self):
        """Start legal reasoning process."""
        text = self.input_text.toPlainText().strip()
        file_path = self.file_path.text().strip()
        
        if not text and not file_path:
            self.status.warn("Please enter text or select a file.")
            return

        # Get reasoning options
        options = {
            "reasoning_type": self.reasoning_type_combo.currentText(),
            "deep_analysis": self.deep_analysis.isChecked(),
        }

        if self.worker is not None and self.worker.isRunning():
            self.status.warn("Analysis already running. Please wait for completion.")
            return

        # Show progress
        self.analyze_button.setEnabled(False)
        self.analyze_button.setText("ANALYZING...")

        # Start worker thread
        self.job_status.set_status("running", "Running legal analysis engine...")
        self.status.loading("Running legal analysis...")
        
        self.worker = LegalReasoningWorker(
            asyncio_thread=None,
            file_path=file_path,
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
            "Review findings in the results browser.",
            "Run Console",
        )
        self.status.success("Legal reasoning complete")
        self.reasoning_completed.emit(results)

    def on_reasoning_error(self, error_msg):
        """Handle reasoning error."""
        self.job_status.set_status("failed", "Analysis failed")
        self.results_summary.set_summary(
            f"Error: {error_msg}",
            "No output generated",
            "Run Console",
        )
        self.status.error(f"Analysis failed: {error_msg}")
        self.cleanup_worker()
        self.reasoning_error.emit(error_msg)

    def cleanup_worker(self):
        """Clean up worker thread."""
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        self.analyze_button.setEnabled(True)
        self.analyze_button.setText("⚡ RUN ANALYSIS")

    def display_results(self, results):
        """Display reasoning results."""
        html_content = self.format_results_html(results)
        self.results_browser.setHtml(html_content)

    def format_results_html(self, results):  # noqa: C901
        """Format results as HTML for display with a professional dark theme."""
        def _safe(value):
            return escape(str(value if value is not None else ""))

        html = ["""
        <html>
        <head>
            <style>
                body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #1e1e1e; color: #e0e0e0; line-height: 1.6; padding: 20px; }
                h2 { color: #4dabf7; border-bottom: 2px solid #3e3e3e; padding-bottom: 8px; margin-top: 30px; }
                h3 { color: #91a7ff; margin-top: 20px; }
                .conclusion { background-color: #252526; border-left: 4px solid #4CAF50; padding: 15px; border-radius: 4px; margin: 10px 0; font-size: 1.1em; }
                .reasoning { background-color: #2d2d2d; padding: 15px; border-radius: 4px; border: 1px solid #3e3e3e; white-space: pre-wrap; font-family: 'Consolas', monospace; }
                .metadata { color: #888; font-size: 0.9em; margin-bottom: 20px; }
                ul { padding-left: 20px; }
                li { margin-bottom: 8px; }
                .risk-item { color: #ff8787; }
                .rec-item { color: #63e6be; }
            </style>
        </head>
        <body>
        """]

        # Handle different result structures (from direct result or nested data)
        data = results.get("data") if isinstance(results.get("data"), dict) else results
        
        # Analysis summary
        html.append("<h2>⚖️ Legal Analysis Results</h2>")
        
        conclusion = data.get("conclusion") or data.get("summary") or "No conclusion provided."
        html.append("<h3>Final Conclusion</h3>")
        html.append(f"<div class='conclusion'>{_safe(conclusion)}</div>")

        reasoning = data.get("reasoning") or data.get("analysis") or "No detailed reasoning available."
        html.append("<h3>Detailed Reasoning</h3>")
        html.append(f"<div class='reasoning'>{_safe(reasoning)}</div>")

        # Supporting evidence (with NLI verification)
        evidence = data.get("legal_issues", [])
        if not evidence:
            evidence = data.get("evidence", [])
            
        if evidence:
            html.append("<h2>📚 Verified Evidence & Issues</h2>")
            for issue in evidence:
                desc = issue.get("description") or str(issue)
                confidence = issue.get("confidence", 0.0)
                entities = issue.get("entities_involved", [])
                
                html.append(f"<h3>Issue: {_safe(desc)}</h3>")
                html.append(f"<div class='metadata'>Base Confidence: {confidence:.2f}</div>")
                
                if entities:
                    html.append("<p><b>Parties Involved:</b> " + ", ".join([e.get("text") for e in entities if "text" in e]) + "</p>")

        # Actionable Recommendations
        recs = data.get("recommendations", [])
        if recs:
            html.append("<h2>💡 Recommendations</h2><ul>")
            for rec in recs:
                html.append(f"<li class='rec-item'>{_safe(rec)}</li>")
            html.append("</ul>")

        # Risks
        risks = data.get("risks", [])
        if risks:
            html.append("<h2>⚠️ Identified Risks</h2><ul>")
            for risk in risks:
                html.append(f"<li class='risk-item'>{_safe(risk)}</li>")
            html.append("</ul>")

        html.append("</body></html>")
        return "\n".join(html)

    def closeEvent(self, event):
        """Stop background work on tab close."""
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(1000)
        super().closeEvent(event)
