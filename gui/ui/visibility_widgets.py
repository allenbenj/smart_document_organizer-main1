"""Shared visibility widgets for GUI operational transparency."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class RunEventBus(QObject):
    event_logged = Signal(str, str, str, str)  # ts, level, source, message


_RUN_EVENT_BUS: Optional[RunEventBus] = None


def get_run_event_bus() -> RunEventBus:
    global _RUN_EVENT_BUS
    if _RUN_EVENT_BUS is None:
        _RUN_EVENT_BUS = RunEventBus()
    return _RUN_EVENT_BUS


def log_run_event(level: str, message: str, source: str = "GUI") -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    get_run_event_bus().event_logged.emit(ts, level.upper(), source, message)


class RunConsolePanel(QGroupBox):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Run Console", parent)
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.clear_btn = QPushButton("Clear")
        self.copy_btn = QPushButton("Copy")
        toolbar.addStretch()
        toolbar.addWidget(self.copy_btn)
        toolbar.addWidget(self.clear_btn)
        layout.addLayout(toolbar)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(140)
        layout.addWidget(self.console)

        self.clear_btn.clicked.connect(self.console.clear)
        self.copy_btn.clicked.connect(self.copy_all)

        get_run_event_bus().event_logged.connect(self.append_event)

    def append_event(self, ts: str, level: str, source: str, message: str) -> None:
        color = {
            "INFO": "#455a64",
            "WARN": "#ef6c00",
            "ERROR": "#c62828",
            "SUCCESS": "#2e7d32",
        }.get(level.upper(), "#37474f")
        self.console.append(
            f"<span style='color:#888;'>[{ts}]</span> "
            f"<b style='color:{color};'>{level}</b> "
            f"<span style='color:#1565c0;'>[{source}]</span> {message}"
        )

    def copy_all(self) -> None:
        QGuiApplication.clipboard().setText(self.console.toPlainText())


@dataclass
class JobStatusModel:
    state: str = "queued"
    detail: str = "Waiting"
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    def elapsed_seconds(self) -> int:
        if self.started_at is None:
            return 0
        end = self.finished_at or datetime.now()
        return max(0, int((end - self.started_at).total_seconds()))


class JobStatusWidget(QFrame):
    def __init__(self, job_name: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.model = JobStatusModel()
        self.job_name = job_name

        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        self.name_label = QLabel(f"{job_name}:")
        self.state_label = QLabel("QUEUED")
        self.detail_label = QLabel("Waiting")
        self.elapsed_label = QLabel("Elapsed: 0s")
        layout.addWidget(self.name_label)
        layout.addWidget(self.state_label)
        layout.addWidget(self.detail_label, 1)
        layout.addWidget(self.elapsed_label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_elapsed)
        self._timer.start(1000)
        self._refresh_style()

    def set_status(self, state: str, detail: str = "") -> None:
        state = (state or "queued").lower()
        self.model.state = state
        if detail:
            self.model.detail = detail
        if state == "running" and self.model.started_at is None:
            self.model.started_at = datetime.now()
            self.model.finished_at = None
        elif state in {"success", "failed"}:
            if self.model.started_at is None:
                self.model.started_at = datetime.now()
            self.model.finished_at = datetime.now()
        self.state_label.setText(state.upper())
        self.detail_label.setText(self.model.detail)
        self._refresh_elapsed()
        self._refresh_style()

    def reset(self, detail: str = "Waiting") -> None:
        self.model = JobStatusModel(state="queued", detail=detail)
        self.state_label.setText("QUEUED")
        self.detail_label.setText(detail)
        self._refresh_elapsed()
        self._refresh_style()

    def _refresh_elapsed(self) -> None:
        self.elapsed_label.setText(f"Elapsed: {self.model.elapsed_seconds()}s")

    def _refresh_style(self) -> None:
        color = {
            "queued": "#616161",
            "running": "#1565c0",
            "success": "#2e7d32",
            "failed": "#c62828",
        }.get(self.model.state, "#616161")
        self.state_label.setStyleSheet(f"font-weight: bold; color: {color};")


class ResultsSummaryBox(QGroupBox):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Results Summary", parent)
        layout = QGridLayout(self)
        layout.addWidget(QLabel("Outcome:"), 0, 0)
        layout.addWidget(QLabel("Output Location:"), 1, 0)
        layout.addWidget(QLabel("Logs:"), 2, 0)
        self.outcome = QLabel("No run yet")
        self.output_path = QLabel("N/A")
        self.logs_path = QLabel("N/A")
        for lbl in (self.outcome, self.output_path, self.logs_path):
            lbl.setWordWrap(True)
        layout.addWidget(self.outcome, 0, 1)
        layout.addWidget(self.output_path, 1, 1)
        layout.addWidget(self.logs_path, 2, 1)

    def set_summary(self, outcome: str, output_location: str, logs_location: str) -> None:
        self.outcome.setText(outcome)
        self.output_path.setText(output_location)
        self.logs_path.setText(logs_location)


class SystemHealthStrip(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        self.backend_label = QLabel("Backend: checking...")
        self.advanced_label = QLabel("Advanced: checking...")
        self.last_check_label = QLabel("Last check: --")
        layout.addWidget(self.backend_label)
        layout.addWidget(self.advanced_label)
        layout.addStretch()
        layout.addWidget(self.last_check_label)

    def update_status(self, backend: str, advanced: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self.backend_label.setText(f"Backend: {backend}")
        self.advanced_label.setText(f"Advanced: {advanced}")
        self.last_check_label.setText(f"Last check: {now}")
