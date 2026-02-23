"""
Heuristic Lifecycle Tab - Tacit knowledge governance

Provides the interface for reviewing, promoting, and managing the lifecycle
of AI heuristics, including dissent tracking and collision detection.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from PySide6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QGroupBox,
        QSplitter,
        QTextEdit,
        QTextBrowser,
        QListWidget,
        QListWidgetItem,
        QTableWidget,
        QTableWidgetItem,
        QAbstractItemView,
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont, QColor
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore

from .status_presenter import TabStatusPresenter
from ..services import api_client

logger = logging.getLogger(__name__)

class HeuristicLifecycleTab(QWidget):  # type: ignore[misc]
    """
    Tab for heuristic promotion and governance.
    Fulfills AEDIS Phase 5 'GUI-Integrated' mandate.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_snapshot = {}
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Heuristic Lifecycle & Governance")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "Manage the promotion of candidate patterns into versioned institutional capital. "
            "Detect expert dissent and resolve heuristic collisions."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; padding: 5px 0;")
        layout.addWidget(desc)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left panel - Candidate Queue
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        candidate_group = QGroupBox("Candidate Heuristics")
        candidate_layout = QVBoxLayout(candidate_group)
        
        self.candidate_table = QTableWidget(0, 4)
        self.candidate_table.setHorizontalHeaderLabels(["ID", "Stage", "Evidence", "Success %"])
        self.candidate_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.candidate_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.candidate_table.setAlternatingRowColors(True)
        candidate_layout.addWidget(self.candidate_table)

        self.refresh_button = QPushButton("🔄 Refresh Queue")
        self.refresh_button.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        candidate_layout.addWidget(self.refresh_button)

        left_layout.addWidget(candidate_group)

        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f5f5f5; border-radius: 3px;")
        left_layout.addWidget(self.status_label)
        self.status = TabStatusPresenter(self, self.status_label, source="Heuristics")

        splitter.addWidget(left_widget)

        # Right panel - Review & Action
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Details Group
        details_group = QGroupBox("Heuristic Details & Collision Detection")
        details_layout = QVBoxLayout(details_group)
        
        details_layout.addWidget(QLabel("Rule Text:"))
        self.rule_browser = QTextBrowser()
        self.rule_browser.setMaximumHeight(150)
        self.rule_browser.setFont(QFont("Courier New", 10))
        details_layout.addWidget(self.rule_browser)

        self.collision_button = QPushButton("🔍 Check for Collisions (Dissent)")
        details_layout.addWidget(self.collision_button)

        self.collision_browser = QTextBrowser()
        self.collision_browser.setPlaceholderText("No collisions detected yet...")
        details_layout.addWidget(QLabel("Detected Dissent/Conflicts:"))
        details_layout.addWidget(self.collision_browser)

        # Action Buttons
        action_row = QHBoxLayout()
        self.promote_button = QPushButton("✓ Promote to Active")
        self.promote_button.setEnabled(False)
        self.promote_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        
        self.deprecate_button = QPushButton("✗ Deprecate")
        self.deprecate_button.setEnabled(False)
        self.deprecate_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 10px;")
        
        action_row.addWidget(self.promote_button)
        action_row.addWidget(self.deprecate_button)
        details_layout.addLayout(action_row)

        right_layout.addWidget(details_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([450, 450])

    def connect_signals(self):
        """Connect UI signals."""
        self.refresh_button.clicked.connect(self.load_snapshot)
        self.candidate_table.itemSelectionChanged.connect(self.on_candidate_selected)
        self.collision_button.clicked.connect(self.check_collisions)
        self.promote_button.clicked.connect(self.promote_selected)
        self.deprecate_button.clicked.connect(self.deprecate_selected)

    def load_snapshot(self):
        """Load the heuristic governance snapshot."""
        self.status.loading("Refreshing heuristic queue...")
        try:
            res = api_client.get_heuristic_governance_snapshot()
            items = res.get("items", [])
            self.current_snapshot = {i["heuristic_id"]: i for i in items}
            
            self.candidate_table.setRowCount(len(items))
            for idx, item in enumerate(items):
                self.candidate_table.setItem(idx, 0, QTableWidgetItem(item["heuristic_id"]))
                self.candidate_table.setItem(idx, 1, QTableWidgetItem(item["stage"]))
                self.candidate_table.setItem(idx, 2, QTableWidgetItem(str(item["evidence_count"])))
                self.candidate_table.setItem(idx, 3, QTableWidgetItem(f"{item['success_rate']:.2%}"))
            
            self.status.success(f"Loaded {len(items)} items")
        except Exception as e:
            self.status.error(f"Failed to load snapshot: {e}")

    def on_candidate_selected(self):
        """Handle candidate selection."""
        selected_items = self.candidate_table.selectedItems()
        if not selected_items:
            self.promote_button.setEnabled(False)
            self.deprecate_button.setEnabled(False)
            return

        h_id = selected_items[0].text()
        item = self.current_snapshot.get(h_id, {})
        
        self.rule_browser.setPlainText(f"ID: {h_id}
Stage: {item.get('stage')}

Rule logic placeholder...")
        self.promote_button.setEnabled(item.get("stage") in ["promoted", "qualified"])
        self.deprecate_button.setEnabled(True)

    def check_collisions(self):
        """Check for collisions for the selected heuristic."""
        selected_items = self.candidate_table.selectedItems()
        if not selected_items: return
        
        h_id = selected_items[0].text()
        self.status.loading(f"Checking collisions for {h_id}...")
        try:
            res = api_client.detect_heuristic_collisions(h_id)
            collisions = res.get("collisions", [])
            if not collisions:
                self.collision_browser.setHtml("<p style='color: green;'>✓ No collisions detected with existing experts.</p>")
            else:
                html = "<h3>Warning: Expert Dissent Detected</h3><ul>"
                for c in collisions:
                    html += f"<li>Conflicts with <b>{c['conflicts_with']}</b> (Overlap: {', '.join(c['overlap_terms'])})</li>"
                html += "</ul>"
                self.collision_browser.setHtml(html)
            self.status.success("Collision check complete")
        except Exception as e:
            self.status.error(f"Collision check failed: {e}")

    def promote_selected(self):
        """Promote the selected heuristic."""
        selected_items = self.candidate_table.selectedItems()
        if not selected_items: return
        h_id = selected_items[0].text()
        self.status.loading(f"Promoting {h_id}...")
        try:
            # Note: API call might be promote_heuristic or activate_heuristic depending on final route
            # Using promote for now.
            api_client.promote_heuristic(h_id)
            self.status.success(f"Heuristic {h_id} promoted to ACTIVE")
            self.load_snapshot()
        except Exception as e:
            self.status.error(f"Promotion failed: {e}")

    def deprecate_selected(self):
        """Deprecate the selected heuristic."""
        selected_items = self.candidate_table.selectedItems()
        if not selected_items: return
        h_id = selected_items[0].text()
        self.status.loading(f"Deprecating {h_id}...")
        # Implementation would follow promote_selected
        self.status.warn("Deprecation logic not yet wired to API")
