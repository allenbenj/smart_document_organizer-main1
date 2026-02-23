"""
Global Search Dialog - Command Palette Style Search

A production-ready implementation of Ctrl+K global search that integrates
with SearchService, VectorStoreService, and FileIndexService.

Features:
- Real-time search with debouncing
- Combined full-text + semantic search
- Keyboard navigation (Up/Down/Enter/Esc)
- Document preview on selection
- Jump to document functionality
- Result highlighting
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
        QListWidget, QListWidgetItem, QLabel, QTextBrowser,
        QSplitter, QWidget, QPushButton
    )
    from PySide6.QtCore import Qt, QTimer, Signal, QThread
    from PySide6.QtGui import QFont, QShortcut, QKeySequence, QColor
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QDialog = QWidget = object
    Signal = lambda *args: None


class SearchWorker(QThread):
    """Background thread for search operations."""
    
    results_ready = Signal(list)  # List of search results
    error_occurred = Signal(str)  # Error message
    
    def __init__(self, query: str, search_mode: str = "combined"):
        super().__init__()
        self.query = query
        self.search_mode = search_mode
    
    def run(self):
        """Execute search in background."""
        try:
            results = []
            
            if self.search_mode in ["text", "combined"]:
                # Full-text search via FileIndexService
                results.extend(self.search_file_index())
            
            if self.search_mode in ["semantic", "combined"]:
                # Semantic search via VectorStoreService
                results.extend(self.search_vector_store())
            
            # Deduplicate and sort by relevance
            unique_results = self.deduplicate_results(results)
            sorted_results = sorted(unique_results, key=lambda x: x.get('score', 0), reverse=True)
            
            self.results_ready.emit(sorted_results[:20])  # Top 20 results
        
        except Exception as e:
            self.error_occurred.emit(f"Search failed: {str(e)}")
    
    def search_file_index(self) -> List[Dict[str, Any]]:
        """Search using FileIndexManager."""
        try:
            from tools.db.file_index_manager import FileIndexManager
            
            db_path = "databases/file_index.db"
            if not Path(db_path).exists():
                return []
            
            manager = FileIndexManager(db_path=db_path, project_root=".")
            
            # Use the search_files method
            raw_results = manager.search_files(self.query)
            
            # Convert to standard format
            results = []
            for result in raw_results:
                results.append({
                    'file_path': result.get('file_path', ''),
                    'filename': Path(result.get('file_path', '')).name,
                    'snippet': f"Category: {result.get('file_category', 'unknown')}",
                    'score': 0.8,  # Default score for text search
                    'source': 'file_index',
                    'file_type': result.get('file_type', 'unknown'),
                    'file_size': result.get('file_size', 0)
                })
            
            return results
        
        except Exception as e:
            print(f"File index search error: {e}")
            return []
    
    def search_vector_store(self) -> List[Dict[str, Any]]:
        """Search using VectorStoreService (semantic search)."""
        try:
            # Try to use the API endpoint if available
            import requests
            
            response = requests.post(
                "http://127.0.0.1:8000/api/vector-store/search",
                json={"query": self.query, "k": 10},
                timeout=5
            )
            
            if response.status_code == 200:
                api_results = response.json().get('results', [])
                
                results = []
                for result in api_results:
                    results.append({
                        'file_path': result.get('metadata', {}).get('file_path', ''),
                        'filename': result.get('metadata', {}).get('filename', 'Unknown'),
                        'snippet': result.get('content', '')[:150],
                        'score': result.get('score', 0.5),
                        'source': 'vector_store',
                        'distance': result.get('distance', 0)
                    })
                
                return results
        
        except Exception as e:
            print(f"Vector store search error: {e}")
        
        return []
    
    def deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate results by file_path."""
        seen = {}
        unique = []
        
        for result in results:
            path = result.get('file_path')
            if not path:
                continue
            
            # Keep highest scoring result for each file
            if path not in seen or result.get('score', 0) > seen[path].get('score', 0):
                seen[path] = result
        
        return list(seen.values())


class GlobalSearchDialog(QDialog):
    """
    Command palette style global search dialog.
    
    Keyboard shortcuts:
    - Ctrl+K: Open (from main window)
    - Esc: Close
    - Enter: Open selected document
    - Up/Down: Navigate results
    """
    
    # Signals
    document_selected = Signal(str)  # file_path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Search")
        self.setModal(False)
        self.resize(900, 650)
        
        # Floating window style
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        
        # Search state
        self.current_worker: Optional[SearchWorker] = None
        self.search_history: List[str] = []
        
        self.setup_ui()
        self.setup_shortcuts()
        
        # Debounce timer for search
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
    
    def setup_ui(self):
        """Build the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header with search input
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_label = QLabel("🔍 Global Search")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2196F3; margin-bottom: 5px;")
        header_layout.addWidget(title_label)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search documents, content, or entities... (Ctrl+K)")
        self.search_input.setFont(QFont("Arial", 14))
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 12px 15px;
                border: 2px solid #2196F3;
                border-radius: 8px;
                background-color: white;
                selection-background-color: #2196F3;
            }
            QLineEdit:focus {
                border: 2px solid #1976D2;
                background-color: #f0f8ff;
            }
        """)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        header_layout.addWidget(self.search_input)
        
        layout.addWidget(header_widget)
        
        # Main content splitter (results + preview)
        self.content_splitter = QSplitter(Qt.Horizontal)
        
        # Left panel: Results list
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        # Results header
        results_header = QHBoxLayout()
        self.results_count_label = QLabel("Type to search...")
        self.results_count_label.setStyleSheet("color: #666; font-size: 11px;")
        results_header.addWidget(self.results_count_label)
        results_header.addStretch()
        
        # Search mode toggle
        self.search_mode_label = QLabel("Mode: Combined")
        self.search_mode_label.setStyleSheet("color: #666; font-size: 11px;")
        results_header.addWidget(self.search_mode_label)
        
        results_layout.addLayout(results_header)
        
        # Results list
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: black;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        self.results_list.itemClicked.connect(self.on_result_selected)
        self.results_list.itemActivated.connect(self.open_selected_document)
        results_layout.addWidget(self.results_list)
        
        self.content_splitter.addWidget(results_widget)
        
        # Right panel: Preview pane
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        preview_label = QLabel("Preview")
        preview_label.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        preview_layout.addWidget(preview_label)
        
        self.preview_browser = QTextBrowser()
        self.preview_browser.setStyleSheet("""
            QTextBrowser {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                padding: 10px;
            }
        """)
        self.preview_browser.setPlaceholderText("Select a result to preview...")
        self.preview_browser.setOpenExternalLinks(False)
        preview_layout.addWidget(self.preview_browser)
        
        self.content_splitter.addWidget(preview_widget)
        
        # Set splitter proportions (60% results, 40% preview)
        self.content_splitter.setSizes([540, 360])
        
        layout.addWidget(self.content_splitter)
        
        # Footer with actions
        footer_layout = QHBoxLayout()
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-size: 10px;")
        footer_layout.addWidget(self.status_label)
        
        footer_layout.addStretch()
        
        # Action buttons
        self.open_button = QPushButton("Open Document")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_selected_document)
        self.open_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        footer_layout.addWidget(self.open_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
            }
        """)
        footer_layout.addWidget(self.close_button)
        
        layout.addLayout(footer_layout)
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # ESC to close
        close_shortcut = QShortcut(QKeySequence("Esc"), self)
        close_shortcut.activated.connect(self.close)
        
        # Enter to open document
        self.search_input.returnPressed.connect(self.open_selected_document)
        
        # Ctrl+1: Text search only
        text_mode = QShortcut(QKeySequence("Ctrl+1"), self)
        text_mode.activated.connect(lambda: self.set_search_mode("text"))
        
        # Ctrl+2: Semantic search only
        semantic_mode = QShortcut(QKeySequence("Ctrl+2"), self)
        semantic_mode.activated.connect(lambda: self.set_search_mode("semantic"))
        
        # Ctrl+3: Combined search
        combined_mode = QShortcut(QKeySequence("Ctrl+3"), self)
        combined_mode.activated.connect(lambda: self.set_search_mode("combined"))
    
    def set_search_mode(self, mode: str):
        """Set search mode (text, semantic, or combined)."""
        mode_labels = {
            "text": "Mode: Text Only",
            "semantic": "Mode: Semantic Only",
            "combined": "Mode: Combined"
        }
        self.search_mode = mode
        self.search_mode_label.setText(mode_labels.get(mode, "Mode: Combined"))
        
        # Re-run search if there's a query
        if self.search_input.text().strip():
            self.perform_search()
    
    def on_search_text_changed(self, text: str):
        """Handle search text changes with debouncing."""
        self.search_timer.stop()
        
        if len(text.strip()) >= 2:
            # Show "searching..." status
            self.status_label.setText("🔄 Searching...")
            self.results_count_label.setText("Searching...")
            
            # Start debounce timer (wait 400ms after user stops typing)
            self.search_timer.start(400)
        else:
            self.results_list.clear()
            self.preview_browser.clear()
            self.results_count_label.setText("Type at least 2 characters...")
            self.status_label.setText("")
            self.open_button.setEnabled(False)
    
    def perform_search(self):
        """Execute the search in background thread."""
        query = self.search_input.text().strip()
        
        if len(query) < 2:
            return
        
        # Cancel any running search
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.quit()
            self.current_worker.wait()
        
        # Start new search
        search_mode = getattr(self, 'search_mode', 'combined')
        self.current_worker = SearchWorker(query, search_mode)
        self.current_worker.results_ready.connect(self.display_results)
        self.current_worker.error_occurred.connect(self.show_error)
        self.current_worker.start()
    
    def display_results(self, results: List[Dict[str, Any]]):
        """Display search results."""
        self.results_list.clear()
        self.preview_browser.clear()
        
        if not results:
            self.results_count_label.setText("No results found")
            self.status_label.setText("")
            item = QListWidgetItem("No results found. Try a different query.")
            item.setFlags(Qt.NoItemFlags)
            self.results_list.addItem(item)
            return
        
        # Update counts
        self.results_count_label.setText(f"{len(results)} results")
        self.status_label.setText(f"✓ Search completed in background")
        
        # Add results to list
        for result in results:
            filename = result.get('filename', 'Unknown')
            snippet = result.get('snippet', '')
            score = result.get('score', 0)
            source = result.get('source', 'unknown')
            file_type = result.get('file_type', '')
            
            # Format item text
            icon = self.get_file_type_icon(file_type)
            score_text = f"[{score:.2f}]" if source == 'vector_store' else ""
            
            item_text = f"{icon} {filename} {score_text}\n{snippet}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, result)  # Store full result
            
            # Color code by source
            if source == 'vector_store':
                item.setForeground(QColor(33, 150, 243))  # Blue for semantic
            else:
                item.setForeground(QColor(76, 175, 80))  # Green for text
            
            self.results_list.addItem(item)
        
        # Auto-select first item
        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)
            self.on_result_selected(self.results_list.item(0))
    
    def get_file_type_icon(self, file_type: str) -> str:
        """Get emoji icon for file type."""
        icons = {
            'py': '🐍',
            'md': '📝',
            'txt': '📄',
            'pdf': '📕',
            'docx': '📘',
            'json': '📋',
            'yaml': '⚙️',
            'yml': '⚙️',
            'html': '🌐',
            'css': '🎨',
            'js': '📜',
        }
        return icons.get(file_type.lower(), '📄')
    
    def on_result_selected(self, item: QListWidgetItem):
        """Handle result selection - show preview."""
        if not item:
            return
        
        result = item.data(Qt.UserRole)
        if not result:
            return
        
        file_path = result.get('file_path', '')
        
        # Enable open button
        self.open_button.setEnabled(True)
        
        # Load preview
        self.load_preview(file_path, result)
    
    def load_preview(self, file_path: str, result: Dict[str, Any]):
        """Load file preview."""
        if not file_path or not os.path.exists(file_path):
            self.preview_browser.setHtml("<p style='color: #999;'>File not found</p>")
            return
        
        try:
            path = Path(file_path)
            
            # Build preview HTML
            html_parts = []
            
            # Header
            html_parts.append(f"""
            <div style='background: #f5f5f5; padding: 10px; border-radius: 4px; margin-bottom: 10px;'>
                <h3 style='margin: 0 0 5px 0;'>{path.name}</h3>
                <p style='color: #666; font-size: 12px; margin: 0;'>
                    <b>Path:</b> {file_path}<br>
                    <b>Type:</b> {result.get('file_type', 'unknown')}<br>
                    <b>Size:</b> {self.format_file_size(result.get('file_size', 0))}
                </p>
            </div>
            """)
            
            # Content preview
            if path.suffix.lower() in ['.txt', '.md', '.py', '.json', '.yaml', '.yml']:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read(2000)  # First 2KB
                    
                    html_parts.append(f"""
                    <div style='background: white; padding: 10px; border: 1px solid #ddd; border-radius: 4px;'>
                        <pre style='white-space: pre-wrap; font-family: monospace; font-size: 12px;'>{self.escape_html(content)}</pre>
                    </div>
                    """)
                except Exception as e:
                    html_parts.append(f"<p style='color: #999;'>Could not load content: {e}</p>")
            else:
                html_parts.append("<p style='color: #999;'>Preview not available for this file type</p>")
            
            self.preview_browser.setHtml(''.join(html_parts))
        
        except Exception as e:
            self.preview_browser.setHtml(f"<p style='color: red;'>Preview error: {e}</p>")
    
    @staticmethod
    def format_file_size(size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
    
    def open_selected_document(self):
        """Open the selected document."""
        current_item = self.results_list.currentItem()
        if not current_item:
            return
        
        result = current_item.data(Qt.UserRole)
        if not result:
            return
        
        file_path = result.get('file_path', '')
        if file_path:
            self.document_selected.emit(file_path)
            self.close()
    
    def show_error(self, error_message: str):
        """Display search error."""
        self.status_label.setText(f"❌ {error_message}")
        self.results_count_label.setText("Search failed")
        
        self.results_list.clear()
        item = QListWidgetItem(error_message)
        item.setForeground(QColor(244, 67, 54))  # Red
        self.results_list.addItem(item)
    
    def showEvent(self, event):
        """Handle dialog show event."""
        super().showEvent(event)
        
        # Focus search input
        self.search_input.setFocus()
        self.search_input.selectAll()


# Example integration with main window
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton
    
    class TestMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Main Window")
            self.resize(1000, 700)
            
            # Create global search dialog
            self.search_dialog = GlobalSearchDialog(self)
            self.search_dialog.document_selected.connect(self.on_document_selected)
            
            # Add button to open search
            button = QPushButton("Open Global Search (Ctrl+K)", self)
            button.move(50, 50)
            button.clicked.connect(self.show_search)
            
            # Global shortcut
            search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
            search_shortcut.activated.connect(self.show_search)
        
        def show_search(self):
            """Show global search dialog."""
            self.search_dialog.show()
            self.search_dialog.raise_()
            self.search_dialog.activateWindow()
        
        def on_document_selected(self, file_path: str):
            """Handle document selection."""
            print(f"Document selected: {file_path}")
            # TODO: Open in document preview widget
    
    app = QApplication(sys.argv)
    window = TestMainWindow()
    window.show()
    sys.exit(app.exec())
