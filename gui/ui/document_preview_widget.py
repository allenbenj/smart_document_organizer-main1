"""
Document Preview Widget - Multi-format document viewer

Provides preview capabilities for:
- PDF documents (using pymupdf/fitz)
- DOCX documents (using python-docx)
- Text and Markdown files
- Document metadata and processing status
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from PySide6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QTextBrowser,
        QComboBox,
        QGroupBox,
        QSpinBox,
        QScrollArea,
        QFrame,
        QTabWidget,
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont, QPixmap, QImage
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = Any = object  # type: ignore

# Import document processing libraries
PDF_AVAILABLE = False
DOCX_AVAILABLE = False

try:
    import fitz  # pymupdf
    PDF_AVAILABLE = True
except ImportError:
    pass

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    pass


class DocumentPreviewWidget(QWidget):  # type: ignore[misc]
    """
    Multi-format document preview widget.
    
    Features:
    - PDF rendering with page navigation
    - DOCX text extraction and display
    - Text/Markdown viewer
    - Metadata display
    - Processing status tracking
    """
    
    # Signals
    document_loaded = Signal(str)  # type: ignore[misc]
    preview_error = Signal(str)  # type: ignore[misc]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file_path: Optional[str] = None
        self.current_file_type: Optional[str] = None
        self.pdf_document: Optional[Any] = None
        self.current_page = 0
        self.total_pages = 0
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5, 5, 5, 5)
        
        # File info label
        self.file_info_label = QLabel("No document loaded")
        self.file_info_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(self.file_info_label)
        
        header_layout.addStretch()
        
        # Page navigation (for PDFs)
        self.nav_widget = QWidget()
        nav_layout = QHBoxLayout(self.nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        
        self.prev_page_button = QPushButton("◀ Prev")
        self.prev_page_button.clicked.connect(self.previous_page)
        nav_layout.addWidget(self.prev_page_button)
        
        self.page_label = QLabel("Page 0 / 0")
        nav_layout.addWidget(self.page_label)
        
        self.next_page_button = QPushButton("Next ▶")
        self.next_page_button.clicked.connect(self.next_page)
        nav_layout.addWidget(self.next_page_button)
        
        self.page_spinbox = QSpinBox()
        self.page_spinbox.setMinimum(1)
        self.page_spinbox.setPrefix("Go to: ")
        self.page_spinbox.valueChanged.connect(self.goto_page)
        nav_layout.addWidget(self.page_spinbox)
        
        self.nav_widget.setVisible(False)
        header_layout.addWidget(self.nav_widget)
        
        # Zoom controls (for PDFs)
        self.zoom_widget = QWidget()
        zoom_layout = QHBoxLayout(self.zoom_widget)
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        
        self.zoom_out_button = QPushButton("🔍-")
        self.zoom_out_button.clicked.connect(self.zoom_out)
        zoom_layout.addWidget(self.zoom_out_button)
        
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["50%", "75%", "100%", "125%", "150%", "200%"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.currentTextChanged.connect(self.on_zoom_changed)
        zoom_layout.addWidget(self.zoom_combo)
        
        self.zoom_in_button = QPushButton("🔍+")
        self.zoom_in_button.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(self.zoom_in_button)
        
        self.zoom_widget.setVisible(False)
        header_layout.addWidget(self.zoom_widget)
        
        layout.addWidget(header_widget)
        
        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # Tabbed content area
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Preview tab
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.preview_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.preview_content = QLabel("Select a document to preview")
        self.preview_content.setAlignment(Qt.AlignCenter)
        self.preview_content.setStyleSheet("color: #999; padding: 20px;")
        self.preview_scroll.setWidget(self.preview_content)
        
        self.tab_widget.addTab(self.preview_scroll, "📄 Preview")
        
        # Text content tab
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setPlaceholderText("Text content will appear here...")
        self.tab_widget.addTab(self.text_browser, "📝 Text")
        
        # Metadata tab
        self.metadata_browser = QTextBrowser()
        self.metadata_browser.setPlaceholderText("Document metadata will appear here...")
        self.tab_widget.addTab(self.metadata_browser, "ℹ️ Metadata")
        
        # Status footer
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(
            "background-color: #f0f0f0; padding: 5px; color: #666; font-size: 11px;"
        )
        layout.addWidget(self.status_label)
    
    def load_document(self, file_path: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Load and display a document.
        
        Args:
            file_path: Path to the document file
            metadata: Optional metadata dict to display
        """
        self.clear() # Close existing handles
        
        if not os.path.exists(file_path):
            self.preview_error.emit(f"File not found: {file_path}")
            self.status_label.setText(f"❌ Error: File not found")
            return
        
        self.current_file_path = file_path
        file_ext = Path(file_path).suffix.lower()
        file_name = os.path.basename(file_path)
        
        self.file_info_label.setText(f"📄 {file_name}")
        self.status_label.setText(f"Loading {file_name}...")
        
        # Reset state
        self.current_page = 0
        self.total_pages = 0
        
        try:
            # Load based on file type
            if file_ext == '.pdf':
                self.load_pdf(file_path)
            elif file_ext in ['.docx', '.doc']:
                self.load_docx(file_path)
            elif file_ext in ['.txt', '.md', '.markdown']:
                self.load_text(file_path)
            else:
                # Try loading as text
                self.load_text(file_path)
            
            # Load metadata
            if metadata:
                self.display_metadata(metadata)
            else:
                self.extract_basic_metadata(file_path)
            
            self.document_loaded.emit(file_path)
            self.status_label.setText(f"✅ Loaded: {file_name}")
            
        except Exception as e:
            error_msg = f"Error loading document: {str(e)}"
            self.preview_error.emit(error_msg)
            self.status_label.setText(f"❌ Error: {str(e)}")
            self.text_browser.setPlainText(error_msg)
    
    def load_pdf(self, file_path: str):
        """Load and display a PDF document."""
        if not PDF_AVAILABLE:
            self.text_browser.setPlainText(
                "PDF preview unavailable - pymupdf not installed.\n\n"
                "Install: pip install pymupdf"
            )
            self.current_file_type = 'pdf_unavailable'
            return
        
        self.current_file_type = 'pdf'
        
        # Open PDF
        self.pdf_document = fitz.open(file_path)
        self.total_pages = len(self.pdf_document)
        
        # Show navigation controls
        self.nav_widget.setVisible(True)
        self.zoom_widget.setVisible(True)
        
        # Update page controls
        self.page_spinbox.setMaximum(self.total_pages)
        self.page_spinbox.setValue(1)
        
        # Render first page
        self.current_page = 0
        self.render_pdf_page()
        
        # Extract text from all pages
        all_text = []
        for page_num in range(self.total_pages):
            page = self.pdf_document[page_num]
            all_text.append(f"=== Page {page_num + 1} ===\n{page.get_text()}\n")
        
        self.text_browser.setPlainText("\n".join(all_text))
    
    def render_pdf_page(self):
        """Render the current PDF page."""
        if not self.pdf_document or self.current_page >= self.total_pages:
            return
        
        # Get zoom level
        zoom_text = self.zoom_combo.currentText().replace('%', '')
        zoom = float(zoom_text) / 100.0
        
        # Get page and render
        page = self.pdf_document[self.current_page]
        mat = fitz.Matrix(zoom * 2, zoom * 2)  # 2x for better quality
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to QImage
        img_data = pix.samples
        img = QImage(
            img_data,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format_RGB888
        )
        
        # Display in label
        pixmap = QPixmap.fromImage(img)
        self.preview_content.setPixmap(pixmap)
        self.preview_content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        # Update page label
        self.page_label.setText(f"Page {self.current_page + 1} / {self.total_pages}")
        
        # Update button states
        self.prev_page_button.setEnabled(self.current_page > 0)
        self.next_page_button.setEnabled(self.current_page < self.total_pages - 1)
    
    def load_docx(self, file_path: str):
        """Load and display a DOCX document."""
        if not DOCX_AVAILABLE:
            self.text_browser.setPlainText(
                "DOCX preview unavailable - python-docx not installed.\n\n"
                "Install: pip install python-docx"
            )
            self.current_file_type = 'docx_unavailable'
            return
        
        self.current_file_type = 'docx'
        
        # Hide navigation controls
        self.nav_widget.setVisible(False)
        self.zoom_widget.setVisible(False)
        
        # Load document
        doc = DocxDocument(file_path)
        
        # Extract text with formatting
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                # Check for heading style
                if para.style.name.startswith('Heading'):
                    level = para.style.name.replace('Heading ', '')
                    text_parts.append(f"\n{'#' * int(level)} {para.text}\n")
                else:
                    text_parts.append(para.text)
        
        extracted_text = "\n".join(text_parts)
        
        # Display in text browser with formatting
        self.text_browser.setMarkdown(extracted_text)
        
        # Simple preview in preview tab
        # Convert newlines to HTML breaks
        html_text = extracted_text.replace('\n', '<br>')
        file_name = os.path.basename(file_path)
        
        preview_html = f"""
        <div style='padding: 20px; font-family: Arial; max-width: 800px;'>
            <h2>{file_name}</h2>
            <div style='white-space: pre-wrap; line-height: 1.6;'>
                {html_text}
            </div>
        </div>
        """
        
        preview_label = QLabel()
        preview_label.setTextFormat(Qt.RichText)
        preview_label.setText(preview_html)
        preview_label.setWordWrap(True)
        preview_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        preview_label.setStyleSheet("background-color: white; padding: 10px;")
        
        self.preview_scroll.setWidget(preview_label)
    
    def load_text(self, file_path: str):
        """Load and display a text file."""
        self.current_file_type = 'text'
        
        # Hide navigation controls
        self.nav_widget.setVisible(False)
        self.zoom_widget.setVisible(False)
        
        # Read file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        # Display in text browser
        if file_path.endswith(('.md', '.markdown')):
            self.text_browser.setMarkdown(content)
        else:
            self.text_browser.setPlainText(content)
        
        # Simple preview
        preview_html = f"""
        <div style='padding: 20px; font-family: monospace; background: white; max-width: 800px;'>
            <pre style='white-space: pre-wrap; line-height: 1.4;'>{content}</pre>
        </div>
        """
        
        preview_label = QLabel()
        preview_label.setTextFormat(Qt.RichText)
        preview_label.setText(preview_html)
        preview_label.setWordWrap(True)
        preview_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        self.preview_scroll.setWidget(preview_label)
    
    def display_metadata(self, metadata: Dict[str, Any]):
        """Display document metadata."""
        html_parts = ["<h3>Document Metadata</h3>", "<table style='width:100%; border-collapse: collapse;'>"]
        
        for key, value in metadata.items():
            html_parts.append(
                f"<tr style='border-bottom: 1px solid #ddd;'>"
                f"<td style='padding: 8px; font-weight: bold; width: 200px;'>{key}</td>"
                f"<td style='padding: 8px;'>{value}</td>"
                f"</tr>"
            )
        
        html_parts.append("</table>")
        self.metadata_browser.setHtml("\n".join(html_parts))
    
    def extract_basic_metadata(self, file_path: str):
        """Extract basic file system metadata."""
        stat = os.stat(file_path)
        metadata = {
            "File Name": os.path.basename(file_path),
            "File Path": file_path,
            "File Size": f"{stat.st_size:,} bytes",
            "File Type": Path(file_path).suffix.upper().replace('.', ''),
            "Modified": str(stat.st_mtime),
        }
        
        if self.current_file_type == 'pdf' and self.pdf_document:
            metadata["Total Pages"] = str(self.total_pages)
            
            # Extract PDF metadata if available
            pdf_meta = self.pdf_document.metadata
            if pdf_meta:
                for key in ['title', 'author', 'subject', 'creator', 'producer']:
                    if key in pdf_meta and pdf_meta[key]:
                        metadata[key.capitalize()] = pdf_meta[key]
        
        self.display_metadata(metadata)
    
    # Navigation methods
    def next_page(self):
        """Go to next page (PDF only)."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.page_spinbox.setValue(self.current_page + 1)
            self.render_pdf_page()
    
    def previous_page(self):
        """Go to previous page (PDF only)."""
        if self.current_page > 0:
            self.current_page -= 1
            self.page_spinbox.setValue(self.current_page + 1)
            self.render_pdf_page()
    
    def goto_page(self, page_number: int):
        """Go to specific page (PDF only)."""
        if 0 < page_number <= self.total_pages:
            self.current_page = page_number - 1
            self.render_pdf_page()
    
    # Zoom methods
    def zoom_in(self):
        """Increase zoom level."""
        current_index = self.zoom_combo.currentIndex()
        if current_index < self.zoom_combo.count() - 1:
            self.zoom_combo.setCurrentIndex(current_index + 1)
    
    def zoom_out(self):
        """Decrease zoom level."""
        current_index = self.zoom_combo.currentIndex()
        if current_index > 0:
            self.zoom_combo.setCurrentIndex(current_index - 1)
    
    def on_zoom_changed(self, zoom_text: str):
        """Handle zoom level change."""
        if self.current_file_type == 'pdf':
            self.render_pdf_page()
    
    def clear(self):
        """Clear the preview."""
        self.current_file_path = None
        self.current_file_type = None
        self.current_page = 0
        self.total_pages = 0
        
        if self.pdf_document:
            self.pdf_document.close()
            self.pdf_document = None
        
        self.preview_content.setText("Select a document to preview")
        self.preview_content.setPixmap(QPixmap())
        self.text_browser.clear()
        self.metadata_browser.clear()
        self.file_info_label.setText("No document loaded")
        self.status_label.setText("Ready")
        
        self.nav_widget.setVisible(False)
        self.zoom_widget.setVisible(False)

    def __del__(self):
        """Ensure resources are released."""
        if hasattr(self, 'pdf_document') and self.pdf_document:
            try:
                self.pdf_document.close()
            except Exception:
                pass
