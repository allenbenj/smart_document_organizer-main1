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
from typing import Optional



from ..services import api_client

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
    from PySide6.QtCore import Qt
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
        self.proposals_cache = []
        self.selected_proposal = None
        self.backend_ready = False
        self.setup_ui()
        self.connect_signals()
        # Defer backend calls until backend is ready
        # self.load_current_llm_provider() - moved to on_backend_ready()

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
        self.llm_provider_combo.addItems(["xai", "deepseek", "local"])
        self.llm_provider_combo.setToolTip("Switch between XAI, DeepSeek, or Local (Heuristic) for organization proposals")
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
        
        action_btn_row.addWidget(self.org_load_button)
        action_btn_row.addWidget(self.org_generate_button)
        action_btn_row.addWidget(self.org_clear_button)
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

        self.org_table = QTableWidget(0, 6)
        self.org_table.setHorizontalHeaderLabels([
            "☑", "ID", "Confidence", "Current Path", "Proposed Folder", "Proposed Filename"
        ])
        self.org_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.org_table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.org_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        header = self.org_table.horizontalHeader()
        header.setStretchLastSection(True)
        
        proposals_layout.addWidget(self.org_table)
        layout.addWidget(proposals_group)

        # Refinement group
        refine_group = QGroupBox("Refine Selected Proposal")
        refine_layout = QVBoxLayout(refine_group)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Folder:"))
        self.org_folder_input = QLineEdit()
        self.org_folder_input.setPlaceholderText("Proposed folder path...")
        path_row.addWidget(self.org_folder_input, 3)
        
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
        
        # Table controls
        self.select_all_btn.clicked.connect(self.select_all_proposals)
        self.select_none_btn.clicked.connect(self.select_none_proposals)
        self.bulk_approve_btn.clicked.connect(self.bulk_approve_proposals)
        self.bulk_reject_btn.clicked.connect(self.bulk_reject_proposals)
        self.export_proposals_btn.clicked.connect(self.export_proposals)
        self.org_table.itemSelectionChanged.connect(self.org_on_selection_changed)
        self.org_table.itemChanged.connect(self.handle_table_cell_changed)
        
        # Proposal actions
        self.org_approve_button.clicked.connect(self.org_approve_selected)
        self.org_reject_button.clicked.connect(self.org_reject_selected)
        self.org_edit_approve_button.clicked.connect(self.org_edit_approve_selected)

    # -------------------------------------------------------------------------
    # Organization Workflow Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_root_scope(path_str: str) -> str:
        """Normalize folder path for consistent API usage."""
        p = path_str.strip()
        if not p:
            return ""
        # Convert Windows paths to WSL format
        p = p.replace("\\", "/")
        return p



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
        try:
            self.status.info("Loading proposals...")
            root = self._normalize_root_scope(self.org_root_input.text())
            
            # Fetch proposals from API
            data = api_client.get(
                "/organization/proposals?status=proposed&limit=1000&offset=0", 
                timeout=30.0
            )
            
            items = data.get("items", []) if isinstance(data, dict) else []
            
            # Filter by root scope if specified
            if root:
                items = [
                    x for x in items 
                    if str(x.get("current_path") or "").replace("\\", "/").startswith(root)
                ]
            
            self.proposals_cache = items
            
            # Populate table (6 columns: checkbox, ID, confidence, current path, folder, filename)
            self.org_table.setRowCount(len(items))
            for i, p in enumerate(items):
                # Column 0: Checkbox for bulk selection
                checkbox = QCheckBox()
                checkbox.setStyleSheet("margin-left:50%; margin-right:50%;")
                self.org_table.setCellWidget(i, 0, checkbox)
                
                # Column 1: ID
                self.org_table.setItem(i, 1, QTableWidgetItem(str(p.get("id") or "")))
                
                # Column 2: Confidence
                confidence = float(p.get('confidence') or 0.0)
                conf_item = QTableWidgetItem(f"{confidence:.2f}")
                self.org_table.setItem(i, 2, conf_item)
                
                # Column 3: Current Path
                self.org_table.setItem(i, 3, QTableWidgetItem(str(p.get("current_path") or "")))
                
                # Column 4: Proposed Folder (editable)
                folder_item = QTableWidgetItem(str(p.get("proposed_folder") or ""))
                self.org_table.setItem(i, 4, folder_item)
                
                # Column 5: Proposed Filename (editable)
                filename_item = QTableWidgetItem(str(p.get("proposed_filename") or ""))
                self.org_table.setItem(i, 5, filename_item)
            
            # Auto-resize columns
            self.org_table.resizeColumnsToContents()
            
            self.results_browser.setPlainText(f"✓ Loaded {len(items)} proposals")
            self.status.success(f"Loaded {len(items)} proposals")
            
        except Exception as e:
            self.status.error(f"Failed to load proposals: {e}")
            self.results_browser.setPlainText(f"Error: {e}")

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
            # Silent failure - don't alert user on startup
            print(f"[OrganizationTab] Silent load failed: {e}")

    def org_generate_scoped(self):
        """Generate new organization proposals for the scoped folder."""
        try:
            self.status.info("Generating proposals (this may take 1-2 minutes)...")
            root = self._normalize_root_scope(self.org_root_input.text())
            
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
            
            # Automatically reload proposals
            self.org_load_proposals()
            
        except Exception as e:
            self.status.error(f"Failed to generate proposals: {e}")
            self.results_browser.setPlainText(f"Error: {e}")

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
            
            # Reload to show updated state
            self.org_load_proposals()
            
        except Exception as e:
            self.status.error(f"Failed to clear proposals: {e}")
            self.results_browser.setPlainText(f"Error: {e}")

    def org_on_selection_changed(self):
        """Handle proposal selection in table - populate refinement inputs."""
        row = self.org_table.currentRow()
        if row < 0 or row >= len(self.proposals_cache):
            self.selected_proposal = None
            self.org_folder_input.clear()
            self.org_filename_input.clear()
            return
        
        p = self.proposals_cache[row]
        self.selected_proposal = p
        
        self.org_folder_input.setText(str(p.get("proposed_folder") or ""))
        self.org_filename_input.setText(str(p.get("proposed_filename") or ""))
        
        # Update status with selection info
        pid = p.get("id", "?")
        self.status.info(f"Selected proposal #{pid}")

    def _selected_proposal_id(self) -> Optional[int]:
        """Get the ID of the currently selected proposal."""
        if not self.selected_proposal:
            return None
        try:
            return int(self.selected_proposal.get("id"))
        except Exception:
            return None

    def org_approve_selected(self):
        """Approve the currently selected proposal."""
        pid = self._selected_proposal_id()
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
            
            # Reload proposals to show updated state
            self.org_load_proposals()
            
        except Exception as e:
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
                "proposed_folder": self.org_folder_input.text(),
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
            self.org_load_proposals_silent()
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
        for row in range(self.org_table.rowCount()):
            checkbox = self.org_table.cellWidget(row, 0)
            if checkbox and isinstance(checkbox, QCheckBox):
                checkbox.setChecked(True)
                count += 1
        
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
        
        self.status.info("Selection cleared")
        
        # Disable bulk operation buttons
        self.bulk_approve_btn.setEnabled(False)
        self.bulk_reject_btn.setEnabled(False)

    def bulk_approve_proposals(self):
        """Approve all selected proposals (via checkboxes)."""
        # Find checked rows
        checked_rows = []
        for row in range(self.org_table.rowCount()):
            checkbox = self.org_table.cellWidget(row, 0)
            if checkbox and isinstance(checkbox, QCheckBox) and checkbox.isChecked():
                checked_rows.append(row)
        
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
        # Find checked rows
        checked_rows = []
        for row in range(self.org_table.rowCount()):
            checkbox = self.org_table.cellWidget(row, 0)
            if checkbox and isinstance(checkbox, QCheckBox) and checkbox.isChecked():
                checked_rows.append(row)
        
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
