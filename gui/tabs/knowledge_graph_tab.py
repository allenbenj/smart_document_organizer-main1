"""
Knowledge Graph Tab - GUI component for knowledge graph operations

This module provides the UI for knowledge graph operations including
entity management, relationship queries, and graph visualization.
"""

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from ..services import api_client


class KnowledgeGraphTab(QWidget):
    """Tab for knowledge graph operations."""

    def __init__(self, asyncio_thread):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.init_ui()

    def init_ui(self):
        """Initialize the knowledge graph tab UI."""
        layout = QVBoxLayout()

        # Title
        title = QLabel("Knowledge Graph Operations")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Graph Operations Group
        operations_group = QGroupBox("Graph Operations")
        operations_layout = QVBoxLayout()

        # Entity input
        entity_layout = QHBoxLayout()
        entity_layout.addWidget(QLabel("Entity:"))
        self.entity_input = QLineEdit()
        self.entity_input.setPlaceholderText("Enter entity name or ID")
        entity_layout.addWidget(self.entity_input)
        operations_layout.addLayout(entity_layout)

        # Relationship input
        rel_layout = QHBoxLayout()
        rel_layout.addWidget(QLabel("Relationship:"))
        self.relationship_input = QLineEdit()
        self.relationship_input.setPlaceholderText("Enter relationship type")
        rel_layout.addWidget(self.relationship_input)
        operations_layout.addLayout(rel_layout)

        # Text reasoning input for KG extraction
        text_row = QVBoxLayout()
        text_row.addWidget(QLabel("Text for KG Reasoning:"))
        self.kg_text = QTextEdit()
        self.kg_text.setMaximumHeight(100)
        self.kg_text.setPlaceholderText(
            "Paste text to extract knowledge graph triples…"
        )
        text_row.addWidget(self.kg_text)
        operations_layout.addLayout(text_row)

        # Operation buttons
        button_layout = QHBoxLayout()
        self.add_entity_btn = QPushButton("Add Entity")
        self.find_relations_btn = QPushButton("List Entities")
        # Ontology type selector for adding entities
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type:"))
        self.kg_type_combo = QComboBox()
        self.kg_type_combo.addItems(["generic"])  # will be replaced if API available
        type_row.addWidget(self.kg_type_combo)
        operations_layout.addLayout(type_row)
        self.visualize_btn = QPushButton("Visualize Graph")
        self.clear_graph_btn = QPushButton("Clear Results")
        self.kg_reason_btn = QPushButton("Extract KG from Text")
        self.kg_import_btn = QPushButton("Import Extracted Triples")
        self.kg_heuristics_cb = QCheckBox("Heuristic typing")
        self.kg_heuristics_cb.setChecked(True)

        button_layout.addWidget(self.add_entity_btn)
        button_layout.addWidget(self.find_relations_btn)
        button_layout.addWidget(self.visualize_btn)
        button_layout.addWidget(self.clear_graph_btn)
        button_layout.addWidget(self.kg_reason_btn)
        button_layout.addWidget(self.kg_import_btn)
        button_layout.addWidget(self.kg_heuristics_cb)
        operations_layout.addLayout(button_layout)

        # Ingestion Group (Files & Folders)
        ingest_group = QGroupBox("Ingest Documents → Knowledge Graph")
        ingest_layout = QVBoxLayout()
        controls_row = QHBoxLayout()
        self.kg_add_file_btn = QPushButton("Add File…")
        self.kg_add_folder_btn = QPushButton("Add Folder…")
        self.kg_process_btn = QPushButton("Extract KG from Files")
        controls_row.addWidget(self.kg_add_file_btn)
        controls_row.addWidget(self.kg_add_folder_btn)
        controls_row.addWidget(self.kg_process_btn)
        controls_row.addStretch()
        ingest_layout.addLayout(controls_row)
        self.kg_queue = QTableWidget(0, 2)
        self.kg_queue.setHorizontalHeaderLabels(["Path", "Status"])
        self.kg_queue.setMinimumHeight(120)
        ingest_layout.addWidget(self.kg_queue)
        ingest_group.setLayout(ingest_layout)

        operations_group.setLayout(operations_layout)

        # Results Group
        results_group = QGroupBox("Graph Results")
        results_layout = QVBoxLayout()

        self.graph_results = QTextEdit()
        self.graph_results.setReadOnly(True)
        self.graph_results.setMinimumHeight(300)
        results_layout.addWidget(self.graph_results)
        results_group.setLayout(results_layout)

        layout.addWidget(operations_group)
        layout.addWidget(ingest_group)
        layout.addWidget(results_group)

        # Proposals Group
        proposals_group = QGroupBox("Knowledge Proposals (Approval)")
        proposals_layout = QVBoxLayout()
        self.proposals_table = QTableWidget(0, 3)
        self.proposals_table.setHorizontalHeaderLabels(["ID", "Kind", "Summary"])
        btn_row = QHBoxLayout()
        self.load_props_btn = QPushButton("Load Proposals")
        self.approve_btn = QPushButton("Approve Selected")
        self.reject_btn = QPushButton("Reject Selected")
        btn_row.addWidget(self.load_props_btn)
        btn_row.addWidget(self.approve_btn)
        btn_row.addWidget(self.reject_btn)
        proposals_layout.addLayout(btn_row)
        proposals_layout.addWidget(self.proposals_table)
        proposals_group.setLayout(proposals_layout)
        layout.addWidget(proposals_group)

        self.setLayout(layout)

        # Connect signals
        self.add_entity_btn.clicked.connect(self.add_entity)
        self.find_relations_btn.clicked.connect(self.find_relations)
        self.visualize_btn.clicked.connect(self.visualize_graph)
        self.clear_graph_btn.clicked.connect(self.clear_graph_results)
        self.kg_reason_btn.clicked.connect(self.kg_reason_over_text)
        self.kg_import_btn.clicked.connect(self.kg_import_triples)
        # Load ontology types for KG
        try:
            result = api_client.get_ontology_entities()
            items = result.get("items", [])
            labels = [
                it.get("label", "").strip() for it in items if it.get("label")
            ]
            if labels:
                self.kg_type_combo.clear()
                self.kg_type_combo.addItems(labels)
        except Exception:
            pass
        # Hook proposal buttons
        self.load_props_btn.clicked.connect(self.load_proposals)
        self.approve_btn.clicked.connect(self.approve_selected)
        self.reject_btn.clicked.connect(self.reject_selected)
        # Ingest controls
        self.kg_add_file_btn.clicked.connect(self._kg_add_file)
        self.kg_add_folder_btn.clicked.connect(self._kg_add_folder)
        self.kg_process_btn.clicked.connect(self._kg_process_files)

    def add_entity(self):  # noqa: C901
        """Add entity to knowledge graph via API."""
        name = self.entity_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Warning", "Please enter an entity name.")
            return
        try:
            data = api_client.add_knowledge_entity(name, self.kg_type_combo.currentText())
            self.graph_results.append(f"Added entity: {name} (id={data.get('id')})")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add entity: {e}")

    def find_relations(self):
        """List entities via API (temporary action)."""
        try:
            data = api_client.get_knowledge_entities()
            items = data.get("items", [])
            self.graph_results.append(f"Entities ({len(items)}):")
            for it in items[:50]:
                self.graph_results.append(
                    f"- {it.get('id','?')}: {it.get('name','')} [{it.get('entity_type','')}]"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to list entities: {e}")

    def _kg_add_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Document", "", "All Files (*);"
        )
        if path:
            row = self.kg_queue.rowCount()
            self.kg_queue.insertRow(row)
            self.kg_queue.setItem(row, 0, QTableWidgetItem(path))
            self.kg_queue.setItem(row, 1, QTableWidgetItem("queued"))

    def _kg_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", "")
        if folder:
            try:
                files = []
                for f in os.listdir(folder):
                    p = os.path.join(folder, f)
                    if os.path.isfile(p):
                        files.append(p)
                for p in files:
                    row = self.kg_queue.rowCount()
                    self.kg_queue.insertRow(row)
                    self.kg_queue.setItem(row, 0, QTableWidgetItem(p))
                    self.kg_queue.setItem(row, 1, QTableWidgetItem("queued"))
            except Exception as e:
                QMessageBox.critical(self, "Folder Error", str(e))

    def _kg_process_files(self):
        files = []
        for i in range(self.kg_queue.rowCount()):
            item = self.kg_queue.item(i, 0)
            if item:
                files.append(item.text())
        if not files:
            QMessageBox.information(self, "Info", "No files queued.")
            return
        self._kg_worker = KGFromFilesWorker(files)
        self._kg_worker.progress_update.connect(self._kg_on_progress)
        self._kg_worker.finished_ok.connect(
            lambda msg: QMessageBox.information(self, "KG", msg)
        )
        self._kg_worker.finished_err.connect(
            lambda err: QMessageBox.critical(self, "KG Error", err)
        )
        self._kg_worker.finished.connect(self._kg_worker.deleteLater)
        self._kg_worker.start()

    def _kg_on_progress(self, index: int, status: str):
        if 0 <= index < self.kg_queue.rowCount():
            self.kg_queue.setItem(index, 1, QTableWidgetItem(status))

    def kg_reason_over_text(self):
        """Call legal analysis agent to extract KG triples from free text."""
        text = self.kg_text.toPlainText().strip()
        if not text:
            QMessageBox.information(
                self, "Info", "Enter text to extract a knowledge graph."
            )
            return
        try:
            result = api_client.analyze_legal_kg(text, {"timeout": 6.0})
            data = result.get("data", {})
            triples = (data.get("knowledge_graph") or {}).get("triples", [])
            # cache last triples for import
            self._last_triples = list(triples)
            self.graph_results.append("Extracted Triples:")
            if not triples:
                self.graph_results.append("(none)")
            for h, rel, t in triples[:50]:
                self.graph_results.append(f"- ({h}) -[{rel}]-> ({t})")
        except Exception as e:
            QMessageBox.critical(self, "KG Reasoning Error", str(e))

    def kg_import_triples(self):
        """Import last extracted triples into knowledge store."""
        triples = getattr(self, "_last_triples", [])
        if not triples:
            QMessageBox.information(self, "Info", "No extracted triples to import.")
            return
        try:
            if not requests:
                raise RuntimeError("requests not available")
            # Use ontology type selected in the UI when available
            default_label = None
            try:
                default_label = self.kg_type_combo.currentText().strip() or None
            except Exception:
                default_label = None
            payload = {
                "triples": triples,
                "entity_type": "generic",
                "entity_type_label": default_label,
                "create_missing": True,
                "use_heuristics": bool(self.kg_heuristics_cb.isChecked()),
            }
            res = api_client.import_triples(triples, {
                "entity_type": "generic",
                "entity_type_label": default_label,
                "create_missing": True,
                "use_heuristics": bool(self.kg_heuristics_cb.isChecked()),
            })
            ce = res.get("created_entities", 0)
            cr = res.get("created_relationships", 0)
            QMessageBox.information(
                self, "Imported", f"Created entities: {ce}, relationships: {cr}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def load_proposals(self):
        try:
            result = api_client.get_knowledge_proposals()
            items = result.get("items", [])
            self.proposals_table.setRowCount(len(items))
            for i, it in enumerate(items):
                self.proposals_table.setItem(
                    i, 0, QTableWidgetItem(str(it.get("id", "")))
                )
                self.proposals_table.setItem(i, 1, QTableWidgetItem(it.get("kind", "")))
                # Summarize data
                data = it.get("data", {})
                summary = ", ".join(f"{k}={v}" for k, v in list(data.items())[:3])
                self.proposals_table.setItem(i, 2, QTableWidgetItem(summary))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load proposals: {e}")

    def _selected_proposal_id(self) -> Optional[int]:
        sel = self.proposals_table.currentRow()
        if sel < 0:
            return None
        item = self.proposals_table.item(sel, 0)
        if not item:
            return None
        try:
            return int(item.text())
        except Exception:
            return None

    def approve_selected(self):
        try:
            pid = self._selected_proposal_id()
            if pid is None:
                QMessageBox.information(self, "Info", "Select a proposal to approve.")
                return
            api_client.approve_proposal(pid)
            QMessageBox.information(
                self, "Approved", "Proposal approved and added to knowledge."
            )
            self.load_proposals()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Approve failed: {e}")

    def reject_selected(self):
        try:
            pid = self._selected_proposal_id()
            if pid is None:
                QMessageBox.information(self, "Info", "Select a proposal to reject.")
                return
            api_client.reject_proposal(pid)
            QMessageBox.information(self, "Rejected", "Proposal rejected.")
            self.load_proposals()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Reject failed: {e}")

    def visualize_graph(self):
        """Visualize knowledge graph."""
        QMessageBox.information(self, "Info", "Graph visualization coming soon.")

    def clear_graph_results(self):
        """Clear graph results."""
        self.graph_results.clear()
        self.entity_input.clear()
        self.relationship_input.clear()


# Import here to avoid circular imports
from .workers import KGFromFilesWorker