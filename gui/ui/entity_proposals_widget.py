"""
Entity Proposals Widget - Human-in-the-loop entity review system

Provides UI for reviewing and approving entity extraction proposals:
- Display extracted entities as proposals
- Individual approve/reject actions
- Bulk approve/reject
- Confidence score display
- Edit before approval
- Memory integration for approved entities
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from PySide6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QHeaderView,
        QGroupBox,
        QCheckBox,
        QLineEdit,
        QTextEdit,
        QComboBox,
        QMessageBox,
        QFrame,
        QSpinBox,
        QDoubleSpinBox,
    )
    from PySide6.QtCore import Qt, Signal, Slot
    from PySide6.QtGui import QFont, QColor, QBrush
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = Any = object  # type: ignore


class EntityProposal:
    """
    Represents an entity extraction proposal awaiting approval.
    """
    
    def __init__(
        self,
        entity_type: str,
        entity_text: str,
        confidence: float,
        context: str = "",
        source_document: str = "",
        attributes: Optional[Dict[str, Any]] = None,
        proposal_id: Optional[str] = None,
    ):
        self.proposal_id = proposal_id or f"{entity_type}_{entity_text}_{datetime.now().timestamp()}"
        self.entity_type = entity_type
        self.entity_text = entity_text
        self.confidence = confidence
        self.context = context
        self.source_document = source_document
        self.attributes = attributes or {}
        self.status = "pending"  # pending, approved, rejected
        self.created_at = datetime.now()
        self.reviewed_at: Optional[datetime] = None
        self.reviewer_notes: str = ""
    
    def approve(self, notes: str = ""):
        """Mark proposal as approved."""
        self.status = "approved"
        self.reviewed_at = datetime.now()
        self.reviewer_notes = notes
    
    def reject(self, notes: str = ""):
        """Mark proposal as rejected."""
        self.status = "rejected"
        self.reviewed_at = datetime.now()
        self.reviewer_notes = notes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "proposal_id": self.proposal_id,
            "entity_type": self.entity_type,
            "entity_text": self.entity_text,
            "confidence": self.confidence,
            "context": self.context,
            "source_document": self.source_document,
            "attributes": self.attributes,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewer_notes": self.reviewer_notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EntityProposal":
        """Create from dictionary."""
        proposal = cls(
            entity_type=data["entity_type"],
            entity_text=data["entity_text"],
            confidence=data["confidence"],
            context=data.get("context", ""),
            source_document=data.get("source_document", ""),
            attributes=data.get("attributes", {}),
            proposal_id=data.get("proposal_id"),
        )
        proposal.status = data.get("status", "pending")
        proposal.reviewer_notes = data.get("reviewer_notes", "")
        return proposal


class EntityProposalsWidget(QWidget):  # type: ignore[misc]
    """
    Widget for reviewing entity extraction proposals.
    
    Features:
    - Table view of pending proposals
    - Individual approve/reject buttons
    - Bulk operations (approve all high confidence, reject all low confidence)
    - Edit entity text/type before approval
    - Filter by confidence threshold
    - Export approved/rejected entities
    """
    
    # Signals
    proposal_approved = Signal(object)  # type: ignore[misc] - EntityProposal
    proposal_rejected = Signal(object)  # type: ignore[misc] - EntityProposal
    proposals_cleared = Signal()  # type: ignore[misc]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.proposals: List[EntityProposal] = []
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("Entity Proposals Review")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Confidence filter
        header_layout.addWidget(QLabel("Min Confidence:"))
        self.confidence_filter = QDoubleSpinBox()
        self.confidence_filter.setRange(0.0, 1.0)
        self.confidence_filter.setSingleStep(0.05)
        self.confidence_filter.setValue(0.5)
        self.confidence_filter.setPrefix("")
        self.confidence_filter.valueChanged.connect(self.filter_proposals)
        header_layout.addWidget(self.confidence_filter)
        
        # Status filter
        header_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Pending", "Approved", "Rejected", "All"])
        self.status_filter.currentTextChanged.connect(self.filter_proposals)
        header_layout.addWidget(self.status_filter)
        
        layout.addLayout(header_layout)
        
        # Statistics bar
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.StyledPanel)
        stats_frame.setStyleSheet("background-color: #f5f5f5; padding: 5px;")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(10, 5, 10, 5)
        
        self.stats_label = QLabel("Proposals: 0 | Pending: 0 | Approved: 0 | Rejected: 0")
        self.stats_label.setFont(QFont("Arial", 10))
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_frame)
        
        # Proposals table
        self.proposals_table = QTableWidget()
        self.proposals_table.setColumnCount(7)
        self.proposals_table.setHorizontalHeaderLabels([
            "Select", "Type", "Text", "Confidence", "Source", "Context", "Actions"
        ])
        
        header = self.proposals_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Select
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(2, QHeaderView.Stretch)           # Text
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Confidence
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Source
        header.setSectionResizeMode(5, QHeaderView.Stretch)           # Context
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Actions
        
        self.proposals_table.setAlternatingRowColors(True)
        self.proposals_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.proposals_table)
        
        # Bulk actions bar
        actions_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("✓ Select All")
        self.select_all_btn.clicked.connect(self.select_all_proposals)
        actions_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("✗ Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all_proposals)
        actions_layout.addWidget(self.deselect_all_btn)
        
        actions_layout.addWidget(QLabel("|"))
        
        self.approve_selected_btn = QPushButton("✅ Approve Selected")
        self.approve_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.approve_selected_btn.clicked.connect(self.approve_selected)
        actions_layout.addWidget(self.approve_selected_btn)
        
        self.reject_selected_btn = QPushButton("❌ Reject Selected")
        self.reject_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.reject_selected_btn.clicked.connect(self.reject_selected)
        actions_layout.addWidget(self.reject_selected_btn)
        
        actions_layout.addStretch()
        
        self.clear_approved_btn = QPushButton("🗑️ Clear Approved")
        self.clear_approved_btn.clicked.connect(self.clear_approved)
        actions_layout.addWidget(self.clear_approved_btn)
        
        self.clear_rejected_btn = QPushButton("🗑️ Clear Rejected")
        self.clear_rejected_btn.clicked.connect(self.clear_rejected)
        actions_layout.addWidget(self.clear_rejected_btn)
        
        layout.addLayout(actions_layout)
    
    def add_proposals(self, proposals: List[EntityProposal]):
        """Add new proposals to the list."""
        self.proposals.extend(proposals)
        self.refresh_table()
    
    def add_proposal(self, proposal: EntityProposal):
        """Add a single proposal."""
        self.proposals.append(proposal)
        self.refresh_table()
    
    def refresh_table(self):
        """Refresh the proposals table."""
        # Get filter criteria
        min_confidence = self.confidence_filter.value()
        status_filter = self.status_filter.currentText().lower()
        
        # Filter proposals
        filtered_proposals = []
        for p in self.proposals:
            if p.confidence < min_confidence:
                continue
            if status_filter != "all" and p.status != status_filter:
                continue
            filtered_proposals.append(p)
        
        # Update table
        self.proposals_table.setRowCount(len(filtered_proposals))
        
        for row, proposal in enumerate(filtered_proposals):
            # Select checkbox
            checkbox = QCheckBox()
            checkbox.setProperty("proposal_id", proposal.proposal_id)
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.proposals_table.setCellWidget(row, 0, checkbox_widget)
            
            # Type
            type_item = QTableWidgetItem(proposal.entity_type)
            self.proposals_table.setItem(row, 1, type_item)
            
            # Text (editable)
            text_item = QTableWidgetItem(proposal.entity_text)
            text_item.setData(Qt.UserRole, proposal.proposal_id)
            self.proposals_table.setItem(row, 2, text_item)
            
            # Confidence
            confidence_item = QTableWidgetItem(f"{proposal.confidence:.2%}")
            confidence_item.setData(Qt.UserRole, proposal.proposal_id)
            
            # Color code by confidence
            if proposal.confidence >= 0.8:
                confidence_item.setBackground(QBrush(QColor("#c8e6c9")))  # Green
            elif proposal.confidence >= 0.5:
                confidence_item.setBackground(QBrush(QColor("#fff9c4")))  # Yellow
            else:
                confidence_item.setBackground(QBrush(QColor("#ffccbc")))  # Orange
            
            self.proposals_table.setItem(row, 3, confidence_item)
            
            # Source
            source_item = QTableWidgetItem(proposal.source_document[:30] + "..." if len(proposal.source_document) > 30 else proposal.source_document)
            source_item.setToolTip(proposal.source_document)
            self.proposals_table.setItem(row, 4, source_item)
            
            # Context
            context_text = proposal.context[:50] + "..." if len(proposal.context) > 50 else proposal.context
            context_item = QTableWidgetItem(context_text)
            context_item.setToolTip(proposal.context)
            self.proposals_table.setItem(row, 5, context_item)
            
            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            
            if proposal.status == "pending":
                approve_btn = QPushButton("✓")
                approve_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 2px 8px;")
                approve_btn.setToolTip("Approve")
                approve_btn.clicked.connect(lambda checked, pid=proposal.proposal_id: self.approve_proposal(pid))
                actions_layout.addWidget(approve_btn)
                
                reject_btn = QPushButton("✗")
                reject_btn.setStyleSheet("background-color: #f44336; color: white; padding: 2px 8px;")
                reject_btn.setToolTip("Reject")
                reject_btn.clicked.connect(lambda checked, pid=proposal.proposal_id: self.reject_proposal(pid))
                actions_layout.addWidget(reject_btn)
            else:
                status_label = QLabel(f"[{proposal.status.upper()}]")
                status_label.setStyleSheet(
                    f"color: {'green' if proposal.status == 'approved' else 'red'}; font-weight: bold;"
                )
                actions_layout.addWidget(status_label)
            
            self.proposals_table.setCellWidget(row, 6, actions_widget)
        
        # Update statistics
        self.update_statistics()
    
    def filter_proposals(self):
        """Filter proposals based on current criteria."""
        self.refresh_table()
    
    def update_statistics(self):
        """Update statistics label."""
        total = len(self.proposals)
        pending = sum(1 for p in self.proposals if p.status == "pending")
        approved = sum(1 for p in self.proposals if p.status == "approved")
        rejected = sum(1 for p in self.proposals if p.status == "rejected")
        
        self.stats_label.setText(
            f"Proposals: {total} | Pending: {pending} | Approved: {approved} | Rejected: {rejected}"
        )
    
    def get_selected_proposal_ids(self) -> List[str]:
        """Get proposal IDs of selected rows."""
        selected_ids = []
        for row in range(self.proposals_table.rowCount()):
            checkbox_widget = self.proposals_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    proposal_id = checkbox.property("proposal_id")
                    selected_ids.append(proposal_id)
        return selected_ids
    
    def select_all_proposals(self):
        """Select all visible proposals."""
        for row in range(self.proposals_table.rowCount()):
            checkbox_widget = self.proposals_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(True)
    
    def deselect_all_proposals(self):
        """Deselect all proposals."""
        for row in range(self.proposals_table.rowCount()):
            checkbox_widget = self.proposals_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(False)
    
    def approve_proposal(self, proposal_id: str):
        """Approve a single proposal."""
        for proposal in self.proposals:
            if proposal.proposal_id == proposal_id:
                proposal.approve()
                self.proposal_approved.emit(proposal)
                break
        self.refresh_table()
    
    def reject_proposal(self, proposal_id: str):
        """Reject a single proposal."""
        for proposal in self.proposals:
            if proposal.proposal_id == proposal_id:
                proposal.reject()
                self.proposal_rejected.emit(proposal)
                break
        self.refresh_table()
    
    def approve_selected(self):
        """Approve all selected proposals."""
        selected_ids = self.get_selected_proposal_ids()
        if not selected_ids:
            QMessageBox.information(self, "No Selection", "Please select proposals to approve.")
            return
        
        count = 0
        for proposal in self.proposals:
            if proposal.proposal_id in selected_ids and proposal.status == "pending":
                proposal.approve()
                self.proposal_approved.emit(proposal)
                count += 1
        
        self.refresh_table()
        QMessageBox.information(self, "Approved", f"Approved {count} proposals.")
    
    def reject_selected(self):
        """Reject all selected proposals."""
        selected_ids = self.get_selected_proposal_ids()
        if not selected_ids:
            QMessageBox.information(self, "No Selection", "Please select proposals to reject.")
            return
        
        count = 0
        for proposal in self.proposals:
            if proposal.proposal_id in selected_ids and proposal.status == "pending":
                proposal.reject()
                self.proposal_rejected.emit(proposal)
                count += 1
        
        self.refresh_table()
        QMessageBox.information(self, "Rejected", f"Rejected {count} proposals.")
    
    def clear_approved(self):
        """Remove approved proposals from the list."""
        reply = QMessageBox.question(
            self,
            "Clear Approved",
            "Remove all approved proposals from the list?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.proposals = [p for p in self.proposals if p.status != "approved"]
            self.refresh_table()
            self.proposals_cleared.emit()
    
    def clear_rejected(self):
        """Remove rejected proposals from the list."""
        reply = QMessageBox.question(
            self,
            "Clear Rejected",
            "Remove all rejected proposals from the list?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.proposals = [p for p in self.proposals if p.status != "rejected"]
            self.refresh_table()
            self.proposals_cleared.emit()
    
    def get_approved_proposals(self) -> List[EntityProposal]:
        """Get list of approved proposals."""
        return [p for p in self.proposals if p.status == "approved"]
    
    def get_rejected_proposals(self) -> List[EntityProposal]:
        """Get list of rejected proposals."""
        return [p for p in self.proposals if p.status == "rejected"]
    
    def get_pending_proposals(self) -> List[EntityProposal]:
        """Get list of pending proposals."""
        return [p for p in self.proposals if p.status == "pending"]
    
    def clear_all(self):
        """Clear all proposals."""
        self.proposals.clear()
        self.refresh_table()
        self.proposals_cleared.emit()


# Example usage
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    widget = EntityProposalsWidget()
    
    # Add sample proposals
    sample_proposals = [
        EntityProposal("Person", "John Smith", 0.95, "John Smith was the plaintiff", "contract_001.pdf"),
        EntityProposal("Organization", "Acme Corp", 0.88, "Acme Corp entered into agreement", "contract_001.pdf"),
        EntityProposal("Date", "January 15, 2024", 0.92, "signed on January 15, 2024", "contract_001.pdf"),
        EntityProposal("Location", "New York", 0.65, "jurisdiction of New York", "contract_001.pdf"),
        EntityProposal("Person", "Jane Doe", 0.45, "mentioned Jane Doe briefly", "contract_002.pdf"),
    ]
    
    widget.add_proposals(sample_proposals)
    widget.show()
    
    sys.exit(app.exec())
