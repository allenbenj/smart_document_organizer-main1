"""
Learning Path Tab - Trace-backed instructional workflow

Provides a GUI workflow for generating and progressing AEDIS learning paths.
"""

from __future__ import annotations

import time
from typing import Optional

try:
    from PySide6.QtWidgets import (
        QLabel,
        QGroupBox,
        QHBoxLayout,
        QLineEdit,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
    )
except ImportError:  # pragma: no cover
    QLabel = object  # type: ignore

from gui.core.base_tab import BaseTab
from gui.services import api_client


class LearningPathTab(BaseTab):
    """Interactive tab for learning-path generation and step progression."""

    def __init__(self, asyncio_thread=None, parent=None):
        super().__init__("Learning Path", asyncio_thread, parent)
        self.current_path_id: Optional[str] = None
        self.current_step_id: Optional[str] = None
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self) -> None:
        title = QLabel("Learning Path Generator")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.main_layout.addWidget(title)

        help_text = QLabel(
            "Quick Start: 1) Generate Path 2) Load Path 3) Get Recommendations "
            "4) Mark First Step Complete."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #9e9e9e; padding: 4px 0 8px 0;")
        self.main_layout.addWidget(help_text)
        self.prereq_status = QLabel("")
        self.prereq_status.setWordWrap(True)
        self.prereq_status.setStyleSheet("color: #ffcc80; padding: 0 0 8px 0;")
        self.main_layout.addWidget(self.prereq_status)

        form_group = QGroupBox("Path Inputs")
        form_layout = QVBoxLayout(form_group)

        user_row = QHBoxLayout()
        user_row.addWidget(QLabel("User ID:"))
        self.user_input = QLineEdit("user-default")
        user_row.addWidget(self.user_input)
        form_layout.addLayout(user_row)

        objective_row = QHBoxLayout()
        objective_row.addWidget(QLabel("Objective ID:"))
        self.objective_input = QLineEdit("OBJECTIVE.LEARN")
        objective_row.addWidget(self.objective_input)
        form_layout.addLayout(objective_row)

        heuristics_row = QHBoxLayout()
        heuristics_row.addWidget(QLabel("Heuristic IDs (comma-separated):"))
        self.heuristics_input = QLineEdit("h-1,h-2")
        heuristics_row.addWidget(self.heuristics_input)
        form_layout.addLayout(heuristics_row)

        self.generate_button = QPushButton("Generate Path")
        form_layout.addWidget(self.generate_button)

        self.main_layout.addWidget(form_group)

        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout(actions_group)
        self.refresh_button = QPushButton("Load Path")
        self.recommend_button = QPushButton("Get Recommendations")
        self.complete_step_button = QPushButton("Mark First Step Complete")
        self.quick_start_button = QPushButton("Run Guided Flow")
        actions_layout.addWidget(self.refresh_button)
        actions_layout.addWidget(self.recommend_button)
        actions_layout.addWidget(self.complete_step_button)
        actions_layout.addWidget(self.quick_start_button)
        self.main_layout.addWidget(actions_group)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Learning path output will appear here...")
        self.main_layout.addWidget(self.output)

        self.main_layout.addWidget(self.status_label)
        self._refresh_action_state()

    def connect_signals(self) -> None:
        self.generate_button.clicked.connect(self.generate_path)
        self.refresh_button.clicked.connect(self.load_path)
        self.recommend_button.clicked.connect(self.get_recommendations)
        self.complete_step_button.clicked.connect(self.complete_first_step)
        self.quick_start_button.clicked.connect(self.run_guided_flow)

    def _refresh_action_state(self) -> None:
        has_path = bool(self.current_path_id)
        has_step = bool(self.current_step_id)
        self.refresh_button.setEnabled(has_path)
        self.recommend_button.setEnabled(has_path)
        self.complete_step_button.setEnabled(has_step)
        if not has_path:
            self.prereq_status.setText("Start here: click Generate Path.")
            self.prereq_status.setStyleSheet("color: #ffcc80; padding: 0 0 8px 0;")
        elif has_path and not has_step:
            self.prereq_status.setText("Path loaded. Next: click Get Recommendations.")
            self.prereq_status.setStyleSheet("color: #81c784; padding: 0 0 8px 0;")
        else:
            self.prereq_status.setText("Ready: load recommendations or mark the first step complete.")
            self.prereq_status.setStyleSheet("color: #81c784; padding: 0 0 8px 0;")

    def _build_path_id(self) -> str:
        return f"lp-{int(time.time())}"

    def _heuristic_list(self) -> list[str]:
        raw = self.heuristics_input.text().strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    def generate_path(self) -> None:
        if self.status:
            self.status.loading("Generating learning path...")

        path_id = self._build_path_id()
        self.current_path_id = path_id

        payload = api_client.generate_learning_path(
            path_id=path_id,
            user_id=self.user_input.text().strip() or "user-default",
            objective_id=self.objective_input.text().strip() or "OBJECTIVE.LEARN",
            heuristic_ids=self._heuristic_list(),
            evidence_spans=[
                {
                    "artifact_row_id": 1,
                    "start_char": 0,
                    "end_char": 10,
                    "quote": "example span",
                }
            ],
        )
        item = payload.get("item", {})
        steps = item.get("steps", []) if isinstance(item, dict) else []
        if steps:
            self.current_step_id = steps[0].get("step_id")

        self.output.setPlainText(str(payload))
        if self.status:
            self.status.success(f"Generated path {path_id}")
        self._refresh_action_state()

    def load_path(self) -> None:
        if not self.current_path_id:
            if self.status:
                self.status.warn("Generate a path first")
            return

        payload = api_client.get_learning_path(self.current_path_id)
        item = payload.get("item", {}) if isinstance(payload, dict) else {}
        steps = item.get("steps", []) if isinstance(item, dict) else []
        if steps:
            self.current_step_id = steps[0].get("step_id")
        self.output.setPlainText(str(payload))
        if self.status:
            self.status.success("Loaded learning path")
        self._refresh_action_state()

    def get_recommendations(self) -> None:
        if not self.current_path_id:
            if self.status:
                self.status.warn("Generate a path first")
            return

        payload = api_client.get_learning_recommendations(self.current_path_id)
        self.output.setPlainText(str(payload))
        if self.status:
            self.status.success("Fetched recommendations")
        self._refresh_action_state()

    def complete_first_step(self) -> None:
        if not self.current_path_id or not self.current_step_id:
            if self.status:
                self.status.warn("No step available to complete")
            return

        payload = api_client.update_learning_step(
            path_id=self.current_path_id,
            step_id=self.current_step_id,
            completed=True,
        )
        self.output.setPlainText(str(payload))
        if self.status:
            self.status.success("Marked step complete")
        self._refresh_action_state()

    def run_guided_flow(self) -> None:
        """Run the default sequence for confused/first-time users."""
        self.generate_path()
        if self.current_path_id:
            self.load_path()
            self.get_recommendations()
        self._refresh_action_state()
