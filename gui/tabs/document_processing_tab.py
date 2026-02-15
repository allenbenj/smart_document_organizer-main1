"""
Document Processing Tab - GUI component for document processing operations

This tab provides the interface for processing documents using
the legal AI agents.
"""

import os
import re
from typing import Any, Optional

import requests

from ..services import api_client

# Runtime imports with fallback
PYSIDE6_AVAILABLE = False

try:
    from PySide6.QtWidgets import (  # noqa: E402
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QGroupBox,
        QProgressBar,
        QSplitter,
        QTextBrowser,
        QMessageBox,
        QFileDialog,
        QCheckBox,
        QListWidget,
        QListWidgetItem,
        QTextEdit,
        QLineEdit,
        QTableWidget,
        QTableWidgetItem,
    )
    from PySide6.QtCore import Qt, Signal, QThread  # noqa: E402
    from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent, QPalette, QColor  # noqa: E402
    PYSIDE6_AVAILABLE = True
except ImportError:
    # Runtime fallback - use Any to avoid type errors
    QWidget = Any  # type: ignore[misc,assignment]
    QVBoxLayout = Any  # type: ignore[misc,assignment]
    QHBoxLayout = Any  # type: ignore[misc,assignment]
    QLabel = Any  # type: ignore[misc,assignment]
    QPushButton = Any  # type: ignore[misc,assignment]
    QGroupBox = Any  # type: ignore[misc,assignment]
    QProgressBar = Any  # type: ignore[misc,assignment]
    QSplitter = Any  # type: ignore[misc,assignment]
    QTextBrowser = Any  # type: ignore[misc,assignment]
    QMessageBox = Any  # type: ignore[misc,assignment]
    QFileDialog = Any  # type: ignore[misc,assignment]
    QCheckBox = Any  # type: ignore[misc,assignment]
    QListWidget = Any  # type: ignore[misc,assignment]
    QListWidgetItem = Any  # type: ignore[misc,assignment]
    QTextEdit = Any  # type: ignore[misc,assignment]
    QLineEdit = Any  # type: ignore[misc,assignment]
    QTableWidget = Any  # type: ignore[misc,assignment]
    QTableWidgetItem = Any  # type: ignore[misc,assignment]
    Qt = Any  # type: ignore[misc,assignment]
    Signal = Any  # type: ignore[misc,assignment]
    QThread = Any  # type: ignore[misc,assignment]
    QFont = Any  # type: ignore[misc,assignment]
    QPalette = Any  # type: ignore[misc,assignment]
    QColor = Any  # type: ignore[misc,assignment]
    QDragEnterEvent = Any  # type: ignore[misc,assignment]
    QDropEvent = Any  # type: ignore[misc,assignment]

from .status_presenter import TabStatusPresenter  # noqa: E402
if PYSIDE6_AVAILABLE:
    from ..ui import JobStatusWidget, ResultsSummaryBox  # noqa: E402
from .workers import UploadManyFilesWorker  # noqa: E402


class DocumentOrganizationTab(QWidget):  # type: ignore[misc]
    """Tab for document processing operations."""

    # Signals
    processing_completed = Signal(dict)  # type: ignore[misc]
    processing_error = Signal(str)  # type: ignore[misc]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.current_results = None
        self.selected_files = []
        self.proposals_cache = []
        self.selected_proposal = None
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Document Processing")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left panel - Input
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # File selection group
        file_group = QGroupBox("Document Files")
        file_layout = QVBoxLayout(file_group)

        # File list
        self.file_list = QListWidget()
        self.file_list.setAcceptDrops(True)
        self.file_list.setDragEnabled(True)
        self.file_list.setSelectionMode(QListWidget.MultiSelection)
        file_layout.addWidget(self.file_list)

        # File buttons
        file_buttons_layout = QHBoxLayout()

        self.add_files_button = QPushButton("Add Files...")
        file_buttons_layout.addWidget(self.add_files_button)

        self.remove_files_button = QPushButton("Remove Selected")
        file_buttons_layout.addWidget(self.remove_files_button)

        self.clear_files_button = QPushButton("Clear All")
        file_buttons_layout.addWidget(self.clear_files_button)

        file_layout.addLayout(file_buttons_layout)
        left_layout.addWidget(file_group)

        # Processing options
        options_group = QGroupBox("Processing Options")
        options_layout = QVBoxLayout(options_group)

        self.extract_text_checkbox = QCheckBox("Extract Text Content")
        self.extract_text_checkbox.setChecked(True)
        options_layout.addWidget(self.extract_text_checkbox)

        self.extract_metadata_checkbox = QCheckBox("Extract Metadata")
        self.extract_metadata_checkbox.setChecked(True)
        options_layout.addWidget(self.extract_metadata_checkbox)

        self.analyze_content_checkbox = QCheckBox("Analyze Content")
        self.analyze_content_checkbox.setChecked(True)
        options_layout.addWidget(self.analyze_content_checkbox)

        self.generate_summary_checkbox = QCheckBox("Generate Summary")
        options_layout.addWidget(self.generate_summary_checkbox)

        left_layout.addWidget(options_group)

        # Organization workflow group (review/manage/refine)
        org_group = QGroupBox("Organization Workflow")
        org_layout = QVBoxLayout(org_group)

        root_row = QHBoxLayout()
        root_row.addWidget(QLabel("Folder scope:"))
        self.org_root_input = QLineEdit()
        self.org_root_input.setPlaceholderText(r"E:\... or /mnt/e/...")
        root_row.addWidget(self.org_root_input)
        self.org_browse_button = QPushButton("Browse Folder...")
        root_row.addWidget(self.org_browse_button)
        org_layout.addLayout(root_row)

        org_btn_row = QHBoxLayout()
        self.org_load_button = QPushButton("Review Proposals")
        self.org_generate_button = QPushButton("Generate Scoped")
        self.org_clear_button = QPushButton("Clear Scoped")
        org_btn_row.addWidget(self.org_load_button)
        org_btn_row.addWidget(self.org_generate_button)
        org_btn_row.addWidget(self.org_clear_button)
        org_layout.addLayout(org_btn_row)

        self.org_table = QTableWidget(0, 5)
        self.org_table.setHorizontalHeaderLabels(["ID", "Conf", "Current Path", "Folder", "Filename"])
        org_layout.addWidget(self.org_table)

        refine_row = QHBoxLayout()
        refine_row.addWidget(QLabel("Folder"))
        self.org_folder_input = QLineEdit()
        refine_row.addWidget(self.org_folder_input)
        refine_row.addWidget(QLabel("Filename"))
        self.org_filename_input = QLineEdit()
        refine_row.addWidget(self.org_filename_input)
        org_layout.addLayout(refine_row)

        self.org_note_input = QTextEdit()
        self.org_note_input.setPlaceholderText("Optional note...")
        self.org_note_input.setMaximumHeight(60)
        org_layout.addWidget(self.org_note_input)

        action_row = QHBoxLayout()
        self.org_approve_button = QPushButton("Approve")
        self.org_reject_button = QPushButton("Reject")
        self.org_edit_approve_button = QPushButton("Refine + Approve")
        action_row.addWidget(self.org_approve_button)
        action_row.addWidget(self.org_reject_button)
        action_row.addWidget(self.org_edit_approve_button)
        org_layout.addLayout(action_row)

        left_layout.addWidget(org_group)

        # Control buttons
        button_layout = QHBoxLayout()

        self.process_button = QPushButton("Process Documents")
        self.process_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #EF6C00;
            }
        """)
        button_layout.addWidget(self.process_button)

        button_layout.addStretch()
        left_layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        left_layout.addWidget(self.status_label)
        self.status = TabStatusPresenter(self, self.status_label, source="Document Processing")
        if PYSIDE6_AVAILABLE:
            self.job_status = JobStatusWidget("Document Processing Job")
            left_layout.addWidget(self.job_status)
            self.results_summary = ResultsSummaryBox()
            left_layout.addWidget(self.results_summary)

        splitter.addWidget(left_widget)

        # Right panel - Results
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Results group
        results_group = QGroupBox("Processing Results")
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

        self.export_text_button = QPushButton("Export Text")
        self.export_text_button.setEnabled(False)
        export_layout.addWidget(self.export_text_button)

        export_layout.addStretch()
        right_layout.addLayout(export_layout)

        splitter.addWidget(right_widget)

        # Set splitter proportions
        splitter.setSizes([400, 400])

    def connect_signals(self):
        """Connect UI signals to handlers."""
        self.add_files_button.clicked.connect(self.add_files)
        self.remove_files_button.clicked.connect(self.remove_selected_files)
        self.clear_files_button.clicked.connect(self.clear_files)
        self.process_button.clicked.connect(self.start_processing)
        self.export_json_button.clicked.connect(self.export_json)
        self.export_text_button.clicked.connect(self.export_text)

        self.org_browse_button.clicked.connect(self.org_pick_folder)
        self.org_load_button.clicked.connect(self.org_load_proposals)
        self.org_generate_button.clicked.connect(self.org_generate_scoped)
        self.org_clear_button.clicked.connect(self.org_clear_scoped)
        self.org_approve_button.clicked.connect(self.org_approve_selected)
        self.org_reject_button.clicked.connect(self.org_reject_selected)
        self.org_edit_approve_button.clicked.connect(self.org_edit_approve_selected)
        self.org_table.itemSelectionChanged.connect(self.org_on_selection_changed)

        # Drag and drop
        self.file_list.dragEnterEvent = self.drag_enter_event
        self.file_list.dropEvent = self.drop_event

    def drag_enter_event(self, event: QDragEnterEvent):
        """Handle drag enter events for file drops."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def drop_event(self, event: QDropEvent):
        """Handle file drop events."""
        urls = event.mimeData().urls()
        for url in urls:
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                self.add_file_to_list(file_path)
        event.acceptProposedAction()

    def add_files(self):
        """Add files through file dialog."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Documents",
            "",
            "All Files (*);;PDF Files (*.pdf);;Word Files (*.docx);;Text Files (*.txt)"
        )

        for file_path in file_paths:
            self.add_file_to_list(file_path)

    def add_file_to_list(self, file_path: str):
        """Add a file to the list widget."""
        if file_path not in self.selected_files:
            self.selected_files.append(file_path)
            file_name = os.path.basename(file_path)
            item = QListWidgetItem(file_name)
            item.setToolTip(file_path)
            self.file_list.addItem(item)

    def remove_selected_files(self):
        """Remove selected files from the list."""
        selected_items = self.file_list.selectedItems()
        for item in selected_items:
            row = self.file_list.row(item)
            if row < len(self.selected_files):
                del self.selected_files[row]
            self.file_list.takeItem(row)

    def clear_files(self):
        """Clear all files from the list."""
        self.file_list.clear()
        self.selected_files.clear()

    def start_processing(self):
        """Start document processing."""
        if not self.selected_files:
            self.status.warn("Please select at least one document to process.")
            return

        # Get processing options
        options = {
            "extract_text": self.extract_text_checkbox.isChecked(),
            "extract_metadata": self.extract_metadata_checkbox.isChecked(),
            "analyze_content": self.analyze_content_checkbox.isChecked(),
            "generate_summary": self.generate_summary_checkbox.isChecked(),
        }

        if self.worker is not None and self.worker.isRunning():
            self.status.warn("Processing already running. Please wait for completion.")
            return

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.process_button.setEnabled(False)
        self.process_button.setText("Processing...")
        if hasattr(self, "job_status"):
            self.job_status.set_status("running", "Processing selected documents")
        self.status.loading("Processing documents...")

        # Start worker thread
        self.worker = UploadManyFilesWorker(self.selected_files, options=options)
        self.worker.finished_ok.connect(self.on_processing_finished)
        self.worker.finished_err.connect(self.on_processing_error)
        self.worker.start()

    def on_processing_finished(self, results):
        """Handle successful processing completion."""
        normalized = results
        if isinstance(results, dict) and "data" in results and isinstance(results["data"], dict):
            normalized = results["data"]

        self.current_results = normalized
        self.display_results(normalized)
        self.cleanup_worker()
        if hasattr(self, "job_status"):
            self.job_status.set_status("success", "Completed")
        if hasattr(self, "results_summary"):
            self.results_summary.set_summary(
                "Document processing completed successfully",
                "Displayed in Processing Results (export JSON/Text optional)",
                "Run Console",
            )
        self.status.success("Document processing complete")

        # Emit signal
        self.processing_completed.emit(normalized if isinstance(normalized, dict) else {})

    def on_processing_error(self, error_msg):
        """Handle processing error."""
        if hasattr(self, "job_status"):
            self.job_status.set_status("failed", "Processing failed")
        if hasattr(self, "results_summary"):
            self.results_summary.set_summary(
                f"Document processing failed: {error_msg}",
                "No output generated",
                "Run Console",
            )
        self.status.error(f"Failed to process documents: {error_msg}")
        self.cleanup_worker()

        # Emit signal
        self.processing_error.emit(error_msg)

    def cleanup_worker(self):
        """Clean up worker thread."""
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

        self.progress_bar.setVisible(False)
        self.process_button.setEnabled(True)
        self.process_button.setText("Process Documents")

    def display_results(self, results):
        """Display processing results."""
        # Format results as HTML for better display
        html_content = self.format_results_html(results)
        self.results_browser.setHtml(html_content)

        # Enable export buttons
        self.export_json_button.setEnabled(True)
        self.export_text_button.setEnabled(True)

    def format_results_html(self, results):  # noqa: C901
        """Format results as HTML for display."""
        html = ["<html><body>"]

        # Process summary
        html.append("<h2>Document Processing Results</h2>")
        html.append(f"<p><strong>Files Processed:</strong> {len(results.get('files', []))}</p>")

        # Individual file results
        for file_result in results.get('files', []):
            file_name = file_result.get('filename', 'Unknown')
            html.append(f"<h3>{file_name}</h3>")

            if 'error' in file_result:
                html.append(f"<p style='color: red;'><strong>Error:</strong> {file_result['error']}</p>")
                continue

            # Metadata
            if 'metadata' in file_result:
                metadata = file_result['metadata']
                html.append("<h4>Metadata</h4><ul>")
                for key, value in metadata.items():
                    html.append(f"<li><strong>{key}:</strong> {value}</li>")
                html.append("</ul>")

            # Content preview
            if 'content' in file_result:
                content = file_result['content']
                preview = content[:500] + "..." if len(content) > 500 else content
                html.append("<h4>Content Preview</h4>")
                html.append(f"<pre>{preview}</pre>")

            # Analysis results
            if 'analysis' in file_result:
                analysis = file_result['analysis']
                html.append("<h4>Analysis</h4>")
                if 'entities' in analysis:
                    html.append("<p><strong>Entities Found:</strong></p><ul>")
                    for entity in analysis['entities'][:10]:  # Limit to 10
                        html.append(f"<li>{entity.get('text', '')} ({entity.get('label', '')})</li>")
                    if len(analysis['entities']) > 10:
                        html.append(f"<li>... and {len(analysis['entities']) - 10} more</li>")
                    html.append("</ul>")

            # Summary
            if 'summary' in file_result:
                html.append("<h4>Summary</h4>")
                html.append(f"<p>{file_result['summary']}</p>")

        html.append("</body></html>")
        return "\n".join(html)

    @staticmethod
    def _normalize_root_scope(path_str: str) -> str:
        s = str(path_str or "").strip().strip('"').strip("'")
        m = re.match(r"^([A-Za-z]):[\\/](.*)$", s)
        if m:
            drive = m.group(1).lower()
            rest = m.group(2).replace("\\", "/").lstrip("/")
            return f"/mnt/{drive}/{rest}"
        return s.replace("\\", "/")

    @staticmethod
    def _api_get(path: str, timeout: float = 30.0) -> dict:
        return api_client._make_request("GET", path, timeout=timeout)

    @staticmethod
    def _api_post(path: str, payload: dict, timeout: float = 120.0) -> dict:
        return api_client._make_request("POST", path, timeout=timeout, json=payload)

    def org_pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Organization Folder", "")
        if folder:
            self.org_root_input.setText(folder)

    def org_load_proposals(self):
        try:
            root = self._normalize_root_scope(self.org_root_input.text())
            data = self._api_get("/organization/proposals?status=proposed&limit=1000&offset=0", timeout=30.0)
            items = data.get("items", []) if isinstance(data, dict) else []
            if root:
                items = [x for x in items if str(x.get("current_path") or "").replace("\\", "/").startswith(root)]
            self.proposals_cache = items
            self.org_table.setRowCount(len(items))
            for i, p in enumerate(items):
                self.org_table.setItem(i, 0, QTableWidgetItem(str(p.get("id") or "")))
                self.org_table.setItem(i, 1, QTableWidgetItem(f"{float(p.get('confidence') or 0.0):.2f}"))
                self.org_table.setItem(i, 2, QTableWidgetItem(str(p.get("current_path") or "")))
                self.org_table.setItem(i, 3, QTableWidgetItem(str(p.get("proposed_folder") or "")))
                self.org_table.setItem(i, 4, QTableWidgetItem(str(p.get("proposed_filename") or "")))
            self.results_browser.setPlainText(f"Loaded {len(items)} scoped proposals")
        except Exception as e:
            self.status.error(f"Failed to load proposals: {e}")

    def org_generate_scoped(self):
        try:
            root = self._normalize_root_scope(self.org_root_input.text())
            payload = {"limit": 500, "root_prefix": root or None}
            out = self._api_post("/organization/proposals/generate", payload, timeout=180.0)
            self.results_browser.setPlainText(str(out))
            self.org_load_proposals()
        except Exception as e:
            self.status.error(f"Failed to generate scoped proposals: {e}")

    def org_clear_scoped(self):
        try:
            root = self._normalize_root_scope(self.org_root_input.text())
            payload = {"status": "proposed", "root_prefix": root or None, "note": "gui_clear"}
            out = self._api_post("/organization/proposals/clear", payload, timeout=120.0)
            self.results_browser.setPlainText(str(out))
            self.org_load_proposals()
        except Exception as e:
            self.status.error(f"Failed to clear scoped proposals: {e}")

    def org_on_selection_changed(self):
        row = self.org_table.currentRow()
        if row < 0 or row >= len(self.proposals_cache):
            self.selected_proposal = None
            return
        p = self.proposals_cache[row]
        self.selected_proposal = p
        self.org_folder_input.setText(str(p.get("proposed_folder") or ""))
        self.org_filename_input.setText(str(p.get("proposed_filename") or ""))

    def _selected_proposal_id(self) -> Optional[int]:
        if not self.selected_proposal:
            return None
        try:
            return int(self.selected_proposal.get("id"))
        except Exception:
            return None

    def org_approve_selected(self):
        pid = self._selected_proposal_id()
        if pid is None:
            self.status.info("Select a proposal first")
            return
        try:
            out = self._api_post(f"/organization/proposals/{pid}/approve", {}, timeout=60.0)
            self.results_browser.setPlainText(str(out))
            self.org_load_proposals()
        except Exception as e:
            self.status.error(f"Approve failed: {e}")

    def org_reject_selected(self):
        pid = self._selected_proposal_id()
        if pid is None:
            self.status.info("Select a proposal first")
            return
        try:
            out = self._api_post(
                f"/organization/proposals/{pid}/reject",
                {"note": (self.org_note_input.toPlainText() or None)},
                timeout=60.0,
            )
            self.results_browser.setPlainText(str(out))
            self.org_load_proposals()
        except Exception as e:
            self.status.error(f"Reject failed: {e}")

    def org_edit_approve_selected(self):
        pid = self._selected_proposal_id()
        if pid is None:
            self.status.info("Select a proposal first")
            return
        try:
            out = self._api_post(
                f"/organization/proposals/{pid}/edit",
                {
                    "proposed_folder": self.org_folder_input.text(),
                    "proposed_filename": self.org_filename_input.text(),
                    "note": (self.org_note_input.toPlainText() or None),
                },
                timeout=60.0,
            )
            self.results_browser.setPlainText(str(out))
            self.org_load_proposals()
        except Exception as e:
            self.status.error(f"Refine+Approve failed: {e}")

    def export_json(self):
        """Export results to JSON file."""
        if not self.current_results:
            return

        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save JSON", "", "JSON files (*.json)"
            )
            if file_path:
                import json  # noqa: E402
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_results, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "Export Successful", "Results exported to JSON.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export JSON: {e}")

    def export_text(self):
        """Export results to text file."""
        if not self.current_results:
            return

        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Text", "", "Text files (*.txt)"
            )
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("Document Processing Results\n")
                    f.write("=" * 50 + "\n\n")

                    for file_result in self.current_results.get('files', []):
                        file_name = file_result.get('filename', 'Unknown')
                        f.write(f"File: {file_name}\n")
                        f.write("-" * 30 + "\n")

                        if 'error' in file_result:
                            f.write(f"Error: {file_result['error']}\n\n")
                            continue

                        if 'content' in file_result:
                            f.write("Content Preview:\n")
                            content = file_result['content']
                            preview = content[:1000] + "..." if len(content) > 1000 else content
                            f.write(f"{preview}\n\n")

                        if 'summary' in file_result:
                            f.write(f"Summary: {file_result['summary']}\n\n")

                        f.write("\n")

                QMessageBox.information(self, "Export Successful", "Results exported to text file.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export text: {e}")

# Import workers
