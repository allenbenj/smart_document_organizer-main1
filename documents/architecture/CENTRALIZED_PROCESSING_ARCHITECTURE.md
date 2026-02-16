# Centralized Processing Architecture - Implementation Guide

## Overview

The Smart Document Organizer has been restructured to implement a **centralized processing model** where:

1. **Organization Tab (First Tab)** - Manages ontology-based file organization
2. **Document Processing Tab (Second Tab)** - Handles content extraction and indexing  
3. **All Other Tabs** - Consume pre-processed data from the shared knowledge base

This eliminates redundant processing and ensures consistent data across the application.

## Architecture Benefits

### ✅ Efficiency
- Documents are processed once, used everywhere
- No redundant file parsing or content extraction
- Reduced processing time and API calls

### ✅ Consistency  
- Single source of truth for document content
- Ontology-based standardization across all tabs
- Unified metadata and tagging

### ✅ Maintainability
- Simplified tab logic (consume vs. produce)
- Centralized error handling for processing
- Easier to add new analysis tabs

## Tab Structure

### 1. Organization Tab (`organization_tab.py`)
**Location**: First tab position  
**Purpose**: Ontology-based document organization workflow

**Features**:
- Browse folder scope for organizational review
- Generate AI-powered organization proposals
- Review proposals in table view (ID, Confidence, Paths)
- Approve/Reject/Refine individual proposals
- Store organized metadata in knowledge base

**Key Methods**:
- `org_load_proposals()` - Load proposals from API
- `org_generate_scoped()` - Generate new proposals  
- `org_approve_selected()` - Approve proposal
- `org_reject_selected()` - Reject proposal
- `org_edit_approve_selected()` - Refine and approve

**Usage Pattern**:
```python
# User workflow:
1. Select folder (e.g., E:\Organization_Folder\02_Working_Folder\02_Analysis\08_Interviews)
2. Click "Generate Scoped" to create proposals
3. Review proposals in table
4. Select proposal and either:
   - Approve as-is
   - Refine folder/filename and approve
   - Reject with note
5. Organized metadata stored in knowledge base
```

### 2. Document Processing Tab (`document_processing_tab.py`)
**Location**: Second tab position  
**Purpose**: Content extraction and preparation pipeline

**Features**:
- File upload (drag-drop, browse)
- Processing options:
  - Extract text content
  - Extract metadata
  - Analyze content structure
  - Generate summaries
  - Index to vector store
- Progress tracking
- Results display
- Export processed results (JSON/Text)

**Key Methods**:
- `add_files()` - Add files for processing
- `start_processing()` - Begin processing pipeline
- `on_processing_finished()` - Handle results
- `export_json()` / `export_text()` - Export results

**Usage Pattern**:
```python
# User workflow:
1. Drag-drop files or click "Add Files"
2. Select processing options (text, metadata, summary, vector indexing)
3. Click "Process Documents"
4. View results in right panel
5. Export if needed
6. Processed content now available in knowledge base for all other tabs
```

### 3. Consumer Tabs (Semantic Analysis, Entity Extraction, etc.)

**New Capability**: Load from Knowledge Base

All analysis tabs can now optionally load pre-processed documents instead of uploading/processing again.

**Integration Pattern**:
```python
# In any tab's __init__:
from gui.ui import KnowledgeBaseBrowser

self.kb_browser = KnowledgeBaseBrowser()
self.kb_browser.document_selected.connect(self.on_kb_document_selected)
layout.addWidget(self.kb_browser)

# Handler method:
def on_kb_document_selected(self, document: dict):
    """Handle document loaded from knowledge base."""
    content = document.get("content", "")
    file_path = document.get("file_path", "")
    # Use pre-processed content directly
    self.text_input.setPlainText(content)
    self.status.info(f"Loaded from KB: {document.get('title')}")
```

## Knowledge Base Browser Widget

**File**: `gui/ui/knowledge_base_browser.py`  
**Purpose**: Reusable widget for accessing centrally processed documents

**Features**:
- Search bar for filtering documents
- Document list with metadata
- Load selected document
- Show document info
- Refresh capability

**Signals**:
- `document_selected(dict)` - Emitted when user selects/loads a document

**API Endpoint**:
The widget queries: `GET /knowledge/documents?limit=100`

**Expected Response**:
```json
{
  "documents": [
    {
      "id": "doc_123",
      "title": "Interview Notes",
      "filename": "Freeman-Happel_Call_1_Interview_Notes.md",
      "file_path": "/mnt/e/Organization_Folder/02_Working_Folder/02_Analysis/08_Interviews/...",
      "content": "Full document content...",
      "processed_date": "2026-02-16T10:30:00Z",
      "size": 45678,
      "metadata": {
        "author": "...",
        "date": "..."
      }
    }
  ]
}
```

## Implementation Checklist for New Tabs

When creating a new analysis tab:

- [ ] Import `KnowledgeBaseBrowser` from `gui.ui`
- [ ] Add widget to tab layout
- [ ] Connect `document_selected` signal to handler
- [ ] Implement handler to use pre-processed content
- [ ] Keep existing file upload as alternative
- [ ] Update UI to indicate data source (KB vs. uploaded)

## Migration Guide for Existing Tabs

To update existing tabs to leverage centralized processing:

### 1. Add Knowledge Base Browser
```python
from gui.ui import KnowledgeBaseBrowser

# In setup_ui():
self.kb_group = QGroupBox("Load from Knowledge Base")
kb_layout = QVBoxLayout()
self.kb_browser = KnowledgeBaseBrowser()
self.kb_browser.document_selected.connect(self.on_kb_document_loaded)
kb_layout.addWidget(self.kb_browser)
self.kb_group.setLayout(kb_layout)
layout.addWidget(self.kb_group)
```

### 2. Add Signal Handler
```python
def on_kb_document_loaded(self, document: dict):
    """Load document from knowledge base."""
    # Extract pre-processed content
    content = document.get("content", "")
    metadata = document.get("metadata", {})
    file_path = document.get("file_path", "")
    
    # Populate UI with pre-processed data
    self.text_input.setPlainText(content)
    self.file_path.setText(file_path)
    
    # Update status
    title = document.get("title", "document")
    self.status.info(f"✓ Loaded from knowledge base: {title}")
    
    # Optional: Auto-run analysis
    # self.start_analysis()
```

### 3. Update Processing Logic
```python
def start_analysis(self):
    # Check if content is from KB (already processed)
    if hasattr(self, 'kb_browser') and self.kb_browser.get_selected_document():
        # Use pre-processed content - skip extraction
        content = self.text_input.toPlainText()
        self.run_analysis_only(content)
    else:
        # Traditional flow: upload, extract, then analyze
        self.upload_and_process()
```

## Data Flow Diagram

```
┌─────────────────────┐
│  Organization Tab   │ ← User organizes files with ontology
└──────────┬──────────┘
           │
           ↓ (Approved proposals stored)
┌─────────────────────┐
│   Knowledge Base    │
│   (Metadata Store)  │
└─────────────────────┘
           ↑
           │
┌──────────┴──────────┐
│ Document Processing │ ← User uploads & processes files
│       Tab           │
└──────────┬──────────┘
           │
           ↓ (Extracted content + vectors indexed)
┌─────────────────────┐
│   Knowledge Base    │
│  (Vector Store +    │
│   Content Cache)    │
└──────────┬──────────┘
           │
           ↓ (All tabs query for pre-processed data)
┌──────────┴──────────────────────────────────────┐
│                                                  │
│  ┌──────────────┐  ┌────────────────┐           │
│  │  Semantic    │  │    Entity      │           │
│  │   Analysis   │  │  Extraction    │  ...etc.  │
│  └──────────────┘  └────────────────┘           │
│                                                  │
│  ┌──────────────┐  ┌────────────────┐           │
│  │    Legal     │  │ Classification │           │
│  │  Reasoning   │  │                │           │
│  └──────────────┘  └────────────────┘           │
│                                                  │
└──────────────────────────────────────────────────┘
    ↑
    └── All tabs consume shared, pre-processed data
```

## Testing the Workflow

### Test Case 1: Organization + Processing
1. Launch application
2. Navigate to **Organization** tab (first tab)
3. Enter folder path: `E:\Organization_Folder\02_Working_Folder\02_Analysis\08_Interviews`
4. Click "Review Proposals"
5. Verify proposals load in table
6. Select a proposal, click "Approve"
7. Navigate to **Document Processing** tab
8. Drag-drop files from 08_Interviews folder
9. Check all processing options
10. Click "Process Documents"
11. Verify results appear with content preview
12. Export JSON to verify structure

### Test Case 2: Consumer Tab with KB
1. Complete Test Case 1 first
2. Navigate to **Semantic Analysis** tab
3. Look for "Knowledge Base" section
4. Click refresh in KB browser
5. Verify processed documents appear
6. Double-click a document
7. Verify content loads in text input
8. Click "Analyze Document"
9. Verify analysis runs without re-uploading

### Test Case 3: Cross-Tab Consistency
1. Process document in Document Processing tab
2. Load same document in Semantic Analysis tab from KB
3. Load same document in Entity Extraction tab from KB
4. Verify content is identical across all tabs
5. Verify no redundant processing occurred

## Backend API Requirements

The centralized architecture requires these API endpoints:

### Organization Endpoints
- `GET /organization/proposals?status={status}&limit={limit}&offset={offset}`
- `POST /organization/proposals/generate`
- `POST /organization/proposals/clear`
- `POST /organization/proposals/{id}/approve`
- `POST /organization/proposals/{id}/reject`
- `POST /organization/proposals/{id}/edit`

### Knowledge Base Endpoints (NEW)
- `GET /knowledge/documents?limit={limit}&offset={offset}` - List processed documents
- `GET /knowledge/documents/{id}` - Get specific document with full content
- `GET /knowledge/documents/search?query={query}` - Semantic search
- `POST /knowledge/documents/bulk` - Batch upload from Document Processing tab

### Processing Endpoints
- `POST /documents/upload/many` - Upload and process multiple files
- `GET /documents/{id}/content` - Get extracted content
- `GET /documents/{id}/metadata` - Get extracted metadata

## Performance Considerations

### Caching Strategy
- Knowledge Base Browser caches document list locally
- Refresh button re-queries API
- Documents loaded on-demand (not all content upfront)

### Vector Store Integration
- Document Processing tab indexes content to vector store
- Enables semantic search across all tabs
- Supports "find similar documents" functionality

### Ontology Application
- Organization tab applies ontology to file structure
- Document Processing tab applies ontology to content tagging
- Consumer tabs query by ontology-based tags

## Future Enhancements

1. **Live Sync**: Real-time updates when documents are processed
2. **Batch Operations**: Bulk approve/reject in Organization tab
3. **Smart Suggestions**: AI-powered refinement suggestions
4. **Version History**: Track document processing versions
5. **Cross-Tab State**: Selected document persists across tab switches

## Troubleshooting

### Issue: KB Browser shows no documents
- Check backend `/knowledge/documents` endpoint is implemented
- Verify documents were processed with vector indexing enabled
- Check API connectivity in console

### Issue: Document loads but is empty
- Ensure content extraction was enabled during processing
- Check document format is supported
- Verify content field exists in API response

### Issue: Organization proposals not loading
- Verify folder path format (Windows vs. WSL)
- Check proposals were generated for that scope
- Try "Generate Scoped" first

## Summary

The centralized processing architecture provides:
- **Organization Tab**: Ontology-based file management (Tab 1)
- **Document Processing Tab**: Content extraction pipeline (Tab 2)  
- **Knowledge Base Browser**: Shared data access for all tabs
- **Consumer Tabs**: Analysis without redundant processing

This structure ensures efficient, consistent, and maintainable document management
across the entire application.
