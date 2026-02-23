"""
Knowledge Graph Tab - GUI component for knowledge graph operations

This module provides the UI for knowledge graph operations including
entity management, relationship queries, and graph visualization.
"""

import os
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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
        # Defer API calls so the UI appears immediately
        QTimer.singleShot(0, self._load_ontology_types)

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

        button_layout.addWidget(self.add_entity_btn)
        button_layout.addWidget(self.find_relations_btn)
        button_layout.addWidget(self.visualize_btn)
        button_layout.addWidget(self.clear_graph_btn)
        button_layout.addWidget(self.kg_reason_btn)
        button_layout.addWidget(self.kg_import_btn)
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

        # Manager Knowledge Group (Agent Memory Curation)
        manager_group = QGroupBox("Agent Memory Manager")
        manager_layout = QVBoxLayout()

        manager_filter_row = QHBoxLayout()
        manager_filter_row.addWidget(QLabel("Status:"))
        self.manager_status_filter = QLineEdit()
        self.manager_status_filter.setPlaceholderText("e.g. proposed, verified")
        manager_filter_row.addWidget(self.manager_status_filter)
        manager_filter_row.addWidget(QLabel("Category:"))
        self.manager_category_filter = QLineEdit()
        self.manager_category_filter.setPlaceholderText("e.g. person, case")
        manager_filter_row.addWidget(self.manager_category_filter)
        manager_filter_row.addWidget(QLabel("Search:"))
        self.manager_query_filter = QLineEdit()
        self.manager_query_filter.setPlaceholderText("term, notes, canonical value...")
        manager_filter_row.addWidget(self.manager_query_filter)
        self.manager_load_btn = QPushButton("Load Memory Items")
        manager_filter_row.addWidget(self.manager_load_btn)
        manager_layout.addLayout(manager_filter_row)

        self.manager_table = QTableWidget(0, 8)
        self.manager_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Term",
                "Category",
                "Canonical",
                "Ontology ID",
                "Confidence",
                "Status",
                "Verified",
            ]
        )
        self.manager_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.manager_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.manager_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.manager_table.setMinimumHeight(180)
        manager_layout.addWidget(self.manager_table)

        manager_edit_row = QHBoxLayout()
        manager_edit_row.addWidget(QLabel("ID:"))
        self.manager_id_edit = QLineEdit()
        self.manager_id_edit.setReadOnly(True)
        self.manager_id_edit.setFixedWidth(90)
        manager_edit_row.addWidget(self.manager_id_edit)
        manager_edit_row.addWidget(QLabel("Canonical:"))
        self.manager_canonical_edit = QLineEdit()
        manager_edit_row.addWidget(self.manager_canonical_edit)
        manager_edit_row.addWidget(QLabel("Ontology ID:"))
        self.manager_ontology_edit = QLineEdit()
        manager_edit_row.addWidget(self.manager_ontology_edit)
        manager_edit_row.addWidget(QLabel("Confidence:"))
        self.manager_confidence_edit = QLineEdit()
        self.manager_confidence_edit.setPlaceholderText("0.0 - 1.0")
        self.manager_confidence_edit.setFixedWidth(90)
        manager_edit_row.addWidget(self.manager_confidence_edit)
        manager_layout.addLayout(manager_edit_row)

        manager_notes_row = QHBoxLayout()
        manager_notes_row.addWidget(QLabel("Status:"))
        self.manager_status_edit = QLineEdit()
        manager_notes_row.addWidget(self.manager_status_edit)
        manager_notes_row.addWidget(QLabel("Verified By:"))
        self.manager_verified_by_edit = QLineEdit()
        manager_notes_row.addWidget(self.manager_verified_by_edit)
        manager_notes_row.addWidget(QLabel("Verified:"))
        self.manager_verified_combo = QComboBox()
        self.manager_verified_combo.addItems(["keep", "true", "false"])
        manager_notes_row.addWidget(self.manager_verified_combo)
        manager_layout.addLayout(manager_notes_row)

        manager_text_row = QHBoxLayout()
        manager_text_row.addWidget(QLabel("User Notes:"))
        self.manager_user_notes_edit = QLineEdit()
        manager_text_row.addWidget(self.manager_user_notes_edit)
        manager_text_row.addWidget(QLabel("Notes:"))
        self.manager_notes_edit = QLineEdit()
        manager_text_row.addWidget(self.manager_notes_edit)
        manager_layout.addLayout(manager_text_row)

        manager_action_row = QHBoxLayout()
        self.manager_create_btn = QPushButton("Create New Memory Item")
        self.manager_update_btn = QPushButton("Update Selected")
        self.manager_delete_one_btn = QPushButton("Delete Current ID")
        self.manager_delete_btn = QPushButton("Delete Selected")
        self.manager_verify_true_btn = QPushButton("Set Selected Verified=True")
        self.manager_verify_false_btn = QPushButton("Set Selected Verified=False")
        self.manager_delete_all_btn = QPushButton("Delete All Loaded")
        manager_action_row.addWidget(self.manager_create_btn)
        manager_action_row.addWidget(self.manager_update_btn)
        manager_action_row.addWidget(self.manager_delete_one_btn)
        manager_action_row.addWidget(self.manager_delete_btn)
        manager_action_row.addWidget(self.manager_verify_true_btn)
        manager_action_row.addWidget(self.manager_verify_false_btn)
        manager_action_row.addWidget(self.manager_delete_all_btn)
        manager_action_row.addStretch()
        manager_layout.addLayout(manager_action_row)

        manager_create_row = QHBoxLayout()
        manager_create_row.addWidget(QLabel("New Term:"))
        self.manager_new_term_edit = QLineEdit()
        self.manager_new_term_edit.setPlaceholderText("required")
        manager_create_row.addWidget(self.manager_new_term_edit)
        manager_create_row.addWidget(QLabel("New Category:"))
        self.manager_new_category_edit = QLineEdit()
        self.manager_new_category_edit.setPlaceholderText("optional")
        manager_create_row.addWidget(self.manager_new_category_edit)
        manager_create_row.addWidget(QLabel("Source:"))
        self.manager_new_source_edit = QLineEdit()
        self.manager_new_source_edit.setPlaceholderText("gui_knowledge_graph_tab")
        manager_create_row.addWidget(self.manager_new_source_edit)
        manager_layout.addLayout(manager_create_row)

        manager_group.setLayout(manager_layout)
        layout.addWidget(manager_group)

        self.setLayout(layout)

        # Connect signals
        self.add_entity_btn.clicked.connect(self.add_entity)
        self.find_relations_btn.clicked.connect(self.find_relations)
        self.visualize_btn.clicked.connect(self.visualize_graph)
        self.clear_graph_btn.clicked.connect(self.clear_graph_results)
        self.kg_reason_btn.clicked.connect(self.kg_reason_over_text)
        self.kg_import_btn.clicked.connect(self.kg_import_triples)
        # Hook proposal buttons
        self.load_props_btn.clicked.connect(self.load_proposals)
        self.approve_btn.clicked.connect(self.approve_selected)
        self.reject_btn.clicked.connect(self.reject_selected)
        # Manager memory controls
        self.manager_load_btn.clicked.connect(self.load_manager_knowledge)
        self.manager_table.itemSelectionChanged.connect(self.on_manager_item_selected)
        self.manager_create_btn.clicked.connect(self.create_manager_memory_item)
        self.manager_update_btn.clicked.connect(self.update_selected_manager_item)
        self.manager_delete_one_btn.clicked.connect(self.delete_current_manager_item)
        self.manager_delete_btn.clicked.connect(self.delete_selected_manager_item)
        self.manager_verify_true_btn.clicked.connect(
            lambda: self.bulk_set_verified_for_selected(True)
        )
        self.manager_verify_false_btn.clicked.connect(
            lambda: self.bulk_set_verified_for_selected(False)
        )
        self.manager_delete_all_btn.clicked.connect(self.delete_all_loaded_manager_items)
        # Ingest controls
        self.kg_add_file_btn.clicked.connect(self._kg_add_file)
        self.kg_add_folder_btn.clicked.connect(self._kg_add_folder)
        self.kg_process_btn.clicked.connect(self._kg_process_files)

    def _load_ontology_types(self):
        """Load ontology types from backend (deferred from constructor)."""
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
            res = api_client.import_triples(triples, {
                "entity_type": "generic",
                "entity_type_label": default_label,
                "create_missing": True,
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

    def load_manager_knowledge(self):
        """Load agent memory items for curation."""
        try:
            result = api_client.list_manager_knowledge(
                status=self.manager_status_filter.text().strip() or None,
                category=self.manager_category_filter.text().strip() or None,
                query=self.manager_query_filter.text().strip() or None,
                limit=500,
                offset=0,
            )
            items = result.get("items", [])
            self.manager_table.setRowCount(len(items))
            for i, item in enumerate(items):
                self.manager_table.setItem(i, 0, QTableWidgetItem(str(item.get("id", ""))))
                self.manager_table.setItem(i, 1, QTableWidgetItem(str(item.get("term", ""))))
                self.manager_table.setItem(i, 2, QTableWidgetItem(str(item.get("category", ""))))
                self.manager_table.setItem(i, 3, QTableWidgetItem(str(item.get("canonical_value", ""))))
                self.manager_table.setItem(i, 4, QTableWidgetItem(str(item.get("ontology_entity_id", ""))))
                self.manager_table.setItem(i, 5, QTableWidgetItem(str(item.get("confidence", ""))))
                self.manager_table.setItem(i, 6, QTableWidgetItem(str(item.get("status", ""))))
                self.manager_table.setItem(i, 7, QTableWidgetItem(str(bool(item.get("verified")))))
            self.graph_results.append(f"Loaded manager memory items: {len(items)}")
        except Exception as e:
            QMessageBox.critical(self, "Memory Load Error", str(e))

    def _selected_manager_id(self) -> Optional[int]:
        row = self.manager_table.currentRow()
        if row < 0:
            return None
        item = self.manager_table.item(row, 0)
        if item is None:
            return None
        try:
            return int(item.text())
        except Exception:
            return None

    def _selected_manager_ids(self) -> list[int]:
        """Return selected manager IDs from table row selection."""
        ids: list[int] = []
        sel = self.manager_table.selectionModel()
        if sel is None:
            return ids
        for idx in sel.selectedRows():
            item = self.manager_table.item(idx.row(), 0)
            if not item:
                continue
            try:
                ids.append(int(item.text()))
            except Exception:
                continue
        return ids

    def _all_loaded_manager_ids(self) -> list[int]:
        ids: list[int] = []
        for row in range(self.manager_table.rowCount()):
            item = self.manager_table.item(row, 0)
            if not item:
                continue
            try:
                ids.append(int(item.text()))
            except Exception:
                continue
        return ids

    def on_manager_item_selected(self):
        """Populate editor fields from selected manager memory item."""
        knowledge_id = self._selected_manager_id()
        if knowledge_id is None:
            return
        try:
            result = api_client.get_manager_knowledge_item(knowledge_id)
            item = result.get("item", {})
            self.manager_id_edit.setText(str(item.get("id", "")))
            self.manager_canonical_edit.setText(str(item.get("canonical_value", "") or ""))
            self.manager_ontology_edit.setText(str(item.get("ontology_entity_id", "") or ""))
            self.manager_confidence_edit.setText(str(item.get("confidence", "") or ""))
            self.manager_status_edit.setText(str(item.get("status", "") or ""))
            self.manager_verified_by_edit.setText(str(item.get("verified_by", "") or ""))
            self.manager_user_notes_edit.setText(str(item.get("user_notes", "") or ""))
            self.manager_notes_edit.setText(str(item.get("notes", "") or ""))
            verified_value = item.get("verified")
            if verified_value is True:
                self.manager_verified_combo.setCurrentText("true")
            elif verified_value is False:
                self.manager_verified_combo.setCurrentText("false")
            else:
                self.manager_verified_combo.setCurrentText("keep")
        except Exception as e:
            QMessageBox.critical(self, "Memory Selection Error", str(e))

    def update_selected_manager_item(self):
        """Persist selected manager memory item updates."""
        knowledge_ids = self._selected_manager_ids()
        if not knowledge_ids:
            single = self._selected_manager_id()
            if single is not None:
                knowledge_ids = [single]
        if not knowledge_ids:
            QMessageBox.information(self, "Info", "Select a memory item first.")
            return

        payload: dict = {
            "canonical_value": self.manager_canonical_edit.text().strip() or None,
            "ontology_entity_id": self.manager_ontology_edit.text().strip() or None,
            "status": self.manager_status_edit.text().strip() or None,
            "verified_by": self.manager_verified_by_edit.text().strip() or None,
            "user_notes": self.manager_user_notes_edit.text().strip() or None,
            "notes": self.manager_notes_edit.text().strip() or None,
        }
        confidence_text = self.manager_confidence_edit.text().strip()
        if confidence_text:
            try:
                payload["confidence"] = float(confidence_text)
            except ValueError:
                QMessageBox.warning(self, "Validation", "Confidence must be a number.")
                return
        verified_mode = self.manager_verified_combo.currentText()
        if verified_mode == "true":
            payload["verified"] = True
        elif verified_mode == "false":
            payload["verified"] = False

        payload = {k: v for k, v in payload.items() if v is not None}
        if not payload:
            QMessageBox.information(self, "Info", "No changes to update.")
            return
        try:
            updated = 0
            failed = 0
            for knowledge_id in knowledge_ids:
                try:
                    api_client.update_manager_knowledge_item(knowledge_id, payload)
                    updated += 1
                except Exception:
                    failed += 1
            self.graph_results.append(
                f"Updated manager memory items: updated={updated}, failed={failed}."
            )
            self.load_manager_knowledge()
        except Exception as e:
            QMessageBox.critical(self, "Memory Update Error", str(e))

    def create_manager_memory_item(self):
        """Create a new manager memory item conforming to manager_knowledge schema."""
        term = self.manager_new_term_edit.text().strip()
        if not term:
            QMessageBox.warning(self, "Validation", "New Term is required.")
            return
        payload: dict = {
            "term": term,
            "category": self.manager_new_category_edit.text().strip() or None,
            "canonical_value": self.manager_canonical_edit.text().strip() or None,
            "ontology_entity_id": self.manager_ontology_edit.text().strip() or None,
            "status": self.manager_status_edit.text().strip() or "proposed",
            "verified_by": self.manager_verified_by_edit.text().strip() or None,
            "user_notes": self.manager_user_notes_edit.text().strip() or None,
            "notes": self.manager_notes_edit.text().strip() or None,
            "source": self.manager_new_source_edit.text().strip() or "gui_knowledge_graph_tab",
            "confidence": 0.5,
            "verified": False,
        }
        confidence_text = self.manager_confidence_edit.text().strip()
        if confidence_text:
            try:
                payload["confidence"] = float(confidence_text)
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Validation",
                    "Confidence must be a number.",
                )
                return
        verified_mode = self.manager_verified_combo.currentText()
        if verified_mode == "true":
            payload["verified"] = True
        elif verified_mode == "false":
            payload["verified"] = False

        payload = {k: v for k, v in payload.items() if v is not None}
        try:
            result = api_client.upsert_manager_knowledge_item(payload)
            new_id = result.get("id")
            self.graph_results.append(
                f"Created manager memory item '{term}' (id={new_id})."
            )
            self.manager_new_term_edit.clear()
            self.load_manager_knowledge()
        except Exception as e:
            QMessageBox.critical(self, "Memory Create Error", str(e))

    def delete_selected_manager_item(self):
        """Delete selected manager memory item(s)."""
        knowledge_ids = self._selected_manager_ids()
        if not knowledge_ids:
            single = self._selected_manager_id()
            if single is not None:
                knowledge_ids = [single]
        if not knowledge_ids:
            QMessageBox.information(self, "Info", "Select one or more memory items first.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete Memory Items",
            f"Delete {len(knowledge_ids)} selected manager memory item(s)?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = 0
            failed = 0
            for knowledge_id in knowledge_ids:
                try:
                    api_client.delete_manager_knowledge_item(knowledge_id)
                    deleted += 1
                except Exception:
                    failed += 1
            self.graph_results.append(
                f"Deleted manager memory items: deleted={deleted}, failed={failed}."
            )
            self.load_manager_knowledge()
        except Exception as e:
            QMessageBox.critical(self, "Memory Delete Error", str(e))

    def delete_current_manager_item(self) -> None:
        """Delete the currently loaded manager memory item by ID field."""
        raw_id = self.manager_id_edit.text().strip()
        if not raw_id:
            QMessageBox.information(self, "Info", "No current ID loaded.")
            return
        try:
            knowledge_id = int(raw_id)
        except ValueError:
            QMessageBox.warning(self, "Validation", "Current ID is invalid.")
            return

        confirm = QMessageBox.question(
            self,
            "Delete Current ID",
            f"Delete manager memory item {knowledge_id}?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            api_client.delete_manager_knowledge_item(knowledge_id)
            self.graph_results.append(f"Deleted manager memory item {knowledge_id}.")
            self.manager_id_edit.clear()
            self.load_manager_knowledge()
        except Exception as e:
            QMessageBox.critical(self, "Memory Delete Error", str(e))

    def bulk_set_verified_for_selected(self, verified: bool) -> None:
        """Batch update verification state for selected rows."""
        knowledge_ids = self._selected_manager_ids()
        if not knowledge_ids:
            QMessageBox.information(self, "Info", "Select one or more rows first.")
            return
        try:
            updated = 0
            failed = 0
            for knowledge_id in knowledge_ids:
                try:
                    api_client.update_manager_knowledge_item(
                        knowledge_id,
                        {"verified": bool(verified), "status": "verified" if verified else "proposed"},
                    )
                    updated += 1
                except Exception:
                    failed += 1
            self.graph_results.append(
                f"Bulk verify update complete: updated={updated}, failed={failed}, value={verified}."
            )
            self.load_manager_knowledge()
        except Exception as e:
            QMessageBox.critical(self, "Bulk Verify Error", str(e))

    def delete_all_loaded_manager_items(self) -> None:
        """Delete all currently loaded manager memory rows."""
        knowledge_ids = self._all_loaded_manager_ids()
        if not knowledge_ids:
            QMessageBox.information(self, "Info", "No loaded memory items to delete.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete All Loaded",
            f"Delete all {len(knowledge_ids)} loaded memory item(s)?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = 0
            failed = 0
            for knowledge_id in knowledge_ids:
                try:
                    api_client.delete_manager_knowledge_item(knowledge_id)
                    deleted += 1
                except Exception:
                    failed += 1
            self.graph_results.append(
                f"Delete all loaded complete: deleted={deleted}, failed={failed}."
            )
            self.load_manager_knowledge()
        except Exception as e:
            QMessageBox.critical(self, "Delete All Error", str(e))


# Import here to avoid circular imports
from .workers import KGFromFilesWorker  # noqa: E402
