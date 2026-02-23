"""
Entity Extraction Tab - GUI component for entity extraction operations

This tab provides the interface for extracting entities from documents
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
        QCheckBox,
        QGroupBox,
        QProgressBar,
        QSplitter,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QFileDialog,
        QLineEdit,
    )
    from PySide6.QtCore import Qt, Signal, QThread  # noqa: E402
    from PySide6.QtGui import (  # noqa: E402
        QFont,
        QPalette,
        QColor,
        QTextCharFormat,
        QTextCursor,
    )
except ImportError:
    # Fallback for systems without PySide6
    QWidget = object
    QVBoxLayout = QHBoxLayout = QLabel = QTextEdit = QPushButton = object
    QComboBox = QCheckBox = QGroupBox = QProgressBar = QSplitter = object
    QListWidget = QListWidgetItem = QMessageBox = QFileDialog = QLineEdit = object
    Qt = QThread = Signal = object
    QFont = QPalette = QColor = QTextCharFormat = QTextCursor = object

from .status_presenter import TabStatusPresenter  # noqa: E402
from ..ui import JobStatusWidget, ResultsSummaryBox  # noqa: E402
from .default_paths import get_default_dialog_dir  # noqa: E402
from ..services import api_client  # noqa: E402
from .workers import (  # noqa: E402
    EntityExtractionFolderWorker,
    EntityExtractionWorker,
    FetchOntologyWorker,
)


class EntityExtractionTab(QWidget):
    """Tab for entity extraction operations."""

    # Signals
    extraction_completed = Signal(dict)
    extraction_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.ontology_worker = None
        self.current_results = None
        self.setup_ui()
        self.connect_signals()
        # self.fetch_ontology() - Defer until backend is ready

    def fetch_ontology(self):
        """Fetch ontology entities dynamically."""
        self.ontology_worker = FetchOntologyWorker()
        self.ontology_worker.finished_ok.connect(self.populate_entity_types)
        self.ontology_worker.finished_err.connect(lambda e: print(f"Ontology fetch error: {e}"))
        self.ontology_worker.start()

    def on_backend_ready(self):
        """Load ontology labels when backend is confirmed online."""
        try:
            self.fetch_ontology()
        except Exception as e:
            print(f"[EntityExtractionTab] on_backend_ready error: {e}")

    def populate_entity_types(self, items: list):
        """Populate combo box with fetched ontology entities."""
        current_text = self.entity_types_combo.currentText()
        self.entity_types_combo.clear()
        self.entity_types_combo.addItem("All")
        
        # items is a list of dicts: {"label": "Person", "attributes": [...], "prompt_hint": ...}
        # We'll use the label for the combo box
        labels = sorted([item.get("label", str(item)) for item in items])
        self.entity_types_combo.addItems(labels)
        
        # Restore previous selection if possible, else default to "All"
        index = self.entity_types_combo.findText(current_text)
        if index >= 0:
            self.entity_types_combo.setCurrentIndex(index)
        else:
            self.entity_types_combo.setCurrentText("All")

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Entity Extraction")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left panel - Input
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # File/Folder Selection
        file_group = QGroupBox("File Input")
        file_layout = QVBoxLayout(file_group)
        
        # File selection
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("File:"))
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("Select a file to extract entities from...")
        file_row.addWidget(self.file_path)
        self.browse_file_btn = QPushButton("Browse File")
        self.browse_file_btn.clicked.connect(self.browse_file)
        file_row.addWidget(self.browse_file_btn)
        file_layout.addLayout(file_row)
        
        # Folder selection
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Folder:"))
        self.folder_path = QLineEdit()
        self.folder_path.setPlaceholderText("Or select a folder to process all files...")
        folder_row.addWidget(self.folder_path)
        self.browse_folder_btn = QPushButton("Browse Folder")
        self.browse_folder_btn.clicked.connect(self.browse_folder)
        folder_row.addWidget(self.browse_folder_btn)
        file_layout.addLayout(folder_row)
        self.folder_path.setToolTip("Select a folder to process supported files.")
        
        left_layout.addWidget(file_group)

        # Input group
        input_group = QGroupBox("Or Enter Text Directly")
        input_layout = QVBoxLayout(input_group)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Enter text to extract entities from...")
        self.input_text.setMaximumHeight(120)
        input_layout.addWidget(self.input_text)

        # Entity types selection
        types_layout = QHBoxLayout()
        types_layout.addWidget(QLabel("Entity Types:"))

        self.entity_types_combo = QComboBox()
        self.entity_types_combo.addItem("All")
        self.entity_types_combo.setCurrentText("All")
        types_layout.addWidget(self.entity_types_combo)

        self.custom_types_checkbox = QCheckBox("Custom Types")
        types_layout.addWidget(self.custom_types_checkbox)
        self.custom_types_checkbox.setEnabled(False)
        self.custom_types_checkbox.setChecked(False)
        self.custom_types_checkbox.setVisible(False)
        self.custom_types_checkbox.setToolTip(
            "Custom types are disabled in this phase. Use ontology entity labels."
        )
        types_layout.addStretch()

        input_layout.addLayout(types_layout)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(
            ["Auto", "GLiNER", "Patterns"]
        )
        self.model_combo.setCurrentText("Auto")
        self.model_combo.setToolTip(
            "Choose a verified extraction engine. Unverified model options are hidden."
        )
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        input_layout.addLayout(model_layout)
        left_layout.addWidget(input_group)

        # Control buttons
        button_layout = QHBoxLayout()

        self.extract_button = QPushButton("Extract Entities")
        self.extract_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        button_layout.addWidget(self.extract_button)

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
        self.status = TabStatusPresenter(self, self.status_label, source="Entity Extraction")
        self.job_status = JobStatusWidget("Entity Extraction Job")
        left_layout.addWidget(self.job_status)

        self.results_summary = ResultsSummaryBox()
        left_layout.addWidget(self.results_summary)

        splitter.addWidget(left_widget)

        # Right panel - Results
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Results group
        results_group = QGroupBox("Extracted Entities")
        results_layout = QVBoxLayout(results_group)

        self.results_list = QListWidget()
        self.results_list.setAlternatingRowColors(True)
        results_layout.addWidget(self.results_list)

        # Results info
        self.results_info = QLabel("No entities extracted yet.")
        results_layout.addWidget(self.results_info)

        right_layout.addWidget(results_group)

        # Export buttons
        export_layout = QHBoxLayout()

        self.export_json_button = QPushButton("Export JSON")
        self.export_json_button.setEnabled(False)
        export_layout.addWidget(self.export_json_button)

        self.export_csv_button = QPushButton("Export CSV")
        self.export_csv_button.setEnabled(False)
        export_layout.addWidget(self.export_csv_button)

        export_layout.addStretch()
        right_layout.addLayout(export_layout)

        splitter.addWidget(right_widget)

        # Set splitter proportions
        splitter.setSizes([400, 400])

    def connect_signals(self):
        """Connect UI signals to handlers."""
        self.extract_button.clicked.connect(self.start_extraction)
        self.clear_button.clicked.connect(self.clear_results)
        self.export_json_button.clicked.connect(self.export_json)
        self.export_csv_button.clicked.connect(self.export_csv)
        self.results_list.itemSelectionChanged.connect(self.highlight_selected_entity)

    def browse_file(self):
        """Browse for a single file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Document",
            get_default_dialog_dir(self.folder_path.text() or self.file_path.text()),
            "All Files (*);;Text Files (*.txt);;PDF Files (*.pdf);;Word Files (*.docx);;Markdown (*.md)",
        )
        if file_path:
            self.file_path.setText(file_path)
            self.folder_path.clear()
            self.input_text.clear()

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
            self.input_text.clear()

    def start_extraction(self):
        """Start entity extraction process."""
        text = self.input_text.toPlainText().strip()
        file_path = self.file_path.text().strip()
        folder_path = self.folder_path.text().strip()
        
        if not text and not file_path and not folder_path:
            self.status.warn("Please enter text, select a file, or select a folder.")
            return
        # Get entity types
        entity_types = None
        if not self.custom_types_checkbox.isChecked():
            selected = self.entity_types_combo.currentText()
            if selected != "All":
                entity_types = [selected]

        if self.worker is not None and self.worker.isRunning():
            self.status.warn("Extraction already running. Please wait for completion.")
            return

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.extract_button.setEnabled(False)
        self.extract_button.setText("Extracting...")

        # Start worker thread
        extraction_type = entity_types[0] if entity_types else "All"
        self.job_status.set_status("running", "Extraction in progress")
        self.status.loading("Extracting entities...")
        options = {
            "entity_types": entity_types or [],
            "custom_types": False,
            "extraction_model": self.model_combo.currentText().strip().lower(),
        }
        if folder_path:
            self.worker = EntityExtractionFolderWorker(
                folder_path=folder_path,
                extraction_type=extraction_type,
                options=options,
            )
        else:
            self.worker = EntityExtractionWorker(
                asyncio_thread=None,
                file_path=file_path,
                text_input=text,
                extraction_type=extraction_type,
                options=options,
            )
        self.worker.result_ready.connect(self.on_extraction_finished)
        self.worker.error_occurred.connect(self.on_extraction_error)
        self.worker.start()

    def on_extraction_finished(self, results):
        """Handle successful extraction completion."""
        synced_count, sync_errors = self._sync_entities_to_manager_memory(results)
        self.current_results = results
        self.display_results(results)
        self.cleanup_worker()
        stats = (
            results.get("extraction_stats", {})
            if isinstance(results.get("extraction_stats"), dict)
            else {}
        )
        files_failed = int(stats.get("files_failed", 0) or 0)
        if files_failed > 0:
            self.status.warn(
                f"Extraction completed with {files_failed} file failures. Check results JSON for file_errors."
            )
            QMessageBox.warning(
                self,
                "Partial Failure",
                f"Extraction completed with {files_failed} failed files.\n"
                "Open exported JSON to inspect extraction_stats.file_errors.",
            )

        self.job_status.set_status("success", "Completed")
        self.results_summary.set_summary(
            "Entity extraction completed successfully",
            (
                f"Displayed in Extracted Entities; synced {synced_count} to Agent Memory"
                if synced_count > 0
                else "Displayed in Extracted Entities (export JSON/CSV optional)"
            ),
            "Run Console",
        )
        if sync_errors:
            self.status.warn(
                f"Entity extraction complete with {sync_errors} memory sync failures."
            )
            QMessageBox.warning(
                self,
                "Memory Sync Partial Failure",
                f"Extraction finished, but {sync_errors} entities failed to sync into Agent Memory.",
            )
        elif synced_count > 0:
            self.status.info(f"Synced {synced_count} entities into Agent Memory.")
        self.status.success("Entity extraction complete")

        # Emit signal
        self.extraction_completed.emit(results)

    def _sync_entities_to_manager_memory(self, results: dict) -> tuple[int, int]:
        """Mirror extracted entities into manager_knowledge for Knowledge Graph edits."""
        entities = results.get("entities")
        if not isinstance(entities, list) or not entities:
            return 0, 0

        synced = 0
        failed = 0
        for entity in entities:
            if not isinstance(entity, dict):
                failed += 1
                continue
            term = str(entity.get("text") or "").strip()
            if not term:
                failed += 1
                continue

            label = str(entity.get("label") or entity.get("entity_type") or "").strip()
            confidence_raw = entity.get("confidence", entity.get("confidence_score", 0.5))
            try:
                confidence = float(confidence_raw)
            except Exception:
                confidence = 0.5

            payload = {
                "term": term,
                "category": label.lower() if label else "entity",
                "canonical_value": term,
                "ontology_entity_id": label or None,
                "attributes": {
                    "start_pos": entity.get("start_pos", entity.get("start")),
                    "end_pos": entity.get("end_pos", entity.get("end")),
                    "extraction_method": entity.get("extraction_method"),
                },
                "source": "entity_extraction_tab",
                "confidence": confidence,
                "status": "proposed",
                "verified": False,
            }
            try:
                api_client.upsert_manager_knowledge_item(payload)
                synced += 1
            except Exception:
                failed += 1

        return synced, failed

    def on_extraction_error(self, error_msg):
        """Handle extraction error."""
        self.job_status.set_status("failed", "Extraction failed")
        self.results_summary.set_summary(
            f"Entity extraction failed: {error_msg}",
            "No output generated",
            "Run Console",
        )
        self.status.error(f"Failed to extract entities: {error_msg}")
        self.results_info.setText(f"Extraction failed: {error_msg}")
        QMessageBox.critical(
            self,
            "Entity Extraction Failed",
            str(error_msg),
        )
        self.cleanup_worker()

        # Emit signal
        self.extraction_error.emit(error_msg)

    def cleanup_worker(self):
        """Clean up worker thread."""
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

        self.progress_bar.setVisible(False)
        self.extract_button.setEnabled(True)
        self.extract_button.setText("Extract Entities")

    def display_results(self, results):
        """Display extraction results."""
        self.results_list.clear()
        if isinstance(results.get("source_text"), str):
            self.input_text.setPlainText(results.get("source_text", ""))
        if results.get("error"):
            self.results_info.setText(f"Extraction failed: {results.get('error')}")
            self.export_json_button.setEnabled(False)
            self.export_csv_button.setEnabled(False)
            return

        entities = results.get("entities", [])
        if not entities:
            stats = (
                results.get("extraction_stats", {})
                if isinstance(results.get("extraction_stats"), dict)
                else {}
            )
            methods = stats.get("extraction_methods_used", [])
            files_total = stats.get("files_total")
            files_processed = stats.get("files_processed")
            files_failed = stats.get("files_failed")
            file_errors = stats.get("file_errors", [])
            diagnostic_parts = []
            if files_total is not None:
                diagnostic_parts.append(
                    f"files={files_processed or 0}/{files_total}, failed={files_failed or 0}"
                )
            if isinstance(methods, list):
                diagnostic_parts.append(
                    f"methods={','.join(str(m) for m in methods) if methods else 'none'}"
                )
            if isinstance(file_errors, list) and file_errors:
                first = file_errors[0]
                if isinstance(first, dict):
                    diagnostic_parts.append(
                        f"first_error={first.get('error', 'unknown')}"
                    )
            diag = " | ".join(diagnostic_parts) if diagnostic_parts else "no diagnostics"
            self.results_info.setText(f"No entities found ({diag}).")
            self.export_json_button.setEnabled(False)
            self.export_csv_button.setEnabled(False)
            return

        # Display entities
        for entity in entities:
            label = entity.get("label") or entity.get("entity_type", "")
            item_text = f"{entity.get('text', '')} ({label})"
            confidence = entity.get("confidence")
            if confidence is None:
                confidence = entity.get("confidence_score", 0)
            if confidence > 0:
                item_text += f" - {confidence:.2f}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, entity)
            self.results_list.addItem(item)

        # Update info
        self.results_info.setText(f"Found {len(entities)} entities.")
        stats = results.get("extraction_stats", {})
        if isinstance(stats, dict):
            methods = stats.get("extraction_methods_used")
            files_total = stats.get("files_total")
            files_processed = stats.get("files_processed")
            files_failed = stats.get("files_failed")
            suffix_parts = []
            if files_total is not None:
                suffix_parts.append(
                    f"files {files_processed or 0}/{files_total} processed"
                )
            if files_failed is not None:
                suffix_parts.append(f"{files_failed} failed")
            if isinstance(methods, list) and methods:
                suffix_parts.append(f"methods: {', '.join(methods)}")
            if suffix_parts:
                self.results_info.setText(
                    f"Found {len(entities)} entities ({'; '.join(suffix_parts)})."
                )
        self.export_json_button.setEnabled(True)
        self.export_csv_button.setEnabled(True)

    def clear_results(self):
        """Clear all results and input."""
        self.input_text.clear()
        self.file_path.clear()
        self.folder_path.clear()
        self.results_list.clear()
        self.results_info.setText("No entities extracted yet.")
        self.export_json_button.setEnabled(False)
        self.export_csv_button.setEnabled(False)
        self.current_results = None
        self.job_status.reset()
        self.results_summary.set_summary("No run yet", "N/A", "Run Console")

    def _entity_span(self, entity: dict) -> tuple[int | None, int | None]:
        """Resolve character offsets from extractor payload."""
        start = entity.get("start_pos")
        end = entity.get("end_pos")
        if start is None:
            start = entity.get("start")
        if end is None:
            end = entity.get("end")
        try:
            s = int(start)
            e = int(end)
        except Exception:
            return None, None
        if s < 0 or e <= s:
            return None, None
        return s, e

    def highlight_selected_entity(self):
        """Highlight selected entity span in source text."""
        selected = self.results_list.selectedItems()
        if not selected:
            return
        entity = selected[0].data(Qt.UserRole)
        if not isinstance(entity, dict):
            return
        span = self._entity_span(entity)
        if not span[0] and span[0] != 0:
            self.status.warn("No provenance span available for selected entity.")
            return
        start, end = span
        text = self.input_text.toPlainText()
        if end > len(text):
            end = len(text)
        if start >= end:
            self.status.warn("Invalid span for selected entity.")
            return

        cursor = self.input_text.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(QTextCharFormat())

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#fff176"))
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.setCharFormat(fmt)
        self.input_text.setTextCursor(cursor)
        self.status.info(f"Highlighted chars {start}-{end} for selected entity.")

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

    def export_csv(self):
        """Export results to CSV file."""
        if not self.current_results:
            return

        try:
            import csv  # noqa: E402
            from PySide6.QtWidgets import QFileDialog  # noqa: E402

            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save CSV", "", "CSV files (*.csv)"
            )
            if file_path:
                entities = self.current_results.get("entities", [])
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Text", "Label", "Confidence", "Start", "End"])
                    for entity in entities:
                        start, end = self._entity_span(entity)
                        writer.writerow([
                            entity.get("text", ""),
                            entity.get("label") or entity.get("entity_type", ""),
                            entity.get("confidence", entity.get("confidence_score", 0)),
                            start if start is not None else "",
                            end if end is not None else "",
                        ])
                QMessageBox.information(self, "Export Successful", "Results exported to CSV.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export CSV: {e}")
