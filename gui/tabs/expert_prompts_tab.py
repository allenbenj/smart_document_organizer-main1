"""
Expert Prompts Tab - GUI component for expert prompt building

This module provides the UI for building expert prompts using
different personas and task types.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from typing import Any, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from ..services import api_client
from gui.core.base_tab import BaseTab


class ExpertPromptsTab(BaseTab):
    def __init__(self, asyncio_thread: Optional[Any] = None, parent=None):
        super().__init__("Expert Prompts", asyncio_thread, parent)
        self.setup_ui()

    def setup_ui(self):
        title = QLabel("Expert Prompt Builder")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        form_group = QGroupBox("Build Prompt")
        form_layout = QVBoxLayout()
        # Persona
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Persona:"))
        self.persona_combo = QComboBox()
        self.persona_combo.addItems(
            [
                "Lex _Legal Researcher_",
                "Ava _Legal Writer_",
                "Max _Detail Analyst_",
                "Aria _Appellate Specialist_",
            ]
        )
        row1.addWidget(self.persona_combo)
        form_layout.addLayout(row1)
        # Task type
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Task Type:"))
        self.task_type = QLineEdit()
        self.task_type.setPlaceholderText(
            "e.g., research_memo, appellate_brief_section"
        )
        row2.addWidget(self.task_type)
        form_layout.addLayout(row2)
        # Task data
        self.task_data = QTextEdit()
        self.task_data.setPlaceholderText("Describe the task or paste relevant text...")
        form_layout.addWidget(self.task_data)
        # Actions
        actions = QHBoxLayout()
        self.gen_btn = QPushButton("Generate Prompt")
        self.clear_btn = QPushButton("Clear")
        actions.addWidget(self.gen_btn)
        actions.addWidget(self.clear_btn)
        form_layout.addLayout(actions)
        form_group.setLayout(form_layout)

        result_group = QGroupBox("Prompt")
        result_layout = QVBoxLayout()
        self.prompt_view = QTextEdit()
        self.prompt_view.setReadOnly(True)
        result_layout.addWidget(self.prompt_view)
        result_group.setLayout(result_layout)

        self.main_layout.addWidget(form_group)
        self.main_layout.addWidget(result_group)

        self.gen_btn.clicked.connect(self.generate)
        self.clear_btn.clicked.connect(
            lambda: (
                self.task_type.clear(),
                self.task_data.clear(),
                self.prompt_view.clear(),
            )
        )

    def generate(self):
        agent_name = self.persona_combo.currentText()
        task_type = self.task_type.text().strip() or "legal_research_memo"
        task_data = (
            self.task_data.toPlainText().strip()
            or "Analyze the provided material and prepare a research memo."
        )
        try:
            result = api_client.get_expert_prompt(agent_name, task_type, task_data)
            self.prompt_view.setPlainText(result.get("prompt", ""))
        except Exception as e:
            QMessageBox.critical(self, "Expert Prompt Error", str(e))
