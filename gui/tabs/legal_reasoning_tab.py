"""
Legal Reasoning Tab - AEDIS High-Fidelity Analysis
Unified interface for complex legal reasoning and synthetic litigation.
"""

import json
from html import escape
from datetime import datetime
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
    QPushButton, QComboBox, QCheckBox, QGroupBox, QSplitter, 
    QTextBrowser, QMessageBox, QFileDialog, QLineEdit, QScrollArea
)

from .status_presenter import TabStatusPresenter
from ..ui import JobStatusWidget, ResultsSummaryBox, KnowledgeBaseBrowser
from .default_paths import get_default_dialog_dir
from .workers import LegalReasoningWorker
from gui.core.base_tab import BaseTab

class LegalReasoningTab(BaseTab):
    reasoning_completed = Signal(dict)
    reasoning_error = Signal(str)

    def __init__(self, asyncio_thread: Optional[Any] = None, parent=None):
        super().__init__("Legal Reasoning", asyncio_thread, parent)
        self.current_results = None
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        # Header
        title = QLabel("Legal Reasoning & Strategic Analysis")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        self.main_layout.addWidget(title)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.main_splitter)

        # LEFT: Input & Context
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 1. Knowledge Base Integration
        kb_group = QGroupBox("1. Load from Knowledge Base")
        kb_layout = QVBoxLayout(kb_group)
        self.kb_browser = KnowledgeBaseBrowser()
        self.kb_browser.document_selected.connect(self.on_kb_document_selected)
        kb_layout.addWidget(self.kb_browser)
        kb_group.setLayout(kb_layout)
        left_layout.addWidget(kb_group)

        # 2. Manual Input
        input_group = QGroupBox("2. Target Document / Context")
        input_layout = QVBoxLayout(input_group)
        
        path_row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("Select file path...")
        path_row.addWidget(self.file_path)
        self.browse_btn = QPushButton("...")
        self.browse_btn.setMaximumWidth(40)
        self.browse_btn.clicked.connect(self.browse_file)
        path_row.addWidget(self.browse_btn)
        input_layout.addLayout(path_row)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Enter legal scenario or paste document text...")
        self.input_text.setMinimumHeight(150)
        input_layout.addWidget(self.input_text)
        left_layout.addWidget(input_group)

        # 3. Strategy
        strategy_group = QGroupBox("3. Reasoning Strategy")
        strategy_layout = QVBoxLayout(strategy_group)
        
        self.reasoning_type_combo = QComboBox()
        self.reasoning_type_combo.addItems([
            "General Analysis", "Case Law Analysis", "Statutory Interpretation", 
            "Contract Analysis", "Precedent Analysis", "Legal Risk Assessment",
            "Adversarial Shadow Mode"
        ])
        strategy_layout.addWidget(self.reasoning_type_combo)
        
        self.deep_analysis = QCheckBox("Deep Semantic Analysis (Multi-Pass)")
        self.deep_analysis.setChecked(True)
        strategy_layout.addWidget(self.deep_analysis)
        left_layout.addWidget(strategy_group)

        # 4. Action
        self.analyze_button = QPushButton("⚡ RUN ANALYSIS")
        self.analyze_button.setMinimumHeight(50)
        self.analyze_button.setStyleSheet("background-color: #0e639c; color: white; font-weight: bold; font-size: 14px;")
        self.analyze_button.clicked.connect(self.start_reasoning)
        left_layout.addWidget(self.analyze_button)
        
        left_layout.addStretch()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left_widget)
        self.main_splitter.addWidget(scroll)

        # RIGHT: Results & Findings
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.results_browser = QTextBrowser()
        self.results_browser.setOpenExternalLinks(True)
        right_layout.addWidget(self.results_browser)
        
        self.status_label = QLabel("Ready") # The QLabel for status is still needed for BaseTab to set text/style
        right_layout.addWidget(self.status_label)
        
        self.job_status = JobStatusWidget("Reasoning Job")
        right_layout.addWidget(self.job_status)

        self.results_summary = ResultsSummaryBox()
        right_layout.addWidget(self.results_summary)

        self.main_splitter.addWidget(right_widget)
        self.main_splitter.setSizes([450, 750])

    def connect_signals(self):
        self.file_path.textChanged.connect(lambda: self.status.info("Input adjusted.") if self.current_results else None)

    def on_kb_document_selected(self, doc):
        self.input_text.setPlainText(doc.get("content", ""))
        self.file_path.setText(doc.get("file_path", ""))
        self.status.success(f"Loaded from KB: {doc.get('title')}")

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Document", get_default_dialog_dir(), 
                                            "Legal Docs (*.pdf *.docx *.txt *.md);;All Files (*)")
        if path:
            self.file_path.setText(path)
            self.input_text.clear()

    def start_reasoning(self):
        text = self.input_text.toPlainText().strip()
        path = self.file_path.text().strip()
        if not text and not path:
            self.status.warn("Input required.")
            return

        self.job_status.set_status("running", "Initializing engine...")
        self.analyze_button.setEnabled(False)
        self.status.loading("Running legal analysis...")

        options = {
            "reasoning_type": self.reasoning_type_combo.currentText(),
            "deep_analysis": self.deep_analysis.isChecked(),
        }

        worker_instance = LegalReasoningWorker(self.asyncio_thread, path, text, options["reasoning_type"], options=options)
        worker_instance.result_ready.connect(self.on_reasoning_finished)
        # BaseTab handles error_occurred, so no need to connect directly
        self.start_worker(worker_instance)

    def on_reasoning_finished(self, results):
        self.current_results = results
        self.display_results(results)
        self.job_status.set_status("success", "Complete")
        self.status.success("Reasoning complete.")
        self.analyze_button.setEnabled(True)



    def display_results(self, results):
        html = self.format_results_html(results)
        self.results_browser.setHtml(html)

    def format_results_html(self, results):
        def _safe(v): return escape(str(v or ""))
        data = results.get("data") or results
        
        html = [f"""
        <html><body style='font-family: sans-serif; background-color: #1e1e1e; color: #e0e0e0; padding: 20px;'>
        <h2 style='color: #4dabf7;'>⚖️ Legal Analysis Results</h2>
        <div style='background: #252526; border-left: 4px solid #4CAF50; padding: 15px; margin: 10px 0;'>
            <b>Conclusion:</b><br>{_safe(data.get("conclusion") or data.get("summary", "No conclusion."))}
        </div>
        <h3>Detailed Reasoning</h3>
        <pre style='background: #2d2d2d; padding: 15px; border: 1px solid #3e3e3e; white-space: pre-wrap;'>{_safe(data.get("reasoning") or data.get("analysis", ""))}</pre>
        """]
        
        issues = data.get("legal_issues", []) or data.get("evidence", [])
        if issues:
            html.append("<h3>Verified Evidence & Issues</h3>")
            for issue in issues:
                desc = issue.get("description") or str(issue)
                html.append(f"<p>• {_safe(desc)} (Conf: {issue.get('confidence', 0.0):.2f})</p>")
        
        recs = data.get("recommendations", [])
        if recs:
            html.append("<h3>💡 Recommendations</h3><ul>")
            for r in recs: html.append(f"<li style='color: #63e6be;'>{_safe(r)}</li>")
            html.append("</ul>")
            
        html.append("</body></html>")
        return "\n".join(html)
