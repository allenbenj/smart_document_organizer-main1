# Global Search Dialog - Integration Guide

## Quick Start: Add Ctrl+K Global Search to Your Dashboard

This guide shows how to integrate the new `GlobalSearchDialog` into your existing `gui_dashboard.py` in **3 minutes**.

---

## 1. Import the Widget

Add to your imports in `gui/gui_dashboard.py`:

```python
from .ui import (
    JobStatusWidget, 
    ResultsSummaryBox, 
    RunConsolePanel, 
    SystemHealthStrip, 
    NLPModelManagerDialog,
    GlobalSearchDialog,  # <-- ADD THIS
)
```

---

## 2. Initialize in Your Main Window

In your `SmartDocOrganizerDashboard.__init__()` method, add:

```python
def __init__(self):
    super().__init__()
    
    # ... existing initialization ...
    
    # Initialize global search dialog
    self.search_dialog = GlobalSearchDialog(self)
    self.search_dialog.document_selected.connect(self.on_search_document_selected)
    
    # ... rest of initialization ...
```

---

## 3. Add Keyboard Shortcut

Add this line in your `__init__()` or in a separate `setup_shortcuts()` method:

```python
from PySide6.QtGui import QShortcut, QKeySequence

# Global search shortcut (Ctrl+K)
search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
search_shortcut.activated.connect(self.show_global_search)
```

---

## 4. Implement Handler Methods

Add these two methods to your main window class:

```python
def show_global_search(self):
    """Show the global search dialog."""
    self.search_dialog.show()
    self.search_dialog.raise_()
    self.search_dialog.activateWindow()

def on_search_document_selected(self, file_path: str):
    """Handle document selection from global search.
    
    This is called when user selects a document and presses Enter.
    """
    # Option 1: Switch to Document Processing tab and load preview
    if hasattr(self, 'tab_widget'):
        # Find the Document Processing tab
        for i in range(self.tab_widget.count()):
            if "Document Processing" in self.tab_widget.tabText(i):
                self.tab_widget.setCurrentIndex(i)
                
                # Get the tab widget and load document
                doc_tab = self.tab_widget.widget(i)
                if hasattr(doc_tab, 'document_preview'):
                    doc_tab.document_preview.load_document(file_path)
                break
    
    # Option 2: Show in status bar
    self.statusBar().showMessage(f"Selected: {file_path}", 5000)
    
    # Option 3: Open in external application
    # import os
    # os.startfile(file_path)  # Windows
    # subprocess.run(['open', file_path])  # macOS
    # subprocess.run(['xdg-open', file_path])  # Linux
```

---

## 5. Optional: Add Menu Action

If you have a menu bar, add a search menu item:

```python
def create_menu_bar(self):
    """Create the application menu bar."""
    menubar = self.menuBar()
    
    # ... existing menus ...
    
    # Edit menu
    edit_menu = menubar.addMenu("Edit")
    
    search_action = QAction("🔍 Global Search...", self)
    search_action.setShortcut(QKeySequence("Ctrl+K"))
    search_action.triggered.connect(self.show_global_search)
    edit_menu.addAction(search_action)
```

---

## Complete Integration Example

Here's the minimal code to add to your existing `gui_dashboard.py`:

```python
# At the top with imports
from PySide6.QtGui import QShortcut, QKeySequence
from .ui import GlobalSearchDialog

# In your __init__ method
class SmartDocOrganizerDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # ... existing initialization ...
        
        # Initialize global search
        self.search_dialog = GlobalSearchDialog(self)
        self.search_dialog.document_selected.connect(self.on_search_document_selected)
        
        # Ctrl+K shortcut
        search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        search_shortcut.activated.connect(self.show_global_search)
        
        # ... rest of initialization ...
    
    def show_global_search(self):
        """Show global search dialog."""
        self.search_dialog.show()
        self.search_dialog.raise_()
        self.search_dialog.activateWindow()
    
    def on_search_document_selected(self, file_path: str):
        """Handle document selection from search."""
        # Switch to Document Processing tab
        for i in range(self.tab_widget.count()):
            tab_title = self.tab_widget.tabText(i)
            if "Document Processing" in tab_title or "Organization" in tab_title:
                self.tab_widget.setCurrentIndex(i)
                
                # Try to load in preview widget
                current_tab = self.tab_widget.widget(i)
                if hasattr(current_tab, 'document_preview'):
                    current_tab.document_preview.load_document(file_path)
                    self.statusBar().showMessage(f"Opened: {os.path.basename(file_path)}", 5000)
                break
```

---

## Testing

1. **Start your application:**
   ```bash
   python Start.py
   ```

2. **Press Ctrl+K** - The search dialog should appear

3. **Type a search query** (at least 2 characters)

4. **Wait 400ms** - Results will appear automatically

5. **Use arrow keys** to navigate results

6. **Press Enter** to open the selected document

7. **Press Esc** to close the dialog

---

## Features

### Search Modes (Toggle with shortcuts)
- **Ctrl+1**: Text search only (FileIndexManager)
- **Ctrl+2**: Semantic search only (Vector Store)
- **Ctrl+3**: Combined search (default)

### Keyboard Navigation
- **Up/Down**: Navigate results
- **Enter**: Open selected document
- **Esc**: Close dialog
- **Ctrl+K**: Open dialog from anywhere

### Visual Indicators
- 🟢 **Green text**: Results from full-text search
- 🔵 **Blue text**: Results from semantic/vector search
- **Score badges**: Relevance scores for semantic results

---

## Customization

### Change Search Delay
Edit `global_search_dialog.py`, line ~270:

```python
# Default: 400ms
self.search_timer.start(400)

# Faster (200ms)
self.search_timer.start(200)

# Slower (600ms)
self.search_timer.start(600)
```

### Change Result Limit
Edit `global_search_dialog.py`, line ~165:

```python
# Default: Top 20 results
self.results_ready.emit(sorted_results[:20])

# More results (50)
self.results_ready.emit(sorted_results[:50])
```

### Change Window Size
Edit `global_search_dialog.py`, line ~256:

```python
# Default: 900x650
self.resize(900, 650)

# Larger window
self.resize(1200, 800)

# Smaller window
self.resize(700, 500)
```

---

## Troubleshooting

### "No results found" even though files exist

**Cause**: FileIndexManager database not populated.

**Fix**: Run the file indexer:
```bash
python tools/db/init_file_index.py
```

### Search is slow (>2 seconds)

**Cause**: No indexes on search columns.

**Fix**: Database optimization ran during tools/db audit. If still slow, check:
```python
# In databases/file_index.db
SELECT COUNT(*) FROM files;  # Should be ~1,155
```

### Semantic search returns nothing

**Cause**: Backend server not running or vector store empty.

**Fix**: 
1. Start backend: `python Start.py`
2. Check health: `http://127.0.0.1:8000/api/health`
3. Verify vector store has embeddings

### Dialog doesn't show on Ctrl+K

**Cause**: Shortcut conflict or not registered.

**Fix**: Check that shortcut is registered in main window's context:
```python
# Must be in __init__ of main window (QMainWindow)
search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
```

---

## Next Steps

1. ✅ **Test the basic integration** (Ctrl+K → Search → Enter)
2. ✅ **Customize the styling** to match your theme
3. ✅ **Add search history** (up/down arrows to cycle through past queries)
4. ✅ **Integrate with Document Preview Widget** for seamless browsing
5. ✅ **Add filters** (file type, date range, tags)

---

## Full Example Application

Run the standalone test:

```bash
# Test the widget independently
python gui/ui/global_search_dialog.py
```

This will open a minimal window with the search dialog for testing.

---

**Questions?** Check the implementation in `gui/ui/global_search_dialog.py` - it's fully documented with comments.

**Want more features?** See `documents/guides/PYQT6_ADVANCED_CAPABILITIES_GUIDE.md` for 9 other high-value PyQt6 features you can add!
