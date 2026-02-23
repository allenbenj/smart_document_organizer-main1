"""
Launch Professional Manager
===========================
The main professional GUI dashboard for the Smart Document Organizer.
Integrates all functional tabs into a unified, dark-themed interface.
"""

import sys
import os
import requests
import asyncio
import threading
import time
import logging
import subprocess
import traceback
from datetime import datetime
from pathlib import Path

# Add project root to python path to ensure imports work correctly
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.backend_runtime import (
    backend_base_url,
    backend_health_url,
    launch_health_timeout_seconds,
)

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QTabWidget, QStatusBar, QMessageBox, QPushButton, QTextEdit,
        QDockWidget, QScrollArea, QFrame, QSizePolicy
    )
    from PySide6.QtCore import Qt, QTimer, QSize, Signal, QThread
    from PySide6.QtGui import QIcon, QFont, QAction
except ImportError:
    print("PySide6 is required. Please install it with: pip install PySide6")
    sys.exit(1)

# Import Tabs
# We wrap imports in try/except to handle missing dependencies gracefully during dev
try:
    from gui.tabs.quick_start_tab import QuickStartTab
    from gui.tabs.organization_tab import OrganizationTab
    from gui.tabs.document_processing_tab import DocumentProcessingTab
    from gui.tabs.semantic_analysis_tab import SemanticAnalysisTab
    from gui.tabs.entity_extraction_tab import EntityExtractionTab
    from gui.tabs.legal_reasoning_tab import LegalReasoningTab
    from gui.tabs.knowledge_graph_tab import KnowledgeGraphTab
    from gui.tabs.vector_search_tab import VectorSearchTab
    from gui.tabs.pipelines_tab import PipelinesTab
    from gui.tabs.expert_prompts_tab import ExpertPromptsTab
    from gui.tabs.embedding_operations_tab import EmbeddingOperationsTab
    from gui.tabs.classification_tab import ClassificationTab
    from gui.tabs.learning_path_tab import LearningPathTab
    from gui.tabs.data_explorer_tab import DataExplorerTab
    from gui.memory_review_tab import AgentMemoryManagerTab
    from gui.contradictions_tab import ContradictionsTab
    from gui.violations_tab import ViolationsTab
except ImportError as e:
    print(f"Error importing tabs: {e}")
    # We will handle missing tabs in the class

from gui.core import AsyncioThread
from gui.core.path_config import default_wsl_project_path
from gui.services import api_client

logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# WSL Backend Configuration
# ---------------------------------------------------------------------------
_WSL_DISTRO = os.getenv("WSL_DISTRO", "Ubuntu")
_WSL_PROJECT_PATH = default_wsl_project_path()
_BACKEND_HEALTH_URL = os.getenv("BACKEND_HEALTH_URL", backend_health_url())
_HEALTH_TIMEOUT = launch_health_timeout_seconds(120)


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
        except Exception as exc:
            logger.debug("Backend pre-check failed for %s: %s", url, exc)
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
            self.status_update.emit("WSL executable not found during stale cleanup.")
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
                except Exception as exc:
                    self.status_update.emit(
                        f"Failed to kill Windows PID {pid}: {exc}"
                    )
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
        except Exception as exc:
            logger.debug("WSL IP resolution failed: %s", exc)
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
            except Exception as exc:
                logger.debug("Backend health poll not ready at %s: %s", self.health_url, exc)
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
            else:
                api_client.base_url = backend_base_url()
            self.status_update.emit("Backend healthy")
            self.healthy.emit()
        else:
            self.failed.emit(
                f"Backend did not become healthy within {self.timeout_s}s.\n"
                f"Check: wsl -d {self.distro} bash -lc "
                f"\"tail -n 80 '{self.linux_path}/logs/backend-wsl.log'\""
            )


class ProfessionalManager(QMainWindow):
    backend_check_finished = Signal(bool, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Document Organizer - Professional Manager")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 700)
        self.asyncio_thread = AsyncioThread(self)
        self.asyncio_thread.start()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._stop_asyncio_thread)
        
        self.api_url = backend_base_url()
        self.setup_ui()
        self.apply_styles()
        self._health_check_inflight = False
        self._consecutive_health_failures = 0
        self._last_error_dialog_at = 0.0
        self._dialog_cooldown_s = 45.0
        self._pending_health_check_user_initiated = False
        self._backend_was_connected = False
        self.backend_check_finished.connect(self._handle_backend_check_result)
        
        # Check backend status on startup and then periodically
        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(lambda: self.check_backend_status(False))
        self.health_timer.start(10000) # Every 10 seconds
        
        QTimer.singleShot(100, lambda: self.check_backend_status(False))

    def apply_styles(self):
        qss_file = Path(__file__).parent / "assets" / "dark_theme.qss"
        if qss_file.exists():
            with open(qss_file, "r") as f:
                self.setStyleSheet(f.read())
        else:
            logger.warning("dark_theme.qss not found at %s", qss_file)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Top Bar ---
        top_bar = QHBoxLayout()
        
        title_label = QLabel("Legal AI Platform Manager")
        title_label.setObjectName("Heading")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4dabf7;")
        top_bar.addWidget(title_label)
        
        top_bar.addStretch()
        
        self.status_indicator = QLabel("Checking Backend...")
        self.status_indicator.setStyleSheet("color: orange; font-weight: bold;")
        top_bar.addWidget(self.status_indicator)
        
        refresh_btn = QPushButton("🔄 Reconnect")
        refresh_btn.clicked.connect(lambda: self.check_backend_status(True))
        top_bar.addWidget(refresh_btn)

        self.toggle_logs_btn = QPushButton("🧾 Logs")
        self.toggle_logs_btn.clicked.connect(self.toggle_diagnostics_dock)
        top_bar.addWidget(self.toggle_logs_btn)
        
        main_layout.addLayout(top_bar)

        # --- Main Tabs ---
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True) # Professional look
        self.tabs.setMovable(True)
        self.load_tabs()
        main_layout.addWidget(self.tabs)

        # --- Diagnostic Log Dock (does not steal tab layout space) ---
        self.diagnostics_dock = QDockWidget("📡 System Connection & Diagnostic Stream", self)
        self.diagnostics_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.diagnostics_dock.setFeatures(
            QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
        )
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(4, 4, 4, 4)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Connection diagnostic logs will appear here...")
        self.log_output.setStyleSheet("background-color: #1a1a1a; color: #00ff00; font-family: Consolas; font-size: 10px; border: 1px solid #333;")
        log_layout.addWidget(self.log_output)
        self.diagnostics_dock.setWidget(log_container)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.diagnostics_dock)
        self.diagnostics_dock.hide()

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Initializing...")

    def load_tabs(self):
        """Initialize and add all functional tabs in strategic order."""
        def _open_tab_by_label(label: str) -> bool:
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == label:
                    self.tabs.setCurrentIndex(i)
                    return True
            return False

        def _wrap_tab_widget(tab: QWidget) -> QScrollArea:
            """Wrap tabs so smaller windows remain usable without clipped controls."""
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            container_layout.addWidget(tab, 0, Qt.AlignTop)
            container_layout.addStretch(1)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            scroll.setWidget(container)
            return scroll

        def _add_optional_tab(
            attr_name: str,
            class_name: str,
            label: str,
            *,
            kwargs: dict | None = None,
            required: bool = False,
            wrap_in_scroll: bool = True,
        ) -> None:
            tab_class = globals().get(class_name)
            if tab_class is None:
                msg = f"{class_name} unavailable; tab '{label}' will use placeholder"
                logger.warning(msg)
                self.tabs.addTab(QLabel(f"{label} not available"), label)
                return
            try:
                tab = tab_class(**(kwargs or {}))
                setattr(self, attr_name, tab)
                self.tabs.addTab(_wrap_tab_widget(tab) if wrap_in_scroll else tab, label)
            except Exception as exc:
                logger.exception("Failed to initialize tab '%s': %s", label, exc)
                if required:
                    raise
                self.tabs.addTab(QLabel(f"{label} failed to initialize"), label)

        _add_optional_tab(
            "quick_start_tab",
            "QuickStartTab",
            "🚦 Quick Start",
            kwargs={
                "open_tab": _open_tab_by_label,
                "run_health_check": lambda: self.check_backend_status(True),
            },
            wrap_in_scroll=True,
        )
        _add_optional_tab("data_explorer_tab", "DataExplorerTab", "🔍 Data Explorer")
        _add_optional_tab("org_tab", "OrganizationTab", "📂 Organization")
        _add_optional_tab("doc_tab", "DocumentProcessingTab", "📄 Processing")
        _add_optional_tab(
            "memory_review_tab",
            "AgentMemoryManagerTab",
            "🧠 Agent Memory Manager",
            wrap_in_scroll=False,
        )
        _add_optional_tab(
            "semantic_tab",
            "SemanticAnalysisTab",
            "🧠 Semantic Analysis",
            kwargs={"asyncio_thread": self.asyncio_thread},
        )
        _add_optional_tab("entity_tab", "EntityExtractionTab", "🔍 Entities")
        _add_optional_tab("reasoning_tab", "LegalReasoningTab", "⚖️ Legal Reasoning")
        _add_optional_tab("vector_tab", "VectorSearchTab", "🔎 Vector Search")
        _add_optional_tab("pipelines_tab", "PipelinesTab", "🚀 Pipelines")
        _add_optional_tab("expert_prompts_tab", "ExpertPromptsTab", "🧑‍🏫 Expert Prompts")
        _add_optional_tab(
            "embedding_ops_tab",
            "EmbeddingOperationsTab",
            "🔩 Embeddings",
            kwargs={"asyncio_thread": self.asyncio_thread},
        )
        _add_optional_tab(
            "learning_path_tab",
            "LearningPathTab",
            "🎯 Learning Paths",
            kwargs={"asyncio_thread": self.asyncio_thread},
        )
        _add_optional_tab("classification_tab", "ClassificationTab", "🏷️ Classification")
        _add_optional_tab("contradictions_tab", "ContradictionsTab", "⚔️ Contradictions")
        _add_optional_tab("violations_tab", "ViolationsTab", "🚨 Violations")
        # Default to first-time guide tab so users land in a known workflow.
        _open_tab_by_label("🚦 Quick Start")

    def check_backend_status(self, user_initiated=False):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{ts}] INFO: Starting backend health check ({self.api_url})...")

        if self._health_check_inflight:
            self.log_output.append(f"[{ts}] INFO: Health check already in progress; skipping.")
            return

        self._health_check_inflight = True
        self._pending_health_check_user_initiated = bool(user_initiated)
        self.status_indicator.setText("Checking...")
        self.status_indicator.setStyleSheet("color: orange;")

        def _worker():
            try:
                # Keep api_client target aligned with Professional Manager base URL
                api_client.base_url = self.api_url
                response_data = api_client.get_health()
                self.backend_check_finished.emit(True, response_data)
            except Exception as e:
                self.backend_check_finished.emit(False, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_backend_check_result(self, success, data):
        self._health_check_inflight = False
        if success:
            self._consecutive_health_failures = 0
            self._update_status_ui("Backend Connected", "#00ff00", "Backend is online.")
            # Only notify tabs on initial connect/reconnect, not every periodic health check.
            if not self._backend_was_connected:
                self.on_backend_ready()
            self._backend_was_connected = True
        else:
            self._consecutive_health_failures += 1
            self._backend_was_connected = False
            self._update_status_ui(
                "Backend Unreachable",
                "red",
                f"Backend connection failed: {data}",
            )
            now = time.time()
            should_show_dialog = (
                self._pending_health_check_user_initiated
                or self._consecutive_health_failures >= 3
            )
            in_cooldown = (now - self._last_error_dialog_at) < self._dialog_cooldown_s
            if should_show_dialog and not in_cooldown:
                self._last_error_dialog_at = now
                self.show_backend_error_dialog()

    def _update_status_ui(self, label, color, message):
        self.status_indicator.setText(label)
        self.status_indicator.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.status_bar.showMessage(message, 5000)
        
        # Add to diagnostic log
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{ts}] {label}: {message}")
        # Auto-scroll to bottom
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def show_backend_error_dialog(self):
        # Ensure we only show one dialog at a time and it's not spammy
        if hasattr(self, "_error_dialog_visible") and self._error_dialog_visible:
            return
        
        self._error_dialog_visible = True
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("Backend Connection Error")
        msg_box.setText("Could not connect to the backend service.")
        msg_box.setInformativeText(f"Please ensure the backend is running at {self.api_url} and is accessible.")
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec()
        self._error_dialog_visible = False

    def on_backend_ready(self):
        """Notify all tabs that the backend is connected."""
        print("[ProfessionalManager] Backend ready. Notifying tabs...")
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            target = widget
            if isinstance(widget, QScrollArea):
                inner = widget.widget()
                if inner and inner.layout() and inner.layout().count() > 0:
                    child = inner.layout().itemAt(0).widget()
                    if child:
                        target = child
            if hasattr(target, "on_backend_ready"):
                try:
                    target.on_backend_ready()
                except Exception as e:
                    logger.exception("Error notifying tab %s on backend ready: %s", i, e)

    def toggle_diagnostics_dock(self):
        """Show/hide diagnostics without affecting tab layout geometry."""
        self.diagnostics_dock.setVisible(not self.diagnostics_dock.isVisible())

    def closeEvent(self, event):
        self._stop_asyncio_thread()
        super().closeEvent(event)

    def _stop_asyncio_thread(self):
        try:
            if getattr(self, "asyncio_thread", None):
                self.asyncio_thread.stop()
                if not self.asyncio_thread.wait(2000):
                    self.asyncio_thread.terminate()
                    self.asyncio_thread.wait(1000)
        except Exception as exc:
            logger.exception("Failed to stop asyncio thread cleanly: %s", exc)

    def __del__(self):
        self._stop_asyncio_thread()


def _handle_fatal_error(e: Exception) -> None:
    """Display fatal startup error information."""
    try:
        print(f"Fatal GUI startup error: {e}", file=sys.stderr)
        traceback.print_exc()
    except Exception as exc:
        logger.error("Failed to print fatal startup traceback: %s", exc)
    try:
        QMessageBox.critical(None, "GUI startup failed", str(e))
    except Exception as exc:
        logger.error("Failed to show fatal startup dialog: %s", exc)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Smart Document Organizer")
    app.setApplicationVersion("2.0.0")

    asyncio_thread = AsyncioThread()
    asyncio_thread.start()

    app.aboutToQuit.connect(asyncio_thread.stop)

    wsl_thread = None
    if os.getenv("GUI_SKIP_WSL_BACKEND_START", "0").lower() not in {"1", "true", "yes"}:
        wsl_thread = WslBackendThread()
    
    try:
        window = ProfessionalManager()
        
        if wsl_thread:
            # Log WSL progress to the diagnostic stream
            wsl_thread.status_update.connect(
                lambda msg: window._update_status_ui("wsl_startup", "orange", msg)
            )
            wsl_thread.failed.connect(
                lambda msg: window._update_status_ui("wsl_failed", "red", msg)
            )
            # When healthy, notify all tabs and refresh status
            wsl_thread.healthy.connect(window.on_backend_ready)
            wsl_thread.healthy.connect(lambda: window.check_backend_status(True))
            wsl_thread.start()
        else:
            # If not using WSL thread, trigger ready checks manually
            QTimer.singleShot(100, lambda: window.check_backend_status(True))

        window.show()
        rc = app.exec()

    except Exception as e:
        logger.exception("Fatal GUI startup error")
        _handle_fatal_error(e)
        rc = 1
    finally:
        # Clean up WSL thread (does NOT stop the backend)
        if wsl_thread and wsl_thread.isRunning():
            wsl_thread.requestInterruption()
            wsl_thread.wait(2000)
        
        # Stop asyncio loop
        if asyncio_thread.isRunning():
            asyncio_thread.stop()
            if not asyncio_thread.wait(2000):
                asyncio_thread.terminate()

    sys.exit(rc)


if __name__ == "__main__":
    main()
