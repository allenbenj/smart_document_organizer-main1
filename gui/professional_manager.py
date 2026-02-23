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
from datetime import datetime
from pathlib import Path

# Add project root to python path to ensure imports work correctly
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.backend_runtime import backend_base_url

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QTabWidget, QStatusBar, QMessageBox, QPushButton, QTextEdit
    )
    from PySide6.QtCore import Qt, QTimer, QSize, Signal
    from PySide6.QtGui import QIcon, QFont, QAction
except ImportError:
    print("PySide6 is required. Please install it with: pip install PySide6")
    sys.exit(1)

# Import Tabs
# We wrap imports in try/except to handle missing dependencies gracefully during dev
try:
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
    from gui.memory_review_tab import MemoryReviewTab
    from gui.contradictions_tab import ContradictionsTab
    from gui.violations_tab import ViolationsTab
except ImportError as e:
    print(f"Error importing tabs: {e}")
    # We will handle missing tabs in the class

from gui.core import AsyncioThread
from utils.backend_runtime import backend_base_url
from gui.services import api_client

# Professional Dark Theme (Consistent with DB Monitor)
DARK_STYLESHEET = """
QMainWindow {
    background-color: #1e1e1e;
    color: #ffffff;
}
QWidget {
    background-color: #1e1e1e;
    color: #ffffff;
}
QGroupBox {
    border: 1px solid #3e3e3e;
    border-radius: 5px;
    margin-top: 10px;
    font-weight: bold;
    color: #4dabf7;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 3px;
}
QTableWidget {
    background-color: #252526;
    gridline-color: #3e3e3e;
    border: 1px solid #3e3e3e;
    color: #e0e0e0;
    selection-background-color: #264f78;
}
QHeaderView::section {
    background-color: #333333;
    color: #ffffff;
    padding: 4px;
    border: 1px solid #3e3e3e;
}
QTableWidget::item:selected {
    background-color: #264f78;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #252526;
    border: 1px solid #3e3e3e;
    color: #e0e0e0;
    padding: 4px;
    font-family: Consolas, monospace;
}
QPushButton {
    background-color: #0e639c;
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: 3px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #1177bb;
}
QPushButton:pressed {
    background-color: #094771;
}
QPushButton:disabled {
    background-color: #333333;
    color: #888888;
}
QComboBox {
    background-color: #252526;
    border: 1px solid #3e3e3e;
    color: #e0e0e0;
    padding: 4px;
}
QComboBox::drop-down {
    border: none;
}
QStatusBar {
    background-color: #007acc;
    color: white;
}
QTabWidget::pane {
    border: 1px solid #3e3e3e;
}
QTabBar::tab {
    background: #2d2d2d;
    color: #cccccc;
    padding: 8px 12px;
    border: 1px solid #3e3e3e;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background: #1e1e1e;
    color: #ffffff;
    border-bottom: 1px solid #1e1e1e; 
}
QTabBar::tab:hover {
    background: #3e3e3e;
}
QLabel#Heading {
    font-size: 16px;
    font-weight: bold;
    color: #4dabf7;
}
"""

class ProfessionalManager(QMainWindow):
    backend_check_finished = Signal(bool, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Document Organizer - Professional Manager")
        self.resize(1400, 900)
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
        self.setStyleSheet(DARK_STYLESHEET)

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
        
        main_layout.addLayout(top_bar)

        # --- Main Tabs (Wrapped in ScrollArea for responsiveness) ---
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self.tabs = QTabWidget()
        self.load_tabs()
        scroll.setWidget(self.tabs)
        main_layout.addWidget(scroll)

        # --- Diagnostic Log ---
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(100)
        self.log_output.setPlaceholderText("Connection diagnostic logs will appear here...")
        self.log_output.setStyleSheet("background-color: #1a1a1a; color: #aaa; font-family: Consolas; font-size: 10px;")
        main_layout.addWidget(self.log_output)

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Initializing...")

    def load_tabs(self):
        """Initialize and add all functional tabs."""
        # 1. Organization
        try:
            self.org_tab = OrganizationTab()
            self.tabs.addTab(self.org_tab, "📂 Organization")
        except NameError:
            self.tabs.addTab(QLabel("Organization Tab not available"), "📂 Organization")

        # 2. Document Processing
        try:
            self.doc_tab = DocumentProcessingTab()
            self.tabs.addTab(self.doc_tab, "📄 Processing")
        except NameError:
            self.tabs.addTab(QLabel("Processing Tab not available"), "📄 Processing")

        # 3. Semantic Analysis
        try:
            self.semantic_tab = SemanticAnalysisTab(asyncio_thread=self.asyncio_thread)
            self.tabs.addTab(self.semantic_tab, "🧠 Semantic Analysis")
        except NameError:
            self.tabs.addTab(QLabel("Semantic Analysis Tab not available"), "🧠 Semantic Analysis")

        # 4. Entity Extraction
        try:
            self.entity_tab = EntityExtractionTab()
            self.tabs.addTab(self.entity_tab, "🔍 Entities")
        except NameError:
            self.tabs.addTab(QLabel("Entity Tab not available"), "🔍 Entities")

        # 5. Legal Reasoning
        try:
            self.reasoning_tab = LegalReasoningTab()
            self.tabs.addTab(self.reasoning_tab, "⚖️ Legal Reasoning")
        except NameError:
            self.tabs.addTab(QLabel("Reasoning Tab not available"), "⚖️ Legal Reasoning")

        # 6. Knowledge Graph
        try:
            self.kg_tab = KnowledgeGraphTab(asyncio_thread=self.asyncio_thread)
            self.tabs.addTab(self.kg_tab, "🕸️ Knowledge Graph")
        except NameError:
            self.tabs.addTab(QLabel("KG Tab not available"), "🕸️ Knowledge Graph")

        # 7. Vector Search
        try:
            self.vector_tab = VectorSearchTab()
            self.tabs.addTab(self.vector_tab, "🔎 Vector Search")
        except NameError:
            self.tabs.addTab(QLabel("Vector Tab not available"), "🔎 Vector Search")
            
        # 8. Pipelines
        try:
            self.pipelines_tab = PipelinesTab()
            self.tabs.addTab(self.pipelines_tab, "🚀 Pipelines")
        except NameError:
            pass

        # 9. Expert Prompts
        try:
            self.expert_prompts_tab = ExpertPromptsTab()
            self.tabs.addTab(self.expert_prompts_tab, "🧑‍🏫 Expert Prompts")
        except NameError:
            self.tabs.addTab(QLabel("Expert Prompts Tab not available"), "🧑‍🏫 Expert Prompts")

        # 10. Embedding Operations
        try:
            self.embedding_ops_tab = EmbeddingOperationsTab(self.asyncio_thread)
            self.tabs.addTab(self.embedding_ops_tab, "🔩 Embeddings")
        except NameError:
            self.tabs.addTab(QLabel("Embedding Tab not available"), "🔩 Embeddings")

        # 11. Classification
        try:
            self.classification_tab = ClassificationTab()
            self.tabs.addTab(self.classification_tab, "🏷️ Classification")
        except NameError:
            self.tabs.addTab(QLabel("Classification Tab not available"), "🏷️ Classification")

        # 12. Contradictions
        try:
            self.contradictions_tab = ContradictionsTab()
            self.tabs.addTab(self.contradictions_tab, "⚔️ Contradictions")
        except NameError:
            self.tabs.addTab(QLabel("Contradictions Tab not available"), "⚔️ Contradictions")

        # 13. Violations
        try:
            self.violations_tab = ViolationsTab()
            self.tabs.addTab(self.violations_tab, "🚨 Violations")
        except NameError:
            self.tabs.addTab(QLabel("Violations Tab not available"), "🚨 Violations")

        # 14. Memory Review
        try:
            self.memory_review_tab = MemoryReviewTab()
            self.tabs.addTab(self.memory_review_tab, "🧠 Memory Review")
        except NameError:
            self.tabs.addTab(QLabel("Memory Review Tab not available"), "🧠 Memory Review")

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
            if hasattr(widget, "on_backend_ready"):
                try:
                    widget.on_backend_ready()
                except Exception as e:
                    print(f"Error notifying tab {i}: {e}")

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
        except Exception:
            pass

    def __del__(self):
        self._stop_asyncio_thread()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProfessionalManager()
    window.show()
    sys.exit(app.exec())
