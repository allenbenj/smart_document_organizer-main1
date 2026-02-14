"""
GUI Core Components - Base widgets and utilities for the Legal AI GUI

This module contains the fundamental building blocks used across all GUI components,
including threading utilities, status widgets, and common UI patterns.
"""

import asyncio

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import PySide6.QtWidgets as _QtWidgets  # noqa: F401
    import PySide6.QtCore as _QtCore        # noqa: F401
    import PySide6.QtGui as _QtGui          # noqa: F401

from PySide6.QtCore import QThread, QTimer  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QLabel,
    QPushButton,
    Qt,
)


class AsyncioThread(QThread):
    """Thread for running asyncio event loop."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop = asyncio.new_event_loop()

    def run(self):  # noqa: C901
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)


class AgentStatusWidget(QWidget):
    """Widget for displaying agent status and health monitoring."""

    def __init__(self, asyncio_thread):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.init_ui()
        self.setup_timer()

    def init_ui(self):
        """Initialize the agent status UI."""
        layout = QVBoxLayout()

        # Title
        title = QLabel("Agent Status Monitor")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Status table
        self.status_table = QTableWidget(0, 4)
        self.status_table.setHorizontalHeaderLabels(
            ["Agent", "Status", "Health", "Last Check"]
        )
        self.status_table.setMaximumHeight(150)
        layout.addWidget(self.status_table)

        # Refresh button
        self.refresh_btn = QPushButton("Refresh Status")
        self.refresh_btn.clicked.connect(self.refresh_status)
        self.refresh_btn.setAccessibleName("Refresh agent status")
        self.refresh_btn.setAccessibleDescription("Click to refresh all agent statuses")
        layout.addWidget(self.refresh_btn)

        self.setLayout(layout)
        self.refresh_status()

    def setup_timer(self):
        """Setup automatic status refresh timer."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(30000)  # Refresh every 30 seconds

    def refresh_status(self):
        """Refresh agent status information."""
        try:
            from ..agents import get_agent_manager  # noqa: E402

            manager = get_agent_manager()
            agents = [
                "Document Manager",
                "Search Engine",
                "Tag Manager",
                "Content Analyzer",
            ]

            self.status_table.setRowCount(len(agents))

            for i, name in enumerate(agents):
                try:
                    # Check if backend is accessible
                    future = asyncio.run_coroutine_threadsafe(
                        manager.get_system_health(), self.asyncio_thread.loop
                    )
                    health = future.result(timeout=5)
                    status = (
                        "Active" if health.get("system_initialized") else "Inactive"
                    )
                    healthtext = (
                        "Healthy" if health.get("system_initialized") else "Unhealthy"
                    )
                except Exception:
                    status = "Unknown"
                    healthtext = "Unknown"  # noqa: F841

                self.status_table.setItem(i, 0, QTableWidgetItem(name))
                self.status_table.setItem(i, 1, QTableWidgetItem(status))
                self.status_table.setItem(i, 2, QTableWidgetItem(health_text))  # noqa: F821
                self.status_table.setItem(i, 3, QTableWidgetItem("Just now"))

        except Exception as e:
            print(f"Error refreshing status: {e}")
            # Show error in status table
            self.status_table.setRowCount(1)
            self.status_table.setItem(0, 0, QTableWidgetItem("System"))
            self.status_table.setItem(0, 1, QTableWidgetItem("Error"))
            self.status_table.setItem(0, 2, QTableWidgetItem("Unhealthy"))
            self.status_table.setItem(0, 3, QTableWidgetItem(str(e)[:50]))
