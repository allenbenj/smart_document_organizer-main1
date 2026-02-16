"""
Diagnostics Tab - View startup logs, API communication, and track bugs

Provides visibility into system health and failure tracking.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    import sys
    _root = Path(__file__).parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from diagnostics.bug_tracker import Bug, BugTracker, get_bug_tracker
except Exception as e:
    print(f"Warning: could not import bug_tracker: {e}")
    Bug = None
    BugTracker = None
    get_bug_tracker = None


class LogViewerPanel(QWidget):
    """Panel to view log files."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logs_dir = Path("logs")
        self.init_ui()
        self.refresh_log_list()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Log Files</b>"))
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_log_list)
        header.addWidget(refresh_btn)
        header.addStretch()
        layout.addLayout(header)
        
        # Log file list
        self.log_list = QListWidget()
        self.log_list.setMaximumHeight(150)
        self.log_list.currentItemChanged.connect(self.on_log_selected)
        layout.addWidget(self.log_list)
        
        # Log content viewer
        self.log_content = QTextEdit()
        self.log_content.setReadOnly(True)
        self.log_content.setFontFamily("Consolas, Monaco, monospace")
        self.log_content.setStyleSheet("font-size: 10pt;")
        layout.addWidget(self.log_content)
        
        # Actions
        actions = QHBoxLayout()
        open_folder_btn = QPushButton("📂 Open Logs Folder")
        open_folder_btn.clicked.connect(self.open_logs_folder)
        actions.addWidget(open_folder_btn)
        
        clear_logs_btn = QPushButton("🗑️ Clear Old Logs")
        clear_logs_btn.clicked.connect(self.clear_old_logs)
        actions.addWidget(clear_logs_btn)
        actions.addStretch()
        layout.addLayout(actions)
        
    def refresh_log_list(self):
        """Refresh the list of log files."""
        self.log_list.clear()
        
        if not self.logs_dir.exists():
            self.log_content.setPlainText("No logs directory found.")
            return
            
        # Get all log files, sorted by modification time (newest first)
        log_files = sorted(
            self.logs_dir.glob("*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        for log_file in log_files:
            # Get file size
            size_kb = log_file.stat().st_size / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            
            # Get modification time
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            time_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
            
            # Add to list
            display_name = f"{log_file.name} ({size_str}) - {time_str}"
            self.log_list.addItem(display_name)
            
        if log_files:
            self.log_list.setCurrentRow(0)
        else:
            self.log_content.setPlainText("No log files found.")
            
    def on_log_selected(self, current, previous):
        """Load and display selected log file."""
        if not current:
            return
            
        # Extract filename from display name
        display_text = current.text()
        filename = display_text.split(" (")[0]
        log_file = self.logs_dir / filename
        
        if not log_file.exists():
            self.log_content.setPlainText(f"Log file not found: {log_file}")
            return
            
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
            self.log_content.setPlainText(content)
        except Exception as e:
            self.log_content.setPlainText(f"Error reading log file: {e}")
            
    def open_logs_folder(self):
        """Open logs folder in file explorer."""
        if self.logs_dir.exists():
            os.startfile(str(self.logs_dir.absolute()))
        else:
            QMessageBox.warning(self, "Not Found", "Logs directory not found.")
            
    def clear_old_logs(self):
        """Delete log files older than 7 days."""
        if not self.logs_dir.exists():
            return
            
        reply = QMessageBox.question(
            self,
            "Clear Old Logs",
            "Delete log files older than 7 days?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        cutoff = datetime.now().timestamp() - (7 * 24 * 60 * 60)
        deleted = 0
        
        for log_file in self.logs_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff:
                try:
                    log_file.unlink()
                    deleted += 1
                except Exception as e:
                    print(f"Error deleting {log_file}: {e}")
                    
        self.refresh_log_list()
        QMessageBox.information(self, "Complete", f"Deleted {deleted} old log files.")


class BugTrackerPanel(QWidget):
    """Panel to track and report bugs."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tracker = get_bug_tracker() if get_bug_tracker else None
        self.init_ui()
        self.refresh_bugs()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        if not self.tracker:
            layout.addWidget(QLabel("⚠️ Bug tracker not available"))
            return
        
        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Bug Tracker</b>"))
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_bugs)
        header.addWidget(refresh_btn)
        
        add_bug_btn = QPushButton("➕ Report Bug")
        add_bug_btn.clicked.connect(self.add_bug)
        header.addWidget(add_bug_btn)
        
        export_btn = QPushButton("📄 Export Report")
        export_btn.clicked.connect(self.export_report)
        header.addWidget(export_btn)
        
        header.addStretch()
        layout.addLayout(header)
        
        # Filter controls
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Filter:"))
        
        self.severity_filter = QComboBox()
        self.severity_filter.addItems(["All Severities", "Critical", "High", "Medium", "Low"])
        self.severity_filter.currentTextChanged.connect(self.refresh_bugs)
        filters.addWidget(self.severity_filter)
        
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Statuses", "Open", "In Progress", "Fixed", "Won't Fix"])
        self.status_filter.currentTextChanged.connect(self.refresh_bugs)
        filters.addWidget(self.status_filter)
        
        filters.addStretch()
        layout.addLayout(filters)
        
        # Bug list
        self.bug_list = QListWidget()
        self.bug_list.setMaximumHeight(200)
        self.bug_list.currentItemChanged.connect(self.on_bug_selected)
        layout.addWidget(self.bug_list)
        
        # Bug details
        self.bug_details = QTextEdit()
        self.bug_details.setReadOnly(True)
        layout.addWidget(self.bug_details)
        
        # Actions
        actions = QHBoxLayout()
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Open", "In Progress", "Fixed", "Won't Fix"])
        actions.addWidget(QLabel("Update Status:"))
        actions.addWidget(self.status_combo)
        
        update_btn = QPushButton("Update")
        update_btn.clicked.connect(self.update_bug_status)
        actions.addWidget(update_btn)
        
        actions.addStretch()
        layout.addLayout(actions)
        
    def refresh_bugs(self):
        """Refresh the bug list."""
        if not self.tracker:
            return
            
        self.bug_list.clear()
        
        # Apply filters
        severity = self.severity_filter.currentText()
        if severity == "All Severities":
            severity = None
            
        status = self.status_filter.currentText()
        if status == "All Statuses":
            status = None
            
        bugs = self.tracker.get_bugs(severity=severity, status=status)
        
        for bug in bugs:
            # Format: [SEVERITY] Title (Component) - Created
            created = datetime.fromisoformat(bug.created_at).strftime("%Y-%m-%d %H:%M")
            component = f" ({bug.component})" if bug.component else ""
            display = f"[{bug.severity}] {bug.title}{component} - {created}"
            
            item = self.bug_list.addItem(display)
            # Store bug ID in item data
            self.bug_list.item(self.bug_list.count() - 1).setData(Qt.UserRole, bug.id)
            
        if not bugs:
            self.bug_details.setPlainText("No bugs found matching filters.")
            
    def on_bug_selected(self, current, previous):
        """Display selected bug details."""
        if not current or not self.tracker:
            return
            
        bug_id = current.data(Qt.UserRole)
        bugs = [b for b in self.tracker.bugs if b.id == bug_id]
        
        if not bugs:
            return
            
        bug = bugs[0]
        
        # Format bug details
        details = []
        details.append(f"Bug ID: {bug.id}")
        details.append(f"Title: {bug.title}")
        details.append(f"Status: {bug.status}")
        details.append(f"Severity: {bug.severity}")
        details.append(f"Category: {bug.category}")
        if bug.component:
            details.append(f"Component: {bug.component}")
        details.append(f"Created: {bug.created_at}")
        details.append("")
        details.append("Description:")
        details.append(bug.description)
        
        if bug.error_message:
            details.append("")
            details.append(f"Error: {bug.error_message}")
            
        if bug.reproduction_steps:
            details.append("")
            details.append("Reproduction Steps:")
            for i, step in enumerate(bug.reproduction_steps, 1):
                details.append(f"  {i}. {step}")
                
        if bug.stack_trace:
            details.append("")
            details.append("Stack Trace:")
            details.append(bug.stack_trace)
            
        if bug.notes:
            details.append("")
            details.append("Notes:")
            for note in bug.notes:
                timestamp = note.get('timestamp', 'N/A')
                details.append(f"  [{timestamp}] {note.get('note', '')}")
                
        self.bug_details.setPlainText("\n".join(details))
        
        # Set status combo to bug's current status
        index = self.status_combo.findText(bug.status)
        if index >= 0:
            self.status_combo.setCurrentIndex(index)
            
    def add_bug(self):
        """Open dialog to add a new bug."""
        from PySide6.QtWidgets import QDialog, QFormLayout, QComboBox, QPlainTextEdit, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Report Bug")
        dialog.setMinimumWidth(600)
        
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        
        title_edit = QLineEdit()
        form.addRow("Title:", title_edit)
        
        severity_combo = QComboBox()
        severity_combo.addItems(["Critical", "High", "Medium", "Low"])
        severity_combo.setCurrentText("Medium")
        form.addRow("Severity:", severity_combo)
        
        category_combo = QComboBox()
        category_combo.addItems(["Startup", "API", "UI", "Processing", "General"])
        form.addRow("Category:", category_combo)
        
        component_edit = QLineEdit()
        form.addRow("Component:", component_edit)
        
        description_edit = QPlainTextEdit()
        description_edit.setPlaceholderText("Describe the bug...")
        description_edit.setMinimumHeight(100)
        form.addRow("Description:", description_edit)
        
        steps_edit = QPlainTextEdit()
        steps_edit.setPlaceholderText("1. First step\n2. Second step\n...")
        steps_edit.setMinimumHeight(100)
        form.addRow("Reproduction Steps:", steps_edit)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            # Parse steps
            steps_text = steps_edit.toPlainText().strip()
            steps = [s.strip() for s in steps_text.split('\n') if s.strip()] if steps_text else []
            
            # Add bug
            bug = self.tracker.add_bug(
                title=title_edit.text(),
                description=description_edit.toPlainText(),
                severity=severity_combo.currentText(),
                category=category_combo.currentText(),
                component=component_edit.text() or None,
                reproduction_steps=steps
            )
            
            self.refresh_bugs()
            QMessageBox.information(self, "Success", f"Bug {bug.id} created successfully!")
            
    def update_bug_status(self):
        """Update the status of the selected bug."""
        current = self.bug_list.currentItem()
        if not current or not self.tracker:
            return
            
        bug_id = current.data(Qt.UserRole)
        new_status = self.status_combo.currentText()
        
        success = self.tracker.update_bug_status(bug_id, new_status, f"Status changed to {new_status}")
        
        if success:
            self.refresh_bugs()
            QMessageBox.information(self, "Success", f"Bug {bug_id} updated to {new_status}")
        else:
            QMessageBox.warning(self, "Error", f"Failed to update bug {bug_id}")
            
    def export_report(self):
        """Export bugs to markdown report."""
        if not self.tracker:
            return
            
        try:
            report_path = self.tracker.export_report()
            QMessageBox.information(self, "Success", f"Bug report exported to:\n{report_path}")
            
            # Offer to open
            reply = QMessageBox.question(self, "Open Report", "Do you want to open the report?")
            if reply == QMessageBox.Yes:
                os.startfile(report_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export report: {e}")


class DiagnosticsTab(QWidget):
    """Main diagnostics tab with logs and bug tracking."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("<h2>🔍 System Diagnostics</h2>")
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "View startup logs, API communication, track bugs, and monitor system health.\n"
            "Use this tab to troubleshoot startup failures and document issues."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Splitter for logs and bugs
        splitter = QSplitter(Qt.Vertical)
        
        # Log viewer
        log_group = QGroupBox("📋 Logs")
        log_layout = QVBoxLayout(log_group)
        self.log_viewer = LogViewerPanel()
        log_layout.addWidget(self.log_viewer)
        splitter.addWidget(log_group)
        
        # Bug tracker
        bug_group = QGroupBox("🐛 Bugs")
        bug_layout = QVBoxLayout(bug_group)
        self.bug_tracker = BugTrackerPanel()
        bug_layout.addWidget(self.bug_tracker)
        splitter.addWidget(bug_group)
        
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)
