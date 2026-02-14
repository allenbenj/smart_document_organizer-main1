from typing import Any, Dict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import PySide6.QtWidgets as _QtWidgets  # noqa: F401
    import PySide6.QtCore as _QtCore        # noqa: F401
    import PySide6.QtGui as _QtGui          # noqa: F401

from PySide6.QtWidgets import (  # noqa: E402
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    import requests  # noqa: E402
except Exception:
    requests = None


API_BASE = "http://127.0.0.1:8000/api"


class MemoryAnalyticsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout()

        controls = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh Analytics")
        self.refresh_btn.clicked.connect(self.refresh)
        controls.addWidget(self.refresh_btn)
        layout.addLayout(controls)

        # Summary labels
        self.total_lbl = QLabel("Total proposals: 0")
        self.flags_lbl = QLabel("Flags: {}")
        layout.addWidget(self.total_lbl)
        layout.addWidget(self.flags_lbl)

        # Status breakdown
        self.status_tbl = QTableWidget(0, 2)
        self.status_tbl.setHorizontalHeaderLabels(["Status", "Count"])
        layout.addWidget(self.status_tbl)

        self.setLayout(layout)

    def _get(self, path: str) -> Dict[str, Any]:
        if requests is None:
            return {}
        r = requests.get(API_BASE + path, timeout=5)
        r.raise_for_status()
        return r.json()

    def refresh(self):
        try:
            stats = self._get("/agents/memory/stats")
            flags = self._get("/agents/memory/flags")
            total = int(stats.get("proposals_total") or stats.get("total") or 0)
            self.total_lbl.setText(f"Total proposals: {total}")
            self.flags_lbl.setText(f"Flags: {flags.get('flags', {})}")
            by_status = stats.get("by_status", {})
            rows = len(by_status)
            self.status_tbl.setRowCount(rows)
            for i, (k, v) in enumerate(by_status.items()):
                self.status_tbl.setItem(i, 0, QTableWidgetItem(str(k)))
                self.status_tbl.setItem(i, 1, QTableWidgetItem(str(v)))
        except Exception:
            # Best-effort display
            self.total_lbl.setText("Total proposals: (unavailable)")
            self.flags_lbl.setText("Flags: (unavailable)")
            self.status_tbl.setRowCount(0)
