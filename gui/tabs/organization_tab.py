"""
Organization Tab - Ontology-based document organization workflow

This tab provides the centralized interface for reviewing, managing, and
approving organization proposals. It serves as the first step in the
document management pipeline, establishing the organizational structure
that all other tabs leverage.

Key Features:
- Folder-scoped proposal review
- Approve/Reject/Refine workflow
- Ontology-based organization
- Centralized metadata management
"""

import os
import re
import json
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus



from ..services import api_client
from ..services.audit_store import OrganizationAuditStore

try:
    from PySide6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QGroupBox,
        QTextBrowser,
        QFileDialog,
        QTextEdit,
        QLineEdit,
        QTableWidget,
        QTableWidgetItem,
        QCheckBox,
        QComboBox,
        QMessageBox,
        QAbstractItemView,
    )
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

from .status_presenter import TabStatusPresenter
from .default_paths import get_default_dialog_dir
if PYSIDE6_AVAILABLE:
    from ..ui import JobStatusWidget


class OrganizationTab(QWidget):  # type: ignore[misc]
    """
    Tab for ontology-based document organization workflow.
    
    This tab manages the organization proposal lifecycle:
    1. Browse and scope folders for review
    2. Generate organization proposals via AI/ontology
    3. Review proposals in table view
    4. Approve/Reject/Refine individual proposals
    5. Store organized metadata for consumption by other tabs
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_proposals_cache = []
        self.proposals_cache = []
        self._folder_cache = {}
        self.audit_store = OrganizationAuditStore()
        self.selected_proposal = None
        self.backend_ready = False
        self.setup_ui()
        self.connect_signals()
        # Defer backend calls until backend is ready
        # self.load_current_llm_provider() - moved to on_backend_ready()

    def _audit(self, event_type: str, payload: dict) -> None:
        safe_payload = payload if isinstance(payload, dict) else {"raw": str(payload)}
        root = self._normalize_root_scope(self.org_root_input.text())
        if root and not safe_payload.get("root"):
            safe_payload["root"] = root
        if isinstance(safe_payload.get("proposal"), dict):
            snap = safe_payload.get("proposal") or {}
        else:
            snap = self._proposal_snapshot(self.selected_proposal)
        if snap and "proposal" not in safe_payload:
            safe_payload["proposal"] = snap
        try:
            self.audit_store.log_event(event_type, safe_payload)
        except Exception:
            pass

    @staticmethod
    def _proposal_snapshot(proposal: Optional[dict]) -> dict:
        if not isinstance(proposal, dict):
            return {}
        return {
            "proposal_id": proposal.get("id"),
            "file_id": proposal.get("file_id"),
            "current_path": proposal.get("current_path"),
            "recommended_folder": proposal.get("proposed_folder"),
            "recommended_filename": proposal.get("proposed_filename"),
            "confidence": proposal.get("confidence"),
            "provider": proposal.get("provider"),
            "model": proposal.get("model"),
            "status": proposal.get("status"),
        }

    def _find_proposal_by_id(self, proposal_id: Optional[int]) -> Optional[dict]:
        if proposal_id is None:
            return None
        try:
            pid = int(proposal_id)
        except Exception:
            return None
        for item in self.proposals_cache:
            if int(item.get("id") or -1) == pid:
                return item
        for item in self.all_proposals_cache:
            if int(item.get("id") or -1) == pid:
                return item
        return None

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Document Organization")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "Ontology-based organization workflow: Review AI-generated proposals, "
            "refine folder structures, and approve organization schemes."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; padding: 5px 0;")
        layout.addWidget(desc)

# LLM Provider Control Group
        llm_group = QGroupBox("🤖 AI Provider (Ontology-Aware)")
        llm_layout = QHBoxLayout(llm_group)

        llm_layout.addWidget(QLabel("Provider:"))
        self.llm_provider_combo = QComboBox()
        self.llm_provider_combo.addItems(["xai", "deepseek"])
        self.llm_provider_combo.setToolTip("Switch between XAI and DeepSeek for organization proposals")
        llm_layout.addWidget(self.llm_provider_combo)

        self.llm_switch_btn = QPushButton("Switch Provider")
        self.llm_switch_btn.setStyleSheet("""
            QPushButton {
                background-color: #673AB7;
                color: white;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #5E35B1; }
        """)
        llm_layout.addWidget(self.llm_switch_btn)

        self.llm_status_label = QLabel("Current: Loading...")
        self.llm_status_label.setStyleSheet("color: #666; font-size: 10px;")
        llm_layout.addWidget(self.llm_status_label)

        llm_layout.addStretch()

        self.stats_btn = QPushButton("📊 Stats")
        self.stats_btn.setToolTip("View organization statistics")
        llm_layout.addWidget(self.stats_btn)

        layout.addWidget(llm_group)

        # Folder scope group
        scope_group = QGroupBox("Folder Scope")
        scope_layout = QVBoxLayout(scope_group)

        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Root Folder:"))
        self.org_root_input = QLineEdit()
        self.org_root_input.setPlaceholderText(r"E:\Organization_Folder or /mnt/e/...")
        default_folder = get_default_dialog_dir()
        if default_folder:
            self.org_root_input.setText(default_folder)
        scope_row.addWidget(self.org_root_input)
        
        self.org_browse_button = QPushButton("Browse...")
        self.org_browse_button.setMaximumWidth(100)
        scope_row.addWidget(self.org_browse_button)
        scope_layout.addLayout(scope_row)

        # Action buttons
        action_btn_row = QHBoxLayout()
        self.org_load_button = QPushButton("📋 Review Proposals")
        self.org_load_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        
        self.org_generate_button = QPushButton("⚡ Generate Scoped")
        self.org_generate_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        
        self.org_clear_button = QPushButton("🗑️ Clear Scoped")
        self.org_clear_button.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        self.org_apply_button = QPushButton("🚚 Apply Approved")
        self.org_apply_button.setStyleSheet("""
            QPushButton {
                background-color: #2E7D32;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1B5E20;
            }
        """)
        
        action_btn_row.addWidget(self.org_load_button)
        action_btn_row.addWidget(self.org_generate_button)
        action_btn_row.addWidget(self.org_clear_button)
        action_btn_row.addWidget(self.org_apply_button)
        action_btn_row.addStretch()
        scope_layout.addLayout(action_btn_row)
        
        layout.addWidget(scope_group)

        # Proposals table group
        proposals_group = QGroupBox("📋 Organization Proposals (Ontology-Based)")
        proposals_layout = QVBoxLayout(proposals_group)

        # Table toolbar
        table_toolbar = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setMaximumWidth(100)
        table_toolbar.addWidget(self.select_all_btn)

        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.setMaximumWidth(100)
        table_toolbar.addWidget(self.select_none_btn)

        table_toolbar.addStretch()

        self.bulk_approve_btn = QPushButton("✓ Bulk Approve")
        self.bulk_approve_btn.setStyleSheet("background:#4CAF50; color:white; padding:4px 10px; border-radius:3px;")
        self.bulk_approve_btn.setEnabled(False)
        table_toolbar.addWidget(self.bulk_approve_btn)

        self.bulk_reject_btn = QPushButton("✗ Bulk Reject")
        self.bulk_reject_btn.setStyleSheet("background:#f44336; color:white; padding:4px 10px; border-radius:3px;")
        self.bulk_reject_btn.setEnabled(False)
        table_toolbar.addWidget(self.bulk_reject_btn)

        self.export_proposals_btn = QPushButton("💾 Export")
        table_toolbar.addWidget(self.export_proposals_btn)

        proposals_layout.addLayout(table_toolbar)

        # Search/filter toolbar
        search_toolbar = QHBoxLayout()
        search_toolbar.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by path, folder, filename, rationale...")
        search_toolbar.addWidget(self.search_input)
        self.search_apply_btn = QPushButton("Filter")
        search_toolbar.addWidget(self.search_apply_btn)
        self.search_clear_btn = QPushButton("Clear")
        search_toolbar.addWidget(self.search_clear_btn)
        self.select_filtered_btn = QPushButton("Select Filtered")
        self.select_filtered_btn.setMaximumWidth(140)
        search_toolbar.addWidget(self.select_filtered_btn)
        proposals_layout.addLayout(search_toolbar)

        self.org_table = QTableWidget(0, 6)
        self.org_table.setHorizontalHeaderLabels([
            "☑", "ID", "Confidence", "Current Path", "Proposed Folder", "Proposed Filename"
        ])
        self.org_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.org_table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.org_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.org_table.setMinimumHeight(320)
        self.org_table.setAlternatingRowColors(True)
        self.org_table.setSortingEnabled(True)
        header = self.org_table.horizontalHeader()
        header.setStretchLastSection(True)
        
        proposals_layout.addWidget(self.org_table)
        layout.addWidget(proposals_group)

        # Refinement group
        refine_group = QGroupBox("Refine Selected Proposal")
        refine_layout = QVBoxLayout(refine_group)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Folder:"))
        self.org_folder_input = QComboBox()
        self.org_folder_input.setEditable(True)
        self.org_folder_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.org_folder_input.setMinimumWidth(260)
        self.org_folder_input.setToolTip("Select a suggested folder or type a new one")
        self.org_folder_input.lineEdit().setPlaceholderText("Proposed folder path...")
        path_row.addWidget(self.org_folder_input, 3)
        self.folder_popup_btn = QPushButton("▼")
        self.folder_popup_btn.setMaximumWidth(34)
        self.folder_popup_btn.setToolTip("Show folder suggestions")
        path_row.addWidget(self.folder_popup_btn)
        self.folder_refresh_btn = QPushButton("↻")
        self.folder_refresh_btn.setMaximumWidth(34)
        self.folder_refresh_btn.setToolTip("Refresh folder suggestions")
        path_row.addWidget(self.folder_refresh_btn)
        
        path_row.addWidget(QLabel("Filename:"))
        self.org_filename_input = QLineEdit()
        self.org_filename_input.setPlaceholderText("Proposed filename...")
        path_row.addWidget(self.org_filename_input, 2)
        refine_layout.addLayout(path_row)

        self.org_note_input = QTextEdit()
        self.org_note_input.setPlaceholderText("Optional note (for rejection/refinement)...")
        self.org_note_input.setMaximumHeight(60)
        refine_layout.addWidget(self.org_note_input)

        # Proposal action buttons
        proposal_action_row = QHBoxLayout()
        self.org_approve_button = QPushButton("✓ Approve")
        self.org_approve_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 24px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.org_reject_button = QPushButton("✗ Reject")
        self.org_reject_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 8px 24px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        
        self.org_edit_approve_button = QPushButton("✎ Refine + Approve")
        self.org_edit_approve_button.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                padding: 8px 24px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        
        proposal_action_row.addWidget(self.org_approve_button)
        proposal_action_row.addWidget(self.org_edit_approve_button)
        proposal_action_row.addWidget(self.org_reject_button)
        proposal_action_row.addStretch()
        refine_layout.addLayout(proposal_action_row)
        
        layout.addWidget(refine_group)

        # Status and results
        self.status_label = QLabel("Ready - Select a folder to begin")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f5f5f5; border-radius: 3px;")
        layout.addWidget(self.status_label)
        
        self.status = TabStatusPresenter(self, self.status_label, source="Organization")
        
        if PYSIDE6_AVAILABLE:
            self.job_status = JobStatusWidget("Organization Job")
            layout.addWidget(self.job_status)

        # Results browser
        results_group = QGroupBox("API Response")
        results_layout = QVBoxLayout(results_group)
        self.results_browser = QTextBrowser()
        self.results_browser.setMaximumHeight(150)
        results_layout.addWidget(self.results_browser)
        layout.addWidget(results_group)

        layout.addStretch()

    def connect_signals(self):
        """Connect UI signals to handlers."""
        # LLM controls
        self.llm_switch_btn.clicked.connect(self.switch_llm_provider)
        self.stats_btn.clicked.connect(self.show_stats)
        
        # Folder controls
        self.org_browse_button.clicked.connect(self.org_pick_folder)
        self.org_load_button.clicked.connect(self.org_load_proposals)
        self.org_generate_button.clicked.connect(self.org_generate_scoped)
        self.org_clear_button.clicked.connect(self.org_clear_scoped)
        self.org_apply_button.clicked.connect(self.org_apply_approved_scoped)
        
        # Table controls
        self.select_all_btn.clicked.connect(self.select_all_proposals)
        self.select_none_btn.clicked.connect(self.select_none_proposals)
        self.bulk_approve_btn.clicked.connect(self.bulk_approve_proposals)
        self.bulk_reject_btn.clicked.connect(self.bulk_reject_proposals)
        self.export_proposals_btn.clicked.connect(self.export_proposals)
        self.search_apply_btn.clicked.connect(self.apply_search_filter)
        self.search_clear_btn.clicked.connect(self.clear_search_filter)
        self.select_filtered_btn.clicked.connect(self.select_filtered_proposals)
        self.search_input.returnPressed.connect(self.apply_search_filter)
        self.org_table.itemSelectionChanged.connect(self.org_on_selection_changed)
        self.org_table.itemChanged.connect(self.handle_table_cell_changed)
        
        # Proposal actions
        self.org_approve_button.clicked.connect(self.org_approve_selected)
        self.org_reject_button.clicked.connect(self.org_reject_selected)
        self.org_edit_approve_button.clicked.connect(self.org_edit_approve_selected)
        self.folder_popup_btn.clicked.connect(self.org_folder_input.showPopup)
        self.folder_refresh_btn.clicked.connect(self.refresh_folder_suggestions)

    # -------------------------------------------------------------------------
    # Organization Workflow Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_root_scope(path_str: str) -> str:
        """Normalize folder path for consistent API usage."""
        p = path_str.strip()
        if not p:
            return ""
        p = p.replace("\\", "/")
        return p

    @staticmethod
    def _scope_prefixes(path_str: str) -> list[str]:
        """Build equivalent scope prefixes for Windows/WSL path variants."""
        root = OrganizationTab._normalize_root_scope(path_str)
        if not root:
            return []
        prefixes = [root]

        # Windows drive path -> WSL equivalent (/mnt/<drive>/...)
        m = re.match(r"^([A-Za-z]):/(.*)$", root)
        if m:
            drive = m.group(1).lower()
            rest = m.group(2).lstrip("/")
            prefixes.append(f"/mnt/{drive}/{rest}")

        # WSL path -> Windows equivalent (<DRIVE>:/...)
        m2 = re.match(r"^/mnt/([A-Za-z])/(.*)$", root)
        if m2:
            drive = m2.group(1).upper()
            rest = m2.group(2).lstrip("/")
            prefixes.append(f"{drive}:/{rest}")

        seen = set()
        unique = []
        for p in prefixes:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        return unique

    def _existing_runtime_roots(self, root: str) -> list[str]:
        """Return root path variants that exist in current runtime."""
        existing: list[str] = []
        for candidate in self._scope_prefixes(root):
            try:
                p = Path(candidate)
                if p.exists() and p.is_dir():
                    existing.append(candidate)
            except Exception:
                continue
        return existing



    def org_pick_folder(self):
        """Open folder browser dialog."""
        default_path = get_default_dialog_dir(self.org_root_input.text())
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Organization Folder Root", 
            default_path
        )
        if folder:
            self.org_root_input.setText(folder)
            self.status.info(f"Scope set to: {folder}")

    def org_load_proposals(self):
        """Load organization proposals from API for the scoped folder."""
        # #region agent log
        try:
            import json as _j, time
            from pathlib import Path as _P
            _log = _P(__file__).resolve().parent.parent.parent / "debug-4d484f.log"
            _before = {"selected_proposal_id": self._selected_proposal_id(), "cache_len": len(self.proposals_cache), "all_cache_len": len(self.all_proposals_cache)}
            _p = {"sessionId": "4d484f", "location": "organization_tab.py:org_load_proposals", "message": "load_proposals_start", "data": _before, "timestamp": int(time.time() * 1000), "hypothesisId": "A"}
            with open(_log, "a", encoding="utf-8") as _f:
                _f.write(_j.dumps(_p) + "\n")
        except Exception:
            pass
        # #endregion
        try:
            self.status.info("Loading proposals...")
            root = self._normalize_root_scope(self.org_root_input.text())

            endpoint = "/organization/proposals?status=proposed&limit=1000&offset=0"
            if root:
                endpoint += f"&root_prefix={quote_plus(root)}"

            # Fetch proposals from API (already root-scoped when root is set)
            data = api_client.get(endpoint, timeout=30.0)
            
            items = data.get("items", []) if isinstance(data, dict) else []

            self.all_proposals_cache = list(items)
            self.apply_search_filter(silent=True)
            # #region agent log
            try:
                _after = {"selected_proposal_id": self._selected_proposal_id(), "cache_len": len(self.proposals_cache), "all_cache_len": len(self.all_proposals_cache), "selected_still_exists": any(p.get("id") == _before.get("selected_proposal_id") for p in self.proposals_cache)}
                _p2 = {"sessionId": "4d484f", "location": "organization_tab.py:org_load_proposals", "message": "load_proposals_end", "data": _after, "timestamp": int(time.time() * 1000), "hypothesisId": "A"}
                with open(_log, "a", encoding="utf-8") as _f:
                    _f.write(_j.dumps(_p2) + "\n")
            except Exception:
                pass
            # #endregion
            self._audit(
                "load_proposals",
                {
                    "root": root,
                    "loaded": len(self.all_proposals_cache),
                    "shown": len(self.proposals_cache),
                },
            )
            
        except Exception as e:
            # #region agent log
            try:
                _p3 = {"sessionId": "4d484f", "location": "organization_tab.py:org_load_proposals", "message": "load_proposals_error", "data": {"error": str(e)}, "timestamp": int(time.time() * 1000), "hypothesisId": "A"}
                with open(_log, "a", encoding="utf-8") as _f:
                    _f.write(_j.dumps(_p3) + "\n")
            except Exception:
                pass
            # #endregion
            self.status.error(f"Failed to load proposals: {e}")
            self.results_browser.setPlainText(f"Error: {e}")

    def _populate_proposals_table(self, items):
        """Populate table from proposal list."""
        # #region agent log
        _before_id = None
        try:
            import json as _j, time
            from pathlib import Path as _P
            _log = _P(__file__).resolve().parent.parent.parent / "debug-4d484f.log"
            _before_id = self._selected_proposal_id()
            _before = {"selected_proposal_id": _before_id, "old_cache_len": len(self.proposals_cache), "new_items_len": len(items)}
            _p = {"sessionId": "4d484f", "location": "organization_tab.py:_populate_proposals_table", "message": "populate_start", "data": _before, "timestamp": int(time.time() * 1000), "hypothesisId": "D"}
            with open(_log, "a", encoding="utf-8") as _f:
                _f.write(_j.dumps(_p) + "\n")
        except Exception:
            pass
        # #endregion
        self.proposals_cache = list(items)

        self.org_table.setSortingEnabled(False)
        # Block signals during repopulation to avoid triggering selection change events
        self.org_table.blockSignals(True)
        self.org_table.setRowCount(len(items))
        for i, p in enumerate(items):
            checkbox = QCheckBox()
            checkbox.setStyleSheet("margin-left:50%; margin-right:50%;")
            self.org_table.setCellWidget(i, 0, checkbox)

            self.org_table.setItem(i, 1, QTableWidgetItem(str(p.get("id") or "")))

            confidence = float(p.get("confidence") or 0.0)
            conf_item = QTableWidgetItem(f"{confidence:.2f}")
            self.org_table.setItem(i, 2, conf_item)

            self.org_table.setItem(i, 3, QTableWidgetItem(str(p.get("current_path") or "")))
            self.org_table.setItem(i, 4, QTableWidgetItem(str(p.get("proposed_folder") or "")))
            self.org_table.setItem(i, 5, QTableWidgetItem(str(p.get("proposed_filename") or "")))

        self.org_table.resizeColumnsToContents()
        self.org_table.setSortingEnabled(True)
        # Clear selected_proposal when table is repopulated - it may no longer exist in cache
        # Validate that selected_proposal still exists in the new cache, otherwise clear it
        if self.selected_proposal is not None:
            # Get ID directly from selected_proposal (don't call _selected_proposal_id() which might clear it)
            try:
                selected_id = int(self.selected_proposal.get("id"))
                # Check if proposal still exists in new cache
                if not any(p.get("id") == selected_id for p in self.proposals_cache):
                    # Selected proposal no longer exists in cache (likely approved/rejected)
                    self.selected_proposal = None
                    self.org_folder_input.clear()
                    self.org_filename_input.clear()
            except Exception:
                # Invalid selected_proposal - clear it
                self.selected_proposal = None
                self.org_folder_input.clear()
                self.org_filename_input.clear()
        # Re-enable signals and clear selection explicitly
        self.org_table.blockSignals(False)
        self.org_table.clearSelection()
        # #region agent log
        try:
            _after = {"selected_proposal_id": self._selected_proposal_id(), "cache_len": len(self.proposals_cache), "table_rows": self.org_table.rowCount(), "selected_still_in_cache": any(p.get("id") == _before_id for p in self.proposals_cache) if _before_id is not None else False}
            _p2 = {"sessionId": "4d484f", "location": "organization_tab.py:_populate_proposals_table", "message": "populate_end", "data": _after, "timestamp": int(time.time() * 1000), "hypothesisId": "D"}
            with open(_log, "a", encoding="utf-8") as _f:
                _f.write(_j.dumps(_p2) + "\n")
        except Exception:
            pass
        # #endregion
        self._refresh_folder_suggestions(items)

    def _refresh_folder_suggestions(self, items):
        """Refresh folder dropdown options from current proposal set."""
        current = self._folder_value()
        options = set()
        for p in items:
            folder = str(p.get("proposed_folder") or "").strip()
            if folder:
                options.add(folder)
            for alt in p.get("alternatives") or []:
                if isinstance(alt, str) and alt.strip():
                    options.add(alt.strip())
        for folder in self._folders_from_root():
            options.add(folder)
        ordered = sorted(options, key=lambda x: x.lower())
        self.org_folder_input.blockSignals(True)
        self.org_folder_input.clear()
        if ordered:
            self.org_folder_input.addItems(ordered)
        if current:
            self.org_folder_input.setEditText(current)
        self.org_folder_input.blockSignals(False)

    def refresh_folder_suggestions(self):
        """Force refresh folder catalog from disk and update dropdown."""
        root = (self.org_root_input.text() or "").strip().lower()
        if root:
            self._folder_cache.pop(root, None)
        self._refresh_folder_suggestions(self.proposals_cache or self.all_proposals_cache)
        self.status.info(f"Folder suggestions: {self.org_folder_input.count()} options")

    @staticmethod
    def _candidate_roots_for_folder_scan(root_txt: str) -> list[Path]:
        """Include scoped root plus broader Organization_Folder root if nested."""
        root = Path(root_txt)
        roots = [root]
        parts = list(root.parts)
        lowered = [p.lower() for p in parts]
        if "organization_folder" in lowered:
            idx = lowered.index("organization_folder")
            broad = Path(*parts[: idx + 1])
            if broad not in roots:
                roots.append(broad)
        return roots

    def _folders_from_root(self, max_items: int = 500) -> list[str]:
        """Collect existing folders under selected root as suggestion options."""
        root_txt = (self.org_root_input.text() or "").strip()
        if not root_txt:
            return []
        key = root_txt.lower()
        if key in self._folder_cache:
            return list(self._folder_cache[key])[:max_items]

        out: list[str] = []
        seen = set()
        roots = [r for r in self._candidate_roots_for_folder_scan(root_txt) if r.exists() and r.is_dir()]
        try:
            for base in roots:
                for dirpath, dirnames, _ in os.walk(str(base)):
                    rel = Path(dirpath).relative_to(base).as_posix()
                    if rel and rel not in seen:
                        seen.add(rel)
                        out.append(rel)
                        if len(out) >= max_items:
                            self._folder_cache[key] = list(out)
                            return out
                    dirnames.sort()
        except Exception:
            pass
        self._folder_cache[key] = list(out)
        return out[:max_items]

    def _folder_value(self) -> str:
        return str(self.org_folder_input.currentText() or "").strip()

    def apply_search_filter(self, silent: bool = False):
        """Filter loaded proposals by search text."""
        text = (self.search_input.text() or "").strip().lower()
        items = list(self.all_proposals_cache)
        if text:
            filtered = []
            for p in items:
                blob = " ".join(
                    [
                        str(p.get("current_path") or ""),
                        str(p.get("proposed_folder") or ""),
                        str(p.get("proposed_filename") or ""),
                        str(p.get("rationale") or ""),
                        str(p.get("provider") or ""),
                        str(p.get("model") or ""),
                    ]
                ).lower()
                if text in blob:
                    filtered.append(p)
            items = filtered

        self._populate_proposals_table(items)
        self.results_browser.setPlainText(
            f"✓ Loaded {len(self.all_proposals_cache)} proposals | Showing {len(items)}"
        )
        if not silent:
            self.status.success(f"Showing {len(items)} of {len(self.all_proposals_cache)} proposals")

    def clear_search_filter(self):
        """Clear proposal search filter."""
        self.search_input.clear()
        self.apply_search_filter()

    def select_filtered_proposals(self):
        """Select all currently filtered/visible proposals."""
        self.select_all_proposals()

    def _checked_or_selected_rows(self) -> list[int]:
        """Resolve bulk targets by checked boxes, fallback to selected rows."""
        checked_rows = []
        for row in range(self.org_table.rowCount()):
            checkbox = self.org_table.cellWidget(row, 0)
            if checkbox and isinstance(checkbox, QCheckBox) and checkbox.isChecked():
                checked_rows.append(row)
        if checked_rows:
            return sorted(set(checked_rows))
        return sorted({idx.row() for idx in self.org_table.selectionModel().selectedRows()})

    def org_load_proposals_silent(self):
        """Silently load proposals on startup without UI feedback (non-blocking)."""
        try:
            # Check if any proposals exist
            data = api_client.get(
                "/organization/proposals?status=proposed&limit=10&offset=0", 
                timeout=5.0
            )
            
            items = data.get("items", []) if isinstance(data, dict) else []
            
            if len(items) > 0:
                # If proposals exist, load them normally
                self.org_load_proposals()
                print(f"[OrganizationTab] Auto-loaded {len(items)} proposals on startup")
            else:
                # No proposals to show
                self.status.info("No pending proposals - use 'Generate Proposals' to create them")
                
        except Exception as e:
            print(f"[OrganizationTab] Silent load failed: {e}")
            self.status.info(f"Auto-load skipped: {e}")

    def org_generate_scoped(self):
        """Generate new organization proposals for the scoped folder."""
        try:
            self.status.info("Indexing scoped files before generation...")
            root = self._normalize_root_scope(self.org_root_input.text())

            if root:
                index_summary = self._index_scope_until_stable(root)
                self._audit("index_scope_until_stable", index_summary)
                self.status.info(
                    f"Indexed scope: {index_summary.get('indexed_total', 0)}/"
                    f"{index_summary.get('target_files', 0)} files"
                )
            self.status.info("Generating proposals (this may take 1-2 minutes)...")
            
            payload = {
                "limit": 500,
                "root_prefix": root or None
            }
            
            out = api_client.post(
                "/organization/proposals/generate", 
                json=payload, 
                timeout=180.0
            )
            
            self.results_browser.setPlainText(str(out))
            self.status.success("Generation complete")
            self._audit(
                "generate_scoped",
                {
                    "root": root,
                    "created": int(out.get("created", 0)),
                    "requested_provider": out.get("requested_provider"),
                    "active_provider": out.get("active_provider"),
                },
            )
            
            # Automatically reload proposals
            self.org_load_proposals()
            
        except Exception as e:
            self.status.error(f"Failed to generate proposals: {e}")
            self.results_browser.setPlainText(f"Error: {e}")

    def _scan_scope_files(self, root: str) -> dict:
        """Scan local filesystem to estimate index target for scoped root."""
        runtime_roots = self._existing_runtime_roots(root)
        if not runtime_roots:
            return {
                "runtime_roots": [],
                "total_files": 0,
                "files_with_ext": 0,
                "files_without_ext": 0,
                "allowed_exts": [],
                "reason": "no_runtime_root_found",
            }

        total_files = 0
        files_with_ext = 0
        ext_set: set[str] = set()
        scanned_roots: list[str] = []
        for scan_root in runtime_roots:
            scan_path = Path(scan_root)
            if not scan_path.exists() or not scan_path.is_dir():
                continue
            scanned_roots.append(scan_root)
            for dirpath, _, filenames in os.walk(str(scan_path)):
                for name in filenames:
                    total_files += 1
                    ext = Path(name).suffix.lower().strip()
                    if ext:
                        files_with_ext += 1
                        ext_set.add(ext)

        return {
            "runtime_roots": scanned_roots,
            "total_files": total_files,
            "files_with_ext": files_with_ext,
            "files_without_ext": max(0, total_files - files_with_ext),
            "allowed_exts": sorted(ext_set),
        }

    def _count_indexed_for_scope(self, root: str) -> int:
        """Get indexed file count for root (supports Windows/WSL path variants)."""
        best_total = 0
        for prefix in self._scope_prefixes(root):
            encoded = quote_plus(prefix)
            data = api_client.get(
                f"/files?limit=1&offset=0&q={encoded}",
                timeout=20.0,
            )
            best_total = max(best_total, int(data.get("total", 0)))
        return best_total

    def _index_scope_until_stable(self, root: str, max_cycles: int = 8) -> dict:
        """Index scoped files repeatedly until indexed totals stabilize."""
        scan = self._scan_scope_files(root)
        runtime_roots = list(scan.get("runtime_roots") or [])
        if not runtime_roots:
            raise RuntimeError(
                f"Selected root is not available in runtime path space: {root}. "
                "Use a path that exists for the running backend (Windows or /mnt/...)."
            )
        target_files = int(scan.get("files_with_ext", 0))
        allowed_exts = scan.get("allowed_exts") or None
        max_files = max(int(scan.get("total_files", 0)) + 1000, 20000)

        if int(scan.get("total_files", 0)) == 0:
            return {
                "root": root,
                "cycles": 0,
                "target_files": 0,
                "indexed_total": 0,
                "reason": "no_files_found",
            }

        prev_total = -1
        indexed_total = 0
        cycles_run = 0
        last_index_result: dict = {}
        stop_reason = "max_cycles_reached"

        while cycles_run < max_cycles:
            cycles_run += 1
            self.status.info(f"Indexing scope pass {cycles_run}/{max_cycles}...")
            payload = {
                "roots": runtime_roots,
                "recursive": True,
                "allowed_exts": allowed_exts,
                "max_files": max_files,
            }
            last_index_result = api_client.post(
                "/files/index?use_taskmaster=false",
                json=payload,
                timeout=240.0,
            )
            indexed_total = self._count_indexed_for_scope(root)
            pass_delta = int(last_index_result.get("indexed", 0))

            self._audit(
                "index_scope_pass",
                {
                    "root": root,
                    "pass": cycles_run,
                    "target_files": target_files,
                    "indexed_total": indexed_total,
                    "pass_indexed": pass_delta,
                },
            )

            if target_files > 0 and indexed_total >= target_files:
                stop_reason = "target_reached"
                break
            if indexed_total == prev_total:
                stop_reason = "stable_no_change"
                break
            prev_total = indexed_total

        refresh_result = {}
        try:
            refresh_result = api_client.post(
                "/files/refresh?run_watches=false&stale_after_hours=1&use_taskmaster=false",
                json={},
                timeout=180.0,
            )
        except Exception as e:
            refresh_result = {"success": False, "error": str(e)}

        return {
            "root": root,
            "cycles": cycles_run,
            "target_files": target_files,
            "indexed_total": indexed_total,
            "stop_reason": stop_reason,
            "scan": scan,
            "last_index_result": last_index_result,
            "refresh_result": refresh_result,
        }

    def org_clear_scoped(self):
        """Clear all proposals for the scoped folder."""
        try:
            self.status.info("Clearing scoped proposals...")
            root = self._normalize_root_scope(self.org_root_input.text())
            
            payload = {
                "status": "proposed",
                "root_prefix": root or None,
                "note": "gui_clear"
            }
            
            out = api_client.post(
                "/organization/proposals/clear", 
                json=payload, 
                timeout=120.0
            )
            
            self.results_browser.setPlainText(str(out))
            self.status.success("Cleared scoped proposals")
            self._audit(
                "clear_scoped",
                {
                    "root": root,
                    "cleared": int(out.get("cleared", 0)),
                },
            )
            
            # Reload to show updated state
            self.org_load_proposals()
            
        except Exception as e:
            self.status.error(f"Failed to clear proposals: {e}")
            self.results_browser.setPlainText(f"Error: {e}")

    def org_apply_approved_scoped(self):
        """Apply approved proposals (move files) for the current root scope."""
        try:
            root = self._normalize_root_scope(self.org_root_input.text())
            reply = QMessageBox.question(
                self,
                "Apply Approved Proposals",
                "This will MOVE approved files on disk for the current scope.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

            self.status.info("Applying approved proposals (moving files)...")
            payload = {"limit": 5000, "dry_run": False, "root_prefix": root or None}
            out = api_client.post("/organization/apply", json=payload, timeout=180.0)
            applied = int(out.get("applied", 0))
            failed = int(out.get("failed", 0))

            # Persist an apply audit artifact for easy recovery/debugging.
            try:
                logs_dir = Path("logs")
                logs_dir.mkdir(parents=True, exist_ok=True)
                audit_path = logs_dir / "organization_apply_last.json"
                audit_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
            except Exception:
                pass

            # Best-effort index refresh so searches reflect moved files sooner.
            try:
                api_client.post(
                    "/files/refresh?run_watches=false&stale_after_hours=1&use_taskmaster=false",
                    json={},
                    timeout=120.0,
                )
            except Exception:
                pass

            self.results_browser.setPlainText(str(out))
            if failed == 0:
                self.status.success(f"Applied {applied} moves")
            else:
                self.status.error(f"Applied {applied}, failed {failed}")
            self._audit(
                "apply_approved",
                {
                    "action": "apply_approved",
                    "outcome": "success" if failed == 0 else "partial",
                    "root": root,
                    "applied": applied,
                    "failed": failed,
                    "results_count": len(out.get("results", []) or []),
                },
            )
            for item in out.get("results", []) or []:
                if not isinstance(item, dict):
                    continue
                self._audit(
                    "apply_result",
                    {
                        "action": "move",
                        "proposal_id": item.get("proposal_id"),
                        "old_path": item.get("from"),
                        "new_path": item.get("to"),
                        "ok": bool(item.get("ok")),
                        "outcome": "success" if bool(item.get("ok")) else "failed",
                        "error": item.get("error"),
                        "proposal": self._proposal_snapshot(
                            self._find_proposal_by_id(item.get("proposal_id"))
                        ),
                    },
                )
            self.org_load_proposals()
        except Exception as e:
            self.status.error(f"Apply failed: {e}")
            self.results_browser.setPlainText(f"Error: {e}")

    def org_on_selection_changed(self):
        """Handle proposal selection in table - populate refinement inputs."""
        row = self.org_table.currentRow()
        # #region agent log
        try:
            import json as _j, time
            from pathlib import Path as _P
            _log = _P(__file__).resolve().parent.parent.parent / "debug-4d484f.log"
            _p = {"sessionId": "4d484f", "location": "organization_tab.py:org_on_selection_changed", "message": "selection_changed", "data": {"row": row, "cache_len": len(self.proposals_cache), "row_valid": 0 <= row < len(self.proposals_cache)}, "timestamp": int(time.time() * 1000), "hypothesisId": "C"}
            with open(_log, "a", encoding="utf-8") as _f:
                _f.write(_j.dumps(_p) + "\n")
        except Exception:
            pass
        # #endregion
        if row < 0 or row >= len(self.proposals_cache):
            self.selected_proposal = None
            self.org_folder_input.clear()
            self.org_filename_input.clear()
            return
        
        p = self.proposals_cache[row]
        self.selected_proposal = p
        # #region agent log
        try:
            _p2 = {"sessionId": "4d484f", "location": "organization_tab.py:org_on_selection_changed", "message": "selection_set", "data": {"proposal_id": p.get("id"), "row": row}, "timestamp": int(time.time() * 1000), "hypothesisId": "C"}
            with open(_log, "a", encoding="utf-8") as _f:
                _f.write(_j.dumps(_p2) + "\n")
        except Exception:
            pass
        # #endregion
        
        # Add selected proposal alternatives as quick-pick options.
        for alt in p.get("alternatives") or []:
            if isinstance(alt, str) and alt.strip() and self.org_folder_input.findText(alt.strip()) < 0:
                self.org_folder_input.addItem(alt.strip())
        self.org_folder_input.setEditText(str(p.get("proposed_folder") or ""))
        self.org_filename_input.setText(str(p.get("proposed_filename") or ""))
        
        # Update status with selection info
        pid = p.get("id", "?")
        self.status.info(f"Selected proposal #{pid}")

    def _selected_proposal_id(self) -> Optional[int]:
        """Get the ID of the currently selected proposal."""
        if not self.selected_proposal:
            return None
        # Validate that selected_proposal still exists in cache
        try:
            pid = int(self.selected_proposal.get("id"))
            # Check if proposal still exists in current cache
            if not any(p.get("id") == pid for p in self.proposals_cache):
                # Selected proposal no longer in cache - clear it
                self.selected_proposal = None
                return None
            return pid
        except Exception:
            return None

    def org_approve_selected(self):
        """Approve the currently selected proposal."""
        pid = self._selected_proposal_id()
        # #region agent log
        try:
            import json as _j, time
            from pathlib import Path as _P
            _log = _P(__file__).resolve().parent.parent.parent / "debug-4d484f.log"
            _p = {"sessionId": "4d484f", "location": "organization_tab.py:org_approve_selected", "message": "approve_start", "data": {"proposal_id": pid, "selected_proposal_exists": self.selected_proposal is not None, "cache_len": len(self.proposals_cache)}, "timestamp": int(time.time() * 1000), "hypothesisId": "B"}
            with open(_log, "a", encoding="utf-8") as _f:
                _f.write(_j.dumps(_p) + "\n")
        except Exception:
            pass
        # #endregion
        if pid is None:
            self.status.info("Please select a proposal first")
            return
        
        try:
            self.status.info(f"Approving proposal #{pid}...")
            out = api_client.post(
                f"/organization/proposals/{pid}/approve", 
                json={}, 
                timeout=60.0
            )
            
            self.results_browser.setPlainText(str(out))
            self.status.success(f"Proposal #{pid} approved")
            # #region agent log
            try:
                _p2 = {"sessionId": "4d484f", "location": "organization_tab.py:org_approve_selected", "message": "approve_api_success", "data": {"proposal_id": pid, "api_response": str(out)[:200]}, "timestamp": int(time.time() * 1000), "hypothesisId": "B"}
                with open(_log, "a", encoding="utf-8") as _f:
                    _f.write(_j.dumps(_p2) + "\n")
            except Exception:
                pass
            # #endregion
            self._audit(
                "approve_proposal",
                {
                    "action": "approve",
                    "proposal_id": pid,
                    "ok": True,
                    "outcome": "success",
                    "proposal": self._proposal_snapshot(self.selected_proposal),
                },
            )
            
            # Reload proposals to show updated state
            self.org_load_proposals()
            
        except Exception as e:
            # #region agent log
            try:
                _p3 = {"sessionId": "4d484f", "location": "organization_tab.py:org_approve_selected", "message": "approve_error", "data": {"proposal_id": pid, "error": str(e)}, "timestamp": int(time.time() * 1000), "hypothesisId": "B"}
                with open(_log, "a", encoding="utf-8") as _f:
                    _f.write(_j.dumps(_p3) + "\n")
            except Exception:
                pass
            # #endregion
            self.status.error(f"Approve failed: {e}")
            self.results_browser.setPlainText(f"Error: {e}")

    def org_reject_selected(self):
        """Reject the currently selected proposal."""
        pid = self._selected_proposal_id()
        if pid is None:
            self.status.info("Please select a proposal first")
            return
        
        try:
            self.status.info(f"Rejecting proposal #{pid}...")
            out = api_client.post(
                f"/organization/proposals/{pid}/reject",
                json={"note": self.org_note_input.toPlainText() or None},
                timeout=60.0,
            )
            
            self.results_browser.setPlainText(str(out))
            self.status.success(f"Proposal #{pid} rejected")
            self._audit(
                "reject_proposal",
                {
                    "action": "reject",
                    "proposal_id": pid,
                    "ok": True,
                    "outcome": "success",
                    "note": self.org_note_input.toPlainText() or None,
                    "proposal": self._proposal_snapshot(self.selected_proposal),
                },
            )
            
            # Clear note input
            self.org_note_input.clear()
            
            # Reload proposals
            self.org_load_proposals()
            
        except Exception as e:
            self.status.error(f"Reject failed: {e}")
            self.results_browser.setPlainText(f"Error: {e}")

    def org_edit_approve_selected(self):
        """Refine and approve the currently selected proposal."""
        pid = self._selected_proposal_id()
        if pid is None:
            self.status.info("Please select a proposal first")
            return
        
        try:
            self.status.info(f"Refining and approving proposal #{pid}...")
            
            payload = {
                "proposed_folder": self._folder_value(),
                "proposed_filename": self.org_filename_input.text(),
                "note": self.org_note_input.toPlainText() or None,
            }
            
            out = api_client.post(
                f"/organization/proposals/{pid}/edit",
                json=payload,
                timeout=60.0,
            )
            
            self.results_browser.setPlainText(str(out))
            self.status.success(f"Proposal #{pid} refined and approved")
            self._audit(
                "edit_approve_proposal",
                {
                    "action": "edit_approve",
                    "outcome": "success",
                    "proposal_id": pid,
                    "current_path": (self.selected_proposal or {}).get("current_path"),
                    "recommended_folder": (self.selected_proposal or {}).get("proposed_folder"),
                    "recommended_filename": (self.selected_proposal or {}).get("proposed_filename"),
                    "final_folder": payload.get("proposed_folder"),
                    "final_filename": payload.get("proposed_filename"),
                    "note": payload.get("note"),
                    "proposed_folder": payload.get("proposed_folder"),
                    "proposed_filename": payload.get("proposed_filename"),
                    "ok": True,
                    "proposal": self._proposal_snapshot(self.selected_proposal),
                },
            )
            
            # Clear note input
            self.org_note_input.clear()
            
            # Reload proposals
            self.org_load_proposals()
            
        except Exception as e:
            self.status.error(f"Refine+Approve failed: {e}")
            self.results_browser.setPlainText(f"Error: {e}")

    # -------------------------------------------------------------------------
    # LLM Provider Management
    # -------------------------------------------------------------------------

    def on_backend_ready(self):
        """Called when backend is ready - load initial data."""
        self.backend_ready = True
        self.llm_status_label.setText("Current: Loading...")
        self.llm_status_label.setStyleSheet("color: #666;")
        self.load_current_llm_provider()
        
        # Auto-load proposals if any exist (non-blocking)
        try:
            QTimer.singleShot(150, self.org_load_proposals_silent)
        except Exception as e:
            print(f"[OrganizationTab] Auto-load proposals failed: {e}")

    def load_current_llm_provider(self):
        """Load and display the current LLM provider."""
        if not self.backend_ready:
            self.llm_status_label.setText("Current: Waiting for backend...")
            self.llm_status_label.setStyleSheet("color: orange;")
            return
            
        try:
            print("[OrganizationTab] Loading current LLM provider...")
            data = api_client.get("/organization/llm", timeout=10.0)
            
            # API returns nested structure: {"active": {...}, "configured": {...}}
            active = data.get("active", {})
            config_map = data.get("configured", {})
            
            current_provider = active.get("provider", "unknown")
            current_model = active.get("model", "N/A")
            
            # Check if current provider is configured in the map
            # config_map might be boolean (old) or dict (new), handle both safely
            if isinstance(config_map, dict):
                configured = config_map.get(current_provider, False)
            else:
                configured = bool(config_map)
            
            # Update status label
            print(f"[OrganizationTab] LLM Config: configured={configured}, provider={current_provider}, model={current_model}")
            if configured:
                self.llm_status_label.setText(f"Current: {current_provider} ({current_model})")
                self.llm_status_label.setStyleSheet("color: green;")
            else:
                self.llm_status_label.setText(f"Current: {current_provider} (NOT CONFIGURED)")
                self.llm_status_label.setStyleSheet("color: red;")
            
            # Set combo box to current provider
            index = self.llm_provider_combo.findText(current_provider, Qt.MatchFixedString)
            if index >= 0:
                self.llm_provider_combo.setCurrentIndex(index)
            
            self.status.info(f"LLM Provider: {current_provider}")
            
        except Exception as e:
            self.llm_status_label.setText("Current: Error loading")
            self.llm_status_label.setStyleSheet("color: red;")
            print(f"[OrganizationTab] Failed to load LLM provider: {e}")
            self.status.error(f"Failed to load LLM provider: {e}")

    def switch_llm_provider(self):
        """Switch to the selected LLM provider."""
        try:
            selected_provider = self.llm_provider_combo.currentText()
            self.status.info(f"Switching to {selected_provider}...")
            
            payload = {"provider": selected_provider}
            data = api_client.post("/organization/llm/switch", json=payload, timeout=15.0)
            
            success = data.get("success", False)
            message = data.get("message", "")
            
            if success:
                self.status.success(f"Switched to {selected_provider}")
                # Reload current provider status
                self.load_current_llm_provider()
            else:
                self.status.error(f"Switch failed: {message}")
                QMessageBox.warning(
                    self,
                    "LLM Provider Switch Failed",
                    f"Could not switch to {selected_provider}.\n\n{message}"
                )
            
        except Exception as e:
            print(f"[OrganizationTab] Switch provider failed: {e}")
            self.status.error(f"Switch provider failed: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to switch LLM provider:\n{e}"
            )

    def show_stats(self):
        """Display organization statistics."""
        try:
            self.status.info("Loading statistics...")
            data = api_client.get("/organization/stats", timeout=30.0)
            
            # Format statistics
            stats_text = "Organization Statistics:\n\n"
            for key, value in data.items():
                # Format key (convert snake_case to Title Case)
                formatted_key = key.replace("_", " ").title()
                stats_text += f"{formatted_key}: {value}\n"
            
            # Show in message box
            QMessageBox.information(
                self,
                "Organization Statistics",
                stats_text
            )
            self.status.success("Statistics loaded")
            
        except Exception as e:
            self.status.error(f"Failed to load statistics: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load organization statistics:\n{e}"
            )

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def select_all_proposals(self):
        """Check all proposal checkboxes."""
        count = 0
        self.org_table.clearSelection()
        for row in range(self.org_table.rowCount()):
            checkbox = self.org_table.cellWidget(row, 0)
            if checkbox and isinstance(checkbox, QCheckBox):
                checkbox.setChecked(True)
                count += 1
            self.org_table.selectRow(row)
        
        self.status.info(f"Selected {count} proposals")
        
        # Enable bulk operation buttons
        self.bulk_approve_btn.setEnabled(count > 0)
        self.bulk_reject_btn.setEnabled(count > 0)

    def select_none_proposals(self):
        """Uncheck all proposal checkboxes."""
        for row in range(self.org_table.rowCount()):
            checkbox = self.org_table.cellWidget(row, 0)
            if checkbox and isinstance(checkbox, QCheckBox):
                checkbox.setChecked(False)
        self.org_table.clearSelection()
        
        self.status.info("Selection cleared")
        
        # Disable bulk operation buttons
        self.bulk_approve_btn.setEnabled(False)
        self.bulk_reject_btn.setEnabled(False)

    def bulk_approve_proposals(self):
        """Approve all selected proposals (via checkboxes)."""
        checked_rows = self._checked_or_selected_rows()
        
        if not checked_rows:
            self.status.info("No proposals selected (check boxes to select)")
            return
        
        # Confirm bulk action
        reply = QMessageBox.question(
            self,
            "Confirm Bulk Approve",
            f"Approve {len(checked_rows)} selected proposals?\n\nThis action will move files to their proposed locations.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            self.status.info(f"Bulk approving {len(checked_rows)} proposals...")
            
            success_count = 0
            fail_count = 0
            errors = []
            
            for row in checked_rows:
                if row >= len(self.proposals_cache):
                    continue
                
                p = self.proposals_cache[row]
                pid = p.get("id")
                
                try:
                    api_client.post(
                        f"/organization/proposals/{pid}/approve",
                        {},
                        timeout=30.0
                    )
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    errors.append(f"Proposal #{pid}: {e}")
            
            # Show results
            result_msg = f"Approved: {success_count}, Failed: {fail_count}"
            
            if errors:
                error_details = "\n".join(errors[:5])  # Show first 5 errors
                if len(errors) > 5:
                    error_details += f"\n... and {len(errors) - 5} more errors"
                
                QMessageBox.warning(
                    self,
                    "Bulk Approve Complete",
                    f"{result_msg}\n\nErrors:\n{error_details}"
                )
            else:
                QMessageBox.information(
                    self,
                    "Bulk Approve Complete",
                    result_msg
                )
            
            self.status.success(result_msg)
            
            # Reload proposals
            self.org_load_proposals()
            
        except Exception as e:
            self.status.error(f"Bulk approve failed: {e}")
            QMessageBox.critical(self, "Error", f"Bulk approve failed:\n{e}")

    def bulk_reject_proposals(self):
        """Reject all selected proposals (via checkboxes)."""
        checked_rows = self._checked_or_selected_rows()
        
        if not checked_rows:
            self.status.info("No proposals selected (check boxes to select)")
            return
        
        # Confirm bulk action
        reply = QMessageBox.question(
            self,
            "Confirm Bulk Reject",
            f"Reject {len(checked_rows)} selected proposals?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            self.status.info(f"Bulk rejecting {len(checked_rows)} proposals...")
            
            success_count = 0
            fail_count = 0
            errors = []
            
            note = self.org_note_input.toPlainText() or "Bulk reject"
            
            for row in checked_rows:
                if row >= len(self.proposals_cache):
                    continue
                
                p = self.proposals_cache[row]
                pid = p.get("id")
                
                try:
                    api_client.post(
                        f"/organization/proposals/{pid}/reject",
                        {"note": note},
                        timeout=30.0
                    )
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    errors.append(f"Proposal #{pid}: {e}")
            
            # Show results
            result_msg = f"Rejected: {success_count}, Failed: {fail_count}"
            
            if errors:
                error_details = "\n".join(errors[:5])
                if len(errors) > 5:
                    error_details += f"\n... and {len(errors) - 5} more errors"
                
                QMessageBox.warning(
                    self,
                    "Bulk Reject Complete",
                    f"{result_msg}\n\nErrors:\n{error_details}"
                )
            else:
                QMessageBox.information(
                    self,
                    "Bulk Reject Complete",
                    result_msg
                )
            
            self.status.success(result_msg)
            
            # Clear note input
            self.org_note_input.clear()
            
            # Reload proposals
            self.org_load_proposals()
            
        except Exception as e:
            self.status.error(f"Bulk reject failed: {e}")
            QMessageBox.critical(self, "Error", f"Bulk reject failed:\n{e}")

    def export_proposals(self):
        """Export proposals to JSON or CSV file."""
        if not self.proposals_cache:
            self.status.info("No proposals to export")
            return
        
        # Ask user for file format
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Proposals",
            "proposals_export.json",
            "JSON Files (*.json);;CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            self.status.info(f"Exporting {len(self.proposals_cache)} proposals...")
            
            if file_path.endswith('.csv'):
                # Export as CSV
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    if self.proposals_cache:
                        fieldnames = list(self.proposals_cache[0].keys())
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(self.proposals_cache)
            else:
                # Export as JSON
                import json
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.proposals_cache, f, indent=2, ensure_ascii=False)
            
            self.status.success(f"Exported {len(self.proposals_cache)} proposals to {file_path}")
            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {len(self.proposals_cache)} proposals to:\n{file_path}"
            )
            
        except Exception as e:
            self.status.error(f"Export failed: {e}")
            QMessageBox.critical(self, "Error", f"Export failed:\n{e}")

    # -------------------------------------------------------------------------
    # Inline Editing
    # -------------------------------------------------------------------------

    def handle_table_cell_changed(self, item):
        """Handle inline editing of table cells."""
        if not item:
            return
        
        row = item.row()
        col = item.column()
        
        if row >= len(self.proposals_cache):
            return
        
        p = self.proposals_cache[row]
        pid = p.get("id")
        
        # Only allow editing of folder (col 4) and filename (col 5)
        if col == 4:  # Proposed Folder
            new_folder = item.text()
            p["proposed_folder"] = new_folder
            self.status.info(f"Proposal #{pid} folder updated to: {new_folder}")
            
        elif col == 5:  # Proposed Filename
            new_filename = item.text()
            p["proposed_filename"] = new_filename
            self.status.info(f"Proposal #{pid} filename updated to: {new_filename}")
        
        # Note: Changes are cached locally. User must use "Edit & Approve" to persist
