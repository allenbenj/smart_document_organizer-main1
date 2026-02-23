"""
Document Processing Tab - Content extraction and preparation pipeline

This tab provides the centralized interface for uploading, extracting, and
preparing document content. It serves as the second step in the document
management pipeline, processing raw files into structured data that all
other tabs can leverage.

Key Features:
- File upload (drag-drop, browse)
- Content extraction from multiple formats
- Metadata extraction
- Content analysis
- Summary generation
- Vector indexing for search
- Export processed results
"""

import json
import os
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore

# Runtime imports with fallback
PYSIDE6_AVAILABLE = False

try:
    from PySide6.QtWidgets import (
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
    )
    from PySide6.QtCore import Qt, Signal, QThread
    from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent
    PYSIDE6_AVAILABLE = True
except ImportError:
    # Fallback types
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
    Qt = Any  # type: ignore[misc,assignment]
    Signal = Any  # type: ignore[misc,assignment]
    QThread = Any  # type: ignore[misc,assignment]
    QFont = Any  # type: ignore[misc,assignment]
    QDragEnterEvent = Any  # type: ignore[misc,assignment]
    QDropEvent = Any  # type: ignore[misc,assignment]

from .status_presenter import TabStatusPresenter  # noqa: E402
if PYSIDE6_AVAILABLE:
    from ..ui import JobStatusWidget, ResultsSummaryBox, DocumentPreviewWidget  # noqa: E402
from .workers import UploadManyFilesWorker  # noqa: E402
from ..services.processing_service import processing_service, JobStatus, ProcessingJob
from ..services import api_client


class DocumentProcessingTab(QWidget):  # type: ignore[misc]
    """
    Tab for document content extraction and processing.
    
    Refactored to follow best practices:
    - Observes ProcessingService for state
    - Uses canonical ApiClient normalization
    - Fixes selection and removal bugs
    """

    # Signals
    processing_completed = Signal(dict)  # type: ignore[misc]
    processing_error = Signal(str)  # type: ignore[misc]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.current_results = None
        self.current_job_id = None
        self.selected_files = [] # List of absolute paths
        self.setup_ui()
        self.connect_signals()
        
        # Subscribe to processing service updates
        processing_service.subscribe(self._on_job_update)

    def _on_job_update(self, job):
        """Handle updates from the processing service."""
        # Check if this job belongs to our current active job
        if self.current_job_id == job.id:
            if job.status == JobStatus.RUNNING:
                self.status.info(f"Processing... {job.progress}%")
                if hasattr(self, 'job_status'):
                    self.job_status.set_status("running", f"{job.progress}%")
            elif job.status == JobStatus.SUCCESS:
                # Results are handled by the _on_worker_finished method
                pass
            elif job.status == JobStatus.FAILED:
                # Errors are handled by the _on_worker_error method
                pass
            elif job.status == JobStatus.CANCELLED:
                self.status.warn("Processing job was cancelled")
                self._reset_ui_after_job()

    def _reset_ui_after_job(self):
        """Re-enable UI components after a job ends."""
        self.process_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.add_files_button.setEnabled(True)
        self.remove_files_button.setEnabled(True)
        self.clear_files_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Document Processing")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "Upload and process documents: Extract content, metadata, and structure. "
            "Processed documents are indexed to the shared knowledge base for all tabs to use."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; padding: 5px 0;")
        layout.addWidget(desc)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left panel - Input
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # File selection group
        file_group = QGroupBox("Select Documents")
        file_layout = QVBoxLayout(file_group)

        # Instructions
        instructions = QLabel("Drag & drop files here, or use the buttons below:")
        instructions.setStyleSheet("color: #888; font-style: italic;")
        file_layout.addWidget(instructions)

        # File list
        self.file_list = QListWidget()
        self.file_list.setAcceptDrops(True)
        self.file_list.setDragEnabled(True)
        self.file_list.setSelectionMode(QListWidget.MultiSelection)
        self.file_list.setMinimumHeight(200)
        file_layout.addWidget(self.file_list)

        # File buttons
        file_buttons_layout = QHBoxLayout()

        self.add_files_button = QPushButton("📁 Add Files...")
        self.add_files_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        file_buttons_layout.addWidget(self.add_files_button)

        self.add_folder_button = QPushButton("📂 Add Folder...")
        self.add_folder_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.add_folder_button.setToolTip("Add all documents from a folder")
        file_buttons_layout.addWidget(self.add_folder_button)

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
        self.extract_text_checkbox.setToolTip("Extract raw text from documents")
        options_layout.addWidget(self.extract_text_checkbox)

        self.extract_metadata_checkbox = QCheckBox("Extract Metadata")
        self.extract_metadata_checkbox.setChecked(True)
        self.extract_metadata_checkbox.setToolTip("Extract author, date, keywords, etc.")
        options_layout.addWidget(self.extract_metadata_checkbox)

        self.analyze_content_checkbox = QCheckBox("Analyze Content Structure")
        self.analyze_content_checkbox.setChecked(True)
        self.analyze_content_checkbox.setToolTip("Identify sections, headings, tables, etc.")
        options_layout.addWidget(self.analyze_content_checkbox)

        self.generate_summary_checkbox = QCheckBox("Generate Summary")
        self.generate_summary_checkbox.setToolTip("AI-powered summary generation")
        options_layout.addWidget(self.generate_summary_checkbox)

        self.index_vector_checkbox = QCheckBox("Index to Vector Store")
        self.index_vector_checkbox.setChecked(True)
        self.index_vector_checkbox.setToolTip("Enable semantic search across tabs")
        options_layout.addWidget(self.index_vector_checkbox)

        self.enable_ocr_checkbox = QCheckBox("Enable OCR")
        self.enable_ocr_checkbox.setChecked(True)
        self.enable_ocr_checkbox.setToolTip("Enable Optical Character Recognition for scanned documents and images")
        options_layout.addWidget(self.enable_ocr_checkbox)

        left_layout.addWidget(options_group)

        # Control buttons
        button_layout = QHBoxLayout()

        self.process_button = QPushButton("⚡ Process Documents")
        self.process_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #EF6C00;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        button_layout.addWidget(self.process_button)

        self.stop_button = QPushButton("🛑 Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        button_layout.addWidget(self.stop_button)

        button_layout.addStretch()
        left_layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        # Status
        self.status_label = QLabel("Ready - Add documents to begin")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f5f5f5; border-radius: 3px;")
        left_layout.addWidget(self.status_label)
        
        self.status = TabStatusPresenter(self, self.status_label, source="Document Processing")
        
        if PYSIDE6_AVAILABLE:
            self.job_status = JobStatusWidget("Document Processing Job")
            left_layout.addWidget(self.job_status)
            self.results_summary = ResultsSummaryBox()
            left_layout.addWidget(self.results_summary)

        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # Right panel - Preview and Results
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Add document preview widget
        if PYSIDE6_AVAILABLE:
            preview_group = QGroupBox("Document Preview & Results")
            preview_layout = QVBoxLayout(preview_group)
            
            # Create tabbed interface
            self.preview_tabs = QSplitter(Qt.Vertical)
            
            # Document preview widget
            self.document_preview = DocumentPreviewWidget()
            self.document_preview.document_loaded.connect(self.on_document_previewed)
            self.document_preview.preview_error.connect(self.on_preview_error)
            self.preview_tabs.addWidget(self.document_preview)
            
            # Processing results browser
            results_widget = QWidget()
            results_layout = QVBoxLayout(results_widget)
            results_label = QLabel("Processing Results")
            results_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            results_layout.addWidget(results_label)
            
            self.results_browser = QTextBrowser()
            self.results_browser.setOpenExternalLinks(True)
            results_layout.addWidget(self.results_browser)
            
            self.preview_tabs.addWidget(results_widget)
            
            # Set proportions (preview larger)
            self.preview_tabs.setSizes([500, 300])
            
            preview_layout.addWidget(self.preview_tabs)
            right_layout.addWidget(preview_group)
        else:
            # Fallback without preview
            results_group = QGroupBox("Processing Results")
            results_layout = QVBoxLayout(results_group)

            self.results_browser = QTextBrowser()
            self.results_browser.setOpenExternalLinks(True)
            results_layout.addWidget(self.results_browser)

            right_layout.addWidget(results_group)

        # Export buttons
        export_layout = QHBoxLayout()

        self.export_json_button = QPushButton("💾 Export JSON")
        self.export_json_button.setEnabled(False)
        self.export_json_button.setToolTip("Export processing results as JSON")
        export_layout.addWidget(self.export_json_button)

        self.export_text_button = QPushButton("📄 Export Text")
        self.export_text_button.setEnabled(False)
        self.export_text_button.setToolTip("Export processing results as text")
        export_layout.addWidget(self.export_text_button)

        export_layout.addStretch()
        right_layout.addLayout(export_layout)

        splitter.addWidget(right_widget)

        # Set splitter proportions
        splitter.setSizes([400, 400])

    def connect_signals(self):
        """Connect UI signals to handlers."""
        self.add_files_button.clicked.connect(self.add_files)
        self.add_folder_button.clicked.connect(self.add_folder)
        self.remove_files_button.clicked.connect(self.remove_selected_files)
        self.clear_files_button.clicked.connect(self.clear_files)
        self.process_button.clicked.connect(self.start_processing)
        self.stop_button.clicked.connect(self.stop_processing)
        self.export_json_button.clicked.connect(self.export_json)
        self.export_text_button.clicked.connect(self.export_text)

        # File list selection - preview document
        self.file_list.itemSelectionChanged.connect(self.on_file_selected)

        # Drag and drop
        self.file_list.dragEnterEvent = self.drag_enter_event
        self.file_list.dropEvent = self.drop_event

    # -------------------------------------------------------------------------
    # File Management
    # -------------------------------------------------------------------------

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
        from .default_paths import get_default_dialog_dir

        default_path = get_default_dialog_dir()
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Documents to Process",
            default_path,
            "All Files (*);;PDF Files (*.pdf);;Word Files (*.docx *.doc);;Text Files (*.txt);;Markdown Files (*.md)"
        )

        for file_path in file_paths:
            self.add_file_to_list(file_path)

    def add_folder(self):
        """Add all files from a folder through folder dialog."""
        from .default_paths import get_default_dialog_dir

        default_path = get_default_dialog_dir()
        
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Process",
            default_path
        )

        if not folder_path:
            return

        # Supported file extensions
        supported_extensions = {
            '.pdf', '.docx', '.doc', '.txt', '.html', '.htm', '.rtf', '.md',
            '.xlsx', '.xls', '.csv', '.pptx', '.ppt', '.png', '.jpg', '.jpeg',
            '.tif', '.bmp', '.mp4', '.mov', '.avi', '.mp3', '.wav'
        }

        # Walk through directory and add all supported files
        added_count = 0
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in supported_extensions:
                    file_path = os.path.join(root, file)
                    self.add_file_to_list(file_path)
                    added_count += 1

        if added_count > 0:
            self.status.success(f"Added {added_count} file(s) from folder")
        else:
            self.status.info("No supported files found in folder")

    def add_file_to_list(self, file_path: str):
        """Add a file to the list widget with duplicate protection."""
        if file_path not in self.selected_files:
            self.selected_files.append(file_path)
            file_name = os.path.basename(file_path)
            item = QListWidgetItem(f"📄 {file_name}")
            item.setToolTip(file_path)
            self.file_list.addItem(item)
            self.status.info(f"Added: {file_name}")
        else:
            self.status.info(f"Skipped duplicate: {os.path.basename(file_path)}")

    def remove_selected_files(self):
        """Remove selected files from the list."""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            self.status.info("No files selected to remove")
            return
        
        # Sort indices in reverse to avoid index shift issues during deletion
        rows = sorted([self.file_list.row(item) for item in selected_items], reverse=True)
        
        for row in rows:
            if row < len(self.selected_files):
                removed_file = self.selected_files[row]
                del self.selected_files[row]
                self.status.info(f"Removed: {os.path.basename(removed_file)}")
            self.file_list.takeItem(row)

    def clear_files(self):
        """Clear all files from the list."""
        count = len(self.selected_files)
        self.file_list.clear()
        self.selected_files.clear()
        self.status.info(f"Cleared {count} files")
        
        # Clear preview
        if PYSIDE6_AVAILABLE and hasattr(self, 'document_preview'):
            self.document_preview.clear()

    def on_file_selected(self):
        """Handle file selection - show preview."""
        if not PYSIDE6_AVAILABLE or not hasattr(self, 'document_preview'):
            return
        
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return
        
        # Get the first selected item
        item = selected_items[0]
        row = self.file_list.row(item)
        
        if row < len(self.selected_files):
            file_path = self.selected_files[row]
            self.document_preview.load_document(file_path)
    
    def on_document_previewed(self, file_path: str):
        """Handle successful document preview load."""
        self.status.info(f"Previewing: {os.path.basename(file_path)}")
    
    def on_preview_error(self, error_msg: str):
        """Handle preview error."""
        self.status.error(f"Preview error: {error_msg}")

    # -------------------------------------------------------------------------
    # Document Processing
    # -------------------------------------------------------------------------

    def start_processing(self):
        """Start document processing using ProcessingService."""
        if not self.selected_files:
            self.status.error("No files selected. Please add documents first.")
            QMessageBox.warning(
                self,
                "No Files",
                "Please add documents to process."
            )
            return

        if self.worker and self.worker.isRunning():
            self.status.error("Processing already in progress")
            return

        # Create job options
        options = {
            "extract_text": self.extract_text_checkbox.isChecked(),
            "extract_metadata": self.extract_metadata_checkbox.isChecked(),
            "analyze_content": self.analyze_content_checkbox.isChecked(),
            "generate_summary": self.generate_summary_checkbox.isChecked(),
            "index_vector": self.index_vector_checkbox.isChecked(),
            "enable_ocr": self.enable_ocr_checkbox.isChecked(),
        }

        # Initialize job via service
        import uuid
        from datetime import datetime
        
        self.current_job_id = str(uuid.uuid4())
        job = ProcessingJob(
            id=self.current_job_id,
            files=list(self.selected_files),
            options=options,
            status=JobStatus.PENDING,
            total_files=len(self.selected_files),
            started_at=datetime.now()
        )
        
        # Register job in service
        processing_service._active_jobs[self.current_job_id] = job
        processing_service._notify(job)

        # Disable buttons during processing
        self.process_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.add_files_button.setEnabled(False)
        self.remove_files_button.setEnabled(False)
        self.clear_files_button.setEnabled(False)

        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        self.status.info(f"Processing {len(self.selected_files)} document(s)...")

        # Create worker with job context
        self.worker = UploadManyFilesWorker(
            paths=self.selected_files,
            options=options,
            job_id=self.current_job_id,
        )

        # Connect signals to explicit methods to ensure thread safety
        self.worker.progress_update.connect(self._on_worker_progress)
        self.worker.finished_ok.connect(self._on_worker_finished)
        self.worker.finished_err.connect(self._on_worker_error)
        self.worker.finished.connect(self.cleanup_worker)

        # Start processing
        self.worker.start()

    def _on_worker_progress(self, pct, msg):
        """Handle progress updates from worker on the UI thread."""
        if self.current_job_id:
            processing_service.update_job_progress(self.current_job_id, pct, JobStatus.RUNNING)
            self.status.info(f"{msg} ({pct}%)")

    def _on_worker_finished(self, results):
        """Handle successful completion on the UI thread."""
        if self.current_job_id:
            processing_service.update_job_progress(self.current_job_id, 100, JobStatus.SUCCESS)
            job = processing_service.get_job(self.current_job_id)
            if job:
                job.results = results
        self.on_processing_finished(results)

    def _on_worker_error(self, err):
        """Handle worker error on the UI thread."""
        if self.current_job_id:
            job = processing_service.get_job(self.current_job_id)
            if job:
                job.error = err
            processing_service.update_job_progress(self.current_job_id, 0, JobStatus.FAILED)
        self.on_processing_error(err)

    def stop_processing(self):
        """Request cancellation of the current processing job."""
        if self.worker and self.worker.isRunning():
            self.status.info("Stopping processing...")
            if self.current_job_id:
                # Signal the worker to stop
                self.worker.requestInterruption()
                # Update service state
                processing_service.update_job_progress(self.current_job_id, 0, JobStatus.CANCELLED)
            
            self.stop_button.setEnabled(False)
            self.status.warn("Stop requested. Waiting for worker to finish...")

    def on_progress_update(self, message: str):
        """Handle progress updates from worker."""
        self.status.info(message)

    def on_processing_finished(self, results):
        """Handle processing completion."""
        # Results are already normalized by ApiClient
        self.current_results = results
        
        # Hide progress bar
        self.progress_bar.setVisible(False)

        # Re-enable buttons
        self._reset_ui_after_job()

        # Enable export buttons
        self.export_json_button.setEnabled(True)
        self.export_text_button.setEnabled(True)

        # Display results
        self.display_results(results)

        # Emit completion signal
        self.processing_completed.emit(results)

        # Update status
        files_count = len(results.get("items", []))
        success_count = int(results.get("processed_count", 0))
        failed_count = int(results.get("failed_count", 0))
        if failed_count > 0:
            self.status.warn(
                f"Processed {success_count}/{files_count} document(s) "
                f"({failed_count} failed)"
            )
        else:
            self.status.success(f"✓ Successfully processed {files_count} document(s)")

    def on_processing_error(self, error_msg):
        """Handle processing errors."""
        # Hide progress bar
        self.progress_bar.setVisible(False)

        # Re-enable buttons
        self.process_button.setEnabled(True)
        self.add_files_button.setEnabled(True)
        self.remove_files_button.setEnabled(True)
        self.clear_files_button.setEnabled(True)

        # Display error
        self.results_browser.setHtml(f"""
            <div style='color: #f44336; padding: 10px; background-color: #ffebee; border-radius: 4px;'>
                <strong>Processing Error:</strong><br>
                {error_msg}
            </div>
        """)

        # Update status
        self.status.error(f"Processing failed: {error_msg}")

        # Emit error signal
        self.processing_error.emit(error_msg)

    def cleanup_worker(self):
        """Clean up worker thread after processing completes."""
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    # -------------------------------------------------------------------------
    # Results Display
    # -------------------------------------------------------------------------

    def display_results(self, results):
        """Display processing results in the browser."""
        html = self.format_results_html(results)
        self.results_browser.setHtml(html)

        # Update summary box if available
        if PYSIDE6_AVAILABLE and hasattr(self, 'results_summary'):
            items = results.get('items', [])
            files_count = len(items)
            success_count = int(results.get("processed_count", 0))
            error_count = int(results.get("failed_count", 0))
            
            summary_text = f"Processed: {success_count}/{files_count}"
            if error_count > 0:
                summary_text += f" ({error_count} errors)"

            self.results_summary.set_summary(
                summary_text,
                "Displayed in Processing Results (export JSON/Text optional)",
                "Run Console",
            )

    def format_results_html(self, results):
        """Format results as HTML for display."""
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 10px; }
                h2 { color: #2196F3; border-bottom: 2px solid #2196F3; padding-bottom: 5px; }
                h3 { color: #666; margin-top: 20px; }
                .file { background-color: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 4px; }
                .success { border-left: 4px solid #4CAF50; }
                .error { border-left: 4px solid #f44336; background-color: #ffebee; }
                .metadata { color: #666; font-size: 0.9em; margin: 5px 0; }
                .content-preview {
                    background-color: white;
                    padding: 10px;
                    margin: 10px 0;
                    border-radius: 3px;
                    max-height: 200px;
                    overflow-y: auto;
                    font-family: monospace;
                    font-size: 0.85em;
                }
                .summary {
                    background-color: #e3f2fd;
                    padding: 10px;
                    margin: 10px 0;
                    border-radius: 3px;
                    border-left: 4px solid #2196F3;
                }
            </style>
        </head>
        <body>
            <h2>📊 Processing Results</h2>
        """

        items = results.get('items', [])
        if not items:
            html += "<p>No files were processed.</p>"
        else:
            for item in items:
                file_name = item.get('filename', 'Unknown')

                if item.get("error") or not bool(item.get("success", True)):
                    html += f"""
                    <div class='file error'>
                        <h3>❌ {file_name}</h3>
                        <p class='metadata'>Status: <strong>Error</strong></p>
                        <p style='color: #f44336;'>{item.get('error') or 'Unknown error'}</p>
                    </div>
                    """
                else:
                    html += f"""
                    <div class='file success'>
                        <h3>✓ {file_name}</h3>
                        <p class='metadata'>Status: <strong>Success</strong></p>
                    """
                    
                    # Metadata
                    if 'metadata' in item:
                        metadata = item['metadata']
                        if metadata:
                            html += "<p class='metadata'><strong>Metadata:</strong> "
                            meta_items = [f"{k}: {v}" for k, v in metadata.items() if v]
                            html += ", ".join(meta_items[:5])  # Show first 5 items
                            html += "</p>"
                    
                    # Summary
                    if 'summary' in item and item['summary']:
                        html += f"""
                        <div class='summary'>
                            <strong>Summary:</strong><br>
                            {item['summary']}
                        </div>
                        """
                    
                    # Content preview
                    if 'content' in item and item['content']:
                        content = item['content']
                        preview = content[:500] + "..." if len(content) > 500 else content
                        # Escape HTML
                        preview = preview.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        html += f"""
                        <div class='content-preview'>
                            <strong>Content Preview:</strong><br>
                            {preview}
                        </div>
                        """
                    
                    html += "</div>"

        html += """
        </body>
        </html>
        """
        return html

    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------

    def export_json(self):
        """Export results to JSON file."""
        if not self.current_results:
            self.status.info("No results to export")
            return

        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save JSON", "", "JSON files (*.json)"
            )
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_results, f, indent=2, ensure_ascii=False)
                
                self.status.success(f"Exported to: {os.path.basename(file_path)}")
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Results exported to:\n{file_path}"
                )
        except Exception as e:
            self.status.error(f"Export failed: {e}")
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export JSON:\n{e}"
            )

    def export_text(self):  # noqa: C901
        """Export results to text file."""
        if not self.current_results:
            self.status.info("No results to export")
            return

        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Text", "", "Text files (*.txt)"
            )
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("=" * 70 + "\n")
                    f.write("DOCUMENT PROCESSING RESULTS\n")
                    f.write("=" * 70 + "\n\n")

                    for item in self.current_results.get('items', []):
                        file_name = item.get('filename', 'Unknown')
                        f.write(f"\nFile: {file_name}\n")
                        f.write("-" * 70 + "\n")

                        if item.get('error'):
                            f.write("Status: ERROR\n")
                            f.write(f"Error: {item['error']}\n\n")
                            continue

                        f.write("Status: SUCCESS\n\n")

                        if item.get('metadata'):
                            f.write("Metadata:\n")
                            for key, value in item['metadata'].items():
                                if value:
                                    f.write(f"  {key}: {value}\n")
                            f.write("\n")

                        if item.get('summary'):
                            f.write(f"Summary:\n{item['summary']}\n\n")

                        if item.get('content'):
                            f.write("Content:\n")
                            content = item['content']
                            preview = content[:2000] + "\n[... truncated ...]" if len(content) > 2000 else content
                            f.write(f"{preview}\n\n")

                        f.write("\n")

                self.status.success(f"Exported to: {os.path.basename(file_path)}")
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Results exported to:\n{file_path}"
                )
        except Exception as e:
            self.status.error(f"Export failed: {e}")
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export text:\n{e}"
            )

    def closeEvent(self, event):
        """Cleanup on close."""
        if self.worker:
            self.worker.requestInterruption()
            self.worker.wait(1000)
        super().closeEvent(event)


# Legacy alias for backward compatibility
DocumentOrganizationTab = DocumentProcessingTab
