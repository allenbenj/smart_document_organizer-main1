"""
Quick Start Tab
===============
First-time-user workflow guide with one-click navigation to core tabs.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class QuickStartTab(QWidget):
    """Guided workflow launcher for first-time users."""

    def __init__(
        self,
        *,
        open_tab: Callable[[str], bool],
        run_health_check: Optional[Callable[[], None]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._open_tab = open_tab
        self._run_health_check = run_health_check
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        title = QLabel("Quick Start: End-to-End Workflow")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        root.addWidget(title)

        subtitle = QLabel(
            "Start here if you are new. Follow steps in order. "
            "Each step has a single primary action."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #b0bec5;")
        root.addWidget(subtitle)

        if self._run_health_check is not None:
            top_actions = QHBoxLayout()
            check_btn = QPushButton("Check Backend Connection")
            check_btn.clicked.connect(self._run_health_check)
            top_actions.addWidget(check_btn)
            top_actions.addStretch()
            root.addLayout(top_actions)

        steps = [
            (
                "1) Organization",
                "Set root scope, load/generate proposals, and approve/refine organization moves.",
                "Why first: downstream tabs need stable file paths and folder structure.",
                "📂 Organization",
            ),
            (
                "2) Processing",
                "Add files/folders and run document processing.",
                "Why now: processing builds normalized text/chunks used by extraction and search.",
                "📄 Processing",
            ),
            (
                "3) Entities",
                "Extract entities, then approve or sync to memory.",
                "Why now: entities become structured signals for memory and reasoning.",
                "🔍 Entities",
            ),
            (
                "4) Agent Memory",
                "Review curated rows, correct fields, and save.",
                "Why now: verified memory is the quality-controlled knowledge base for later steps.",
                "🧠 Agent Memory Manager",
            ),
            (
                "5) Semantic Analysis",
                "Run discovery on selected content.",
                "Why now: thematic discovery is stronger after memory curation and normalized inputs.",
                "🧠 Semantic Analysis",
            ),
            (
                "6) Learning Paths",
                "Generate path, load it, then get recommendations.",
                "Why now: learning paths depend on curated signals and analysis outputs.",
                "🎯 Learning Paths",
            ),
            (
                "7) Legal Reasoning",
                "Run structured legal reasoning after curation.",
                "Why now: reasoning quality improves when evidence/entities/themes are already aligned.",
                "⚖️ Legal Reasoning",
            ),
            (
                "8) QA Checks",
                "Run Contradictions and Violations as final QA.",
                "Why last: QA validates consistency and risk after all prior outputs are produced.",
                "⚔️ Contradictions",
            ),
        ]

        for heading, detail, why, tab_name in steps:
            root.addWidget(self._step_card(heading, detail, why, tab_name))

        note = QLabel(
            "If a step has no output: complete the previous step first, "
            "then come back and retry."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #90a4ae;")
        root.addWidget(note)
        root.addStretch()

    def _step_card(self, heading: str, detail: str, why: str, tab_name: str) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)

        text_col = QVBoxLayout()
        h = QLabel(heading)
        h.setFont(QFont("Arial", 11, QFont.Bold))
        text_col.addWidget(h)

        d = QLabel(detail)
        d.setWordWrap(True)
        d.setStyleSheet("color: #b0bec5;")
        text_col.addWidget(d)

        why_label = QLabel(why)
        why_label.setWordWrap(True)
        why_label.setStyleSheet("color: #90caf9; font-style: italic;")
        text_col.addWidget(why_label)
        layout.addLayout(text_col, 1)

        open_btn = QPushButton("Open Tab")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(lambda _=False, n=tab_name: self._open_target_tab(n))
        layout.addWidget(open_btn)

        return frame

    def _open_target_tab(self, tab_name: str) -> None:
        ok = self._open_tab(tab_name)
        if not ok:
            # Fallback for QA checks step if contradictions tab label changed/missing.
            if tab_name == "⚔️ Contradictions":
                self._open_tab("🚨 Violations")
