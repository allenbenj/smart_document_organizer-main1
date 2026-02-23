"""
Knowledge Graph Tab - GUI component for knowledge graph operations

This module provides the UI for knowledge graph operations including
entity management, relationship queries, and graph visualization.
"""

import os
import json
import logging
from typing import Any, Optional

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
    QTabWidget,
)

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from ..services import api_client
from gui.core.base_tab import BaseTab

logger = logging.getLogger(__name__)


class KnowledgeGraphTab(BaseTab):
    """Tab for knowledge graph operations."""

    def __init__(self, asyncio_thread: Optional[Any] = None, parent=None):
        super().__init__("Knowledge Graph", asyncio_thread, parent)
        self.init_ui()
        # Defer API calls so the UI appears immediately
        QTimer.singleShot(0, self._load_ontology_types)

    def setup_ui(self):
        """Initialize the knowledge graph tab UI."""
        # Main title
        title = QLabel("Knowledge Graph Workflow")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        # Create a tab widget to organize the workflow
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        # Create the three main workflow tabs
        self.ingest_tab = QWidget()
        self.review_tab = QWidget()
        self.explore_tab = QWidget()

        self.tab_widget.addTab(self.ingest_tab, "1. Ingest & Extract")
        self.tab_widget.addTab(self.review_tab, "2. Review & Approve")
        self.tab_widget.addTab(self.explore_tab, "3. Explore & Manage")

        # Set up the UI for each tab
        self._setup_ingest_ui()
        self._setup_review_ui()
        self._setup_explore_ui()

        # Connect signals
        self._connect_signals()
        
    def _setup_ingest_ui(self):
        """Set up the UI for the Ingest & Extract tab."""
        layout = QVBoxLayout(self.ingest_tab)

        # Group for text-based extraction
        text_group = QGroupBox("Extract Knowledge from Text")
        text_layout = QVBoxLayout(text_group)
        self.kg_text = QTextEdit()
        self.kg_text.setPlaceholderText("Paste text here to extract knowledge graph triples...")
        self.kg_text.setMinimumHeight(150)
        text_layout.addWidget(self.kg_text)
        self.kg_reason_btn = QPushButton("Extract from Text")
        text_layout.addWidget(self.kg_reason_btn)
        layout.addWidget(text_group)

        # Group for file-based ingestion
        ingest_group = QGroupBox("Extract Knowledge from Documents")
        ingest_layout = QVBoxLayout(ingest_group)
        controls_row = QHBoxLayout()
        self.kg_add_file_btn = QPushButton("Add File(s)...")
        self.kg_add_folder_btn = QPushButton("Add Folder...")
        controls_row.addWidget(self.kg_add_file_btn)
        controls_row.addWidget(self.kg_add_folder_btn)
        controls_row.addStretch()
        ingest_layout.addLayout(controls_row)
        
        self.kg_queue = QTableWidget(0, 2)
        self.kg_queue.setHorizontalHeaderLabels(["Path", "Status"])
        self.kg_queue.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        ingest_layout.addWidget(self.kg_queue)

        self.kg_process_btn = QPushButton("Process Queued Files")
        ingest_layout.addWidget(self.kg_process_btn)
        layout.addWidget(ingest_group)

        # Output log for this tab
        results_group = QGroupBox("Extraction Log")
        results_layout = QVBoxLayout(results_group)
        self.graph_results = QTextEdit()
        self.graph_results.setReadOnly(True)
        results_layout.addWidget(self.graph_results)
        self.clear_graph_btn = QPushButton("Clear Log")
        results_layout.addWidget(self.clear_graph_btn)
        layout.addWidget(results_group)

        layout.addStretch()

    def _setup_review_ui(self):
        """Set up the UI for the Review & Approve tab."""
        layout = QVBoxLayout(self.review_tab)

        proposals_group = QGroupBox("Review Extracted Knowledge Proposals")
        proposals_layout = QVBoxLayout(proposals_group)
        
        btn_row = QHBoxLayout()
        self.load_props_btn = QPushButton("Refresh Proposals")
        self.approve_btn = QPushButton("Approve Selected")
        self.reject_btn = QPushButton("Reject Selected")
        self.kg_import_btn = QPushButton("Import Extracted Triples")
        btn_row.addWidget(self.load_props_btn)
        btn_row.addWidget(self.approve_btn)
        btn_row.addWidget(self.reject_btn)
        btn_row.addWidget(self.kg_import_btn)
        proposals_layout.addLayout(btn_row)

        self.proposals_table = QTableWidget(0, 3)
        self.proposals_table.setHorizontalHeaderLabels(["ID", "Type", "Summary"])
        self.proposals_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.proposals_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        proposals_layout.addWidget(self.proposals_table)
        
        layout.addWidget(proposals_group)
        layout.addStretch()

    def _setup_explore_ui(self):
        """Set up the UI for the Explore & Manage tab."""
        layout = QVBoxLayout(self.explore_tab)
        
        # Entity and relationship exploration
        explore_group = QGroupBox("Explore the Knowledge Graph")
        explore_layout = QVBoxLayout(explore_group)
        
        entity_layout = QHBoxLayout()
        entity_layout.addWidget(QLabel("Entity:"))
        self.entity_input = QLineEdit()
        self.entity_input.setPlaceholderText("Enter entity name or ID")
        entity_layout.addWidget(self.entity_input)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type:"))
        self.kg_type_combo = QComboBox()
        self.kg_type_combo.addItems(["generic"])  # will be replaced if API available
        type_row.addWidget(self.kg_type_combo)
        entity_layout.addLayout(type_row)
        
        self.add_entity_btn = QPushButton("Add Entity")
        entity_layout.addWidget(self.add_entity_btn)
        
        self.find_relations_btn = QPushButton("Find Entities/Relationships")
        entity_layout.addWidget(self.find_relations_btn)
        explore_layout.addLayout(entity_layout)

        self.visualize_btn = QPushButton("Visualize Graph")
        explore_layout.addWidget(self.visualize_btn)
        layout.addWidget(explore_group)

        # Agent Memory Manager (Curation)
        manager_group = QGroupBox("Curate Agent Memory")
        manager_layout = QVBoxLayout(manager_group)

        manager_filter_row = QHBoxLayout()
        manager_filter_row.addWidget(QLabel("Search:"))
        self.manager_query_filter = QLineEdit()
        self.manager_query_filter.setPlaceholderText("term, category, status...")
        manager_filter_row.addWidget(self.manager_query_filter)
        self.manager_load_btn = QPushButton("Load Memory")
        manager_filter_row.addWidget(self.manager_load_btn)
        manager_layout.addLayout(manager_filter_row)

        self.manager_table = QTableWidget(0, 9)
        self.manager_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Term",
                "Category",
                "Canonical",
                "Ontology ID",
                "Jurisdiction",
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
        manager_layout.addWidget(self.manager_table)
        
        # Simplified edit controls
        manager_edit_row = QHBoxLayout()
        manager_edit_row.addWidget(QLabel("ID:"))
        self.manager_id_edit = QLineEdit()
        self.manager_id_edit.setReadOnly(True)
        manager_edit_row.addWidget(self.manager_id_edit)
        manager_edit_row.addWidget(QLabel("Canonical:"))
        self.manager_canonical_edit = QLineEdit()
        manager_edit_row.addWidget(self.manager_canonical_edit)
        self.manager_update_btn = QPushButton("Update Selected")
        manager_edit_row.addWidget(self.manager_update_btn)
        self.manager_delete_btn = QPushButton("Delete Selected")
        manager_edit_row.addWidget(self.manager_delete_btn)
        manager_layout.addLayout(manager_edit_row)

        manager_group.setLayout(manager_layout)
        layout.addWidget(manager_group)
        layout.addStretch()

    def _connect_signals(self):
        """Connect all UI signals to their respective slots."""
        # Ingest Tab
        self.kg_reason_btn.clicked.connect(self.kg_reason_over_text)
        self.kg_add_file_btn.clicked.connect(self._kg_add_file)
        self.kg_add_folder_btn.clicked.connect(self._kg_add_folder)
        self.kg_process_btn.clicked.connect(self._kg_process_files)
        self.clear_graph_btn.clicked.connect(self.clear_graph_results)

        # Review Tab
        self.load_props_btn.clicked.connect(self.load_proposals)
        self.approve_btn.clicked.connect(self.approve_selected)
        self.reject_btn.clicked.connect(self.reject_selected)
        self.kg_import_btn.clicked.connect(self.kg_import_triples)

        # Explore Tab
        self.add_entity_btn.clicked.connect(self.add_entity)
        self.find_relations_btn.clicked.connect(self.find_relations)
        self.visualize_btn.clicked.connect(self.visualize_graph)
        self.manager_load_btn.clicked.connect(self.load_manager_knowledge)
        self.manager_table.itemSelectionChanged.connect(self.on_manager_item_selected)
        self.manager_update_btn.clicked.connect(self.update_selected_manager_item)
        self.manager_delete_btn.clicked.connect(self.delete_selected_manager_item)
    
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
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error loading ontology types: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response loading ontology types: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred loading ontology types: {e}")

    def add_entity(self):  # noqa: C901
        """Add entity to knowledge graph via API."""
        name = self.entity_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Warning", "Please enter an entity name.")
            return
        try:
            data = api_client.add_knowledge_entity(name, self.kg_type_combo.currentText())
            self.graph_results.append(f"Added entity: {name} (id={data.get('id')})")
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error adding entity: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add entity (API connection error): {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response adding entity: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add entity (Invalid API response): {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred adding entity: {e}")
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
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error listing entities: {e}")
            QMessageBox.critical(self, "Error", f"Failed to list entities (API connection error): {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response listing entities: {e}")
            QMessageBox.critical(self, "Error", f"Failed to list entities (Invalid API response): {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred listing entities: {e}")
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
            except (IOError, OSError) as e:
                logger.error(f"File system error adding folder: {e}")
                QMessageBox.critical(self, "Folder Error", f"File system error: {e}")
            except Exception as e:
                logger.exception(f"An unexpected error occurred adding folder: {e}")
                QMessageBox.critical(self, "Folder Error", f"An unexpected error occurred: {e}")
                
    def _kg_process_files(self):
        files = []
        for i in range(self.kg_queue.rowCount()):
            item = self.kg_queue.item(i, 0)
            if item:
                files.append(item.text())
        if not files:
            QMessageBox.information(self, "Info", "No files queued.")
            return
        worker_instance = KGFromFilesWorker(files)
        worker_instance.progress_update.connect(self._kg_on_progress)
        worker_instance.finished_ok.connect(
            lambda msg: QMessageBox.information(self, "KG", msg)
        )
        # BaseTab handles finished_err and finished, so no need to connect directly
        self.start_worker(worker_instance)

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
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error during KG reasoning: {e}")
            QMessageBox.critical(self, "KG Reasoning Error", f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response during KG reasoning: {e}")
            QMessageBox.critical(self, "KG Reasoning Error", f"Invalid API response: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred during KG reasoning: {e}")
            QMessageBox.critical(self, "KG Reasoning Error", f"An unexpected error occurred: {e}")

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
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error importing triples: {e}")
            QMessageBox.critical(self, "Import Error", f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response importing triples: {e}")
            QMessageBox.critical(self, "Import Error", f"Invalid API response: {e}")
        except RuntimeError as e:
            logger.error(f"Runtime error importing triples: {e}")
            QMessageBox.critical(self, "Import Error", f"Runtime error: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred importing triples: {e}")
            QMessageBox.critical(self, "Import Error", f"An unexpected error occurred: {e}")

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
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error loading proposals: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load proposals (API connection error): {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response loading proposals: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load proposals (Invalid API response): {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred loading proposals: {e}")
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
        except ValueError:
            logger.warning(f"Invalid proposal ID in table: '{item.text()}'")
            return None
        except Exception as e:
            logger.exception(f"An unexpected error occurred in _selected_proposal_id: {e}")
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
        
    def load_manager_knowledge(self):
        """Load agent memory items for curation."""
        try:
            result = api_client.list_manager_knowledge(
                status=self.manager_query_filter.text().strip() or None,
                category=self.manager_query_filter.text().strip() or None,
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
                self.manager_table.setItem(i, 5, QTableWidgetItem(str(item.get("jurisdiction", ""))))
                self.manager_table.setItem(i, 6, QTableWidgetItem(str(item.get("confidence", ""))))
                self.manager_table.setItem(i, 7, QTableWidgetItem(str(item.get("status", ""))))
                self.manager_table.setItem(i, 8, QTableWidgetItem(str(bool(item.get("verified")))))
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
        except ValueError:
            logger.warning(f"Invalid manager ID in table: '{item.text()}'")
            return None
        except Exception as e:
            logger.exception(f"An unexpected error occurred in _selected_manager_id: {e}")
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
            except ValueError:
                logger.warning(f"Invalid manager ID in selected row: '{item.text()}'")
                continue
            except Exception as e:
                logger.exception(f"An unexpected error occurred processing selected manager ID: {e}")
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
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error getting manager knowledge item {knowledge_id}: {e}")
            QMessageBox.critical(self, "Memory Selection Error", f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response getting manager knowledge item {knowledge_id}: {e}")
            QMessageBox.critical(self, "Memory Selection Error", f"Invalid API response: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred getting manager knowledge item {knowledge_id}: {e}")
            QMessageBox.critical(self, "Memory Selection Error", f"An unexpected error occurred: {e}")
            
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
        }
        
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
                except requests.exceptions.RequestException as e:
                    logger.error(f"API connection error updating manager knowledge item {knowledge_id}: {e}")
                    failed += 1
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid API response updating manager knowledge item {knowledge_id}: {e}")
                    failed += 1
                except Exception as e:
                    logger.exception(f"An unexpected error occurred updating manager knowledge item {knowledge_id}: {e}")
                    failed += 1
            self.graph_results.append(
                f"Updated manager memory items: updated={updated}, failed={failed}."
            )
            self.load_manager_knowledge()
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error for memory update: {e}")
            QMessageBox.critical(self, "Memory Update Error", f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response for memory update: {e}")
            QMessageBox.critical(self, "Memory Update Error", f"Invalid API response: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred during memory update: {e}")
            QMessageBox.critical(self, "Memory Update Error", f"An unexpected error occurred: {e}")

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
                except requests.exceptions.RequestException as e:
                    logger.error(f"API connection error deleting manager knowledge item {knowledge_id}: {e}")
                    failed += 1
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid API response deleting manager knowledge item {knowledge_id}: {e}")
                    failed += 1
                except Exception as e:
                    logger.exception(f"An unexpected error occurred deleting manager knowledge item {knowledge_id}: {e}")
                    failed += 1
            self.graph_results.append(
                f"Deleted manager memory items: deleted={deleted}, failed={failed}."
            )
            self.load_manager_knowledge()
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error for memory delete: {e}")
            QMessageBox.critical(self, "Memory Delete Error", f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response for memory delete: {e}")
            QMessageBox.critical(self, "Memory Delete Error", f"Invalid API response: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred during memory delete: {e}")
            QMessageBox.critical(self, "Memory Delete Error", f"An unexpected error occurred: {e}")
            
# Import here to avoid circular imports
from .workers import KGFromFilesWorker  # noqa: E402
