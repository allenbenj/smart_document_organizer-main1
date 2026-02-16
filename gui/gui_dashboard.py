"""Thin GUI dashboard shell for Smart Document Organizer."""

import asyncio
import logging
import os
import subprocess
import sys
import webbrowser
import traceback
from typing import Callable

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QHBoxLayout,
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
    from .tabs.organization_tab import OrganizationTab
    from .tabs.document_processing_tab import DocumentProcessingTab
    from .tabs.diagnostics_tab import DiagnosticsTab
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
    from .ui import RunConsolePanel, SystemHealthStrip, NLPModelManagerDialog
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
    from gui.tabs.organization_tab import OrganizationTab
    from gui.tabs.document_processing_tab import DocumentProcessingTab
    from gui.tabs.diagnostics_tab import DiagnosticsTab
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
    from gui.ui import RunConsolePanel, SystemHealthStrip, NLPModelManagerDialog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WSL Backend Configuration
# ---------------------------------------------------------------------------
_WSL_DISTRO = os.getenv("WSL_DISTRO", "Ubuntu")
_WSL_PROJECT_PATH = os.getenv(
    "WSL_PROJECT_PATH", "/mnt/e/Project/smart_document_organizer-main"
)
_BACKEND_HEALTH_URL = os.getenv(
    "BACKEND_HEALTH_URL", "http://127.0.0.1:8000/api/health"
)
_HEALTH_TIMEOUT = int(os.getenv("BACKEND_HEALTH_TIMEOUT", "120"))


class WslBackendThread(QThread):
    """Start the backend inside WSL and poll until healthy (or timeout)."""

    status_update = Signal(str)  # emitted with progress messages
    healthy = Signal()           # emitted once health-check passes
    failed = Signal(str)         # emitted if backend never became healthy

    def __init__(
        self,
        distro: str = _WSL_DISTRO,
        linux_path: str = _WSL_PROJECT_PATH,
        health_url: str = _BACKEND_HEALTH_URL,
        timeout_s: int = _HEALTH_TIMEOUT,
        parent=None,
    ):
        super().__init__(parent)
        self.distro = distro
        self.linux_path = linux_path
        self.health_url = health_url
        self.timeout_s = timeout_s

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _backend_already_healthy(url: str) -> bool:
        """Quick check — is the backend already responding?"""
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=2) as r:
                return r.status == 200
        except Exception:
            return False

    def _kill_stale(self) -> None:
        """Kill any stale backend processes so we can start clean."""
        self._kill_stale_wsl()
        self._kill_stale_windows()
        # Brief pause so ports are released
        import time
        time.sleep(0.5)

    def _kill_stale_wsl(self) -> None:
        """Kill stale backend processes inside WSL."""
        kill_cmd = (
            f"set +e; cd '{self.linux_path}'; "
            f"if [ -f .backend-wsl.pid ]; then "
            f"  kill $(cat .backend-wsl.pid) 2>/dev/null; "
            f"  rm -f .backend-wsl.pid; "
            f"fi; "
            f"pkill -f 'uvicorn Start:app' 2>/dev/null; "
            f"echo CLEANED"
        )
        try:
            result = subprocess.run(
                ["wsl", "-d", self.distro, "bash", "-lc", kill_cmd],
                capture_output=True, text=True, timeout=15,
            )
            self.status_update.emit(
                f"Stale cleanup (WSL): {result.stdout.strip() or 'done'}"
            )
        except FileNotFoundError:
            pass  # no WSL — will be caught later in _start_in_wsl
        except Exception as exc:
            self.status_update.emit(f"Stale cleanup warning: {exc}")

    @staticmethod
    def _find_pids_on_port(netstat_output: str, port: int = 8000) -> set[int]:
        """Parse netstat -ano output for PIDs listening on *port*."""
        my_pid = os.getpid()
        pids: set[int] = set()
        for line in netstat_output.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                try:
                    pid = int(parts[-1])
                    if pid > 0 and pid != my_pid:
                        pids.add(pid)
                except (ValueError, IndexError):
                    pass
        return pids

    def _kill_stale_windows(self) -> None:
        """Kill any Windows processes listening on port 8000."""
        try:
            ns = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=10,
            )
            for pid in self._find_pids_on_port(ns.stdout):
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        capture_output=True, timeout=5,
                    )
                    self.status_update.emit(f"Killed stale Windows PID {pid}")
                except Exception:
                    pass
        except Exception as exc:
            self.status_update.emit(f"Windows cleanup warning: {exc}")

    def _start_in_wsl(self) -> str:
        """Launch the backend inside WSL. Returns stdout text."""
        result = subprocess.run(
            [
                "wsl", "-d", self.distro, "bash",
                f"{self.linux_path}/tools/launchers/start_backend_wsl.sh",
                self.linux_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        return (result.stdout + result.stderr).strip()

    def _resolve_wsl_ip(self) -> str | None:
        """Get the WSL2 distro's IP address (for when localhost forwarding is broken)."""
        try:
            result = subprocess.run(
                ["wsl", "-d", self.distro, "hostname", "-I"],
                capture_output=True, text=True, timeout=5,
            )
            ip = result.stdout.strip().split()[0]
            if ip:
                return ip
        except Exception:
            pass
        return None

    def _poll_health(self) -> bool:
        """Block until the backend is healthy or we time out."""
        import time, urllib.request  # noqa: E401
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            if self.isInterruptionRequested():
                return False
            try:
                with urllib.request.urlopen(self.health_url, timeout=2) as r:
                    if r.status == 200:
                        return True
            except Exception:
                pass
            time.sleep(1.2)
        return False

    # -- thread entry point -----------------------------------------------
    def run(self):  # noqa: C901
        # 1) Kill stale instances for a clean start
        self.status_update.emit("Cleaning up stale processes...")
        self._kill_stale()

        # 2) Start backend via WSL
        self.status_update.emit(f"Starting backend in WSL ({self.distro})...")
        try:
            out = self._start_in_wsl()
            self.status_update.emit(f"WSL: {out}")
        except FileNotFoundError:
            self.failed.emit("wsl.exe not found — is WSL installed?")
            return
        except subprocess.TimeoutExpired:
            self.failed.emit("WSL start command timed out (30 s)")
            return
        except Exception as exc:
            self.failed.emit(f"WSL launch error: {exc}")
            return

        # 3) Resolve WSL2 IP and update health URL
        wsl_ip = self._resolve_wsl_ip()
        if wsl_ip:
            self.health_url = f"http://{wsl_ip}:8000/api/health"
            self.status_update.emit(f"WSL2 IP: {wsl_ip} — using it for health checks")
        else:
            self.status_update.emit("Could not resolve WSL2 IP, trying localhost")

        # 4) Poll for health
        self.status_update.emit("Waiting for backend to become healthy...")
        if self._poll_health():
            # Update the global api_client so all tabs use the correct URL
            if wsl_ip:
                api_client.base_url = f"http://{wsl_ip}:8000"
            self.status_update.emit("Backend healthy")
            self.healthy.emit()
        else:
            self.failed.emit(
                f"Backend did not become healthy within {self.timeout_s}s.\n"
                f"Check: wsl -d {self.distro} bash -lc "
                f"\"tail -n 80 '{self.linux_path}/logs/backend-wsl.log'\""
            )


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
        # Defer the initial check so the UI appears immediately
        QTimer.singleShot(0, self.refresh_status)

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

    def launch_db_monitor(self):
        try:
            script_path = os.path.join(os.path.dirname(__file__), "db_monitor.py")
            subprocess.Popen([sys.executable, script_path])
        except Exception as e:
            QMessageBox.warning(self, "Launch Error", f"Could not launch DB Monitor: {e}")

    def launch_professional_manager(self):
        try:
            script_path = os.path.join(os.path.dirname(__file__), "professional_manager.py")
            subprocess.Popen([sys.executable, script_path])
        except Exception as e:
            QMessageBox.warning(self, "Launch Error", f"Could not launch Professional Manager: {e}")

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

        # Tools Toolbar
        tools_layout = QHBoxLayout()
        btn_monitor = QPushButton("Launch DB Monitor")
        btn_monitor.clicked.connect(self.launch_db_monitor)
        tools_layout.addWidget(btn_monitor)
        
        btn_prof = QPushButton("Professional Manager")
        btn_prof.clicked.connect(self.launch_professional_manager)
        tools_layout.addWidget(btn_prof)
        
        tools_layout.addStretch()
        main_layout.addLayout(tools_layout)

        workflow_label = QLabel("Suggested Workflow:\n1. Ingest documents in 'Document Organization' tab.\n2. Analyze in 'Semantic Analysis', 'Entity Extraction', 'Legal Reasoning' tabs.\n3. Organize/Apply in 'Classification', 'Pipelines' tabs.")
        workflow_label.setWordWrap(True)
        main_layout.addWidget(workflow_label)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(True)
        main_layout.addWidget(splitter)

        self.status_widget = AgentStatusWidget(self.asyncio_thread)
        self.status_widget.setMinimumHeight(0)
        self.status_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        splitter.addWidget(self.status_widget)

        self.tab_widget = QTabWidget()
        self.tab_widget.setUsesScrollButtons(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setElideMode(Qt.TextElideMode.ElideRight)
        splitter.addWidget(self.tab_widget)

        self.run_console = RunConsolePanel()
        self.run_console.setMinimumHeight(0)
        self.run_console.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        splitter.addWidget(self.run_console)
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, True)
        splitter.setCollapsible(2, True)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([100, 560, 180])

        tabs = [
            ("Organization", lambda: OrganizationTab()),
            ("Document Processing", lambda: DocumentProcessingTab()),
            (
                "Semantic Analysis",
                lambda: SemanticAnalysisTab(asyncio_thread=self.asyncio_thread),
            ),
            ("Entity Extraction", lambda: EntityExtractionTab()),
            ("Legal Reasoning", lambda: LegalReasoningTab()),
            ("Classification", lambda: ClassificationTab()),
            ("Embedding Operations", lambda: EmbeddingOperationsTab(self.asyncio_thread)),
            ("Knowledge Graph", lambda: KnowledgeGraphTab(self.asyncio_thread)),
            ("Vector Search", lambda: VectorSearchTab()),
            ("Pipelines", lambda: PipelinesTab()),
            ("Expert Prompts", lambda: ExpertPromptsTab()),
            ("Contradictions", lambda: ContradictionsTab()),
            ("Violations", lambda: ViolationsTab()),
            ("Diagnostics", lambda: DiagnosticsTab()),
            ("Memory Review", lambda: MemoryReviewTab()),
            ("Memory Analytics", lambda: MemoryAnalyticsTab()),
        ]

        for label, factory in tabs:
            self.tab_widget.addTab(self._safe_tab(label, factory), label)

        try:
            self.setWindowIcon(QIcon("assets/icon.png"))
        except Exception:
            pass

        # Defer health check so the window appears immediately
        QTimer.singleShot(0, self._refresh_advanced_status)
        self._adv_timer = QTimer(self)
        self._adv_timer.timeout.connect(self._refresh_advanced_status)
        self._adv_timer.start(15000)

    def _init_menu(self):
        menu_bar = self.menuBar()
        
        # Tools menu
        tools_menu = menu_bar.addMenu("Tools")
        act_nlp_manager = QAction("📦 NLP Model Manager", self)
        act_nlp_manager.triggered.connect(self.open_nlp_model_manager)
        tools_menu.addAction(act_nlp_manager)

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

    def on_backend_ready(self):
        """Notify all tabs that the backend is ready."""
        print("[Dashboard] Backend ready signal received. Refreshing tabs...", flush=True)
        # Refresh Entity Extraction tab if it exists
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            # Check for tabs by class name or attribute
            if hasattr(widget, "on_backend_ready"):
                print(f"[Dashboard] Calling on_backend_ready() for {widget.__class__.__name__}", flush=True)
                try:
                    widget.on_backend_ready()
                except Exception as e:
                    print(f"[Dashboard] Error in {widget.__class__.__name__}.on_backend_ready(): {e}", flush=True)
            if hasattr(widget, "fetch_ontology"):
                print(f"[Dashboard] Refreshing ontology for {widget.__class__.__name__}", flush=True)
                widget.fetch_ontology()
            if hasattr(widget, "load_presets"):
                print(f"[Dashboard] Refreshing presets for {widget.__class__.__name__}", flush=True)
                widget.load_presets()
    
    def open_nlp_model_manager(self):
        """Open the NLP Model Manager dialog."""
        try:
            dialog = NLPModelManagerDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open NLP Model Manager: {str(e)}"
            )

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
                        self._stop_single_worker(th, timeout_ms)
        except Exception as e:
            logger.warning("Error while stopping tab workers: %s", e)

    @staticmethod
    def _stop_single_worker(th: QThread, timeout_ms: int) -> None:
        """Shut down a single QThread worker gracefully."""
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


def _stop_asyncio_thread(asyncio_thread: AsyncioThread) -> None:
    """Best-effort cleanup of the asyncio background thread."""
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


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Legal AI Dashboard")
    app.setApplicationVersion("1.0.0")

    asyncio_thread = AsyncioThread()
    asyncio_thread.start()

    app.aboutToQuit.connect(lambda: _stop_asyncio_thread(asyncio_thread))

    skip_wsl_backend = os.getenv("GUI_SKIP_WSL_BACKEND_START", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    wsl_thread = None
    if not skip_wsl_backend:
        # --- Start backend in WSL (non-blocking) ---
        wsl_thread = WslBackendThread()
        # Log WSL progress to stdout so the user sees what's happening
        wsl_thread.status_update.connect(lambda msg: print(f"[WSL] {msg}", flush=True))
        wsl_thread.failed.connect(lambda msg: print(f"[WSL] FAILED: {msg}", flush=True))
        wsl_thread.healthy.connect(lambda: print("[WSL] Backend is healthy", flush=True))
        wsl_thread.start()

    try:
        dashboard = LegalAIDashboard(asyncio_thread)

        if wsl_thread is not None:
            # Wire WSL status into the dashboard health strip
            wsl_thread.status_update.connect(
                lambda msg: dashboard.health_strip.update_status(msg, "starting...")
            )
            # When healthy, refresh system status AND notify tabs
            wsl_thread.healthy.connect(dashboard._refresh_advanced_status)
            wsl_thread.healthy.connect(dashboard.on_backend_ready)
            wsl_thread.failed.connect(
                lambda msg: dashboard.health_strip.update_status("WSL FAILED", msg[:60])
            )
        else:
            QTimer.singleShot(200, dashboard._refresh_advanced_status)
            QTimer.singleShot(300, dashboard.on_backend_ready)

        dashboard.show()
        rc = app.exec()
    except Exception as e:
        logger.exception("Fatal GUI startup error")
        _handle_fatal_error(e)
        rc = 1
    finally:
        # Clean up WSL thread (does NOT stop the backend — it keeps running)
        if wsl_thread is not None and wsl_thread.isRunning():
            wsl_thread.requestInterruption()
            wsl_thread.wait(3000)
        _stop_asyncio_thread(asyncio_thread)

    sys.exit(rc)


def _handle_fatal_error(e: Exception) -> None:
    """Display fatal startup error information."""
    try:
        print(f"Fatal GUI startup error: {e}", file=sys.stderr)
        traceback.print_exc()
    except Exception:
        pass
    try:
        QMessageBox.critical(None, "GUI startup failed", str(e))
    except Exception:
        pass


if __name__ == "__main__":
    main()
