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
    )
    from PySide6.QtCore import Qt, Signal, QThread  # noqa: E402
    from PySide6.QtGui import QFont, QPalette, QColor  # noqa: E402
except ImportError:
    # Fallback for systems without PySide6
    QWidget = object
    QVBoxLayout = QHBoxLayout = QLabel = QTextEdit = QPushButton = object
    QComboBox = QCheckBox = QGroupBox = QProgressBar = QSplitter = object
    QListWidget = QListWidgetItem = QMessageBox = object
    Qt = QThread = Signal = object
    QFont = QPalette = QColor = object

from .status_presenter import TabStatusPresenter  # noqa: E402
from ..ui import JobStatusWidget, ResultsSummaryBox  # noqa: E402
from .workers import EntityExtractionWorker  # noqa: E402


class EntityExtractionTab(QWidget):
    """Tab for entity extraction operations."""

    # Signals
    extraction_completed = Signal(dict)
    extraction_error = Signal(str)

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
        title = QLabel("Entity Extraction")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left panel - Input
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Input group
        input_group = QGroupBox("Input Text")
        input_layout = QVBoxLayout(input_group)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Enter text to extract entities from...")
        input_layout.addWidget(self.input_text)

        # Entity types selection
        types_layout = QHBoxLayout()
        types_layout.addWidget(QLabel("Entity Types:"))

        self.entity_types_combo = QComboBox()
        self.entity_types_combo.addItems([
            "All",
            "PERSON",
            "ORG",
            "GPE",
            "MONEY",
            "DATE",
            "LAW",
            "CASE",
            "STATUTE"
        ])
        self.entity_types_combo.setCurrentText("All")
        types_layout.addWidget(self.entity_types_combo)

        self.custom_types_checkbox = QCheckBox("Custom Types")
        types_layout.addWidget(self.custom_types_checkbox)
        types_layout.addStretch()

        input_layout.addLayout(types_layout)
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
        self.custom_types_checkbox.toggled.connect(self.toggle_custom_types)

    def toggle_custom_types(self, checked):
        """Handle custom types checkbox toggle."""
        # For now, just enable/disable the combo box
        self.entity_types_combo.setEnabled(not checked)

    def start_extraction(self):
        """Start entity extraction process."""
        text = self.input_text.toPlainText().strip()
        if not text:
            self.status.warn("Please enter text to extract entities from.")
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
        self.worker = EntityExtractionWorker(
            asyncio_thread=None,
            file_path="",
            text_input=text,
            extraction_type=extraction_type,
            options={
                "entity_types": entity_types or [],
                "custom_types": self.custom_types_checkbox.isChecked(),
            },
        )
        self.worker.result_ready.connect(self.on_extraction_finished)
        self.worker.error_occurred.connect(self.on_extraction_error)
        self.worker.start()

    def on_extraction_finished(self, results):
        """Handle successful extraction completion."""
        self.current_results = results
        self.display_results(results)
        self.cleanup_worker()

        self.job_status.set_status("success", "Completed")
        self.results_summary.set_summary(
            "Entity extraction completed successfully",
            "Displayed in Extracted Entities (export JSON/CSV optional)",
            "Run Console",
        )
        self.status.success("Entity extraction complete")

        # Emit signal
        self.extraction_completed.emit(results)

    def on_extraction_error(self, error_msg):
        """Handle extraction error."""
        self.job_status.set_status("failed", "Extraction failed")
        self.results_summary.set_summary(
            f"Entity extraction failed: {error_msg}",
            "No output generated",
            "Run Console",
        )
        self.status.error(f"Failed to extract entities: {error_msg}")
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

        entities = results.get("entities", [])
        if not entities:
            self.results_info.setText("No entities found.")
            self.export_json_button.setEnabled(False)
            self.export_csv_button.setEnabled(False)
            return

        # Display entities
        for entity in entities:
            item_text = f"{entity.get('text', '')} ({entity.get('label', '')})"
            confidence = entity.get('confidence', 0)
            if confidence > 0:
                item_text += f" - {confidence:.2f}"

            item = QListWidgetItem(item_text)
            self.results_list.addItem(item)

        # Update info
        self.results_info.setText(f"Found {len(entities)} entities.")
        self.export_json_button.setEnabled(True)
        self.export_csv_button.setEnabled(True)

    def clear_results(self):
        """Clear all results and input."""
        self.input_text.clear()
        self.results_list.clear()
        self.results_info.setText("No entities extracted yet.")
        self.export_json_button.setEnabled(False)
        self.export_csv_button.setEnabled(False)
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
                        writer.writerow([
                            entity.get("text", ""),
                            entity.get("label", ""),
                            entity.get("confidence", 0),
                            entity.get("start", ""),
                            entity.get("end", "")
                        ])
                QMessageBox.information(self, "Export Successful", "Results exported to CSV.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export CSV: {e}")
