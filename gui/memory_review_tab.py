import json
import sys
from typing import Any, Dict, List  # noqa: E402

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import PySide6.QtWidgets as _QtWidgets  # noqa: F401
    import PySide6.QtCore as _QtCore        # noqa: F401
    import PySide6.QtGui as _QtGui          # noqa: F401

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
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

from gui.services import api_client

class MemoryReviewTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.filtertext = ""
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout()

        controls = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        self.approve_btn = QPushButton("Approve")
        self.approve_btn.clicked.connect(self.approve_selected)
        self.reject_btn = QPushButton("Reject")
        self.reject_btn.clicked.connect(self.reject_selected)
        controls.addWidget(self.refresh_btn)
        controls.addWidget(self.approve_btn)
        controls.addWidget(self.reject_btn)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText(
            "Filter by flag (e.g., sensitive) or status (pending)..."
        )
        self.filter_input.returnPressed.connect(self.refresh)
        controls.addWidget(QLabel("Filter:"))
        controls.addWidget(self.filter_input)

        layout.addLayout(controls)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Namespace", "Key", "Status", "Flags", "Confidence", "Importance"]
        )
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)

        # Detail View
        detail_group = QGroupBox("Proposal Content Detail")
        detail_layout = QVBoxLayout()
        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        detail_layout.addWidget(self.detail_view)
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        self.setLayout(layout)
        self.items: List[Dict[str, Any]] = []

    def on_selection_changed(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.items):
            self.detail_view.clear()
            return
        
        item = self.items[row]
        content = item.get("content", "")
        try:
            # Try to format JSON content nicely
            parsed = json.loads(content)
            formatted = json.dumps(parsed, indent=2)
            self.detail_view.setPlainText(formatted)
        except Exception:
            self.detail_view.setPlainText(content)

    def refresh(self):
        try:
            filt = (self.filter_input.text() or "").strip().lower()
            data = api_client._make_request("GET", "/api/agents/memory/proposals", params={"limit": 50})
            self.items = data.get("proposals", [])
            if filt:
                self.items = [
                    p
                    for p in self.items
                    if filt in ",".join(p.get("flags", [])).lower()
                    or filt in str(p.get("status", "")).lower()
                ]
            self.table.setRowCount(len(self.items))
            for i, p in enumerate(self.items):
                self.table.setItem(i, 0, QTableWidgetItem(str(p.get("id"))))
                self.table.setItem(i, 1, QTableWidgetItem(p.get("namespace", "")))
                self.table.setItem(i, 2, QTableWidgetItem(p.get("key", "")))
                self.table.setItem(i, 3, QTableWidgetItem(p.get("status", "")))
                self.table.setItem(
                    i, 4, QTableWidgetItem(", ".join(p.get("flags", [])))
                )
                self.table.setItem(
                    i, 5, QTableWidgetItem(str(p.get("confidence_score", "")))
                )
                self.table.setItem(
                    i, 6, QTableWidgetItem(str(p.get("importance_score", "")))
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load proposals: {e}")

    def _selected_id(self) -> int:
        row = self.table.currentRow()
        if row < 0:
            return 0
        item = self.table.item(row, 0)
        if not item:
            return 0
        try:
            return int(item.text())
        except Exception:
            return 0

    def approve_selected(self):
        pid = self._selected_id()
        if not pid:
            QMessageBox.information(self, "Approve", "Select a proposal first")
            return
        try:
            api_client._make_request("POST", "/api/agents/memory/proposals/approve", json={"proposal_id": pid})
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Approve failed: {e}")

    def reject_selected(self):
        pid = self._selected_id()
        if not pid:
            QMessageBox.information(self, "Reject", "Select a proposal first")
            return
        try:
            api_client._make_request("POST", "/api/agents/memory/proposals/reject", json={"proposal_id": pid})
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Reject failed: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MemoryReviewTab()
    w.setWindowTitle("Memory Review")
    w.resize(900, 500)
    w.show()
    sys.exit(app.exec())
