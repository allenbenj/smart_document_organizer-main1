"""
Agent Memory Manager - The High-Fidelity Intelligence Curation Hub
==================================================================
Unifies Memory Proposals (Pending AI findings) and Manager Knowledge (Verified KG)
into a single, high-resolution workspace for human expert curation.
"""

import json
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QSplitter,
    QAbstractItemView,
    QHeaderView,
    QTabWidget,
    QDialog,
    QSizePolicy,
)

from gui.services import api_client

EDITOR_JSON_TO_API_KEY = {
    "components_json": "components",
    "legal_use_cases_json": "legal_use_cases",
    "root_cause_json": "root_cause",
    "related_frameworks_json": "related_frameworks",
    "aliases_json": "aliases",
    "attributes_json": "attributes",
    "relations_json": "relations",
    "sources_json": "sources",
}

class AgentMemoryManagerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: List[Dict[str, Any]] = []
        self.curated_items: List[Dict[str, Any]] = []
        self.unified_items: List[Dict[str, Any]] = []
        self._dirty_curated_ids: set[int] = set()
        self._dirty_unified_rows: set[int] = set()
        self._last_bulk_undo: Optional[Dict[str, Any]] = None
        self._loading_curated = False
        self._loading_unified = False
        self.init_ui()
        
        # Initial Data Load
        QTimer.singleShot(100, self.refresh_all)

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Top Action Bar ---
        top_bar = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 Refresh All")
        self.refresh_btn.clicked.connect(self.refresh_all)
        self.refresh_btn.setStyleSheet("font-weight: bold; padding: 5px;")
        
        self.import_btn = QPushButton("📥 Import JSON")
        self.import_btn.clicked.connect(self.import_json)
        
        top_bar.addWidget(self.refresh_btn)
        top_bar.addWidget(self.import_btn)
        top_bar.addStretch()
        
        self.ont_status_label = QLabel("Ontology: Checking...")
        top_bar.addWidget(self.ont_status_label)
        
        main_layout.addLayout(top_bar)

        # --- Workspace: Tools (left) + Main Surface (center/right) ---
        self.workspace_splitter = QSplitter(Qt.Horizontal)
        self.workspace_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.workspace_splitter, 1)

        tools_panel = QWidget()
        tools_layout = QVBoxLayout(tools_panel)
        tools_panel.setMaximumWidth(220)
        tools_panel.setMinimumWidth(170)

        tools_title = QLabel("Tools")
        tools_title.setAlignment(Qt.AlignCenter)
        tools_title.setFont(QFont("Arial", 12, QFont.Bold))
        tools_layout.addWidget(tools_title)

        self.tools_btn_refresh = QPushButton("Refresh")
        self.tools_btn_refresh.clicked.connect(self.refresh_all)
        tools_layout.addWidget(self.tools_btn_refresh)

        self.tools_btn_multi_edit = QPushButton("Save Selected Rows")
        self.tools_btn_multi_edit.clicked.connect(self.save_unified_selected)
        tools_layout.addWidget(self.tools_btn_multi_edit)

        self.tools_btn_focus_search = QPushButton("Focus Search")
        self.tools_btn_focus_search.clicked.connect(lambda: self.unified_search_input.setFocus())
        tools_layout.addWidget(self.tools_btn_focus_search)

        self.tools_btn_verify_sel = QPushButton("Verify Selected")
        self.tools_btn_verify_sel.clicked.connect(
            lambda: self.bulk_set_verified(selected_only=True, verified=True)
        )
        tools_layout.addWidget(self.tools_btn_verify_sel)

        self.tools_btn_unverify_sel = QPushButton("Unverify Selected")
        self.tools_btn_unverify_sel.clicked.connect(
            lambda: self.bulk_set_verified(selected_only=True, verified=False)
        )
        tools_layout.addWidget(self.tools_btn_unverify_sel)

        self.tools_btn_save_all = QPushButton("Save All Rows")
        self.tools_btn_save_all.clicked.connect(self.save_unified_all)
        tools_layout.addWidget(self.tools_btn_save_all)

        self.tools_btn_show_pending = QPushButton("Open Pending Table")
        self.tools_btn_show_pending.clicked.connect(self.show_pending_table)
        tools_layout.addWidget(self.tools_btn_show_pending)

        self.tools_btn_show_curated = QPushButton("Open Curated Table")
        self.tools_btn_show_curated.clicked.connect(self.show_curated_table)
        tools_layout.addWidget(self.tools_btn_show_curated)

        self.tools_btn_clear_search = QPushButton("Clear Search")
        self.tools_btn_clear_search.clicked.connect(lambda: self.unified_search_input.setText(""))
        tools_layout.addWidget(self.tools_btn_clear_search)

        tools_layout.addStretch()
        self.workspace_splitter.addWidget(tools_panel)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.addWidget(self.main_splitter)

        # 0. UNIFIED MEMORY WORKSPACE
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(6)

        unified_group = QGroupBox("Unified Memory Ontology Workspace")
        unified_layout = QVBoxLayout(unified_group)

        unified_hint = QLabel(
            "Single editing surface for AI Pending Proposals + Curated Knowledge Graph."
        )
        unified_hint.setStyleSheet("color: #666;")
        unified_layout.addWidget(unified_hint)

        unified_search_row = QHBoxLayout()
        self.unified_search_input = QLineEdit()
        self.unified_search_input.setPlaceholderText("Search term/category/source/ontology...")
        self.unified_search_input.textChanged.connect(self.apply_unified_search_filter)
        unified_search_row.addWidget(self.unified_search_input)
        self.unified_clear_search_btn = QPushButton("Clear")
        self.unified_clear_search_btn.clicked.connect(
            lambda: self.unified_search_input.setText("")
        )
        unified_search_row.addWidget(self.unified_clear_search_btn)
        unified_layout.addLayout(unified_search_row)

        unified_actions = QHBoxLayout()
        self.save_unified_selected_btn = QPushButton("💾 Save Unified Selected")
        self.save_unified_selected_btn.clicked.connect(self.save_unified_selected)
        self.save_unified_selected_btn.setStyleSheet(
            "background-color: #1565c0; color: white;"
        )
        self.save_unified_all_btn = QPushButton("💾 Save Unified All Rows")
        self.save_unified_all_btn.clicked.connect(self.save_unified_all)
        self.save_unified_all_btn.setStyleSheet(
            "background-color: #0277bd; color: white; font-weight: bold;"
        )
        self.refresh_unified_btn = QPushButton("🔄 Refresh Unified View")
        self.refresh_unified_btn.clicked.connect(self.refresh_all)
        unified_actions.addWidget(self.save_unified_selected_btn)
        unified_actions.addWidget(self.save_unified_all_btn)
        unified_actions.addWidget(self.refresh_unified_btn)
        unified_actions.addStretch()
        unified_layout.addLayout(unified_actions)

        self.unified_table = QTableWidget(0, 13)
        self.unified_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.unified_table.verticalHeader().setDefaultSectionSize(22)
        self.unified_table.verticalHeader().setMinimumSectionSize(18)
        self.unified_table.verticalHeader().setVisible(False)
        self.unified_table.setHorizontalHeaderLabels(
            [
                "Source",
                "ID",
                "Status",
                "Category",
                "Ontology ID",
                "Label/Term",
                "Canonical/Key",
                "Namespace",
                "Confidence",
                "Jurisdiction",
                "Verified",
                "Flags",
                "Dirty",
            ]
        )
        self.unified_table.setSortingEnabled(True)
        self.unified_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.unified_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.unified_table.horizontalHeader().setSectionsClickable(True)
        self.unified_table.horizontalHeader().setStretchLastSection(True)
        self.unified_table.horizontalHeader().sectionClicked.connect(
            self.on_unified_header_clicked
        )
        self.unified_table.horizontalHeader().setStretchLastSection(True)
        self.unified_table.itemChanged.connect(self.on_unified_item_changed)
        self.unified_table.itemSelectionChanged.connect(self.on_unified_selected)
        unified_layout.addWidget(self.unified_table)

        center_layout.addWidget(unified_group)

        # 1. PROPOSALS SECTION
        proposal_group = QGroupBox("1. AI Pending Proposals (Batch Editable)")
        proposal_layout = QVBoxLayout(proposal_group)

        prop_actions = QHBoxLayout()
        self.save_prop_batch_btn = QPushButton("💾 Save Batch Status")
        self.save_prop_batch_btn.clicked.connect(self.save_proposal_batch)
        self.save_prop_batch_btn.setStyleSheet("background-color: #0277bd; color: white;")
        self.save_prop_selected_btn = QPushButton("💾 Save Selected")
        self.save_prop_selected_btn.clicked.connect(self.save_proposal_selected)
        self.save_prop_selected_btn.setStyleSheet("background-color: #1565c0; color: white;")
        self.approve_btn = QPushButton("✅ Approve Selected")
        self.approve_btn.clicked.connect(self.approve_selected)
        self.approve_btn.setStyleSheet("background-color: #2e7d32; color: white;")
        self.reject_btn = QPushButton("❌ Reject Selected")
        self.reject_btn.clicked.connect(self.reject_selected)
        self.reject_btn.setStyleSheet("background-color: #c62828; color: white;")
        self.delete_prop_selected_btn = QPushButton("🗑️ Delete Selected")
        self.delete_prop_selected_btn.clicked.connect(self.delete_proposal_selected)
        self.delete_prop_selected_btn.setStyleSheet("background-color: #b71c1c; color: white;")
        prop_actions.addWidget(self.save_prop_batch_btn)
        prop_actions.addWidget(self.save_prop_selected_btn)
        prop_actions.addWidget(self.approve_btn)
        prop_actions.addWidget(self.reject_btn)
        prop_actions.addWidget(self.delete_prop_selected_btn)
        prop_actions.addStretch()
        proposal_layout.addLayout(prop_actions)
        
        self.proposal_table = QTableWidget(0, 9)
        self.proposal_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.proposal_table.verticalHeader().setDefaultSectionSize(22)
        self.proposal_table.verticalHeader().setMinimumSectionSize(18)
        self.proposal_table.verticalHeader().setVisible(False)
        self.proposal_table.setHorizontalHeaderLabels(
            ["ID", "Preview", "Namespace", "Key", "Status", "Category", "Flags", "Confidence", "Importance"]
        )
        self.proposal_table.setSortingEnabled(True)
        self.proposal_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.proposal_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.proposal_table.horizontalHeader().setSectionsClickable(True)
        self.proposal_table.horizontalHeader().sectionClicked.connect(self.on_proposal_header_clicked)
        self.proposal_table.itemSelectionChanged.connect(self.on_proposal_selected)
        proposal_layout.addWidget(self.proposal_table)
        
        # 2. CURATED KNOWLEDGE SECTION
        curated_group = QGroupBox("2. Curated Knowledge Graph (Batch Editable)")
        curated_layout = QVBoxLayout(curated_group)
        
        filter_row = QHBoxLayout()
        self.kg_search_input = QLineEdit()
        self.kg_search_input.setPlaceholderText("Search Knowledge Graph...")
        self.kg_search_input.returnPressed.connect(self.refresh_curated)
        filter_row.addWidget(self.kg_search_input)

        self.kg_status_filter = QComboBox()
        self.kg_status_filter.addItems(["All Statuses", "proposed", "verified", "flagged", "rejected"])
        self.kg_status_filter.currentTextChanged.connect(lambda _v: self.refresh_curated())
        filter_row.addWidget(self.kg_status_filter)

        self.kg_verified_filter = QComboBox()
        self.kg_verified_filter.addItems(["All Verified", "Verified Only", "Unverified Only"])
        self.kg_verified_filter.currentTextChanged.connect(lambda _v: self.refresh_curated())
        filter_row.addWidget(self.kg_verified_filter)
        
        self.kg_load_btn = QPushButton("Search KG")
        self.kg_load_btn.clicked.connect(self.refresh_curated)
        filter_row.addWidget(self.kg_load_btn)
        curated_layout.addLayout(filter_row)

        kg_batch_actions = QHBoxLayout()
        self.save_kg_batch_btn = QPushButton("💾 Save Batch Edits (Category/Status/Verified)")
        self.save_kg_batch_btn.clicked.connect(self.save_curated_batch)
        self.save_kg_batch_btn.setStyleSheet("background-color: #0277bd; color: white; font-weight: bold;")
        kg_batch_actions.addWidget(self.save_kg_batch_btn)
        self.save_kg_selected_btn = QPushButton("💾 Save Selected")
        self.save_kg_selected_btn.clicked.connect(self.save_curated_selected)
        self.save_kg_selected_btn.setStyleSheet("background-color: #1565c0; color: white;")
        kg_batch_actions.addWidget(self.save_kg_selected_btn)
        self.delete_kg_selected_btn = QPushButton("🗑️ Delete Selected KG")
        self.delete_kg_selected_btn.clicked.connect(self.delete_curated_selected)
        self.delete_kg_selected_btn.setStyleSheet("background-color: #b71c1c; color: white;")
        kg_batch_actions.addWidget(self.delete_kg_selected_btn)
        self.bulk_verify_selected_btn = QPushButton("✅ Verify Selected")
        self.bulk_verify_selected_btn.clicked.connect(
            lambda: self.bulk_set_verified(selected_only=True, verified=True)
        )
        kg_batch_actions.addWidget(self.bulk_verify_selected_btn)
        self.bulk_unverify_selected_btn = QPushButton("↩ Unverify Selected")
        self.bulk_unverify_selected_btn.clicked.connect(
            lambda: self.bulk_set_verified(selected_only=True, verified=False)
        )
        kg_batch_actions.addWidget(self.bulk_unverify_selected_btn)
        self.bulk_verify_all_btn = QPushButton("✅ Verify All Rows")
        self.bulk_verify_all_btn.clicked.connect(
            lambda: self.bulk_set_verified(selected_only=False, verified=True)
        )
        kg_batch_actions.addWidget(self.bulk_verify_all_btn)
        self.undo_bulk_btn = QPushButton("↶ Undo Last Bulk")
        self.undo_bulk_btn.clicked.connect(self.undo_last_bulk_update)
        self.undo_bulk_btn.setEnabled(False)
        kg_batch_actions.addWidget(self.undo_bulk_btn)
        kg_batch_actions.addStretch()
        curated_layout.addLayout(kg_batch_actions)

        self.kg_table = QTableWidget(0, 8)
        self.kg_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.kg_table.verticalHeader().setDefaultSectionSize(22)
        self.kg_table.verticalHeader().setMinimumSectionSize(18)
        self.kg_table.verticalHeader().setVisible(False)
        self.kg_table.setHorizontalHeaderLabels(
            ["ID", "Term", "Category", "Canonical", "Ontology ID", "Conf", "Status", "Verified"]
        )
        self.kg_table.setSortingEnabled(True)
        self.kg_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.kg_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.kg_table.horizontalHeader().setSectionsClickable(True)
        self.kg_table.horizontalHeader().sectionClicked.connect(self.on_kg_header_clicked)
        self.kg_table.itemSelectionChanged.connect(self.on_curated_selected)
        self.kg_table.itemChanged.connect(self.on_curated_item_changed)
        curated_layout.addWidget(self.kg_table)
        
        bulk_row = QHBoxLayout()
        bulk_row.addWidget(QLabel("Bulk Field:"))
        self.bulk_field_combo = QComboBox()
        self.bulk_field_combo.addItems(
            [
                "term",
                "category",
                "canonical_value",
                "ontology_entity_id",
                "framework_type",
                "jurisdiction",
                "preferred_perspective",
                "is_canonical",
                "issue_category",
                "severity",
                "impact_description",
                "fix_status",
                "resolution_evidence",
                "resolution_date",
                "next_review_date",
                "source",
                "description",
                "confidence",
                "status",
                "verified",
                "verified_by",
                "user_notes",
                "notes",
                "components",
                "legal_use_cases",
                "root_cause",
                "related_frameworks",
                "aliases",
                "attributes",
                "relations",
                "sources",
            ]
        )
        bulk_row.addWidget(self.bulk_field_combo)
        bulk_row.addWidget(QLabel("Value:"))
        self.bulk_value_input = QLineEdit()
        self.bulk_value_input.setPlaceholderText(
            "Type value (JSON for list/object fields)"
        )
        bulk_row.addWidget(self.bulk_value_input)
        self.bulk_apply_selected_btn = QPushButton("Apply to Selected")
        self.bulk_apply_selected_btn.clicked.connect(
            lambda: self.bulk_update_field(selected_only=True)
        )
        bulk_row.addWidget(self.bulk_apply_selected_btn)
        self.bulk_apply_all_btn = QPushButton("Apply to All Rows")
        self.bulk_apply_all_btn.clicked.connect(
            lambda: self.bulk_update_field(selected_only=False)
        )
        bulk_row.addWidget(self.bulk_apply_all_btn)
        curated_layout.addLayout(bulk_row)
        
        self.secondary_tabs = QTabWidget()
        self.secondary_tabs.addTab(proposal_group, "Pending Proposals")
        self.secondary_tabs.addTab(curated_group, "Curated Knowledge")
        self.secondary_dialog = QDialog(self)
        self.secondary_dialog.setWindowTitle("Agent Memory - Secondary Tables")
        self.secondary_dialog.resize(1200, 700)
        secondary_layout = QVBoxLayout(self.secondary_dialog)
        secondary_layout.setContentsMargins(8, 8, 8, 8)
        secondary_layout.addWidget(self.secondary_tabs)

        self.main_splitter.addWidget(center_panel)

        # 3. EXPERT EDITOR SECTION
        editor_container = QWidget()
        editor_v_layout = QVBoxLayout(editor_container)
        self.editor_group = QGroupBox("3. High-Fidelity Expert Editor")
        editor_layout = QVBoxLayout(self.editor_group)

        editor_actions = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save Expert Edits")
        self.save_btn.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold; padding: 10px;")
        self.save_btn.clicked.connect(self.save_edits)
        self.delete_btn = QPushButton("🗑️ Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected)
        editor_actions.addWidget(self.save_btn)
        editor_actions.addWidget(self.delete_btn)
        editor_actions.addStretch()
        editor_layout.addLayout(editor_actions)
        
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Taxonomic Category Override:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("(Unchanged)")
        self.refresh_ontology()
        cat_row.addWidget(self.category_combo)
        
        self.reload_ont_btn = QPushButton("🔄 Reload Ontology")
        self.reload_ont_btn.clicked.connect(self.refresh_ontology)
        cat_row.addWidget(self.reload_ont_btn)
        cat_row.addStretch()
        editor_layout.addLayout(cat_row)

        self.detail_view = QTextEdit()
        self.detail_view.setPlaceholderText("Select any item above to edit its content...")
        editor_layout.addWidget(self.detail_view)
        
        editor_v_layout.addWidget(self.editor_group)
        self.main_splitter.addWidget(editor_container)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([1250, 700])
        self.workspace_splitter.setSizes([190, 1700])

    def toggle_secondary_tables(self) -> None:
        if self.secondary_dialog.isVisible():
            self.secondary_dialog.hide()
        else:
            self.secondary_dialog.show()
            self.secondary_dialog.raise_()
            self.secondary_dialog.activateWindow()

    def show_pending_table(self) -> None:
        self.secondary_tabs.setCurrentIndex(0)
        self.secondary_dialog.show()
        self.secondary_dialog.raise_()
        self.secondary_dialog.activateWindow()

    def show_curated_table(self) -> None:
        self.secondary_tabs.setCurrentIndex(1)
        self.secondary_dialog.show()
        self.secondary_dialog.raise_()
        self.secondary_dialog.activateWindow()

    def refresh_ontology(self):
        """Fetch types from the central ontology registry."""
        current_val = self.category_combo.currentText()
        self.category_combo.clear()
        self.category_combo.addItem("(Unchanged)")
        try:
            from agents.extractors.ontology import LegalEntityType
            types = sorted([et.value.label for et in LegalEntityType])
            if types:
                self.category_combo.addItems(types)
                self.ont_status_label.setText(f"Ontology: {len(types)} Types Loaded")
                self.ont_status_label.setStyleSheet("color: #4caf50;")
        except Exception:
            self.ont_status_label.setText("Ontology: Using Fallbacks")
            self.ont_status_label.setStyleSheet("color: orange;")
            self.category_combo.addItems(["Person", "Organization", "Case", "Statute", "Violation", "ExpertWitness"])
        idx = self.category_combo.findText(current_val)
        if idx >= 0: self.category_combo.setCurrentIndex(idx)

    def _ontology_category_labels(self) -> List[str]:
        try:
            from agents.extractors.ontology import LegalEntityType
            return sorted([et.value.label for et in LegalEntityType])
        except Exception:
            return ["Person", "Organization", "Case", "Statute", "Violation", "ExpertWitness", "Defendant"]

    def refresh_all(self):
        self.refresh_proposals()
        self.refresh_curated()
        self.refresh_unified()
        self.refresh_ontology()

    def apply_predefined_filter_verified(self) -> None:
        """Quick filter matching the most common curation task."""
        self.unified_search_input.setText("curated verified")

    def apply_unified_search_filter(self) -> None:
        """Filter unified table rows by visible text tokens."""
        query = self.unified_search_input.text().strip().lower()
        if not query:
            for row in range(self.unified_table.rowCount()):
                self.unified_table.setRowHidden(row, False)
            return

        tokens = [t for t in query.split() if t]
        for row in range(self.unified_table.rowCount()):
            row_text_parts: List[str] = []
            for col in [0, 1, 5, 6, 9, 11]:
                item = self.unified_table.item(row, col)
                if item is not None:
                    row_text_parts.append(item.text().lower())
            for col in [2, 3, 4, 10]:
                widget = self.unified_table.cellWidget(row, col)
                if isinstance(widget, QComboBox):
                    row_text_parts.append(widget.currentText().lower())
            row_text = " ".join(row_text_parts)
            hide = any(tok not in row_text for tok in tokens)
            self.unified_table.setRowHidden(row, hide)

    def _proposal_preview_text(self, proposal: Dict[str, Any]) -> str:
        content_raw = proposal.get("content", "")
        preview_text = str(content_raw or "")
        try:
            c_obj = json.loads(preview_text)
            preview_text = c_obj.get("text") or c_obj.get("label") or str(c_obj)[:120]
        except Exception:
            pass
        return str(preview_text)

    def _compose_unified_items(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for proposal in self.items:
            metadata = proposal.get("metadata") if isinstance(proposal.get("metadata"), dict) else {}
            rows.append(
                {
                    "source": "proposal",
                    "id": int(proposal.get("id", 0) or 0),
                    "status": str(proposal.get("status", "pending") or "pending"),
                    "category": str(metadata.get("entity_type", "") or ""),
                    "ontology_entity_id": str(metadata.get("ontology_entity_id", "") or ""),
                    "jurisdiction": str(metadata.get("jurisdiction", "") or ""),
                    "label_term": self._proposal_preview_text(proposal),
                    "canonical_key": str(proposal.get("key", "") or ""),
                    "namespace": str(proposal.get("namespace", "") or ""),
                    "confidence": float(proposal.get("confidence_score", 0.0) or 0.0),
                    "verified": None,
                    "flags": ", ".join(proposal.get("flags", []) or []),
                }
            )

        for curated in self.curated_items:
            rows.append(
                {
                    "source": "curated",
                    "id": int(curated.get("id", 0) or 0),
                    "status": str(curated.get("status", "proposed") or "proposed"),
                    "category": str(curated.get("category", "") or ""),
                    "ontology_entity_id": str(curated.get("ontology_entity_id", "") or ""),
                    "jurisdiction": str(curated.get("jurisdiction", "") or ""),
                    "label_term": str(curated.get("term", "") or ""),
                    "canonical_key": str(curated.get("canonical_value", "") or ""),
                    "namespace": "knowledge_manager",
                    "confidence": float(curated.get("confidence", 0.0) or 0.0),
                    "verified": bool(curated.get("verified")),
                    "flags": "",
                }
            )

        return sorted(rows, key=lambda x: (str(x.get("source")), int(x.get("id", 0))))

    def refresh_unified(self) -> None:
        try:
            self._loading_unified = True
            category_labels = self._ontology_category_labels()
            ontology_ids = []
            try:
                from agents.extractors.ontology import LegalEntityType

                for et in LegalEntityType:
                    ontology_ids.append(str(et.name))
                    ontology_ids.append(str(et.value.label).replace(" ", ""))
            except Exception:
                ontology_ids = ["PERSON", "ORGANIZATION", "CASE", "STATUTE", "VIOLATION"]
            ontology_ids = sorted({x for x in ontology_ids if x})

            self.unified_items = self._compose_unified_items()
            self.unified_table.setSortingEnabled(False)
            self.unified_table.setRowCount(len(self.unified_items))
            for i, row in enumerate(self.unified_items):
                source_item = QTableWidgetItem(str(row.get("source", "")))
                source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
                self.unified_table.setItem(i, 0, source_item)

                id_item = QTableWidgetItem()
                id_item.setData(Qt.EditRole, int(row.get("id", 0)))
                id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
                self.unified_table.setItem(i, 1, id_item)

                status_combo = QComboBox()
                if row.get("source") == "proposal":
                    status_combo.addItems(["pending", "approved", "rejected"])
                else:
                    status_combo.addItems(["proposed", "verified", "flagged", "rejected"])
                status_combo.setCurrentText(str(row.get("status", "")))
                status_combo.currentTextChanged.connect(
                    lambda _v, r=i: self._mark_unified_row_dirty(r)
                )
                self.unified_table.setCellWidget(i, 2, status_combo)

                category_combo = QComboBox()
                category_combo.addItem("")
                category_combo.addItems(category_labels)
                current_category = str(row.get("category", "")).strip()
                if current_category and category_combo.findText(current_category) < 0:
                    category_combo.addItem(current_category)
                category_combo.setCurrentText(current_category)
                category_combo.currentTextChanged.connect(
                    lambda _v, r=i: self._mark_unified_row_dirty(r)
                )
                self.unified_table.setCellWidget(i, 3, category_combo)

                ont_combo = QComboBox()
                ont_combo.addItem("")
                ont_combo.addItems(ontology_ids)
                current_ontology = str(row.get("ontology_entity_id", "")).strip()
                if current_ontology and ont_combo.findText(current_ontology) < 0:
                    ont_combo.addItem(current_ontology)
                ont_combo.setCurrentText(current_ontology)
                ont_combo.currentTextChanged.connect(
                    lambda _v, r=i: self._mark_unified_row_dirty(r)
                )
                self.unified_table.setCellWidget(i, 4, ont_combo)

                self.unified_table.setItem(i, 5, QTableWidgetItem(str(row.get("label_term", ""))))
                self.unified_table.setItem(i, 6, QTableWidgetItem(str(row.get("canonical_key", ""))))
                self.unified_table.setItem(i, 7, QTableWidgetItem(str(row.get("namespace", ""))))

                conf_item = QTableWidgetItem()
                conf_item.setData(Qt.EditRole, float(row.get("confidence", 0.0) or 0.0))
                self.unified_table.setItem(i, 8, conf_item)

                self.unified_table.setItem(
                    i,
                    9,
                    QTableWidgetItem(str(row.get("jurisdiction", ""))),
                )

                ver_combo = QComboBox()
                if row.get("source") == "proposal":
                    ver_combo.addItems(["N/A"])
                else:
                    ver_combo.addItems(["True", "False"])
                    ver_combo.setCurrentText("True" if bool(row.get("verified")) else "False")
                    ver_combo.currentTextChanged.connect(
                        lambda _v, r=i: self._mark_unified_row_dirty(r)
                    )
                self.unified_table.setCellWidget(i, 10, ver_combo)

                self.unified_table.setItem(i, 11, QTableWidgetItem(str(row.get("flags", ""))))

                dirty_item = QTableWidgetItem("")
                dirty_item.setFlags(dirty_item.flags() & ~Qt.ItemIsEditable)
                self.unified_table.setItem(i, 12, dirty_item)
                self._apply_unified_dirty_style(i)

            self.unified_table.setSortingEnabled(True)
        finally:
            self._loading_unified = False

    def refresh_proposals(self):
        try:
            self.proposal_table.setSortingEnabled(False)
            data = api_client.list_memory_proposals(limit=100)
            self.items = data.get("proposals", [])
            category_labels = self._ontology_category_labels()
            self.proposal_table.setRowCount(len(self.items))
            for i, p in enumerate(self.items):
                id_item = QTableWidgetItem()
                id_item.setData(Qt.EditRole, int(p.get("id", 0)))
                self.proposal_table.setItem(i, 0, id_item)
                
                # PREVIEW COLUMN: Extract text from JSON content if possible
                content_raw = p.get("content", "")
                preview_text = content_raw
                try:
                    c_obj = json.loads(content_raw)
                    preview_text = c_obj.get("text") or c_obj.get("label") or str(c_obj)[:50]
                except Exception:
                    # Keep raw preview_text when content is not JSON.
                    pass
                self.proposal_table.setItem(i, 1, QTableWidgetItem(str(preview_text)))

                self.proposal_table.setItem(i, 2, QTableWidgetItem(p.get("namespace", "")))
                self.proposal_table.setItem(i, 3, QTableWidgetItem(p.get("key", "")))
                
                # Editable Status Combo
                status_combo = QComboBox()
                status_combo.addItems(["pending", "approved", "rejected"])
                status_combo.setCurrentText(p.get("status", "pending"))
                self.proposal_table.setCellWidget(i, 4, status_combo)

                category_combo = QComboBox()
                category_combo.addItem("(Unchanged)")
                category_combo.addItems(category_labels)
                current_category = str((p.get("metadata") or {}).get("entity_type", "")).strip()
                if current_category and category_combo.findText(current_category) < 0:
                    category_combo.addItem(current_category)
                if current_category:
                    category_combo.setCurrentText(current_category)
                self.proposal_table.setCellWidget(i, 5, category_combo)

                self.proposal_table.setItem(i, 6, QTableWidgetItem(", ".join(p.get("flags", []))))
                
                conf_item = QTableWidgetItem()
                conf_item.setData(Qt.EditRole, float(p.get("confidence_score", 0.0)))
                self.proposal_table.setItem(i, 7, conf_item)
                
                imp_item = QTableWidgetItem()
                imp_item.setData(Qt.EditRole, float(p.get("importance_score", 0.0)))
                self.proposal_table.setItem(i, 8, imp_item)
            self.proposal_table.setSortingEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Refresh Error", f"Failed to refresh proposals:\n{e}")

    def refresh_curated(self, *, focus_ids: Optional[List[int]] = None):
        try:
            self._loading_curated = True
            self.kg_table.setSortingEnabled(False)
            query = self.kg_search_input.text().strip()
            status_filter = self.kg_status_filter.currentText()
            status = None if status_filter == "All Statuses" else status_filter
            result = api_client.list_manager_knowledge(query=query or None, status=status, limit=500)
            self.curated_items = result.get("items", [])
            verified_filter = self.kg_verified_filter.currentText()
            if verified_filter == "Verified Only":
                self.curated_items = [x for x in self.curated_items if bool(x.get("verified"))]
            elif verified_filter == "Unverified Only":
                self.curated_items = [x for x in self.curated_items if not bool(x.get("verified"))]
            self.kg_table.setRowCount(len(self.curated_items))
            
            # Fetch ontology types for the category dropdowns
            try:
                from agents.extractors.ontology import LegalEntityType
                ont_types = sorted([et.value.label for et in LegalEntityType])
                ontology_id_set = set()
                for et in LegalEntityType:
                    ontology_id_set.add(str(et.name))
                    ontology_id_set.add(str(et.value.label).replace(" ", ""))
                ontology_ids_raw = sorted([x for x in ontology_id_set if x])
                seen_lower = set()
                ontology_ids = []
                for val in ontology_ids_raw:
                    key = val.lower()
                    if key in seen_lower:
                        continue
                    seen_lower.add(key)
                    ontology_ids.append(val)
            except:
                ont_types = ["Person", "Organization", "Case", "Statute", "Violation"]
                ontology_ids = ["PERSON", "ORGANIZATION", "CASE", "STATUTE", "VIOLATION"]

            for i, item in enumerate(self.curated_items):
                id_item = QTableWidgetItem()
                id_item.setData(Qt.EditRole, int(item.get("id", 0)))
                self.kg_table.setItem(i, 0, id_item)
                
                self.kg_table.setItem(i, 1, QTableWidgetItem(str(item.get("term", ""))))
                
                # 1. Editable Category Combo
                cat_combo = QComboBox()
                cat_combo.addItems(ont_types)
                current_category = str(item.get("category", "")).strip()
                if current_category and cat_combo.findText(current_category) < 0:
                    # Preserve existing data values even when not in current ontology list.
                    cat_combo.addItem(current_category)
                if current_category:
                    cat_combo.setCurrentText(current_category)
                self.kg_table.setCellWidget(i, 2, cat_combo)
                cat_combo.currentTextChanged.connect(lambda _v, rid=int(item.get("id", 0)): self._mark_curated_dirty(rid))
                
                self.kg_table.setItem(i, 3, QTableWidgetItem(str(item.get("canonical_value", ""))))
                ont_combo = QComboBox()
                ont_combo.addItems(ontology_ids)
                current_ontology_id = str(item.get("ontology_entity_id", "")).strip()
                if current_ontology_id and ont_combo.findText(current_ontology_id) < 0:
                    ont_combo.addItem(current_ontology_id)
                if current_ontology_id:
                    ont_combo.setCurrentText(current_ontology_id)
                self.kg_table.setCellWidget(i, 4, ont_combo)
                ont_combo.currentTextChanged.connect(lambda _v, rid=int(item.get("id", 0)): self._mark_curated_dirty(rid))
                
                conf_item = QTableWidgetItem()
                conf_item.setData(Qt.EditRole, float(item.get("confidence", 0.5)))
                self.kg_table.setItem(i, 5, conf_item)
                
                # 2. Editable Status Combo
                stat_combo = QComboBox()
                stat_combo.addItems(["proposed", "verified", "flagged"])
                stat_combo.setCurrentText(str(item.get("status", "proposed")))
                self.kg_table.setCellWidget(i, 6, stat_combo)
                stat_combo.currentTextChanged.connect(lambda _v, rid=int(item.get("id", 0)): self._mark_curated_dirty(rid))
                
                # 3. Editable Verified Combo
                ver_combo = QComboBox()
                ver_combo.addItems(["True", "False"])
                ver_combo.setCurrentText("True" if item.get("verified") else "False")
                self.kg_table.setCellWidget(i, 7, ver_combo)
                ver_combo.currentTextChanged.connect(lambda _v, rid=int(item.get("id", 0)): self._mark_curated_dirty(rid))
                self._apply_dirty_row_style(i, int(item.get("id", 0)))
                
            self.kg_table.setSortingEnabled(True)
            self._focus_curated_rows(focus_ids or [])
        except Exception as e:
            QMessageBox.critical(self, "Refresh Error", f"Failed to refresh curated knowledge:\n{e}")
        finally:
            self._loading_curated = False

    def _focus_curated_rows(self, focus_ids: List[int]) -> None:
        if not focus_ids:
            return
        wanted = {int(x) for x in focus_ids if int(x) > 0}
        if not wanted:
            return

        first_row: Optional[int] = None
        found: set[int] = set()
        for row in range(self.kg_table.rowCount()):
            id_item = self.kg_table.item(row, 0)
            if id_item is None:
                continue
            try:
                rid = int(id_item.text())
            except Exception:
                continue
            if rid in wanted:
                found.add(rid)
                if first_row is None:
                    first_row = row

        if first_row is not None:
            self.kg_table.setCurrentCell(first_row, 0)
            self.kg_table.selectRow(first_row)
            self.kg_table.scrollToItem(
                self.kg_table.item(first_row, 0),
                QAbstractItemView.PositionAtCenter,
            )

        missing = wanted - found
        if missing:
            query = self.kg_search_input.text().strip() or "(none)"
            status = self.kg_status_filter.currentText()
            verified = self.kg_verified_filter.currentText()
            QMessageBox.information(
                self,
                "Rows Hidden By Filters",
                (
                    f"Saved rows are not visible in the current curated view.\n"
                    f"Hidden IDs: {', '.join(str(x) for x in sorted(missing)[:20])}\n\n"
                    f"Current filters:\n"
                    f"- Search: {query}\n"
                    f"- Status: {status}\n"
                    f"- Verified: {verified}"
                ),
            )

    def _selected_proposal_ids(self) -> List[int]:
        ids: List[int] = []
        for idx in self.proposal_table.selectionModel().selectedRows():
            item = self.proposal_table.item(idx.row(), 0)
            if item is None:
                continue
            try:
                ids.append(int(item.text()))
            except Exception:
                continue
        return ids

    def _apply_proposal_transition(
        self,
        proposal_id: int,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        p = next((x for x in self.items if int(x.get("id", 0)) == int(proposal_id)), {})
        api_client.update_memory_proposal(
            int(proposal_id),
            str(p.get("content", "")),
            metadata if metadata else None,
        )
        normalized = str(status or "pending").strip().lower()
        if normalized == "approved":
            api_client.approve_memory_proposal(int(proposal_id))
        elif normalized == "rejected":
            api_client.reject_memory_proposal(int(proposal_id))

    def on_proposal_selected(self):
        pid = self._selected_id(self.proposal_table)
        if pid == 0: return
        self.kg_table.clearSelection()
        self.unified_table.clearSelection()
        
        # FIND ITEM BY ID (Fixes sorting mismatch)
        item = next((x for x in self.items if x.get("id") == pid), None)
        if not item: return
        
        self.editor_group.setTitle(f"Expert Proposal Editor (ID: {pid})")
        self._load_into_editor(item)

    def on_curated_selected(self):
        kid = self._selected_id(self.kg_table)
        if kid == 0: return
        self.proposal_table.clearSelection()
        self.unified_table.clearSelection()
        
        # FIND ITEM BY ID (Fixes sorting mismatch)
        item = next((x for x in self.curated_items if x.get("id") == kid), None)
        if not item: return
        
        self.editor_group.setTitle(f"Expert Curated Editor (ID: {kid})")
        # Normalize key for curated items
        item_copy = dict(item)
        item_copy["content"] = item.get("term") or item.get("canonical_value", "")
        self._load_into_editor(item_copy)

    def _load_into_editor(self, item):
        editor_item = dict(item or {})
        # Expose API-write keys (no *_json suffix) so edited JSON persists.
        for json_key, api_key in EDITOR_JSON_TO_API_KEY.items():
            if api_key not in editor_item and json_key in editor_item:
                editor_item[api_key] = editor_item.get(json_key)
            editor_item.pop(json_key, None)
        self.detail_view.setPlainText(json.dumps(editor_item, indent=2, default=str))
        cat = item.get("category") or item.get("metadata", {}).get("entity_type")
        idx = self.category_combo.findText(str(cat))
        self.category_combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _normalize_curated_editor_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(payload or {})
        for json_key, api_key in EDITOR_JSON_TO_API_KEY.items():
            if api_key not in out and json_key in out:
                out[api_key] = out.get(json_key)
            out.pop(json_key, None)
        return out

    def save_proposal_batch(self):
        """Save all status changes in the proposal table."""
        updated = 0
        failed = 0
        errors: List[str] = []
        for i in range(self.proposal_table.rowCount()):
            pid = int(self.proposal_table.item(i, 0).text())
            status_combo = self.proposal_table.cellWidget(i, 4)
            category_combo = self.proposal_table.cellWidget(i, 5)
            if status_combo:
                new_status = status_combo.currentText()
                try:
                    p = next((x for x in self.items if int(x.get("id", 0)) == pid), {})
                    metadata = dict((p.get("metadata") or {}))
                    selected_category = category_combo.currentText() if category_combo else "(Unchanged)"
                    if selected_category and selected_category != "(Unchanged)":
                        metadata["entity_type"] = selected_category
                    self._apply_proposal_transition(pid, new_status, metadata if metadata else None)
                    updated += 1
                except Exception as e:
                    failed += 1
                    if len(errors) < 10:
                        errors.append(f"#{pid}: {e}")
        msg = f"Updated {updated}/{self.proposal_table.rowCount()} proposals."
        if failed:
            msg += f"\nFailed: {failed}"
            if errors:
                msg += "\n\n" + "\n".join(errors)
        QMessageBox.information(self, "Batch Saved", msg)
        self.refresh_all()

    def save_proposal_selected(self) -> None:
        """Save status for selected proposal rows only."""
        selected_ids = self._selected_proposal_ids()
        if not selected_ids:
            QMessageBox.information(self, "Save Selected", "No proposal rows selected.")
            return

        updated = 0
        failed = 0
        errors: List[str] = []
        for row in range(self.proposal_table.rowCount()):
            id_item = self.proposal_table.item(row, 0)
            if id_item is None:
                continue
            try:
                proposal_id = int(id_item.text())
            except Exception:
                continue
            if proposal_id not in set(selected_ids):
                continue
            status_combo = self.proposal_table.cellWidget(row, 4)
            category_combo = self.proposal_table.cellWidget(row, 5)
            if status_combo is None:
                continue
            status = status_combo.currentText()
            try:
                p = next((x for x in self.items if int(x.get("id", 0)) == int(proposal_id)), {})
                metadata = dict((p.get("metadata") or {}))
                selected_category = category_combo.currentText() if category_combo else "(Unchanged)"
                if selected_category and selected_category != "(Unchanged)":
                    metadata["entity_type"] = selected_category
                self._apply_proposal_transition(proposal_id, status, metadata if metadata else None)
                updated += 1
            except Exception as e:
                failed += 1
                if len(errors) < 10:
                    errors.append(f"#{proposal_id}: {e}")
                continue

        msg = f"Updated {updated}/{len(selected_ids)} selected proposals."
        if failed:
            msg += f"\nFailed: {failed}"
            if errors:
                msg += "\n\n" + "\n".join(errors)
        QMessageBox.information(
            self,
            "Save Selected",
            msg,
        )
        self.refresh_all()

    def delete_proposal_selected(self) -> None:
        """Delete selected proposal rows only."""
        selected_rows = self.proposal_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Delete Selected", "No proposal rows selected.")
            return
        if (
            QMessageBox.question(
                self,
                "Delete Selected",
                f"Permanently delete {len(selected_rows)} selected proposal(s)?",
            )
            != QMessageBox.Yes
        ):
            return

        deleted = 0
        for idx in selected_rows:
            row = idx.row()
            id_item = self.proposal_table.item(row, 0)
            if id_item is None:
                continue
            try:
                proposal_id = int(id_item.text())
            except Exception:
                continue
            try:
                api_client.delete_memory_proposal(proposal_id)
                deleted += 1
            except Exception:
                continue

        QMessageBox.information(
            self,
            "Delete Selected",
            f"Deleted {deleted}/{len(selected_rows)} selected proposals.",
        )
        self.refresh_proposals()

    def save_curated_batch(self):
        """Save batch edits from the curated Knowledge Graph table."""
        updated = 0
        failed = 0
        errors: List[str] = []
        updated_ids: List[int] = []
        for i in range(self.kg_table.rowCount()):
            kid = int(self.kg_table.item(i, 0).text())
            cat_combo = self.kg_table.cellWidget(i, 2)
            ont_combo = self.kg_table.cellWidget(i, 4)
            stat_combo = self.kg_table.cellWidget(i, 6)
            ver_combo = self.kg_table.cellWidget(i, 7)
            
            payload = {
                "category": cat_combo.currentText(),
                "ontology_entity_id": ont_combo.currentText() if ont_combo else None,
                "status": stat_combo.currentText(),
                "verified": ver_combo.currentText() == "True"
            }
            try:
                api_client.update_manager_knowledge_item(kid, payload)
                updated += 1
                updated_ids.append(kid)
                if kid in self._dirty_curated_ids:
                    self._dirty_curated_ids.remove(kid)
            except Exception as exc:
                failed += 1
                if len(errors) < 10:
                    errors.append(f"#{kid}: {exc}")
        msg = f"Updated {updated}/{self.kg_table.rowCount()} Knowledge Graph rows."
        if failed:
            msg += f"\nFailed: {failed}"
            if errors:
                msg += "\n\n" + "\n".join(errors)
        QMessageBox.information(self, "Batch Saved", msg)
        self.refresh_curated(focus_ids=updated_ids)

    def save_curated_selected(self) -> None:
        """Save only selected curated rows."""
        selected_ids = self._selected_curated_ids()
        if not selected_ids:
            QMessageBox.information(self, "Save Selected", "No curated rows selected.")
            return

        selected_set = set(selected_ids)
        updated = 0
        failed = 0
        errors: List[str] = []
        updated_ids: List[int] = []
        for i in range(self.kg_table.rowCount()):
            id_item = self.kg_table.item(i, 0)
            if id_item is None:
                continue
            try:
                kid = int(id_item.text())
            except Exception:
                continue
            if kid not in selected_set:
                continue

            cat_combo = self.kg_table.cellWidget(i, 2)
            ont_combo = self.kg_table.cellWidget(i, 4)
            stat_combo = self.kg_table.cellWidget(i, 6)
            ver_combo = self.kg_table.cellWidget(i, 7)
            payload = {
                "category": cat_combo.currentText() if cat_combo else None,
                "ontology_entity_id": ont_combo.currentText() if ont_combo else None,
                "status": stat_combo.currentText() if stat_combo else None,
                "verified": (ver_combo.currentText() == "True") if ver_combo else None,
            }
            try:
                api_client.update_manager_knowledge_item(kid, payload)
                updated += 1
                updated_ids.append(kid)
                if kid in self._dirty_curated_ids:
                    self._dirty_curated_ids.remove(kid)
            except Exception as exc:
                failed += 1
                if len(errors) < 10:
                    errors.append(f"#{kid}: {exc}")
                continue
        msg = f"Updated {updated}/{len(selected_ids)} selected rows."
        if failed:
            msg += f"\nFailed: {failed}"
            if errors:
                msg += "\n\n" + "\n".join(errors)
        QMessageBox.information(self, "Save Selected", msg)
        self.refresh_curated(focus_ids=updated_ids or selected_ids)

    def delete_curated_selected(self) -> None:
        """Delete selected curated rows only."""
        selected_ids = self._selected_curated_ids()
        if not selected_ids:
            QMessageBox.information(self, "Delete Selected", "No curated rows selected.")
            return
        if (
            QMessageBox.question(
                self,
                "Delete Selected",
                f"Permanently delete {len(selected_ids)} selected curated item(s)?",
            )
            != QMessageBox.Yes
        ):
            return

        deleted = 0
        for knowledge_id in selected_ids:
            try:
                api_client.delete_manager_knowledge_item(int(knowledge_id))
                deleted += 1
                if knowledge_id in self._dirty_curated_ids:
                    self._dirty_curated_ids.remove(knowledge_id)
            except Exception:
                continue
        QMessageBox.information(
            self,
            "Delete Selected",
            f"Deleted {deleted}/{len(selected_ids)} selected rows.",
        )
        self.refresh_curated()

    def save_edits(self):
        unified_row = self.unified_table.currentRow()
        unified_source = ""
        target_id = 0
        if unified_row >= 0:
            source_item = self.unified_table.item(unified_row, 0)
            id_item = self.unified_table.item(unified_row, 1)
            if source_item and id_item:
                unified_source = source_item.text().strip().lower()
                try:
                    target_id = int(id_item.text())
                except Exception:
                    target_id = 0
        if not target_id:
            is_prop = self.proposal_table.currentRow() >= 0
            target_id = self._selected_id(self.proposal_table if is_prop else self.kg_table)
            unified_source = "proposal" if is_prop else "curated"
        if not target_id:
            return
        editor_text = self.detail_view.toPlainText().strip()
        selected_cat = self.category_combo.currentText()
        payload = {"content": editor_text}
        if selected_cat != "(Unchanged)":
            payload["metadata"] = {"entity_type": selected_cat, "expert_override": True}
        try:
            if unified_source == "proposal":
                parsed = None
                try:
                    parsed = json.loads(editor_text)
                except Exception:
                    parsed = None
                if isinstance(parsed, dict):
                    content_value = parsed.get("content", editor_text)
                    metadata_value = parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else payload.get("metadata")
                else:
                    content_value = editor_text
                    metadata_value = payload.get("metadata")
                api_client.update_memory_proposal(
                    target_id,
                    content_value,
                    metadata_value,
                )
            else:
                parsed_obj = json.loads(editor_text)
                if not isinstance(parsed_obj, dict):
                    raise ValueError("Editor content must be a JSON object for curated items.")
                update_payload = self._normalize_curated_editor_payload(parsed_obj)
                # Remove immutable/server-managed fields if present.
                update_payload.pop("id", None)
                update_payload.pop("created_at", None)
                update_payload.pop("updated_at", None)
                if selected_cat != "(Unchanged)":
                    update_payload["category"] = selected_cat
                api_client.update_manager_knowledge_item(target_id, update_payload)
            QMessageBox.information(self, "Success", "Edits saved.")
            self.refresh_all()
            self._focus_unified_rows([(unified_source or "curated", int(target_id))])
            if (unified_source or "curated") == "curated":
                self.refresh_curated(focus_ids=[int(target_id)])
        except Exception as e: QMessageBox.critical(self, "Save Failed", str(e))

    def _selected_curated_ids(self) -> List[int]:
        ids: List[int] = []
        for idx in self.kg_table.selectionModel().selectedRows():
            item = self.kg_table.item(idx.row(), 0)
            if item is None:
                continue
            try:
                ids.append(int(item.text()))
            except Exception:
                continue
        return ids

    def _selected_unified_rows(self) -> List[int]:
        rows: List[int] = []
        for idx in self.unified_table.selectionModel().selectedRows():
            rows.append(idx.row())
        return rows

    def _focus_unified_rows(self, entries: List[tuple[str, int]]) -> None:
        if not entries:
            return
        wanted = {
            (str(src).strip().lower(), int(sid))
            for src, sid in entries
            if int(sid) > 0
        }
        if not wanted:
            return

        first_row: Optional[int] = None
        found: set[tuple[str, int]] = set()
        for row in range(self.unified_table.rowCount()):
            source_item = self.unified_table.item(row, 0)
            id_item = self.unified_table.item(row, 1)
            if source_item is None or id_item is None:
                continue
            try:
                key = (source_item.text().strip().lower(), int(id_item.text()))
            except Exception:
                continue
            if key in wanted:
                found.add(key)
                if first_row is None:
                    first_row = row

        if first_row is not None:
            self.unified_table.setCurrentCell(first_row, 0)
            self.unified_table.selectRow(first_row)
            self.unified_table.scrollToItem(
                self.unified_table.item(first_row, 0),
                QAbstractItemView.PositionAtCenter,
            )

        missing = wanted - found
        if missing:
            query = self.unified_search_input.text().strip() or "(none)"
            ids = ", ".join(f"{src}#{sid}" for src, sid in sorted(missing)[:20])
            QMessageBox.information(
                self,
                "Rows Not In Current View",
                (
                    f"Some saved rows are not visible after refresh.\n"
                    f"Hidden rows: {ids}\n\n"
                    f"Active Unified Search: {query}"
                ),
            )

    def _mark_unified_row_dirty(self, row: int) -> None:
        if row < 0:
            return
        self._dirty_unified_rows.add(int(row))
        self._apply_unified_dirty_style(row)

    def _apply_unified_dirty_style(self, row: int) -> None:
        dirty_item = self.unified_table.item(row, 12)
        if dirty_item is None:
            return
        is_dirty = int(row) in self._dirty_unified_rows
        dirty_item.setText("Yes" if is_dirty else "")
        dirty_item.setForeground(QColor("#b71c1c" if is_dirty else "#666666"))

    def on_unified_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_unified:
            return
        if item.column() in {5, 6, 7, 8, 9, 11}:
            self._mark_unified_row_dirty(item.row())

    def on_unified_selected(self) -> None:
        row = self.unified_table.currentRow()
        if row < 0:
            return
        self.proposal_table.clearSelection()
        self.kg_table.clearSelection()
        source_item = self.unified_table.item(row, 0)
        id_item = self.unified_table.item(row, 1)
        if source_item is None or id_item is None:
            return
        source = source_item.text().strip().lower()
        try:
            source_id = int(id_item.text())
        except Exception:
            return

        if source == "proposal":
            item = next((x for x in self.items if int(x.get("id", 0)) == source_id), None)
            if item:
                self.editor_group.setTitle(f"Expert Proposal Editor (ID: {source_id})")
                self._load_into_editor(item)
        elif source == "curated":
            item = next(
                (x for x in self.curated_items if int(x.get("id", 0)) == source_id),
                None,
            )
            if item:
                self.editor_group.setTitle(f"Expert Curated Editor (ID: {source_id})")
                item_copy = dict(item)
                item_copy["content"] = item.get("term") or item.get("canonical_value", "")
                self._load_into_editor(item_copy)

    def on_unified_header_clicked(self, logical_index: int) -> None:
        if logical_index in {0, 1, 12}:
            return
        self.bulk_edit_column(self.unified_table, logical_index)

    def _save_unified_rows(
        self,
        rows: List[int],
    ) -> tuple[int, int, List[str], List[tuple[str, int]]]:
        updated = 0
        failed = 0
        errors: List[str] = []
        updated_entries: List[tuple[str, int]] = []
        for row in rows:
            source_item = self.unified_table.item(row, 0)
            id_item = self.unified_table.item(row, 1)
            if source_item is None or id_item is None:
                continue
            source = source_item.text().strip().lower()
            try:
                source_id = int(id_item.text())
            except Exception:
                continue

            status_combo = self.unified_table.cellWidget(row, 2)
            category_combo = self.unified_table.cellWidget(row, 3)
            ont_combo = self.unified_table.cellWidget(row, 4)
            verified_combo = self.unified_table.cellWidget(row, 10)
            label_item = self.unified_table.item(row, 5)
            canonical_item = self.unified_table.item(row, 6)
            conf_item = self.unified_table.item(row, 8)
            jurisdiction_item = self.unified_table.item(row, 9)

            status = status_combo.currentText() if isinstance(status_combo, QComboBox) else ""
            category = category_combo.currentText() if isinstance(category_combo, QComboBox) else ""
            ontology_entity_id = ont_combo.currentText() if isinstance(ont_combo, QComboBox) else ""
            label_term = label_item.text().strip() if label_item else ""
            canonical_key = canonical_item.text().strip() if canonical_item else ""
            jurisdiction = jurisdiction_item.text().strip() if jurisdiction_item else ""
            try:
                confidence = float(conf_item.text()) if conf_item and conf_item.text() else 0.0
            except Exception:
                confidence = 0.0

            try:
                if source == "proposal":
                    proposal = next(
                        (x for x in self.items if int(x.get("id", 0)) == source_id),
                        {},
                    )
                    metadata = dict(proposal.get("metadata") or {})
                    if category:
                        metadata["entity_type"] = category
                    if ontology_entity_id:
                        metadata["ontology_entity_id"] = ontology_entity_id
                    if jurisdiction:
                        metadata["jurisdiction"] = jurisdiction
                    api_client.update_memory_proposal(
                        source_id,
                        str(proposal.get("content", "")),
                        metadata if metadata else None,
                    )
                    normalized = str(status or "pending").strip().lower()
                    if normalized == "approved":
                        api_client.approve_memory_proposal(source_id)
                    elif normalized == "rejected":
                        api_client.reject_memory_proposal(source_id)
                elif source == "curated":
                    verified = None
                    if isinstance(verified_combo, QComboBox):
                        verified = verified_combo.currentText() == "True"
                    payload = {
                        "term": label_term,
                        "canonical_value": canonical_key,
                        "category": category or None,
                        "ontology_entity_id": ontology_entity_id or None,
                        "jurisdiction": jurisdiction or None,
                        "confidence": confidence,
                        "status": status or None,
                        "verified": verified,
                    }
                    api_client.update_manager_knowledge_item(source_id, payload)
                updated += 1
                updated_entries.append((source, source_id))
                if row in self._dirty_unified_rows:
                    self._dirty_unified_rows.remove(row)
                    self._apply_unified_dirty_style(row)
            except Exception as exc:
                failed += 1
                if len(errors) < 10:
                    errors.append(f"{source}#{source_id}: {exc}")
        return updated, failed, errors, updated_entries

    def save_unified_selected(self) -> None:
        rows = self._selected_unified_rows()
        if not rows:
            QMessageBox.information(self, "Unified Save", "No unified rows selected.")
            return
        updated, failed, errors, updated_entries = self._save_unified_rows(rows)
        msg = f"Updated {updated}/{len(rows)} unified rows."
        if failed:
            msg += f"\nFailed: {failed}"
            if errors:
                msg += "\n\n" + "\n".join(errors)
        QMessageBox.information(self, "Unified Save Selected", msg)
        self.refresh_all()
        self._focus_unified_rows(updated_entries)

    def save_unified_all(self) -> None:
        rows = list(range(self.unified_table.rowCount()))
        if not rows:
            QMessageBox.information(self, "Unified Save", "No unified rows available.")
            return
        updated, failed, errors, updated_entries = self._save_unified_rows(rows)
        msg = f"Updated {updated}/{len(rows)} unified rows."
        if failed:
            msg += f"\nFailed: {failed}"
            if errors:
                msg += "\n\n" + "\n".join(errors)
        QMessageBox.information(self, "Unified Save All", msg)
        self.refresh_all()
        self._focus_unified_rows(updated_entries)

    def bulk_set_verified(self, *, selected_only: bool, verified: bool) -> None:
        if selected_only:
            target_ids = self._selected_curated_ids()
        else:
            target_ids = []
            for i in range(self.kg_table.rowCount()):
                id_item = self.kg_table.item(i, 0)
                if id_item is None:
                    continue
                try:
                    target_ids.append(int(id_item.text()))
                except Exception:
                    continue
        if not target_ids:
            QMessageBox.information(self, "No Rows", "No curated rows selected.")
            return

        updated = 0
        before_by_id: Dict[int, Dict[str, Any]] = {}
        by_id = {int(x.get("id", 0)): x for x in self.curated_items if int(x.get("id", 0)) > 0}
        for knowledge_id in target_ids:
            try:
                existing = by_id.get(int(knowledge_id), {})
                before_by_id[int(knowledge_id)] = {
                    "verified": existing.get("verified"),
                    "status": existing.get("status"),
                }
                api_client.update_manager_knowledge_item(
                    knowledge_id,
                    {
                        "verified": verified,
                        "status": "verified" if verified else "proposed",
                    },
                )
                updated += 1
            except Exception:
                continue
        QMessageBox.information(
            self,
            "Bulk Verification",
            f"Updated {updated}/{len(target_ids)} rows.",
        )
        if updated:
            self._last_bulk_undo = {"targets": target_ids, "before": before_by_id}
            self.undo_bulk_btn.setEnabled(True)
        self.refresh_curated()

    def _parse_bulk_value(self, field: str, raw_value: str) -> Any:
        value = raw_value.strip()
        if field in {"verified", "is_canonical"}:
            lowered = value.lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
            raise ValueError("Boolean fields must be true/false.")

        if field == "confidence":
            return float(value)

        if field in {
            "components",
            "attributes",
        }:
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError(f"{field} must be a JSON object.")
            return parsed

        if field in {
            "legal_use_cases",
            "root_cause",
            "related_frameworks",
            "aliases",
            "relations",
            "sources",
        }:
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError(f"{field} must be a JSON array.")
            return parsed

        return value

    def bulk_update_field(self, *, selected_only: bool) -> None:
        field = self.bulk_field_combo.currentText().strip()
        raw_value = self.bulk_value_input.text()
        if not field:
            QMessageBox.information(self, "Bulk Update", "Select a field first.")
            return
        if raw_value is None or not str(raw_value).strip():
            QMessageBox.information(self, "Bulk Update", "Enter a value first.")
            return

        try:
            parsed_value = self._parse_bulk_value(field, str(raw_value))
        except Exception as exc:
            QMessageBox.critical(self, "Bulk Update Error", str(exc))
            return

        if selected_only:
            target_ids = self._selected_curated_ids()
        else:
            target_ids = []
            for i in range(self.kg_table.rowCount()):
                id_item = self.kg_table.item(i, 0)
                if id_item is None:
                    continue
                try:
                    target_ids.append(int(id_item.text()))
                except Exception:
                    continue
        if not target_ids:
            QMessageBox.information(self, "Bulk Update", "No rows selected.")
            return

        updated = 0
        payload = {field: parsed_value}
        before_by_id: Dict[int, Dict[str, Any]] = {}
        by_id = {int(x.get("id", 0)): x for x in self.curated_items if int(x.get("id", 0)) > 0}
        for knowledge_id in target_ids:
            try:
                existing = by_id.get(int(knowledge_id), {})
                before_by_id[int(knowledge_id)] = {field: existing.get(field)}
                api_client.update_manager_knowledge_item(knowledge_id, payload)
                updated += 1
            except Exception:
                continue

        QMessageBox.information(
            self,
            "Bulk Update",
            f"Updated {updated}/{len(target_ids)} rows for field '{field}'.",
        )
        if updated:
            self._last_bulk_undo = {"targets": target_ids, "before": before_by_id}
            self.undo_bulk_btn.setEnabled(True)
        self.refresh_curated()

    def undo_last_bulk_update(self) -> None:
        if not self._last_bulk_undo:
            QMessageBox.information(self, "Undo Bulk", "No bulk update to undo.")
            return
        targets = self._last_bulk_undo.get("targets") or []
        before = self._last_bulk_undo.get("before") or {}
        restored = 0
        for knowledge_id in targets:
            payload = before.get(int(knowledge_id))
            if not isinstance(payload, dict):
                continue
            try:
                api_client.update_manager_knowledge_item(int(knowledge_id), payload)
                restored += 1
            except Exception:
                continue
        QMessageBox.information(self, "Undo Bulk", f"Restored {restored}/{len(targets)} rows.")
        self._last_bulk_undo = None
        self.undo_bulk_btn.setEnabled(False)
        self.refresh_curated()

    def on_curated_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_curated:
            return
        if item.column() not in {1, 3, 5}:
            return
        row = item.row()
        id_item = self.kg_table.item(row, 0)
        if id_item is None:
            return
        try:
            rid = int(id_item.text())
        except Exception:
            return
        self._mark_curated_dirty(rid)
        self._apply_dirty_row_style(row, rid)

    def _mark_curated_dirty(self, row_id: int) -> None:
        if row_id > 0:
            self._dirty_curated_ids.add(int(row_id))

    def _apply_dirty_row_style(self, row: int, row_id: int) -> None:
        is_dirty = int(row_id) in self._dirty_curated_ids
        term_item = self.kg_table.item(row, 1)
        if term_item is not None:
            term_text = term_item.text().lstrip("* ").strip()
            term_item.setText(f"* {term_text}" if is_dirty else term_text)

    def approve_selected(self):
        ids = self._selected_proposal_ids()
        if not ids:
            pid = self._selected_id(self.proposal_table)
            if pid:
                ids = [pid]
        if not ids:
            QMessageBox.information(self, "Approve", "No proposals selected.")
            return
        ok = 0
        failed = 0
        errors: List[str] = []
        for pid in ids:
            try:
                api_client.approve_memory_proposal(pid)
                ok += 1
            except Exception as e:
                failed += 1
                if len(errors) < 10:
                    errors.append(f"#{pid}: {e}")
        msg = f"Approved {ok}/{len(ids)} proposal(s)."
        if failed:
            msg += f"\nFailed: {failed}"
            if errors:
                msg += "\n\n" + "\n".join(errors)
        QMessageBox.information(self, "Approve Results", msg)
        self.refresh_all()

    def reject_selected(self):
        ids = self._selected_proposal_ids()
        if not ids:
            pid = self._selected_id(self.proposal_table)
            if pid:
                ids = [pid]
        if not ids:
            QMessageBox.information(self, "Reject", "No proposals selected.")
            return
        ok = 0
        failed = 0
        errors: List[str] = []
        for pid in ids:
            try:
                api_client.reject_memory_proposal(pid)
                ok += 1
            except Exception as e:
                failed += 1
                if len(errors) < 10:
                    errors.append(f"#{pid}: {e}")
        msg = f"Rejected {ok}/{len(ids)} proposal(s)."
        if failed:
            msg += f"\nFailed: {failed}"
            if errors:
                msg += "\n\n" + "\n".join(errors)
        QMessageBox.information(self, "Reject Results", msg)
        self.refresh_all()

    def delete_selected(self):
        unified_row = self.unified_table.currentRow()
        source = ""
        target_id = 0
        if unified_row >= 0:
            source_item = self.unified_table.item(unified_row, 0)
            id_item = self.unified_table.item(unified_row, 1)
            if source_item and id_item:
                source = source_item.text().strip().lower()
                try:
                    target_id = int(id_item.text())
                except Exception:
                    target_id = 0
        if not target_id:
            is_prop = self.proposal_table.currentRow() >= 0
            source = "proposal" if is_prop else "curated"
            target_id = self._selected_id(self.proposal_table if is_prop else self.kg_table)
        if not target_id:
            return
        if QMessageBox.question(self, "Delete", "Permanently remove this item?") != QMessageBox.Yes:
            return
        try:
            if source == "proposal":
                api_client.delete_memory_proposal(target_id)
            else:
                api_client.delete_manager_knowledge_item(target_id)
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "Delete Failed", str(exc))

    def import_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import JSON", "", "JSON files (*.json)")
        if not file_path: return
        try:
            with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
            entities = data.get("entities") or data.get("extraction_result", {}).get("entities", [])
            for ent in entities:
                proposal = {
                    "namespace": "manual_import",
                    "key": f"import_{int(time.time())}",
                    "content": json.dumps(ent),
                    "memory_type": "entity",
                    "metadata": {"entity_type": ent.get("entity_type")},
                    "confidence_score": 1.0,
                    "created_at": datetime.now().isoformat()
                }
                api_client.create_memory_proposal(proposal)
            self.refresh_all()
            QMessageBox.information(self, "Success", f"Imported {len(entities)} items.")
        except Exception as e: QMessageBox.critical(self, "Import Failed", str(e))

    def _selected_id(self, table: QTableWidget) -> int:
        row = table.currentRow()
        if row < 0: return 0
        item = table.item(row, 0)
        try: return int(item.text())
        except Exception: return 0

    def on_proposal_header_clicked(self, logical_index):
        if logical_index < 2: return # Don't bulk edit ID or Preview
        self.bulk_edit_column(self.proposal_table, logical_index)

    def on_kg_header_clicked(self, logical_index):
        if logical_index == 0: return # Don't bulk edit ID
        self.bulk_edit_column(self.kg_table, logical_index)

    def bulk_edit_column(self, table: QTableWidget, col_index: int):
        header_text = table.horizontalHeaderItem(col_index).text()
        
        # Ask for scope: All or Selected
        selected_rows = table.selectionModel().selectedRows()
        scope_msg = f"Update all {table.rowCount()} rows in column '{header_text}'?"
        if selected_rows:
            res = QMessageBox.question(self, "Bulk Edit", 
                                     f"Update ONLY the {len(selected_rows)} selected rows?\n(Click No to update ALL rows)",
                                     QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if res == QMessageBox.Cancel: return
            rows_to_update = [r.row() for r in selected_rows] if res == QMessageBox.Yes else range(table.rowCount())
        else:
            if QMessageBox.question(self, "Bulk Edit", scope_msg) != QMessageBox.Yes: return
            rows_to_update = range(table.rowCount())

        # Get the new value
        from PySide6.QtWidgets import QInputDialog
        new_val, ok = QInputDialog.getText(self, f"Bulk Edit: {header_text}", f"Enter new value for {header_text}:")
        if not ok: return

        # Apply updates
        count = 0
        for row in rows_to_update:
            widget = table.cellWidget(row, col_index)
            if isinstance(widget, QComboBox):
                idx = widget.findText(new_val)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
                else:
                    widget.addItem(new_val)
                    widget.setCurrentText(new_val)
            else:
                item = table.item(row, col_index)
                if not item:
                    item = QTableWidgetItem()
                    table.setItem(row, col_index, item)
                item.setText(new_val)
            
            # Mark dirty if it's the KG table
            if table == self.kg_table:
                id_item = table.item(row, 0)
                if id_item:
                    self._mark_curated_dirty(int(id_item.text()))
            elif table == self.unified_table:
                self._mark_unified_row_dirty(int(row))
            count += 1

        self.ont_status_label.setText(
            f"Bulk update: {count} rows in '{header_text}'. Save to persist."
        )
        self.ont_status_label.setStyleSheet("color: #1565c0; font-weight: bold;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AgentMemoryManagerTab()
    w.show()
    sys.exit(app.exec())
