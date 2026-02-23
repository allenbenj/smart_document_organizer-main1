# Gemini Project Context

## 1. Project Overview
This project is a **[Organizer / legal tool, e.g.,pyq6 gui that needs a lot of help]** aimed at **helping organize and assist in legal advice when asked**.
1. **FastAPI Backend** - [`Start.py`](Start.py) - Entry point with API routes
2. **API Routes** - `routes/` directory
   - `routes/agents.py` - Agent management endpoints
   - `routes/health.py` - Health check and system status
   - `routes/documents.py`, `routes/search.py`, `routes/tags.py` - Document management
   - `routes/knowledge.py`, `routes/vector_store.py`, `routes/ontology.py` - Knowledge management
3. **Agents Module** - `agents/` directory
   - `production_agent_manager.py` - Main agent orchestrator
   - `simple_agent_manager.py` - Fallback HTTP-based manager
   - `legal/` - Legal reasoning agents (IRAC, Toulmin, reasoning engine)
   - `extractors/` - Entity extraction agents (hybrid, GLiNER, NLP)
   - `analysis/` - DAG orchestrator and semantic analysis
4. **Database Layer** - `mem_db/` directory
   - `database.py` - SQLite document database manager
   - `memory/unified_memory_manager.py` - Unified memory with ChromaDB/FAISS vector search
   - `vector_store/unified_vector_store.py` - FAISS-based vector indexing
   - `knowledge/unified_knowledge_graph_manager.py` - Knowledge graph management
5. **GUI** - `gui/` directory
   - `gui_dashboard.py` - PySide6 main dashboard with multiple analysis tabs
   - `memory_review_tab.py`, `memory_analytics_tab.py` - Memory management
6. **Tests** - `tests/` directory - pytest suite
7. **Configuration** - `config/` and `agents/config/` directories
Dependacies
- FastAPI, Uvicorn, Starlette - Web framework
- PySide6 - GUI framework
- SQLite3, aiosqlite - Database
- ChromaDB, FAISS - Vector search
- sentence-transformers, transformers - Embeddings and NLP
- spaCy, fitz (PyMuPDF), python-docx - Document processing
- numpy, torch - Numerical computations
- requests, aiohttp - HTTP clients
- asyncio, threading - Concurrency

What the System Was INTENDED to Do
├── Serve as a Legal AI platform for document analysis
├── Provide multiple reasoning frameworks (IRAC, Toulmin, etc.)
├── Extract legal entities and relationships from documents
├── Offer a PySide6 GUI dashboard for user interaction
├── Provide RESTful API endpoints
├── Manage document storage and retrieval
├── Support vector-based semantic search
├── Implement knowledge graph management
├── Provide memory review and analytics capabilities
└── Handle various document formats (PDF, DOCX, TXT, etc.) and organize them based off their content using mutltiple advanced techniques that are symplified through the GUI

What the System ACTUALLY Does
├── Fails to start due to structural issues in main entry point
├── Has conflicting agent managers (production vs. simple)
├── Missing core imports and modules
├── Tests fail due to import mismatches
├── GUI fails to connect to backend
└── Database connections fail


## 2. Coding Style & Conventions
> **Rule #1:** Always prioritize readability over cleverness.

### Syntax Preferences
- **TypeScript:** Use `interface` for public APIs and `type` for internal unions/intersections.
- **Functions:** Prefer `const` arrow functions for components; standard `function` keywords for hoisting utilities.
- **Imports:** Absolute imports (`@/components/...`) over relative (`../../`).
- **Async:** Always use `async/await` over `.then()` chains.

### Error Handling
- Do not swallow errors. Log them to the console or an error service.
- Use strict null checks. Avoid `any` unless absolutely necessary (and comment why).

## 3. Architecture Patterns
- **Directory Structure:** 'Feature-based' folders (e.g., `/features/auth`, `/features/cart`) rather than 'Type-based' (`/components`, `/hooks`).
- **Data Fetching:** All API calls must go through the `/services` layer. Components should never call `fetch` directly.
- **Testing:** We use Jest + React Testing Library. Write tests for happy paths and one failure case.

## 4. Forbidden Practices (The "Do Not" List)
- 🚫 **Do NOT** use `export default`. Use named exports only to ensure consistent naming.
- 🚫 **Do NOT** include comments that say what code does (e.g., `// loop through array`). Only comment *why* complex logic exists.
- 🚫 **Do NOT** suggest deprecated libraries (e.g., `moment.js` -> use `date-fns` instead).

## 5. Tone & Output Format
- **Brevity:** Do not give me a lecture. Give me the code first, then a brief explanation if needed.
- **Diffs:** When updating code, show the surrounding lines so I know where to paste it.
- **Safety:** Always check for potential security vulnerabilities (SQL injection, XSS) in your suggestions.