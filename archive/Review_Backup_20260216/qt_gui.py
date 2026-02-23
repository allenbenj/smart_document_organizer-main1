#!/usr/bin/env python3
"""
File Organizer Desktop GUI - PyQt6-based interface for master organization

Provides a desktop GUI for configuring and running the file organization process.
"""

import sys
import os
import asyncio
import subprocess
import threading
from pathlib import Path
from typing import Optional

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import organization components (only when needed)
# import organizer_config
# import organizer.processor

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QProgressBar,
    QFileDialog, QGroupBox, QMessageBox, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor


class OrganizationWorker(QThread):
    """Worker thread for running organization process"""

    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    log_updated = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, source_path: str, output_path: str, dry_run: bool = False):
        super().__init__()
        self.source_path = source_path
        self.output_path = output_path
        self.dry_run = dry_run

    def run(self):
        """Run the organization process"""
        try:
            # Import here to avoid startup issues
            import organizer_config
            import organizer.processor

            self.status_updated.emit("Starting organization...")
            self.log_updated.emit("🚀 Starting file organization...")
            self.log_updated.emit(f"📂 Source: {self.source_path}")
            self.log_updated.emit(f"📂 Output: {self.output_path}")

            # Build command
            cmd = [
                sys.executable,
                str(current_dir / "master_organization_example.py"),
                "--source", self.source_path,
                "--output", self.output_path
            ]

            if self.dry_run:
                cmd.append("--dry-run")
                self.log_updated.emit("🔍 Running in preview mode...")

            self.log_updated.emit(f"Running: {' '.join(cmd)}")

            # Run the process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Read output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.log_updated.emit(output.strip())
                    # Update progress based on output (simple heuristic)
                    if "Analyzed" in output and "/" in output:
                        try:
                            parts = output.split("/")
                            if len(parts) == 2:
                                current = int(parts[0].split()[-1])
                                total = int(parts[1].split()[0])
                                progress = int((current / total) * 100)
                                self.progress_updated.emit(progress)
                        except:
                            pass

            return_code = process.poll()

            if return_code == 0:
                self.status_updated.emit("✅ Organization completed successfully!")
                self.log_updated.emit("✅ Organization completed successfully!")
                self.progress_updated.emit(100)
                self.finished_signal.emit(True, "Success")
            else:
                error_msg = f"❌ Organization failed with code {return_code}"
                self.status_updated.emit(error_msg)
                self.log_updated.emit(error_msg)
                self.finished_signal.emit(False, f"Process exited with code {return_code}")

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            self.status_updated.emit(error_msg)
            self.log_updated.emit(error_msg)
            self.finished_signal.emit(False, str(e))


class FileOrganizerGUI(QMainWindow):
    """Main GUI window for file organization"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.is_running = False

        # Set default paths
        self.source_path = str(current_dir / "test_files")
        self.output_path = str(current_dir / "organized")

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("🗂️ File Organizer - AI-Powered Organization")
        self.setGeometry(100, 100, 1000, 700)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)

        # Title
        title_label = QLabel("🗂️ File Organizer - AI-Powered Organization")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Directory selection section
        dir_group = QGroupBox("Directory Selection")
        dir_layout = QVBoxLayout()

        # Source directory
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Source Directory:"))
        self.source_edit = QLineEdit(self.source_path)
        source_layout.addWidget(self.source_edit)
        source_browse_btn = QPushButton("Browse...")
        source_browse_btn.clicked.connect(lambda: self.browse_directory("source"))
        source_layout.addWidget(source_browse_btn)
        dir_layout.addLayout(source_layout)

        # Output directory
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output Directory:"))
        self.output_edit = QLineEdit(self.output_path)
        output_layout.addWidget(self.output_edit)
        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(lambda: self.browse_directory("output"))
        output_layout.addWidget(output_browse_btn)
        dir_layout.addLayout(output_layout)

        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)

        # Control buttons
        control_layout = QHBoxLayout()

        self.preview_btn = QPushButton("🔍 Preview")
        self.preview_btn.setStyleSheet("QPushButton { background-color: #17a2b8; color: white; padding: 8px 16px; }")
        self.preview_btn.clicked.connect(self.preview_organization)
        control_layout.addWidget(self.preview_btn)

        self.run_btn = QPushButton("▶️ Run Organization")
        self.run_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; padding: 8px 16px; }")
        self.run_btn.clicked.connect(self.run_organization)
        control_layout.addWidget(self.run_btn)

        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; padding: 8px 16px; }")
        self.stop_btn.clicked.connect(self.stop_organization)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)

        layout.addLayout(control_layout)

        # Progress section
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to organize files...")
        progress_layout.addWidget(self.status_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Log section
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Set layout proportions
        layout.setStretchFactor(log_group, 1)

        # Initialize log
        self.log_message("File Organizer GUI initialized")
        self.log_message(f"Source: {self.source_path}")
        self.log_message(f"Output: {self.output_path}")

    def browse_directory(self, dir_type: str):
        """Browse for directory"""
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.Directory)

        if dialog.exec():
            selected_dir = dialog.selectedFiles()[0]
            if dir_type == "source":
                self.source_edit.setText(selected_dir)
                self.source_path = selected_dir
            else:
                self.output_edit.setText(selected_dir)
                self.output_path = selected_dir

    def preview_organization(self):
        """Run preview (dry-run)"""
        if self.is_running:
            return

        source_path = self.source_edit.text().strip()
        output_path = self.output_edit.text().strip()

        if not source_path or not os.path.exists(source_path):
            QMessageBox.warning(self, "Error", "Please select a valid source directory.")
            return

        if not output_path:
            QMessageBox.warning(self, "Error", "Please select an output directory.")
            return

        self.start_organization(source_path, output_path, dry_run=True)

    def run_organization(self):
        """Run full organization"""
        if self.is_running:
            return

        source_path = self.source_edit.text().strip()
        output_path = self.output_edit.text().strip()

        if not source_path or not os.path.exists(source_path):
            QMessageBox.warning(self, "Error", "Please select a valid source directory.")
            return

        if not output_path:
            QMessageBox.warning(self, "Error", "Please select an output directory.")
            return

        # Confirm before running
        reply = QMessageBox.question(
            self, "Confirm Organization",
            f"This will organize files from:\n{source_path}\n\nto:\n{output_path}\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.start_organization(source_path, output_path, dry_run=False)

    def start_organization(self, source_path: str, output_path: str, dry_run: bool):
        """Start the organization process"""
        self.is_running = True
        self.preview_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)

        # Create and start worker thread
        self.worker = OrganizationWorker(source_path, output_path, dry_run)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.status_updated.connect(self.status_label.setText)
        self.worker.log_updated.connect(self.log_message)
        self.worker.finished_signal.connect(self.organization_finished)
        self.worker.start()

    def stop_organization(self):
        """Stop the organization process"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
            self.organization_finished(False, "Stopped by user")

    def organization_finished(self, success: bool, message: str):
        """Handle organization completion"""
        self.is_running = False
        self.preview_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if success:
            QMessageBox.information(self, "Success", "Organization completed successfully!")
        else:
            QMessageBox.warning(self, "Error", f"Organization failed: {message}")

    def log_message(self, message: str):
        """Add message to log"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        """Handle window close event"""
        if self.is_running:
            reply = QMessageBox.question(
                self, "Confirm Exit",
                "Organization is running. Stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.stop_organization()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("File Organizer")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("File Organizer Team")

    # Create and show main window
    window = FileOrganizerGUI()
    window.show()

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()