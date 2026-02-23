"""
System Tray Icon - Background Operations Monitor

A production-ready system tray implementation that provides:
- Background monitoring of TaskMasterService job queue
- Real-time notifications when documents are processed
- Quick access menu for common actions
- System status indicators

Integration: Add to gui_dashboard.py on startup
"""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime

try:
    from PySide6.QtWidgets import (
        QSystemTrayIcon, QMenu, QApplication, QMessageBox
    )
    from PySide6.QtCore import QTimer, Qt, QThread, Signal
    from PySide6.QtGui import QIcon, QAction, QPixmap
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QSystemTrayIcon = QMenu = QAction = object
    Signal = lambda *args: None


class JobMonitorWorker(QThread):
    """Background thread for monitoring job queue."""
    
    job_status_changed = Signal(dict)  # {pending, running, completed, failed}
    job_completed = Signal(str)  # job_name
    job_failed = Signal(str, str)  # job_name, error_message
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.last_status = None
    
    def run(self):
        """Poll TaskMasterService every 5 seconds."""
        while self.running:
            try:
                # Get job statistics
                stats = self.get_job_statistics()
                
                # Check if status changed
                if stats != self.last_status:
                    self.job_status_changed.emit(stats)
                    
                    # Detect completions
                    if self.last_status:
                        new_completed = stats['completed'] - self.last_status.get('completed', 0)
                        new_failed = stats['failed'] - self.last_status.get('failed', 0)
                        
                        if new_completed > 0:
                            self.job_completed.emit(f"{new_completed} job(s)")
                        
                        if new_failed > 0:
                            self.job_failed.emit(f"{new_failed} job(s)", "Check logs for details")
                    
                    self.last_status = stats
                
            except Exception as e:
                print(f"Job monitor error: {e}")
            
            # Sleep 5 seconds
            self.msleep(5000)
    
    def get_job_statistics(self) -> dict:
        """Get current job queue statistics."""
        try:
            # Try API endpoint first (faster)
            import requests
            response = requests.get(
                "http://127.0.0.1:8000/api/taskmaster/stats",
                timeout=2
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        
        # Fallback: Direct service access
        try:
            from services.taskmaster_service import TaskMasterService
            
            jobs = TaskMasterService.get_all_jobs()
            
            return {
                'pending': sum(1 for j in jobs if j.get('status') == 'pending'),
                'running': sum(1 for j in jobs if j.get('status') == 'running'),
                'completed': sum(1 for j in jobs if j.get('status') == 'completed'),
                'failed': sum(1 for j in jobs if j.get('status') == 'failed'),
                'total': len(jobs)
            }
        except Exception:
            # Service not available
            return {
                'pending': 0,
                'running': 0,
                'completed': 0,
                'failed': 0,
                'total': 0
            }
    
    def stop(self):
        """Stop the monitoring thread."""
        self.running = False


class DocumentOrganizerTrayIcon(QSystemTrayIcon):
    """
    System tray icon for Smart Document Organizer.
    
    Features:
    - Background job monitoring
    - System notifications
    - Quick access menu
    - Status indicators (idle/processing/error)
    """
    
    def __init__(self, main_window=None):
        # Create default icon (you should replace with actual icon file)
        icon = self.create_default_icon()
        super().__init__(icon, main_window)
        
        self.main_window = main_window
        self.icon_idle = icon
        self.icon_processing = self.create_processing_icon()
        self.icon_error = self.create_error_icon()
        
        # Current status
        self.current_stats = {
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
            'total': 0
        }
        
        # Setup menu
        self.setup_menu()
        
        # Setup monitoring
        self.monitor_worker = JobMonitorWorker()
        self.monitor_worker.job_status_changed.connect(self.on_job_status_changed)
        self.monitor_worker.job_completed.connect(self.on_job_completed)
        self.monitor_worker.job_failed.connect(self.on_job_failed)
        self.monitor_worker.start()
        
        # Handle clicks
        self.activated.connect(self.on_tray_activated)
        
        # Show the tray icon
        self.show()
        
        # Welcome notification
        self.showMessage(
            "Smart Document Organizer",
            "Running in background. Right-click for options.",
            QSystemTrayIcon.Information,
            3000
        )
    
    def setup_menu(self):
        """Create the context menu."""
        menu = QMenu()
        
        # Status display (non-clickable)
        self.status_action = QAction("✅ Idle - 0 jobs pending", self)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)
        
        menu.addSeparator()
        
        # Quick actions
        quick_import_action = QAction("📁 Quick Import...", self)
        quick_import_action.triggered.connect(self.quick_import)
        menu.addAction(quick_import_action)
        
        global_search_action = QAction("🔍 Global Search", self)
        global_search_action.setShortcut("Ctrl+K")
        global_search_action.triggered.connect(self.open_global_search)
        menu.addAction(global_search_action)
        
        menu.addSeparator()
        
        # Main window controls
        show_action = QAction("📊 Show Dashboard", self)
        show_action.triggered.connect(self.show_main_window)
        menu.addAction(show_action)
        
        hide_action = QAction("🙈 Hide Dashboard", self)
        hide_action.triggered.connect(self.hide_main_window)
        menu.addAction(hide_action)
        
        menu.addSeparator()
        
        # Settings
        settings_action = QAction("⚙️ Settings...", self)
        settings_action.triggered.connect(self.open_settings)
        menu.addAction(settings_action)
        
        # About
        about_action = QAction("ℹ️ About", self)
        about_action.triggered.connect(self.show_about)
        menu.addAction(about_action)
        
        menu.addSeparator()
        
        # Quit
        quit_action = QAction("❌ Quit", self)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(quit_action)
        
        self.setContextMenu(menu)
    
    def on_job_status_changed(self, stats: dict):
        """Handle job status changes."""
        self.current_stats = stats
        
        pending = stats.get('pending', 0)
        running = stats.get('running', 0)
        failed = stats.get('failed', 0)
        
        # Update status text
        if running > 0:
            self.status_action.setText(f"⏳ Processing - {running} active, {pending} queued")
            self.setIcon(self.icon_processing)
            self.setToolTip(f"Smart Document Organizer - Processing {running} job(s)")
        elif pending > 0:
            self.status_action.setText(f"⏸️ Pending - {pending} job(s) waiting")
            self.setIcon(self.icon_idle)
            self.setToolTip(f"Smart Document Organizer - {pending} job(s) pending")
        elif failed > 0:
            self.status_action.setText(f"⚠️ Issues - {failed} job(s) failed")
            self.setIcon(self.icon_error)
            self.setToolTip(f"Smart Document Organizer - {failed} job(s) failed")
        else:
            self.status_action.setText("✅ Idle - 0 jobs pending")
            self.setIcon(self.icon_idle)
            self.setToolTip("Smart Document Organizer - Idle")
    
    def on_job_completed(self, job_name: str):
        """Show notification when job completes."""
        self.showMessage(
            "Job Completed",
            f"✅ {job_name} processed successfully",
            QSystemTrayIcon.Information,
            4000
        )
    
    def on_job_failed(self, job_name: str, error_message: str):
        """Show notification when job fails."""
        self.showMessage(
            "Job Failed",
            f"❌ {job_name} failed: {error_message}",
            QSystemTrayIcon.Critical,
            5000
        )
    
    def on_tray_activated(self, reason):
        """Handle tray icon activation (clicks)."""
        if reason == QSystemTrayIcon.DoubleClick:
            # Double-click: Show main window
            self.show_main_window()
        elif reason == QSystemTrayIcon.Trigger:
            # Single click on some platforms
            pass  # Context menu will show automatically
    
    def quick_import(self):
        """Open quick file import dialog."""
        if self.main_window:
            # Show main window
            self.show_main_window()
            
            # Switch to Document Processing tab
            if hasattr(self.main_window, 'tab_widget'):
                for i in range(self.main_window.tab_widget.count()):
                    if "Document Processing" in self.main_window.tab_widget.tabText(i):
                        self.main_window.tab_widget.setCurrentIndex(i)
                        
                        # Trigger file dialog
                        tab = self.main_window.tab_widget.widget(i)
                        if hasattr(tab, 'add_files'):
                            tab.add_files()
                        break
    
    def open_global_search(self):
        """Open global search dialog."""
        if self.main_window and hasattr(self.main_window, 'show_global_search'):
            self.show_main_window()
            self.main_window.show_global_search()
    
    def show_main_window(self):
        """Show and activate the main window."""
        if self.main_window:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
    
    def hide_main_window(self):
        """Hide the main window (minimize to tray)."""
        if self.main_window:
            self.main_window.hide()
    
    def open_settings(self):
        """Open settings dialog."""
        if self.main_window:
            self.show_main_window()
            # TODO: Open settings dialog
            QMessageBox.information(
                self.main_window,
                "Settings",
                "Settings dialog not yet implemented.\n\nComing soon!"
            )
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            None,
            "About Smart Document Organizer",
            """
            <h3>Smart Document Organizer</h3>
            <p><b>Version:</b> 2.0</p>
            <p><b>Build Date:</b> February 2026</p>
            <br>
            <p>A professional-grade document management and analysis system
            with AI-powered organization, semantic search, and entity extraction.</p>
            <br>
            <p><b>Features:</b></p>
            <ul>
                <li>Automated document classification</li>
                <li>Vector-based semantic search</li>
                <li>Entity extraction and analysis</li>
                <li>Background job processing</li>
                <li>Multi-format support (PDF, DOCX, TXT, MD)</li>
            </ul>
            """
        )
    
    def quit_application(self):
        """Quit the entire application."""
        reply = QMessageBox.question(
            None,
            "Quit Application",
            "Are you sure you want to quit?\n\nAll background monitoring will stop.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Stop monitoring
            self.monitor_worker.stop()
            self.monitor_worker.wait()
            
            # Quit application
            QApplication.quit()
    
    @staticmethod
    def create_default_icon() -> QIcon:
        """Create a default icon (idle state)."""
        # Create a simple colored pixmap
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        
        from PySide6.QtGui import QPainter, QColor, QPen
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw a green circle (idle)
        painter.setBrush(QColor(76, 175, 80))  # Green
        painter.setPen(QPen(QColor(56, 142, 60), 2))
        painter.drawEllipse(8, 8, 48, 48)
        
        # Draw document icon
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(QPen(QColor(76, 175, 80), 1))
        painter.drawRect(20, 20, 24, 28)
        
        painter.end()
        
        return QIcon(pixmap)
    
    @staticmethod
    def create_processing_icon() -> QIcon:
        """Create processing state icon (blue)."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        
        from PySide6.QtGui import QPainter, QColor, QPen
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw a blue circle (processing)
        painter.setBrush(QColor(33, 150, 243))  # Blue
        painter.setPen(QPen(QColor(25, 118, 210), 2))
        painter.drawEllipse(8, 8, 48, 48)
        
        # Draw progress indicator
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(24, 24, 16, 16)
        
        painter.end()
        
        return QIcon(pixmap)
    
    @staticmethod
    def create_error_icon() -> QIcon:
        """Create error state icon (red)."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        
        from PySide6.QtGui import QPainter, QColor, QPen
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw a red circle (error)
        painter.setBrush(QColor(244, 67, 54))  # Red
        painter.setPen(QPen(QColor(211, 47, 47), 2))
        painter.drawEllipse(8, 8, 48, 48)
        
        # Draw X
        painter.setPen(QPen(QColor(255, 255, 255), 4))
        painter.drawLine(24, 24, 40, 40)
        painter.drawLine(40, 24, 24, 40)
        
        painter.end()
        
        return QIcon(pixmap)
    
    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'monitor_worker'):
            self.monitor_worker.stop()
            self.monitor_worker.wait()


# Example integration
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QMainWindow, QLabel
    
    class TestMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Main Window")
            self.resize(800, 600)
            
            label = QLabel("Main window content.\nMinimize to see system tray.", self)
            label.setAlignment(Qt.AlignCenter)
            self.setCentralWidget(label)
    
    app = QApplication(sys.argv)
    
    # Check if system tray is available
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(
            None,
            "System Tray Error",
            "System tray is not available on this system."
        )
        sys.exit(1)
    
    # Create main window
    window = TestMainWindow()
    window.show()
    
    # Create tray icon
    tray = DocumentOrganizerTrayIcon(window)
    
    # Make sure app doesn't quit when window is closed
    app.setQuitOnLastWindowClosed(False)
    
    sys.exit(app.exec())
