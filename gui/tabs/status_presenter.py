"""Shared non-blocking status presenter for GUI tabs."""

from __future__ import annotations


try:
    from ..ui import log_run_event
except Exception:  # pragma: no cover
    def log_run_event(level: str, message: str, source: str = "GUI") -> None:
        return

try:
    from PySide6.QtWidgets import QLabel, QMessageBox, QWidget
except ImportError:  # pragma: no cover
    QLabel = object  # type: ignore
    QMessageBox = object  # type: ignore
    QWidget = object  # type: ignore


class TabStatusPresenter:
    """Small helper to standardize loading/success/error presentation in tabs.

    Uses an inline QLabel for non-blocking feedback. Optional modal dialog can
    still be shown when explicitly requested.
    """

    def __init__(self, parent: QWidget, label: QLabel, source: str = "Tab"):
        self.parent = parent
        self.label = label
        self.source = source

    def info(self, message: str) -> None:
        self._set(message, "#555")
        log_run_event("info", message, self.source)

    def loading(self, message: str = "Working...") -> None:
        self._set(message, "#1e88e5")
        log_run_event("info", message, self.source)

    def success(self, message: str) -> None:
        self._set(message, "#2e7d32")
        log_run_event("success", message, self.source)

    def error(self, message: str, *, title: str = "Error", modal: bool = False) -> None:
        self._set(message, "#c62828")
        log_run_event("error", message, self.source)
        if modal and hasattr(QMessageBox, "critical"):
            QMessageBox.critical(self.parent, title, message)

    def warn(self, message: str, *, title: str = "Warning", modal: bool = False) -> None:
        self._set(message, "#ef6c00")
        log_run_event("warn", message, self.source)
        if modal and hasattr(QMessageBox, "warning"):
            QMessageBox.warning(self.parent, title, message)

    def _set(self, message: str, color: str) -> None:
        if not self.label:
            return
        self.label.setText(message)
        self.label.setStyleSheet(f"color: {color}; font-style: italic;")
