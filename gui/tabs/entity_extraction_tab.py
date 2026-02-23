"""
Entity Extraction Tab - Modern High-Resolution Interface
Consolidates multi-model extraction with interactive curation.
"""

import json
import os
import time
from datetime import datetime
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
    QPushButton, QComboBox, QCheckBox, QGroupBox, QProgressBar, 
    QSplitter, QTableWidget, QTableWidgetItem, QMessageBox, 
    QFileDialog, QLineEdit, QHeaderView, QAbstractItemView
)

from .status_presenter import TabStatusPresenter
from ..ui import JobStatusWidget, ResultsSummaryBox
from .default_paths import get_default_dialog_dir
from ..services import api_client
from .workers import (
    EntityExtractionFolderWorker,
    EntityExtractionWorker,
    FetchOntologyWorker,
)
from gui.core.base_tab import BaseTab

class EntityExtractionTab(BaseTab):
    extraction_completed = Signal(dict)
    extraction_error = Signal(str)

    def __init__(self, asyncio_thread: Optional[Any] = None, parent=None):
        super().__init__("Entity Extraction", asyncio_thread, parent)
        self.ontology_worker = None
        self.current_results = None
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Setup the modern, high-resolution user interface."""
        # Header
        title = QLabel("Legal Entity Extraction & Curation")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        self.main_layout.addWidget(title)
        
        header_desc = QLabel("Multi-model ensemble (Oracle, GLiNER, Patterns) with Knowledge Graph grounding.")
        header_desc.setStyleSheet("color: #666; font-style: italic;")
        self.main_layout.addWidget(header_desc)

        # Primary Splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.main_splitter)

        # LEFT: Config & Input
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)

        # 1. Input
        input_group = QGroupBox("1. Intelligence Input")
        input_layout = QVBoxLayout(input_group)
        
        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select file or folder...")
        path_row.addWidget(self.path_input)
        self.browse_btn = QPushButton("Browse...")
        path_row.addWidget(self.browse_btn)
        input_layout.addLayout(path_row)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Or paste legal text directly...")
        self.input_text.setMaximumHeight(150)
        input_layout.addWidget(self.input_text)
        left_layout.addWidget(input_group)

        # 2. Strategy
        config_group = QGroupBox("2. Extraction Strategy")
        config_layout = QVBoxLayout(config_group)
        
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Target Ontology:"))
        self.entity_types_combo = QComboBox()
        self.entity_types_combo.addItem("All")
        type_row.addWidget(self.entity_types_combo, 1)
        config_layout.addLayout(type_row)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Ensemble Engine:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["Auto (Ensemble)", "GLiNER Oracle", "Regex Patterns", "LLM Enhanced"])
        model_row.addWidget(self.model_combo, 1)
        config_layout.addLayout(model_row)
        
        self.kb_grounding_cb = QCheckBox("Enable Knowledge Graph Grounding")
        self.kb_grounding_cb.setChecked(True)
        config_layout.addWidget(self.kb_grounding_cb)
        left_layout.addWidget(config_group)

        # 3. Execution
        exec_group = QGroupBox("3. Execution")
        exec_layout = QVBoxLayout(exec_group)
        self.extract_button = QPushButton("⚡ RUN EXTRACTION")
        self.extract_button.setMinimumHeight(50)
        self.extract_button.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; font-size: 14px;")
        exec_layout.addWidget(self.extract_button)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        exec_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready") # The QLabel for status is still needed for BaseTab to set text/style
        exec_layout.addWidget(self.status_label) # The QLabel for status is still needed for BaseTab to set text/style
        
        self.job_status = JobStatusWidget("Extraction Job")
        exec_layout.addWidget(self.job_status)
        left_layout.addWidget(exec_group)
        left_layout.addStretch()
        
        self.main_splitter.addWidget(left_container)

        # RIGHT: Results
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        results_group = QGroupBox("4. Extracted Findings (Editable)")
        results_layout = QVBoxLayout(results_group)
        
        table_tools = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter findings...")
        table_tools.addWidget(self.search_input)
        self.bulk_approve_btn = QPushButton("Approve Selection")
        table_tools.addWidget(self.bulk_approve_btn)
        results_layout.addLayout(table_tools)

        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(["Entity Text", "Type", "Conf", "Method", "Status"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        results_layout.addWidget(self.results_table)
        
        self.results_info = QLabel("No entities extracted.")
        results_layout.addWidget(self.results_info)
        right_layout.addWidget(results_group)

        export_group = QGroupBox("5. Export & Knowledge Transfer")
        export_layout = QHBoxLayout(export_group)
        self.sync_btn = QPushButton("📤 Sync to Agent Memory")
        self.sync_btn.setStyleSheet("background-color: #1565c0; color: white;")
        export_layout.addWidget(self.sync_btn)
        self.export_json_btn = QPushButton("💾 Export JSON")
        export_layout.addWidget(self.export_json_btn)
        self.clear_btn = QPushButton("🗑️ Clear Workspace")
        export_layout.addWidget(self.clear_btn)
        right_layout.addWidget(export_group)
        
        self.main_splitter.addWidget(right_container)
        self.main_splitter.setSizes([400, 800])

    def connect_signals(self):
        self.browse_btn.clicked.connect(self.browse_general)
        self.extract_button.clicked.connect(self.start_extraction)
        self.search_input.textChanged.connect(self.filter_table)
        self.bulk_approve_btn.clicked.connect(self.approve_table_selection)
        self.sync_btn.clicked.connect(self.sync_to_memory)
        self.export_json_btn.clicked.connect(self.export_json)
        self.clear_btn.clicked.connect(self.clear_results)

    def fetch_ontology(self):
        self.ontology_worker = FetchOntologyWorker()
        self.ontology_worker.finished_ok.connect(self.populate_entity_types)
        self.ontology_worker.start()

    def populate_entity_types(self, items: list):
        current = self.entity_types_combo.currentText()
        self.entity_types_combo.clear()
        self.entity_types_combo.addItem("All")
        labels = sorted([item.get("label", str(item)) for item in items])
        self.entity_types_combo.addItems(labels)
        idx = self.entity_types_combo.findText(current)
        if idx >= 0: self.entity_types_combo.setCurrentIndex(idx)

    def on_backend_ready(self):
        self.fetch_ontology()

    def browse_general(self):
        res = QMessageBox.question(self, "Browse Selection", "Process a single FILE?\n(Click No to select a FOLDER)", 
                                 QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if res == QMessageBox.Yes:
            path, _ = QFileDialog.getOpenFileName(self, "Select Document", get_default_dialog_dir(), 
                                                "Legal Docs (*.pdf *.docx *.txt *.md);;All Files (*)")
            if path: self.path_input.setText(path)
        elif res == QMessageBox.No:
            path = QFileDialog.getExistingDirectory(self, "Select Folder", get_default_dialog_dir())
            if path: self.path_input.setText(path)

    def start_extraction(self):
        text = self.input_text.toPlainText().strip()
        path = self.path_input.text().strip()
        if not text and not path:
            self.status.warn("Input required.")
            return
        is_folder = os.path.isdir(path) if path else False
        selected_type = self.entity_types_combo.currentText()
        extraction_type = selected_type if selected_type != "All" else "All"
        options = {
            "entity_types": [] if selected_type == "All" else [selected_type],
            "extraction_model": self.model_combo.currentText().split(" ")[0].lower(),
            "grounding_enabled": self.kb_grounding_cb.isChecked()
        }
        self.extract_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.job_status.set_status("running", "Extracting...")
        self.status.loading("Running legal ensemble...")

        worker_instance = None
        if is_folder:
            worker_instance = EntityExtractionFolderWorker(path, extraction_type, options)
        else:
            # Pass self.asyncio_thread to the worker if it expects it
            worker_instance = EntityExtractionWorker(self.asyncio_thread, path, text, extraction_type, options)
        
        # Connect signals
        if worker_instance:
            worker_instance.result_ready.connect(self.on_extraction_finished)
            # BaseTab handles error_occurred, so no need to connect directly
            self.start_worker(worker_instance) # Use BaseTab's start_worker

    def on_extraction_finished(self, results):
        self.current_results = results
        self.display_results(results)
        self.job_status.set_status("success", "Complete")
        self.status.success(f"Found {len(results.get('entities', []))} entities.")
        self.extract_button.setEnabled(True)
        self.progress_bar.setVisible(False)



    def display_results(self, results):
        self.results_table.setSortingEnabled(False)
        entities = results.get("entities", [])
        self.results_table.setRowCount(len(entities))
        for i, ent in enumerate(entities):
            text_item = QTableWidgetItem(ent.get("text", ""))
            type_item = QTableWidgetItem(ent.get("entity_type", ""))
            conf = float(ent.get("confidence", 0.5))
            conf_item = QTableWidgetItem(f"{conf:.2f}")
            if conf > 0.8: conf_item.setForeground(QColor("#2e7d32"))
            elif conf < 0.6: conf_item.setForeground(QColor("#c62828"))
            method_item = QTableWidgetItem(ent.get("extraction_method", "unknown"))
            status_item = QTableWidgetItem("Pending")
            self.results_table.setItem(i, 0, text_item)
            self.results_table.setItem(i, 1, type_item)
            self.results_table.setItem(i, 2, conf_item)
            self.results_table.setItem(i, 3, method_item)
            self.results_table.setItem(i, 4, status_item)
            text_item.setData(Qt.UserRole, ent)
        self.results_table.setSortingEnabled(True)
        self.results_info.setText(f"Ensemble Extraction: {len(entities)} items identified.")

    def filter_table(self, text):
        for i in range(self.results_table.rowCount()):
            match = any(text.lower() in (self.results_table.item(i, j).text().lower() if self.results_table.item(i, j) else "") 
                       for j in range(self.results_table.columnCount()))
            self.results_table.setRowHidden(i, not match)

    def approve_table_selection(self):
        for idx in self.results_table.selectionModel().selectedRows():
            self.results_table.setItem(idx.row(), 4, QTableWidgetItem("Approved ✅"))
            self.results_table.item(idx.row(), 4).setForeground(QColor("#2e7d32"))

    def sync_to_memory(self):
        if not self.current_results: return
        self.status.loading("Syncing to Agent Memory...")
        count, failed = self._sync_entities_to_manager_memory(self.current_results)
        if count > 0: self.status.success(f"Synced {count} entities.")
        else: self.status.error("Sync failed.")

    def _sync_entities_to_manager_memory(self, results: dict) -> tuple[int, int]:
        entities = results.get("entities", [])
        synced, failed = 0, 0
        for ent in entities:
            term = str(ent.get("text", "")).strip()
            if not term: continue
            proposal = {
                "namespace": "legal_entities",
                "key": f"entity_{int(time.time())}_{synced}",
                "content": json.dumps(ent),
                "memory_type": "entity",
                "agent_id": "entity_tab",
                "document_id": results.get("document_id", "manual"),
                "metadata": {"entity_type": ent.get("entity_type")},
                "confidence_score": float(ent.get("confidence", 0.5)),
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
            try:
                api_client.post("/api/agents/memory/proposals", json=proposal)
                synced += 1
            except Exception: failed += 1
        return synced, failed

    def export_json(self):
        if not self.current_results: return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save JSON", "", "JSON (*.json)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.current_results, f, indent=2)
            self.status.success("Exported.")

    def clear_results(self):
        self.results_table.setRowCount(0)
        self.input_text.clear()
        self.path_input.clear()
        self.current_results = None
        self.job_status.reset()
        self.status.info("Workspace cleared.")
