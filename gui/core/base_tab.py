"""
BaseTab - A base class for all functional tabs in the GUI.

This class abstracts common boilerplate for UI setup, worker management,
and status reporting to enforce consistency and reduce code duplication.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..core import AsyncioThread
    from ..tabs.status_presenter import TabStatusPresenter

try:
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
    from PySide6.QtCore import QThread
except ImportError:
    QWidget = object  # type: ignore
    QThread = object  # type: ignore

logger = logging.getLogger(__name__)


class BaseTab(QWidget):  # type: ignore
    """
    A base QWidget for all main tabs in the application.

    Provides common infrastructure for:
    - Asynchronous worker management.
    - Standardized UI setup (`setup_ui`, `connect_signals`).
    - A `TabStatusPresenter` for consistent user feedback.
    - A hook for when the backend becomes available (`on_backend_ready`).
    """
    def __init__(
        self,
        tab_name: str,
        asyncio_thread: Optional[AsyncioThread] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.tab_name = tab_name
        self.asyncio_thread = asyncio_thread
        self.worker: Optional[QThread] = None

        # Main layout
        self.main_layout = QVBoxLayout(self)

        # Common status label
        self.status_label = QLabel(f"{self.tab_name} is ready.")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f5f5f5; border-radius: 3px;")
        
        # Late-bind the status presenter to avoid circular dependencies
        try:
            from gui.tabs.status_presenter import TabStatusPresenter
            self.status = TabStatusPresenter(self, self.status_label, source=self.tab_name)
        except ImportError:
            logger.error("Could not import TabStatusPresenter. Status updates will be disabled for %s", self.tab_name)
            self.status = None

        # Subclasses should call these in their __init__
        # self.setup_ui()
        # self.connect_signals()

    def setup_ui(self) -> None:
        """
        Placeholder for UI widget initialization.
        Subclasses must implement this and add their widgets to `self.main_layout`.
        """
        raise NotImplementedError("Subclasses must implement setup_ui")

    def init_ui(self) -> None: # Add this for backward compatibility
        """
        Backward compatibility for init_ui calls.
        Delegates to setup_ui.
        """
        self.setup_ui()

    def connect_signals(self) -> None:
        """
        Placeholder for connecting widget signals to slots.
        Subclasses should implement this.
        """
        pass

    def on_backend_ready(self) -> None:
        """
        Hook called when the main application signals the backend is available.
        Tabs can implement this to fetch initial data.
        """
        if self.status:
            self.status.info("Backend is ready. Tab is functional.")
        logger.debug("%s received on_backend_ready signal.", self.tab_name)

    def start_worker(self, worker: QThread) -> None:
        """
        Starts a new worker thread, ensuring any previous worker is cleaned up.
        Connects a default error handler.
        """
        if self.worker and self.worker.isRunning():
            if self.status:
                self.status.warn("A task is already in progress.")
            return

        self.worker = worker
        # Generic error signal handling
        if hasattr(self.worker, "error_occurred"):
            self.worker.error_occurred.connect(self._handle_worker_error)
        elif hasattr(self.worker, "finished_err"):
            self.worker.finished_err.connect(self._handle_worker_error)

        self.worker.finished.connect(self._cleanup_worker)
        self.worker.start()

    def stop_worker(self) -> None:
        """Requests the current worker to stop."""
        if self.worker and self.worker.isRunning():
            if self.status:
                self.status.info("Requesting task cancellation...")
            self.worker.requestInterruption()
        else:
            if self.status:
                self.status.info("No active task to stop.")

    def _handle_worker_error(self, error_message: str) -> None:
        """Default slot to handle errors emitted from a worker."""
        if self.status:
            self.status.error(f"Task failed: {error_message}", modal=True)
        logger.error("Worker for tab %s failed: %s", self.tab_name, error_message)
        self._cleanup_worker()

    def _cleanup_worker(self) -> None:
        """Cleans up the worker thread after it has finished."""
        if self.worker:
            logger.debug("Cleaning up worker for tab %s", self.tab_name)
            self.worker.deleteLater()
            self.worker = None

    def closeEvent(self, event) -> None:
        """Ensure worker is stopped when the tab is closed."""
        self.stop_worker()
        if self.worker:
            # Wait a moment for the thread to terminate
            self.worker.wait(1000)
        super().closeEvent(event)
