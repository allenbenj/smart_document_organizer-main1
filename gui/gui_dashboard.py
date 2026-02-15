"""Thin GUI dashboard shell for Smart Document Organizer."""

import asyncio
import logging
import os
import sys
import webbrowser
import traceback
from typing import Callable

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

try:
    import requests
except Exception:
    requests = None

# Support both module import and direct script execution.
if __package__:
    from .contradictions_tab import ContradictionsTab
    from .memory_analytics_tab import MemoryAnalyticsTab
    from .memory_review_tab import MemoryReviewTab
    from .tabs.classification_tab import ClassificationTab
    from .tabs.document_processing_tab import DocumentOrganizationTab
    from .tabs.embedding_operations_tab import EmbeddingOperationsTab
    from .tabs.entity_extraction_tab import EntityExtractionTab
    from .tabs.expert_prompts_tab import ExpertPromptsTab
    from .tabs.knowledge_graph_tab import KnowledgeGraphTab
    from .tabs.legal_reasoning_tab import LegalReasoningTab
    from .tabs.pipelines_tab import PipelinesTab
    from .tabs.semantic_analysis_tab import SemanticAnalysisTab
    from .tabs.vector_search_tab import VectorSearchTab
    from .violations_tab import ViolationsTab
    from .services import api_client
    from .ui import RunConsolePanel, SystemHealthStrip
else:
    # Running as script: `python gui/gui_dashboard.py`
    _here = os.path.dirname(__file__)
    _root = os.path.dirname(_here)
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from gui.contradictions_tab import ContradictionsTab
    from gui.memory_analytics_tab import MemoryAnalyticsTab
    from gui.memory_review_tab import MemoryReviewTab
    from gui.tabs.classification_tab import ClassificationTab
    from gui.tabs.document_processing_tab import DocumentOrganizationTab
    from gui.tabs.embedding_operations_tab import EmbeddingOperationsTab
    from gui.tabs.entity_extraction_tab import EntityExtractionTab
    from gui.tabs.expert_prompts_tab import ExpertPromptsTab
    from gui.tabs.knowledge_graph_tab import KnowledgeGraphTab
    from gui.tabs.legal_reasoning_tab import LegalReasoningTab
    from gui.tabs.pipelines_tab import PipelinesTab
    from gui.tabs.semantic_analysis_tab import SemanticAnalysisTab
    from gui.tabs.vector_search_tab import VectorSearchTab
    from gui.violations_tab import ViolationsTab
    from gui.services import api_client
    from gui.ui import RunConsolePanel, SystemHealthStrip

logger = logging.getLogger(__name__)


class AsyncioThread(QThread):
    """Background thread hosting an asyncio event loop."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop = asyncio.new_event_loop()

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        try:
            self.loop.call_soon_threadsafe(self.loop.stop)
        except Exception:
            pass


class AgentStatusWidget(QWidget):
    """Minimal system status banner."""

    def __init__(self, asyncio_thread: AsyncioThread):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        layout = QVBoxLayout(self)
        title = QLabel("Agent Status")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        self.status = QLabel("Checking backend...")
        layout.addWidget(self.status)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(15000)
        self.refresh_status()

    def refresh_status(self):
        try:
            if requests is None:
                self.status.setText("requests unavailable")
                return
            r = requests.get(f"{api_client.base_url}/api/health", timeout=3)
            if r.status_code == 200:
                self.status.setText("Backend healthy")
            else:
                self.status.setText(f"Backend unhealthy: HTTP {r.status_code}")
        except Exception as e:
            self.status.setText(f"Status unavailable: {e}")


class ErrorTab(QWidget):
    """Fallback tab shown when a tab fails to construct."""

    def __init__(self, name: str, error_text: str):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel(f"{name} failed to load")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        body = QLabel(error_text)
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)


class LegalAIDashboard(QMainWindow):
    """Main dashboard shell. Owns layout and tab orchestration only."""

    def __init__(self, asyncio_thread: AsyncioThread):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.agent_manager = None
        self._init_ui()
        # Optional: avoid heavyweight agent imports on GUI startup unless explicitly enabled.
        if os.getenv("GUI_ENABLE_AGENT_MANAGER", "0").strip().lower() in {"1", "true", "yes", "on"}:
            self._setup_agent_manager()

    def _safe_tab(self, title: str, factory: Callable[[], QWidget]) -> QWidget:
        try:
            return factory()
        except Exception as e:
            logger.exception("Failed to create tab %s", title)
            return ErrorTab(title, str(e))

    def _init_ui(self):
        self.setWindowTitle("Legal AI Modular System - Dashboard")
        self.setGeometry(100, 100, 1200, 800)

        self._init_menu()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        title = QLabel("Legal AI Modular System Dashboard")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        self.health_strip = SystemHealthStrip()
        main_layout.addWidget(self.health_strip)

        workflow_label = QLabel("Suggested Workflow:\n1. Ingest documents in 'Document Organization' tab.\n2. Analyze in 'Semantic Analysis', 'Entity Extraction', 'Legal Reasoning' tabs.\n3. Organize/Apply in 'Classification', 'Pipelines' tabs.")
        workflow_label.setWordWrap(True)
        main_layout.addWidget(workflow_label)

        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)

        self.status_widget = AgentStatusWidget(self.asyncio_thread)
        splitter.addWidget(self.status_widget)

        self.tab_widget = QTabWidget()
        splitter.addWidget(self.tab_widget)

        self.run_console = RunConsolePanel()
        splitter.addWidget(self.run_console)
        splitter.setSizes([100, 560, 180])

        tabs = [
            ("Document Organization", lambda: DocumentOrganizationTab()),
            (
                "Semantic Analysis",
                lambda: SemanticAnalysisTab(asyncio_thread=self.asyncio_thread),
            ),
            ("Entity Extraction", lambda: EntityExtractionTab()),
            ("Legal Reasoning", lambda: LegalReasoningTab()),
            ("Embedding Operations", lambda: EmbeddingOperationsTab(self.asyncio_thread)),
            ("Knowledge Graph", lambda: KnowledgeGraphTab(self.asyncio_thread)),
            ("Vector Search", lambda: VectorSearchTab()),
            ("Classification", lambda: ClassificationTab()),
            ("Pipelines", lambda: PipelinesTab()),
            ("Expert Prompts", lambda: ExpertPromptsTab()),
            ("Contradictions", lambda: ContradictionsTab()),
            ("Violations", lambda: ViolationsTab()),
            ("Memory Review", lambda: MemoryReviewTab()),
            ("Memory Analytics", lambda: MemoryAnalyticsTab()),
        ]

        for label, factory in tabs:
            self.tab_widget.addTab(self._safe_tab(label, factory), label)

        try:
            self.setWindowIcon(QIcon("assets/icon.png"))
        except Exception:
            pass

        self._refresh_advanced_status()
        self._adv_timer = QTimer(self)
        self._adv_timer.timeout.connect(self._refresh_advanced_status)
        self._adv_timer.start(15000)

    def _init_menu(self):
        menu_bar = self.menuBar()

        help_menu = menu_bar.addMenu("Help")
        act_health = QAction("Open API Health", self)
        act_health.triggered.connect(lambda: webbrowser.open(f"{api_client.base_url}/api/health"))
        help_menu.addAction(act_health)

        act_docs = QAction("Open API Docs (/docs)", self)
        act_docs.triggered.connect(lambda: webbrowser.open(f"{api_client.base_url}/docs"))
        help_menu.addAction(act_docs)

        mem_menu = menu_bar.addMenu("Memory")
        act_flags = QAction("Open Memory Flags", self)
        act_flags.triggered.connect(lambda: webbrowser.open(f"{api_client.base_url}/api/agents/memory/flags"))
        mem_menu.addAction(act_flags)

    def _setup_agent_manager(self):
        try:
            if __package__:
                from ..agents import get_agent_manager
            else:
                from agents import get_agent_manager
            self.agent_manager = get_agent_manager()
        except Exception as e:
            logger.warning("Agent manager initialization warning: %s", e)

    def _refresh_advanced_status(self):
        backend = "unavailable"
        advanced = "unavailable"
        try:
            if requests is None:
                self.health_strip.update_status("requests unavailable", "requests unavailable")
                return

            rh = requests.get(f"{api_client.base_url}/api/health", timeout=3)
            backend = "healthy" if rh.status_code == 200 else f"HTTP {rh.status_code}"

            r = requests.get(f"{api_client.base_url}/api/health/details", timeout=3)
            if r.status_code == 200:
                data = r.json()
                adv = (data.get("components", {}) or {}).get("advanced", {})
                ready = bool(adv.get("ready"))
                advanced = "READY" if ready else "NOT READY"
            else:
                advanced = f"HTTP {r.status_code}"
        except Exception:
            pass

        self.health_strip.update_status(backend, advanced)

    def _stop_tab_workers(self, timeout_ms: int = 2000) -> None:
        """Best-effort shutdown of active QThread workers held by tabs."""
        try:
            for i in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(i)
                if tab is None:
                    continue
                # Common worker attribute names used across tabs
                for attr in ("worker", "_worker", "_kg_worker"):
                    th = getattr(tab, attr, None)
                    if isinstance(th, QThread) and th.isRunning():
                        try:
                            th.requestInterruption()
                        except Exception:
                            pass
                        try:
                            th.quit()
                        except Exception:
                            pass
                        if not th.wait(timeout_ms):
                            try:
                                th.terminate()
                                th.wait(500)
                            except Exception:
                                pass
        except Exception as e:
            logger.warning("Error while stopping tab workers: %s", e)

    def closeEvent(self, event):
        # Stop active tab workers first to avoid: QThread destroyed while still running
        self._stop_tab_workers(timeout_ms=1500)

        try:
            if self.agent_manager is not None and hasattr(self.agent_manager, "shutdown"):
                fut = asyncio.run_coroutine_threadsafe(
                    self.agent_manager.shutdown(), self.asyncio_thread.loop
                )
                fut.result(timeout=5)
        except Exception as e:
            logger.warning("Error during GUI shutdown: %s", e)

        try:
            self.asyncio_thread.stop()
            if not self.asyncio_thread.wait(1500):
                self.asyncio_thread.terminate()
                self.asyncio_thread.wait(500)
        except Exception:
            pass
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Legal AI Dashboard")
    app.setApplicationVersion("1.0.0")

    asyncio_thread = AsyncioThread()
    asyncio_thread.start()

    def _stop_thread():
        try:
            if asyncio_thread.isRunning():
                asyncio_thread.stop()
                if not asyncio_thread.wait(3000):
                    try:
                        asyncio_thread.terminate()
                        asyncio_thread.wait(1000)
                    except Exception:
                        pass
        except Exception:
            pass

    app.aboutToQuit.connect(_stop_thread)

    try:
        dashboard = LegalAIDashboard(asyncio_thread)
        dashboard.show()
        rc = app.exec()
    except Exception as e:
        logger.exception("Fatal GUI startup error")
        try:
            print(f"Fatal GUI startup error: {e}", file=sys.stderr)
            traceback.print_exc()
        except Exception:
            pass
        try:
            QMessageBox.critical(None, "GUI startup failed", str(e))
        except Exception:
            pass
        rc = 1
    finally:
        _stop_thread()

    sys.exit(rc)


if __name__ == "__main__":
    main()
