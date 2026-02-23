# PyQt6/PySide6 Advanced Capabilities Guide
## Smart Document Organizer - Enhanced GUI Features

**Date**: 2026-02-16  
**Context**: Your application has 26 production services, but several lack GUI exposure. This guide shows PyQt6/PySide6 advanced features that would leverage your architecture's full potential.

---

## 📊 Current GUI Status

### ✅ Already Implemented (Excellent Work!)
- **Document Preview Widget**: PDF/DOCX/Text/Markdown (498 lines)
- **Interactive Stats Dashboard**: Plotly charts + QWebEngineView (600 lines)
- **Drag & Drop**: File upload in Document Processing Tab
- **Multi-pane Layouts**: QSplitter throughout
- **Network Graphs**: Ontology visualization
- **15+ Tabs**: Comprehensive coverage
- **System Health Monitoring**: Real-time status strip
- **NLP Model Manager**: Model lifecycle UI

### ❌ Missing Features (High-Value Opportunities)
1. **System Tray Icon** - Background monitoring
2. **Real-Time File Watcher** - Auto-import from watched folders
3. **Global Search Interface** - Leveraging `search_service.py`
4. **Job Queue Visualizer** - Exposing `taskmaster_service.py`
5. **Timeline Visualization** - Document processing history
6. **File Tagging UI** - Exposing `file_tagging_rules.py`
7. **Document Relationship Network** - Doc-to-doc connections
8. **Webhook Dashboard** - Exposing `workflow_webhook_service.py`

---

## 🚀 Advanced PyQt6 Features (Priority Order)

### 1. **QSystemTrayIcon - Background Operations Monitor** ⭐⭐⭐⭐⭐
**Value**: Run app in background, get notifications when documents are processed.

**Use Case**: 
- Monitor `taskmaster_service.py` job queue
- Show notifications when processing completes
- Quick access menu (File Import, Search, Settings)
- Indicator for pending tasks

**Implementation Complexity**: Low (2-3 hours)

```python
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction

class DocumentOrganizerTray(QSystemTrayIcon):
    def __init__(self, parent=None):
        super().__init__(QIcon("icon.png"), parent)
        
        # Context menu
        menu = QMenu()
        
        # Quick actions
        quick_import = QAction("📁 Quick Import...", self)
        quick_import.triggered.connect(self.show_import_dialog)
        menu.addAction(quick_import)
        
        search_action = QAction("🔍 Global Search", self)
        search_action.triggered.connect(self.show_search)
        menu.addAction(search_action)
        
        menu.addSeparator()
        
        # Status display
        self.status_action = QAction("✅ Idle - 0 jobs pending", self)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)
        
        menu.addSeparator()
        
        # Show/Quit
        show_action = QAction("Show Dashboard", self)
        show_action.triggered.connect(parent.show)
        menu.addAction(show_action)
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)
        
        self.setContextMenu(menu)
        
        # Update every 10 seconds
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_job_count)
        self.timer.start(10000)
    
    def update_job_count(self):
        """Poll TaskMasterService for pending jobs."""
        try:
            from services.taskmaster_service import TaskMasterService
            pending = TaskMasterService.get_pending_jobs_count()
            
            if pending > 0:
                self.status_action.setText(f"⏳ Processing - {pending} jobs")
                self.setIcon(QIcon("icon_busy.png"))
            else:
                self.status_action.setText("✅ Idle - 0 jobs")
                self.setIcon(QIcon("icon.png"))
        except Exception as e:
            self.status_action.setText(f"⚠️ Error: {str(e)}")
    
    def show_notification(self, title, message):
        """Show system notification."""
        self.showMessage(title, message, QSystemTrayIcon.Information, 5000)
```

**Integration Points**:
- `services/taskmaster_service.py` - Job queue monitoring
- `gui/gui_dashboard.py` - Add tray icon on startup

---

### 2. **QFileSystemWatcher - Auto-Import from Watched Folders** ⭐⭐⭐⭐⭐
**Value**: Automatically detect new documents in specified folders and import them.

**Use Case**:
- Watch `E:\Organization_Folder\02_Working_Folder\` for new files
- Auto-trigger `file_ingest_pipeline.py` on detection
- Show toast notifications via system tray
- Configurable watch rules (file types, delay)

**Implementation Complexity**: Medium (4-6 hours)

```python
from PySide6.QtCore import QFileSystemWatcher, QTimer
from pathlib import Path
import time

class SmartFileWatcher(QObject):
    file_detected = Signal(str)  # Emits file path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.watcher = QFileSystemWatcher()
        self.watcher.directoryChanged.connect(self.on_directory_changed)
        
        # Debounce mechanism (avoid triggering on partial writes)
        self.pending_files = {}  # {path: detection_time}
        self.debounce_timer = QTimer()
        self.debounce_timer.timeout.connect(self.process_pending_files)
        self.debounce_timer.start(2000)  # Check every 2 seconds
    
    def add_watch_path(self, path: str):
        """Add a directory to watch."""
        if Path(path).is_dir():
            self.watcher.addPath(path)
            print(f"👁️ Now watching: {path}")
    
    def on_directory_changed(self, directory: str):
        """Directory changed - scan for new files."""
        dir_path = Path(directory)
        
        for file_path in dir_path.glob("*"):
            if file_path.is_file() and not file_path.name.startswith('.'):
                # Add to pending (will process after 3 seconds of no changes)
                self.pending_files[str(file_path)] = time.time()
    
    def process_pending_files(self):
        """Process files that haven't changed for 3+ seconds."""
        current_time = time.time()
        stable_files = []
        
        for file_path, detection_time in list(self.pending_files.items()):
            if current_time - detection_time >= 3.0:
                stable_files.append(file_path)
                del self.pending_files[file_path]
        
        for file_path in stable_files:
            self.file_detected.emit(file_path)
            self.auto_import_file(file_path)
    
    def auto_import_file(self, file_path: str):
        """Trigger file ingestion pipeline."""
        try:
            from services.file_ingest_pipeline import FileIngestPipeline
            
            # Run in background thread
            worker = IngestWorker(file_path)
            worker.finished.connect(lambda: self.notify_success(file_path))
            worker.error.connect(lambda e: self.notify_error(file_path, e))
            worker.start()
            
        except Exception as e:
            print(f"Auto-import failed for {file_path}: {e}")
    
    def notify_success(self, file_path: str):
        """Show success notification."""
        if hasattr(self.parent(), 'tray_icon'):
            self.parent().tray_icon.showMessage(
                "Document Imported",
                f"✅ {Path(file_path).name}",
                QSystemTrayIcon.Information,
                3000
            )
```

**Integration Points**:
- `services/file_ingest_pipeline.py` - Auto-process detected files
- `config/configuration_manager.py` - Store watch paths
- GUI Settings tab - Manage watch folders

---

### 3. **Custom Widget: Global Search Interface** ⭐⭐⭐⭐⭐
**Value**: Expose `search_service.py` with full-text search across all documents.

**Use Case**:
- Command palette style search (Ctrl+K hotkey)
- Search file content, metadata, entities
- Real-time results as you type
- Jump to document preview
- Integration with vector similarity

**Implementation Complexity**: Medium (5-7 hours)

```python
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QVBoxLayout
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence

class GlobalSearchDialog(QDialog):
    """
    Command palette style global search.
    
    Features:
    - Fuzzy search across all indexed documents
    - Real-time results with debouncing
    - Keyboard navigation (Up/Down/Enter)
    - Preview pane on selection
    - Jump to document action
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Search")
        self.setModal(False)
        self.resize(800, 600)
        
        # Make it float above main window
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        
        layout = QVBoxLayout(self)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search documents, entities, or content...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                font-size: 16px;
                padding: 12px;
                border: 2px solid #2196F3;
                border-radius: 8px;
            }
        """)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        layout.addWidget(self.search_input)
        
        # Results list
        self.results_list = QListWidget()
        self.results_list.itemActivated.connect(self.open_document)
        layout.addWidget(self.results_list)
        
        # Debounce timer
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        
        # Keyboard shortcuts
        self.search_input.returnPressed.connect(self.open_selected_document)
        
        # ESC to close
        close_shortcut = QShortcut(QKeySequence("Esc"), self)
        close_shortcut.activated.connect(self.close)
    
    def on_search_text_changed(self, text: str):
        """Debounce search (wait for user to stop typing)."""
        self.search_timer.stop()
        if len(text) >= 2:
            self.search_timer.start(300)  # Wait 300ms
        else:
            self.results_list.clear()
    
    def perform_search(self):
        """Execute search via SearchService."""
        query = self.search_input.text()
        
        try:
            from services.search_service import SearchService
            from services.vector_store_service import VectorStoreService
            
            # Combined search: Full-text + Vector similarity
            text_results = SearchService.search_content(query, limit=10)
            vector_results = VectorStoreService.similarity_search(query, k=5)
            
            # Merge and deduplicate
            all_results = self.merge_results(text_results, vector_results)
            
            # Display
            self.results_list.clear()
            for result in all_results:
                item_text = f"📄 {result['filename']} - {result['snippet'][:100]}..."
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, result['file_path'])
                self.results_list.addItem(item)
            
            if not all_results:
                self.results_list.addItem("No results found")
        
        except Exception as e:
            self.results_list.clear()
            self.results_list.addItem(f"Search error: {e}")
    
    def open_selected_document(self):
        """Open the selected document."""
        current_item = self.results_list.currentItem()
        if current_item:
            file_path = current_item.data(Qt.UserRole)
            if file_path:
                self.open_document(file_path)
    
    def open_document(self, file_path: str):
        """Open document in main window preview."""
        self.close()
        
        # Signal to main window to show document
        if hasattr(self.parent(), 'show_document_preview'):
            self.parent().show_document_preview(file_path)
    
    def merge_results(self, text_results, vector_results):
        """Merge and deduplicate search results."""
        seen = set()
        merged = []
        
        for result in text_results + vector_results:
            path = result.get('file_path')
            if path and path not in seen:
                seen.add(path)
                merged.append(result)
        
        return merged


# Usage in main window:
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Global search hotkey (Ctrl+K)
        search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        search_shortcut.activated.connect(self.show_global_search)
        
        self.search_dialog = None
    
    def show_global_search(self):
        """Show global search dialog."""
        if not self.search_dialog:
            self.search_dialog = GlobalSearchDialog(self)
        
        self.search_dialog.show()
        self.search_dialog.search_input.setFocus()
```

**Integration Points**:
- `services/search_service.py` - Text search
- `services/vector_store_service.py` - Semantic search
- `services/file_index_service.py` - Indexed metadata

---

### 4. **Custom Widget: Job Queue Visualizer** ⭐⭐⭐⭐
**Value**: Expose `taskmaster_service.py` for visual job management.

**Use Case**:
- See all pending/running/completed jobs
- Progress bars for each job
- Cancel/retry actions
- Log viewer per job
- Performance metrics (jobs/hour, avg time)

**Implementation Complexity**: Medium (6-8 hours)

```python
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, 
                               QTableWidgetItem, QPushButton, QHBoxLayout,
                               QHeaderView, QProgressBar)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor

class JobQueueVisualizerTab(QWidget):
    """
    Real-time visualization of TaskMasterService job queue.
    
    Features:
    - Live table of all jobs (pending/running/completed/failed)
    - Progress indicators
    - Job actions (cancel, retry, view logs)
    - Charts (processing time distribution, throughput)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
        # Auto-refresh every 2 seconds
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_job_list)
        self.refresh_timer.start(2000)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header with stats
        stats_layout = QHBoxLayout()
        
        self.pending_label = QLabel("⏳ Pending: 0")
        self.running_label = QLabel("▶️ Running: 0")
        self.completed_label = QLabel("✅ Completed: 0")
        self.failed_label = QLabel("❌ Failed: 0")
        
        stats_layout.addWidget(self.pending_label)
        stats_layout.addWidget(self.running_label)
        stats_layout.addWidget(self.completed_label)
        stats_layout.addWidget(self.failed_label)
        stats_layout.addStretch()
        
        layout.addLayout(stats_layout)
        
        # Job table
        self.job_table = QTableWidget()
        self.job_table.setColumnCount(7)
        self.job_table.setHorizontalHeaderLabels([
            "Job ID", "Type", "Status", "Progress", "Start Time", "Duration", "Actions"
        ])
        self.job_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.job_table)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.clicked.connect(self.refresh_job_list)
        button_layout.addWidget(self.refresh_button)
        
        self.clear_completed_button = QPushButton("🗑️ Clear Completed")
        self.clear_completed_button.clicked.connect(self.clear_completed_jobs)
        button_layout.addWidget(self.clear_completed_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
    
    def refresh_job_list(self):
        """Fetch and display current jobs from TaskMasterService."""
        try:
            from services.taskmaster_service import TaskMasterService
            
            jobs = TaskMasterService.get_all_jobs()
            
            # Update stats
            pending = sum(1 for j in jobs if j['status'] == 'pending')
            running = sum(1 for j in jobs if j['status'] == 'running')
            completed = sum(1 for j in jobs if j['status'] == 'completed')
            failed = sum(1 for j in jobs if j['status'] == 'failed')
            
            self.pending_label.setText(f"⏳ Pending: {pending}")
            self.running_label.setText(f"▶️ Running: {running}")
            self.completed_label.setText(f"✅ Completed: {completed}")
            self.failed_label.setText(f"❌ Failed: {failed}")
            
            # Update table
            self.job_table.setRowCount(len(jobs))
            
            for row, job in enumerate(jobs):
                # Job ID
                self.job_table.setItem(row, 0, QTableWidgetItem(job['id'][:8]))
                
                # Type
                self.job_table.setItem(row, 1, QTableWidgetItem(job['type']))
                
                # Status with color
                status_item = QTableWidgetItem(job['status'].upper())
                if job['status'] == 'completed':
                    status_item.setBackground(QColor(76, 175, 80, 100))
                elif job['status'] == 'failed':
                    status_item.setBackground(QColor(244, 67, 54, 100))
                elif job['status'] == 'running':
                    status_item.setBackground(QColor(33, 150, 243, 100))
                self.job_table.setItem(row, 2, status_item)
                
                # Progress bar
                progress_widget = QWidget()
                progress_layout = QHBoxLayout(progress_widget)
                progress_layout.setContentsMargins(0, 0, 0, 0)
                
                progress_bar = QProgressBar()
                progress_bar.setValue(int(job.get('progress', 0)))
                progress_layout.addWidget(progress_bar)
                
                self.job_table.setCellWidget(row, 3, progress_widget)
                
                # Start time
                self.job_table.setItem(row, 4, QTableWidgetItem(job.get('start_time', 'N/A')))
                
                # Duration
                duration = job.get('duration', 0)
                self.job_table.setItem(row, 5, QTableWidgetItem(f"{duration:.1f}s"))
                
                # Actions
                action_widget = self.create_action_buttons(job)
                self.job_table.setCellWidget(row, 6, action_widget)
        
        except Exception as e:
            print(f"Error refreshing job list: {e}")
    
    def create_action_buttons(self, job):
        """Create action buttons for a job."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        
        if job['status'] in ['pending', 'running']:
            cancel_btn = QPushButton("❌")
            cancel_btn.setMaximumWidth(40)
            cancel_btn.clicked.connect(lambda: self.cancel_job(job['id']))
            layout.addWidget(cancel_btn)
        
        if job['status'] == 'failed':
            retry_btn = QPushButton("🔄")
            retry_btn.setMaximumWidth(40)
            retry_btn.clicked.connect(lambda: self.retry_job(job['id']))
            layout.addWidget(retry_btn)
        
        logs_btn = QPushButton("📄")
        logs_btn.setMaximumWidth(40)
        logs_btn.clicked.connect(lambda: self.show_job_logs(job['id']))
        layout.addWidget(logs_btn)
        
        return widget
    
    def cancel_job(self, job_id: str):
        """Cancel a running job."""
        from services.taskmaster_service import TaskMasterService
        TaskMasterService.cancel_job(job_id)
        self.refresh_job_list()
    
    def retry_job(self, job_id: str):
        """Retry a failed job."""
        from services.taskmaster_service import TaskMasterService
        TaskMasterService.retry_job(job_id)
        self.refresh_job_list()
    
    def show_job_logs(self, job_id: str):
        """Show detailed logs for a job."""
        # Open dialog with job logs
        pass
    
    def clear_completed_jobs(self):
        """Remove completed jobs from queue."""
        from services.taskmaster_service import TaskMasterService
        TaskMasterService.clear_completed()
        self.refresh_job_list()
```

**Integration Points**:
- `services/taskmaster_service.py` - Job management
- Add as new tab in `gui/gui_dashboard.py`

---

### 5. **QChartView - Timeline Visualization** ⭐⭐⭐⭐
**Value**: Show document processing history over time.

**Use Case**:
- Timeline showing when documents were processed
- Volume trends (docs/day, docs/week)
- Entity extraction trends
- Performance degradation detection

**Implementation Complexity**: Medium (5-7 hours)

```python
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QPainter
from datetime import datetime, timedelta

class ProcessingTimelineWidget(QWidget):
    """
    Timeline visualization of document processing history.
    
    Shows:
    - Documents processed over time (line chart)
    - Entity extraction volume trends
    - Processing time trends
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Chart
        self.chart = QChart()
        self.chart.setTitle("Document Processing Timeline")
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # Chart view
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        layout.addWidget(self.chart_view)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"])
        self.time_range_combo.currentTextChanged.connect(self.load_data)
        controls_layout.addWidget(QLabel("Time Range:"))
        controls_layout.addWidget(self.time_range_combo)
        
        controls_layout.addStretch()
        
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.clicked.connect(self.load_data)
        controls_layout.addWidget(self.refresh_button)
        
        layout.addLayout(controls_layout)
    
    def load_data(self):
        """Load processing history from database."""
        try:
            from services.file_index_service import FileIndexService
            
            # Determine time range
            range_text = self.time_range_combo.currentText()
            if "7 Days" in range_text:
                start_date = datetime.now() - timedelta(days=7)
            elif "30 Days" in range_text:
                start_date = datetime.now() - timedelta(days=30)
            elif "90 Days" in range_text:
                start_date = datetime.now() - timedelta(days=90)
            else:
                start_date = datetime(2020, 1, 1)
            
            # Fetch processing history
            history = FileIndexService.get_processing_history(start_date)
            
            # Aggregate by day
            daily_counts = {}
            for entry in history:
                date = entry['processed_date'].date()
                daily_counts[date] = daily_counts.get(date, 0) + 1
            
            # Create series
            series = QLineSeries()
            series.setName("Documents Processed")
            
            for date, count in sorted(daily_counts.items()):
                timestamp = QDateTime(date).toMSecsSinceEpoch()
                series.append(timestamp, count)
            
            # Clear and add series
            self.chart.removeAllSeries()
            self.chart.addSeries(series)
            
            # Setup axes
            axis_x = QDateTimeAxis()
            axis_x.setFormat("MMM dd")
            axis_x.setTitleText("Date")
            self.chart.addAxis(axis_x, Qt.AlignBottom)
            series.attachAxis(axis_x)
            
            axis_y = QValueAxis()
            axis_y.setTitleText("Documents")
            axis_y.setLabelFormat("%d")
            self.chart.addAxis(axis_y, Qt.AlignLeft)
            series.attachAxis(axis_y)
        
        except Exception as e:
            print(f"Error loading timeline data: {e}")
```

**Integration Points**:
- `services/file_index_service.py` - Historical data
- `mem_db/memory/unified_memory_manager.py` - Entity trends
- Add to Dashboard or as new tab

---

### 6. **Custom Widget: File Tagging Interface** ⭐⭐⭐⭐
**Value**: Expose `file_tagging_rules.py` for manual and automated tagging.

**Use Case**:
- View all tags in system
- Apply/remove tags from documents
- Create tagging rules (regex patterns)
- Tag-based filtering and search

**Implementation Complexity**: Medium (5-7 hours)

```python
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                               QLineEdit, QPushButton, QLabel, QTextEdit, QSplitter)
from PySide6.QtCore import Qt

class FileTaggingTab(QWidget):
    """
    File tagging management interface.
    
    Features:
    - View all tags
    - Apply tags to documents
    - Create automated tagging rules
    - Tag-based search
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_tags()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("File Tagging & Rules")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: Tag list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        left_layout.addWidget(QLabel("All Tags:"))
        
        self.tag_list = QListWidget()
        self.tag_list.itemClicked.connect(self.on_tag_selected)
        left_layout.addWidget(self.tag_list)
        
        # New tag input
        new_tag_layout = QHBoxLayout()
        self.new_tag_input = QLineEdit()
        self.new_tag_input.setPlaceholderText("New tag name...")
        new_tag_layout.addWidget(self.new_tag_input)
        
        add_tag_btn = QPushButton("➕ Add")
        add_tag_btn.clicked.connect(self.add_new_tag)
        new_tag_layout.addWidget(add_tag_btn)
        
        left_layout.addLayout(new_tag_layout)
        
        splitter.addWidget(left_widget)
        
        # Right: Tag details and rules
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        right_layout.addWidget(QLabel("Tag Rules:"))
        
        self.rules_text = QTextEdit()
        self.rules_text.setPlaceholderText(
            "Define automated tagging rules:\n\n"
            "Pattern: *.pdf\n"
            "Tag: pdf_document\n\n"
            "Pattern: *invoice*\n"
            "Tag: financial\n"
        )
        right_layout.addWidget(self.rules_text)
        
        # Rule actions
        rule_buttons = QHBoxLayout()
        
        save_rules_btn = QPushButton("💾 Save Rules")
        save_rules_btn.clicked.connect(self.save_rules)
        rule_buttons.addWidget(save_rules_btn)
        
        test_rules_btn = QPushButton("🧪 Test Rules")
        test_rules_btn.clicked.connect(self.test_rules)
        rule_buttons.addWidget(test_rules_btn)
        
        apply_rules_btn = QPushButton("▶️ Apply to All Files")
        apply_rules_btn.clicked.connect(self.apply_rules_to_all)
        rule_buttons.addWidget(apply_rules_btn)
        
        right_layout.addLayout(rule_buttons)
        
        splitter.addWidget(right_widget)
        
        layout.addWidget(splitter)
    
    def load_tags(self):
        """Load all tags from the system."""
        try:
            from services.file_tagging_rules import RuleTagger
            
            tagger = RuleTagger()
            tags = tagger.get_all_tags()
            
            self.tag_list.clear()
            for tag in tags:
                self.tag_list.addItem(tag)
        
        except Exception as e:
            print(f"Error loading tags: {e}")
    
    def add_new_tag(self):
        """Add a new tag."""
        tag_name = self.new_tag_input.text().strip()
        if tag_name:
            self.tag_list.addItem(tag_name)
            self.new_tag_input.clear()
    
    def save_rules(self):
        """Save tagging rules to configuration."""
        rules_text = self.rules_text.toPlainText()
        
        try:
            from services.file_tagging_rules import RuleTagger
            
            tagger = RuleTagger()
            tagger.save_rules_from_text(rules_text)
            
            QMessageBox.information(self, "Success", "✅ Rules saved successfully!")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save rules: {e}")
    
    def test_rules(self):
        """Test rules on a sample file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Test File")
        
        if file_path:
            try:
                from services.file_tagging_rules import RuleTagger
                
                tagger = RuleTagger()
                tags = tagger.get_tags_for_file(file_path)
                
                QMessageBox.information(
                    self,
                    "Test Results",
                    f"Tags for {Path(file_path).name}:\n\n{', '.join(tags)}"
                )
            
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Test failed: {e}")
    
    def apply_rules_to_all(self):
        """Apply tagging rules to all indexed files."""
        reply = QMessageBox.question(
            self,
            "Confirm",
            "Apply tagging rules to ALL indexed files?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                from services.file_tagging_rules import RuleTagger
                from services.file_index_service import FileIndexService
                
                tagger = RuleTagger()
                files = FileIndexService.get_all_files()
                
                for file_info in files:
                    tags = tagger.get_tags_for_file(file_info['path'])
                    FileIndexService.update_tags(file_info['id'], tags)
                
                QMessageBox.information(
                    self,
                    "Complete",
                    f"✅ Tagged {len(files)} files!"
                )
            
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Tagging failed: {e}")
```

**Integration Points**:
- `services/file_tagging_rules.py` - Tagging logic
- `services/file_index_service.py` - File metadata
- `config/file_tagging_rules.json` - Rule persistence

---

## 🎨 Advanced PyQt6 Features (Lower Priority)

### 7. **QGraphicsView - Document Relationship Network** ⭐⭐⭐
- Visualize document connections (citations, references, related docs)
- Interactive graph with zoom/pan
- Click nodes to preview document

### 8. **QDockWidget - Floating Panels** ⭐⭐⭐
- Detachable preview pane
- Floating log viewer
- Multi-monitor support

### 9. **Custom Painting with QPainter** ⭐⭐
- Custom progress indicators
- Heat maps for document activity
- Visual confidence meters

### 10. **QWebChannel - Web Integration** ⭐⭐
- Embed Chart.js/D3.js visualizations
- Two-way communication Qt ↔ JavaScript

---

## 📋 Implementation Roadmap

### Week 1: Quick Wins (10-15 hours)
1. ✅ System Tray Icon (3 hours)
2. ✅ Global Search Dialog (5 hours)
3. ✅ File System Watcher (5 hours)

### Week 2: High-Value Features (15-20 hours)
4. ✅ Job Queue Visualizer Tab (8 hours)
5. ✅ File Tagging Interface (6 hours)
6. ✅ Timeline Visualization (6 hours)

### Week 3: Polish & Integration (10 hours)
7. ✅ Integrate all features into main dashboard
8. ✅ Add settings for new features
9. ✅ Testing and bug fixes

---

## 🛠️ Technical Notes

### Threading Best Practices
All long-running operations MUST use QThread:

```python
class Worker(QThread):
    finished = Signal(dict)
    progress = Signal(int)
    error = Signal(str)
    
    def __init__(self, task_func, *args):
        super().__init__()
        self.task_func = task_func
        self.args = args
    
    def run(self):
        try:
            result = self.task_func(*self.args)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
```

### Async/Sync Bridge
Your services use `async`, but PyQt6 is synchronous. Bridge pattern:

```python
import asyncio

def run_async_in_thread(async_func, *args):
    """Run async function in thread-safe way."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(async_func(*args))
    loop.close()
    return result

# Usage in QThread:
class AsyncWorker(QThread):
    def run(self):
        result = run_async_in_thread(async_service_call, param1, param2)
        self.finished.emit(result)
```

### Signal/Slot Type Safety
Use `typing` to avoid runtime errors:

```python
from PySide6.QtCore import Signal

class MyWidget(QWidget):
    # Type annotations prevent bugs
    document_loaded = Signal(str)  # file_path
    processing_complete = Signal(dict)  # results
    error_occurred = Signal(str, int)  # message, code
```

---

## 💡 Key Takeaways

1. **Your architecture is solid** - These features expose existing capabilities, not add new ones
2. **Focus on user workflows** - System tray + file watcher = "set it and forget it"
3. **Visual feedback matters** - Job queue visualizer turns backend into tangible progress
4. **PyQt6 is powerful** - You're using ~30% of its capabilities currently

---

## 📚 Resources

- [Qt Documentation](https://doc.qt.io/qt-6/)
- [PySide6 Examples](https://doc.qt.io/qtforpython-6/examples/)
- [PyQt6 Tutorial](https://www.pythonguis.com/)

---

**Next Step**: Pick ONE feature from Week 1 (System Tray or Global Search) and implement it. Start small, validate the pattern, then scale to others.
