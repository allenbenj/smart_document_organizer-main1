"""
Planner-Judge Tab - Deterministic strategy verification

Provides the interface for composing strategies via the Planner and
validating them against deterministic rules via the Judge.
"""

from __future__ import annotations

import json
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
        QLineEdit,
        QSpinBox,
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont, QColor
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore

from .status_presenter import TabStatusPresenter
from ..services import api_client
from gui.core.base_tab import BaseTab

logger = logging.getLogger(__name__)

class PlannerJudgeTab(BaseTab):  # type: ignore[misc]
    """
    Tab for running and inspecting Planner-Judge cycles.
    Fulfills AEDIS Phase 4 'GUI-Integrated' mandate.
    """

    def __init__(self, asyncio_thread: Optional[Any] = None, parent=None):
        super().__init__("Planner-Judge", asyncio_thread, parent)
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Setup the user interface."""
        # Title
        title = QLabel("Planner-Judge Verification Core")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.main_layout.addWidget(title)

        # Description
        desc = QLabel(
            "Compose AI strategies and verify them against deterministic rulesets. "
            "No output persists until it achieves a Judge PASS."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; padding: 5px 0;")
        self.main_layout.addWidget(desc)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(splitter)

        # Left panel - Planner Composition
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Planner Strategy Group
        planner_group = QGroupBox("Planner Strategy Composition")
        planner_layout = QVBoxLayout(planner_group)
        
        obj_row = QHBoxLayout()
        obj_row.addWidget(QLabel("Objective ID:"))
        self.objective_input = QLineEdit()
        self.objective_input.setText("OBJECTIVE.ORGANIZE_DOCUMENT")
        obj_row.addWidget(self.objective_input)
        planner_layout.addLayout(obj_row)

        art_row = QHBoxLayout()
        art_row.addWidget(QLabel("Artifact Row ID:"))
        self.artifact_id_spin = QSpinBox()
        self.artifact_id_spin.setRange(1, 999999)
        art_row.addWidget(self.artifact_id_spin)
        planner_layout.addLayout(art_row)

        planner_layout.addWidget(QLabel("Strategy JSON:"))
        self.strategy_edit = QTextEdit()
        self.strategy_edit.setPlaceholderText("""{
  "goal": "organize into legal folders",
  "steps": []
}""")
        self.strategy_edit.setFont(QFont("Courier New", 10))
        planner_layout.addWidget(self.strategy_edit)

        self.run_button = QPushButton("⚡ Run Planner + Judge")
        self.run_button.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 10px;")
        planner_layout.addWidget(self.run_button)

        left_layout.addWidget(planner_group)

        # Status
        self.status_label = QLabel("Ready") # The QLabel for status is still needed for BaseTab to set text/style
        self.status_label.setStyleSheet("padding: 5px; background-color: #f5f5f5; border-radius: 3px;")
        left_layout.addWidget(self.status_label)
        # self.status is now handled by BaseTab

        splitter.addWidget(left_widget)

        # Right panel - Judge Outcome
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Scorecard Group
        scorecard_group = QGroupBox("Judge Scorecard")
        scorecard_layout = QVBoxLayout(scorecard_group)
        
        self.verdict_label = QLabel("VERDICT: PENDING")
        self.verdict_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.verdict_label.setAlignment(Qt.AlignCenter)
        scorecard_layout.addWidget(self.verdict_label)

        self.score_label = QLabel("Score: 0.00")
        self.score_label.setAlignment(Qt.AlignCenter)
        scorecard_layout.addWidget(self.score_label)

        right_layout.addWidget(scorecard_group)

        # Failure & Remediation
        self.failure_browser = QTextBrowser()
        self.failure_browser.setPlaceholderText("Failure reasons and remediation hints will appear here...")
        right_layout.addWidget(QLabel("Failure Details & Remediation:"))
        right_layout.addWidget(self.failure_browser)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 400])

    def connect_signals(self):
        """Connect UI signals."""
        self.run_button.clicked.connect(self.execute_cycle)

    def execute_cycle(self):
        """Execute the Planner-Judge cycle via API."""
        obj_id = self.objective_input.text().strip()
        art_id = self.artifact_id_spin.value()
        
        try:
            strategy = json.loads(self.strategy_edit.toPlainText())
        except json.JSONDecodeError as e:
            logger.error(f"Invalid Strategy JSON: {e}")
            self.status.error(f"Invalid Strategy JSON: {e}")
            return
        except Exception as e:
            logger.exception(f"An unexpected error occurred during JSON parsing: {e}")
            self.status.error(f"An unexpected error occurred during JSON parsing: {e}")
            return

        self.status.loading("Executing Planner-Judge cycle...")
        try:
            result = api_client.run_planner_judge(obj_id, art_id, strategy)
            if not result.get("success"):
                error_message = result.get('error', 'Unknown error during execution.')
                logger.error(f"Planner-Judge execution failed: {error_message}")
                self.status.error(f"Execution Failed: {error_message}")
                return

            self.update_scorecard(result.get("judge_run", {}))
            self.status.success("Cycle completed")
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error during Planner-Judge cycle: {e}")
            self.status.error(f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response during Planner-Judge cycle: {e}")
            self.status.error(f"Invalid API response: {e}")
        except RuntimeError as e: # Catch custom RuntimeError
            logger.error(f"Runtime error during Planner-Judge cycle: {e}")
            self.status.error(f"Runtime error: {e}")
        except Exception as e:
            logger.exception(f"An unexpected API error occurred during Planner-Judge cycle: {e}")
            self.status.error(f"An unexpected API error occurred: {e}")

    def update_scorecard(self, judge_run: dict):
        """Update the UI with judge results."""
        verdict = judge_run.get("verdict", "FAIL")
        score = judge_run.get("score", 0.0)
        
        self.verdict_label.setText(f"VERDICT: {verdict}")
        self.score_label.setText(f"Score: {score:.2f}")
        
        if verdict == "PASS":
            self.verdict_label.setStyleSheet("color: #2e7d32; background-color: #e8f5e9; padding: 10px;")
        else:
            self.verdict_label.setStyleSheet("color: #c62828; background-color: #ffebee; padding: 10px;")

        # Format failures
        html = "<h3>Reasons:</h3><ul>"
        for r in judge_run.get("reasons", []):
            html += f"<li>{r}</li>"
        html += "</ul>"
        
        html += "<h3>Remediation Hints:</h3><ul>"
        for h in judge_run.get("remediation", []):
            html += f"<li><b>{h}</b></li>"
        html += "</ul>"
        
        self.failure_browser.setHtml(html)
