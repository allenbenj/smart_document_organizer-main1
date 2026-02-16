"""
Knowledge Base Browser - Reusable widget for accessing centrally processed documents

This widget allows tabs to query and load documents that have already been
processed by the Document Processing tab and stored in the shared knowledge base.

This eliminates redundant processing and demonstrates the centralized architecture
where documents are processed once and leveraged by all tabs.
"""

from typing import Optional

try:
    from PySide6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QListWidget,
        QListWidgetItem,
        QLineEdit,
    )
    from PySide6.QtCore import Signal
    from PySide6.QtGui import QFont
except ImportError:
    pass

from ..services import api_client


class KnowledgeBaseBrowser(QWidget):
    """
    Widget for browsing and loading documents from the shared knowledge base.
    
    This widget can be embedded in any tab to provide access to
    centrally processed documents, eliminating the need for each
    tab to process documents independently.
    
    Signals:
        document_selected(dict): Emitted when user selects a document
    """
    
    document_selected = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.documents_cache = []
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the knowledge base browser UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("📚 Knowledge Base")
        header.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(header)
        
        desc = QLabel("Load pre-processed documents from the shared knowledge base")
        desc.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        layout.addWidget(desc)
        
        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search documents...")
        self.search_input.textChanged.connect(self.filter_documents)
        search_layout.addWidget(self.search_input)
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setMaximumWidth(40)
        self.refresh_btn.setToolTip("Refresh document list")
        self.refresh_btn.clicked.connect(self.load_documents)
        search_layout.addWidget(self.refresh_btn)
        layout.addLayout(search_layout)
        
        # Document list
        self.doc_list = QListWidget()
        self.doc_list.setMaximumHeight(150)
        self.doc_list.itemDoubleClicked.connect(self.on_document_double_clicked)
        layout.addWidget(self.doc_list)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        self.load_btn = QPushButton("Load Selected")
        self.load_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.load_btn.clicked.connect(self.load_selected_document)
        btn_layout.addWidget(self.load_btn)
        
        self.info_btn = QPushButton("Info")
        self.info_btn.clicked.connect(self.show_document_info)
        btn_layout.addWidget(self.info_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Status
        self.status_label = QLabel("Click refresh to load documents")
        self.status_label.setStyleSheet("font-size: 9px; color: #888;")
        layout.addWidget(self.status_label)
        
        # Auto-load on creation
        self.load_documents()
    
    def load_documents(self):
        """Load documents from the knowledge base."""
        try:
            self.status_label.setText("Loading...")
            
            # Query the vector store or document index
            # This would be your actual API endpoint for listing processed documents
            response = api_client.get("/knowledge/documents?limit=100", timeout=10)
            
            if isinstance(response, dict):
                self.documents_cache = response.get("documents", [])
            else:
                self.documents_cache = []
            
            self.populate_list(self.documents_cache)
            
            count = len(self.documents_cache)
            self.status_label.setText(f"Loaded {count} document(s)")
            
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)[:50]}")
            self.documents_cache = []
            self.doc_list.clear()
    
    def populate_list(self, documents):
        """Populate the document list widget."""
        self.doc_list.clear()
        
        for doc in documents:
            # Extract document info
            title = doc.get("title") or doc.get("filename") or doc.get("file_path", "Unknown")
            doc_id = doc.get("id", "")
            
            # Create list item
            item = QListWidgetItem(f"📄 {title}")
            item.setData(256, doc)  # Store full document data
            item.setToolTip(f"ID: {doc_id}\nPath: {doc.get('file_path', 'N/A')}")
            
            self.doc_list.addItem(item)
    
    def filter_documents(self, search_text: str):
        """Filter documents based on search text."""
        if not search_text:
            self.populate_list(self.documents_cache)
            return
        
        search_lower = search_text.lower()
        filtered = [
            doc for doc in self.documents_cache
            if search_lower in str(doc.get("title", "")).lower()
            or search_lower in str(doc.get("filename", "")).lower()
            or search_lower in str(doc.get("file_path", "")).lower()
        ]
        
        self.populate_list(filtered)
    
    def load_selected_document(self):
        """Load the currently selected document."""
        current = self.doc_list.currentItem()
        if not current:
            self.status_label.setText("No document selected")
            return
        
        doc = current.data(256)
        if doc:
            self.document_selected.emit(doc)
            title = doc.get("title") or doc.get("filename", "document")
            self.status_label.setText(f"Loaded: {title}")
    
    def on_document_double_clicked(self, item):
        """Handle double-click on a document."""
        doc = item.data(256)
        if doc:
            self.document_selected.emit(doc)
    
    def show_document_info(self):
        """Show detailed info about the selected document."""
        current = self.doc_list.currentItem()
        if not current:
            return
        
        doc = current.data(256)
        if doc:
            from PySide6.QtWidgets import QMessageBox
            
            info_text = f"""
Document Information:

Title: {doc.get('title', 'N/A')}
Filename: {doc.get('filename', 'N/A')}
Path: {doc.get('file_path', 'N/A')}
ID: {doc.get('id', 'N/A')}
Processed: {doc.get('processed_date', 'N/A')}
Size: {doc.get('size', 'N/A')} bytes
Content Length: {len(doc.get('content', ''))} characters
"""
            
            QMessageBox.information(
                self,
                "Document Information",
                info_text
            )
    
    def get_selected_document(self) -> Optional[dict]:
        """Get the currently selected document."""
        current = self.doc_list.currentItem()
        if current:
            return current.data(256)
        return None
