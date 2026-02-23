# Production Workflow - February 2026
## Smart Document Organizer Enhancement Plan

**Status Overview**: 🔄 In Progress | Created: Feb 16, 2026  
**Goal**: Add advanced NLP capabilities, interactive visualizations, and comprehensive ML optimization

---

## 📊 Current Implementation Audit

### ✅ Already Implemented & Working
- **Organization Tab**: LLM provider switching (XAI/DeepSeek), bulk operations, inline editing, checkboxes, export
- **Document Processing Tab**: File upload, text/metadata/summary extraction, basic processing
- **Knowledge Base Browser**: Reusable widget for shared data access across tabs
- **Entity Extraction Tab**: Ontology integration via FetchOntologyWorker
- **Vector Search Tab**: GUI exists, API endpoints ready (awaiting FAISS installation)
- **Ontology System**: 50+ legal entity types in `agents/extractors/ontology.py`

### 🔍 ML Libraries - Current Usage

| Library | Status | Used In | Functions |
|---------|--------|---------|-----------|
| **sentence-transformers** | ✅ Active | Embedding agents, semantic analyzer, precedent analyzer, document service, memory manager | Text embeddings, semantic similarity |
| **transformers** | ✅ Active | Semantic analyzer, NER extractors, embedding agents, production manager | NLP pipelines, token classification |
| **scikit-learn** | ✅ Partial | Semantic analyzer (KMeans, LDA, TfidfVectorizer), precedent analyzer (cosine_similarity) | Clustering, topic modeling, similarity |
| **faiss-cpu** | ⚠️ Available (dev) | **NOT USED** - Vector store routes mention it but it's not installed | Vector similarity search |
| **spacy** | ⚠️ Optional | **NOT USED** - Available in requirements-optional.txt | Industrial NLP, NER |
| **gliner** | ⚠️ Optional | **NOT USED** - Available in requirements-optional.txt | Zero-shot entity recognition |
| **plotly** | ⚠️ Optional | **NOT USED** - Available in requirements-optional.txt | Interactive charts |
| **networkx** | ⚠️ Optional | **NOT USED** - Available in requirements-optional.txt | Graph operations |

---

## 🎯 Feature Implementation Roadmap

### **PHASE 1: Document Preview & Content Viewing** 📄
**Priority**: HIGH | **Timeline**: Days 1-2 | **Requested**: "Is it gonna have where we can view the content"

#### Subtasks:
- [ ] **1.1** Design split-pane layout for Document Processing Tab
  - Left: File list with processing controls
  - Right: Content preview pane with tabs (PDF/DOCX/Text/Markdown)
  
- [ ] **1.2** Implement PDF Preview
  - Use `pymupdf` (already installed)
  - Render pages as images in QLabel or QGraphicsView
  - Add zoom controls and page navigation
  
- [ ] **1.3** Implement DOCX Preview  
  - Use `python-docx` (already installed)
  - Extract text with formatting preservation
  - Display in QTextEdit with rich text
  
- [ ] **1.4** Implement Text/Markdown Preview
  - Use `markdown` library (already installed) for .md files
  - Syntax highlighting for code files
  - Plain text viewer for .txt files
  
- [ ] **1.5** Add "Where it's going" indicator
  - Show proposed organization location
  - Display processing pipeline status (extraction → analysis → indexing)
  - Show final destination (knowledge base path, vector store ID)

**Deliverable**: Users can upload a file and immediately see its content with processing destination info

---

### **PHASE 2: NLP Model Manager** 🤖
**Priority**: HIGH | **Timeline**: Days 3-5 | **Requested**: "Set it up so all three of those can be download... click gliner or transformers and it goes to the download process"

#### Subtasks:
- [ ] **2.1** Create Model Manager Dialog/Tab
  - Add "NLP Models" button in settings or tools menu
  - Create QDialog with model installation UI
  
- [ ] **2.2** Add Model Detection
  - Check if spacy models exist in `.venv/lib/site-packages/spacy`
  - Check if gliner is installed: `importlib.util.find_spec('gliner')`
  - Check if transformers models cached in `~/.cache/huggingface`
  - Display current status: ✅ Installed | ⚠️ Not Found | 🔄 Downloading
  
- [ ] **2.3** Implement Download Handlers
  - **Spacy**: Checkbox → `python -m spacy download en_core_web_sm` subprocess
  - **Gliner**: Checkbox → `pip install gliner` + model download
  - **Transformers**: Checkbox → Download specific models (e.g., `dslim/bert-base-NER`)
  - Show progress bars using QProgressBar
  - Stream subprocess output to QTextEdit
  
- [ ] **2.4** Validate Installation
  - After download: Try `import spacy; nlp = spacy.load('en_core_web_sm')`
  - Try `import gliner; GLiNER.from_pretrained(...)`
  - Try loading transformer model
  - Display validation results: ✅ Usable | ❌ Failed | 🔧 Needs Config
  
- [ ] **2.5** Integrate with Entity Extraction
  - Add model selector in Entity Extraction tab
  - Use installed models for entity proposals

**Deliverable**: One-click model installation UI with validation and status tracking

---

### **PHASE 3: Entity Extraction Proposals System** 🏷️
**Priority**: HIGH | **Timeline**: Days 6-8 | **Requested**: "Proposals should be available before they're committed to the database"

#### Subtasks:
- [ ] **3.1** Review & Enhance Core Ontology
  - Audit `agents/extractors/ontology.py` - 50+ entity types already defined
  - Add missing legal entity types if needed
  - Ensure prompt hints are comprehensive for LLM guidance
  
- [ ] **3.2** Create Custom Entity UI
  - Add "Create Entity Type" button in Entity Extraction tab
  - Dialog: Entity Label, Attributes (list), Prompt Hint
  - Save to `config/custom_entity_types.json`
  - Load custom entities on startup
  
- [ ] **3.3** Build Entity Proposals Table
  - New section in Entity Extraction tab: "Pending Proposals"
  - Columns: Entity Text | Type | Confidence | Source Document | Status
  - Editable cells for entity type and text
  - Checkbox column for bulk operations
  
- [ ] **3.4** Add Proposal Actions
  - Approve: Commit entity to database
  - Reject: Mark as false positive
  - Edit: Modify entity type/text before committing
  - Bulk Approve/Reject: Process multiple proposals
  
- [ ] **3.5** API Integration
  - Create `/entities/proposals/generate` endpoint
  - Create `/entities/proposals/{id}/approve` endpoint
  - Create `/entities/proposals/{id}/reject` endpoint
  - Store proposals in `mem_db` with status='proposed'

**Deliverable**: Entity extraction workflow with human-in-the-loop approval before database commits

---

### **PHASE 4: Interactive Statistics Dashboard** 📊
**Priority**: MEDIUM | **Timeline**: Days 9-11 | **Requested**: "Great idea! you should make it like a switch back and forth tab inside of the tab"

#### Subtasks:
- [ ] **4.1** Install & Verify Plotly
  - Check if `plotly` is installed (it's in requirements-optional.txt)
  - If not: Add "Install Plotly" option in Model Manager
  - Validate: `import plotly.graph_objects as go`
  
- [ ] **4.2** Create Tab Switcher UI
  - Add QTabWidget to Organization tab statistics section
  - Tab 1: "Simple" - Current text-based stats
  - Tab 2: "Charts" - Interactive plotly visualizations
  
- [ ] **4.3** Build Plotly Charts
  - **Chart 1**: Proposals by Status (pie chart: proposed/approved/rejected)
  - **Chart 2**: Confidence Distribution (histogram)
  - **Chart 3**: Daily Activity (line chart: proposals generated over time)
  - **Chart 4**: Top Folders (bar chart: most active folders)
  - Use `plotly.offline.plot()` to generate HTML
  - Display in QWebEngineView (requires `PySide6-WebEngine`)
  
- [ ] **4.4** Add Interactive Features
  - Click on pie slice → filter proposals table
  - Hover on bars → show details
  - Date range selector for timeline charts
  
- [ ] **4.5** Export Chart Data
  - Add "Export Chart" button
  - Options: PNG image, HTML interactive, CSV data

**Deliverable**: Interactive charts for organization statistics with drill-down capabilities

---

### **PHASE 5: Ontology Graph Visualization** 🕸️
**Priority**: MEDIUM | **Timeline**: Days 12-15 | **Requested**: "Could visualize entity relationships from ontology! Heck yes amazing"

#### Subtasks:
- [ ] **5.1** Install & Verify Dependencies
  - Check `networkx` (in requirements-optional.txt)
  - Check `plotly` (from Phase 4)
  - Validate: `import networkx as nx`
  
- [ ] **5.2** Build Graph from Ontology
  - Parse `agents/extractors/ontology.py` relationships
  - Create networkx graph: Nodes = Entity Types, Edges = Relationships
  - Add node attributes: entity_count, attributes, prompt_hint
  - Add edge attributes: relationship_type, strength
  
- [ ] **5.3** Create Graph Viewer Tab
  - Add new tab: "Ontology Graph" or subtab in Entity Extraction
  - Use plotly network graph: `plotly.graph_objects.Scatter` for nodes/edges
  - Color nodes by category (Person, Document, Event, etc.)
  - Size nodes by entity count in database
  
- [ ] **5.4** Add Interactivity
  - Click node → Show entity details panel (attributes, count, examples)
  - Click edge → Show relationship details
  - Filter by entity category
  - Search for specific entity types
  - Zoom/pan controls
  
- [ ] **5.5** Layout Algorithms
  - Implement multiple layouts: Force-directed, Hierarchical, Circular
  - Add layout selector dropdown
  - Save/load layout preferences

**Deliverable**: Interactive graph showing ontology structure with entity relationships and statistics

---

### **PHASE 6: Excel Export Enhancement** 📑
**Priority**: MEDIUM | **Timeline**: Days 16-17 | **Requested**: "Could add Excel export with multiple sheets - Heck yes"

#### Subtasks:
- [ ] **6.1** Add Excel Option to Export
  - Update `export_proposals()` in Organization tab
  - Add "Excel Workbook (*.xlsx)" to file dialog filters
  - Verify `openpyxl` is installed (it is in requirements.txt)
  
- [ ] **6.2** Create Multi-Sheet Export
  - **Sheet 1: Proposals** - All proposal data with columns from table
  - **Sheet 2: Statistics** - Organization stats (counts, confidence averages)
  - **Sheet 3: Entities** - Extracted entities from processed documents
  - **Sheet 4: Timeline** - Chronological activity log
  
- [ ] **6.3** Add Formatting
  - Header row: Bold, colored background, frozen pane
  - Auto-width columns based on content
  - Conditional formatting: Color-code confidence scores (red/yellow/green)
  - Alternating row colors for readability
  - Number formatting: Dates, percentages, decimals
  
- [ ] **6.4** Add Charts in Excel
  - Embed Excel charts (not just data)
  - Chart 1: Proposals by status (pie)
  - Chart 2: Confidence distribution (histogram)
  - Use `openpyxl.chart` module
  
- [ ] **6.5** Apply to Other Tabs
  - Add Excel export to Document Processing tab
  - Add Excel export to Entity Extraction tab
  - Add Excel export to Semantic Analysis tab

**Deliverable**: Professional Excel exports with multiple sheets, formatting, and embedded charts

---

### **PHASE 7: ML Library Optimization** 🔬
**Priority**: MEDIUM | **Timeline**: Days 18-22 | **Requested**: "See if these things are being used and if they're not how can we best optimally implement them"

#### 7A: FAISS Vector Search Integration

- [ ] **7A.1** Install FAISS
  - Add `faiss-cpu>=1.13` to main requirements.txt (currently only in dev)
  - Test installation: `import faiss`
  - Verify numpy compatibility
  
- [ ] **7A.2** Implement FAISS Index
  - Create `services/faiss_service.py`
  - Build FAISS index from document embeddings
  - Support multiple index types: Flat (exact), IVF (approximate)
  - Save/load index from disk
  
- [ ] **7A.3** Integrate with Vector Search Tab
  - Update `/api/vector_store/vector/search` to use FAISS
  - Add "Index Type" selector: ChromaDB vs FAISS
  - Benchmark search speed: ChromaDB vs FAISS
  
- [ ] **7A.4** Add Similarity Search Features
  - "Find Similar Documents" button in Document Processing tab
  - Show top-k similar documents with scores
  - Filter by document type, date range, folder

#### 7B: Scikit-Learn Clustering & Analysis

- [ ] **7B.1** Document Clustering
  - Create `services/clustering_service.py`
  - Use KMeans to cluster documents by content similarity
  - Auto-determine optimal cluster count (elbow method)
  - Visualize clusters in 2D using t-SNE or UMAP
  
- [ ] **7B.2** Add Clustering UI
  - New tab or section: "Document Clusters"
  - Show cluster summaries: size, top keywords, representative docs
  - Interactive cluster visualization
  - Assign cluster labels manually
  
- [ ] **7B.3** Topic Modeling Enhancement
  - LDA (Latent Dirichlet Allocation) already used in semantic_analyzer
  - Enhance with interactive topic browsers
  - Show topic evolution over time
  - Export topics to Excel

#### 7C: Sentence-Transformers Optimization

- [ ] **7C.1** Model Benchmarking
  - Test multiple sentence-transformer models
  - Measure: Speed, accuracy, memory usage
  - Recommend optimal model for legal domain
  
- [ ] **7C.2** Batch Processing
  - Add batch embedding in `agents/embedding/unified_embedding_agent.py`
  - Process documents in batches of 32-64
  - Show progress bars during bulk embedding
  
- [ ] **7C.3** Embedding Cache
  - Cache embeddings in SQLite: `databases/embeddings_cache.db`
  - Check cache before re-embedding
  - Add "Clear Cache" option in settings

**Deliverable**: Optimized ML pipeline with FAISS search, document clustering, and efficient embedding

---

## 🗓️ Implementation Timeline

| Week | Phase | Features | Deliverable |
|------|-------|----------|-------------|
| **Week 1** | Phase 1 | Document Preview Pane | Content viewer with PDF/DOCX/Text rendering |
| **Week 2** | Phase 2 | NLP Model Manager | One-click spacy/gliner/transformers installation |
| **Week 2-3** | Phase 3 | Entity Proposals | Human-in-the-loop entity approval workflow |
| **Week 3** | Phase 4 | Interactive Stats | Plotly charts with drill-down |
| **Week 4** | Phase 5 | Ontology Graph | NetworkX + Plotly graph visualization |
| **Week 4** | Phase 6 | Excel Export | Multi-sheet formatted workbooks |
| **Week 5** | Phase 7 | ML Optimization | FAISS search, clustering, embedding cache |

---

## 📋 Dependencies & Prerequisites

### Required Installations (Already in requirements.txt)
- ✅ pymupdf, python-docx, markdown - Document rendering
- ✅ openpyxl - Excel export
- ✅ sentence-transformers, transformers - NLP
- ✅ scikit-learn - ML algorithms
- ✅ PySide6 - GUI framework

### Optional Installations (requirements-optional.txt)
- ⚠️ spacy - Industrial NLP (needs manual model download)
- ⚠️ gliner - Zero-shot NER
- ⚠️ plotly - Interactive charts
- ⚠️ networkx - Graph operations

### Dev Dependencies (requirements-dev.txt)  
- ⚠️ faiss-cpu - Vector similarity search (should move to main requirements)

### New Requirements
- PySide6-WebEngine - For displaying plotly HTML charts in Qt

---

## 🎯 Success Metrics

1. **Preview Pane**: Users can view document content before processing
2. **Model Manager**: One-click installation of spacy/gliner/transformers with validation
3. **Entity Proposals**: 100% of entities reviewed before database commit
4. **Interactive Stats**: Charts load in <2 seconds, support drill-down filtering
5. **Graph Visualization**: All ontology relationships visualized with <3 second load time
6. **Excel Export**: Professional formatting with multiple sheets and charts
7. **FAISS Search**: 10x faster than ChromaDB for similarity search on 10k+ documents

---

## 🚀 Next Steps

1. ✅ **Completed**: Organization tab enhancements (LLM switching, bulk ops, inline editing)
2. 🔄 **Current**: Creating production workflow document (this file)
3. ⏭️ **Next**: Begin Phase 1 - Document Preview Pane implementation

**Ready to start implementation!** Which phase would you like to tackle first?

---

## 📝 Notes & Decisions

- **Architecture**: Centralized processing model - Organization → Document Processing → Analysis Tabs
- **LLM Providers**: XAI (Grok-4-fast-reasoning) and DeepSeek integrated
- **Ontology**: 50+ legal entity types defined in `agents/extractors/ontology.py`
- **Vector Storage**: Hybrid approach - ChromaDB for persistence, FAISS for speed
- **UI Framework**: PySide6 (Qt 6) - Consistent with existing codebase

---

**Last Updated**: February 16, 2026  
**Document Owner**: Development Team  
**Status**: 🔄 Active Development
