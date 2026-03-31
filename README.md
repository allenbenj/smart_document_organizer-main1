# Smart Document Organizer

**Adaptive Epistemic Document Intelligence System (AEDIS)**

A modern, open-source Legal AI platform combining a **PySide6 desktop GUI** with a **FastAPI backend** for structured document analysis, entity modeling, knowledge graph construction, and multi-round adjudication workflows.

## Open Source License

This project is released under the **MIT License**.

You are free to use the software commercially, modify the source code, distribute copies, and create derivative works — provided that the original copyright and license notice are included. See the [LICENSE](LICENSE) file for full terms.

## Purpose

Smart Document Organizer provides a structured analytical environment designed to:

- Manage document-centric case workflows
- Execute multi-round reasoning pipelines
- Maintain versioned entity and relationship graphs
- Attach evidence spans to structured claims
- Support human-in-the-loop ACK validation
- Feed curated knowledge back into iterative analytical rounds

The system emphasizes:

- **Provenance** — all analytical claims traced to source evidence
- **Deterministic state transitions** — reproducible pipeline behavior
- **Version-controlled knowledge** — entity and relationship versioning
- **Modular service architecture** — decoupled backend services, agent layer, and GUI

## Architecture

The application consists of two runtime tiers:

| Tier | Technology | Entry Point | Purpose |
|------|-----------|-------------|---------|
| **Backend** | FastAPI + Uvicorn | `python Start.py` | REST API, agent orchestration, persistence, NLP pipelines |
| **GUI** | PySide6 | `python launch.py` | Desktop dashboard, document viewer, analysis tabs |

The GUI connects to the backend over HTTP (`http://127.0.0.1:8000` by default). The launcher (`launch.py`) can optionally manage the backend lifecycle automatically.

### Project Layout

```
Start.py                  # FastAPI backend entry point
launch.py                 # Unified GUI launcher (manages backend + GUI)
app/bootstrap/            # Router registration, lifecycle loops
routes/                   # FastAPI route modules (25+ route groups)
services/                 # Domain service layer (30+ services)
agents/                   # Production agents, fallback agents, orchestration
  ├── processors/         # Document processing agents
  ├── extractors/         # Entity extraction agents
  ├── legal/              # IRAC, Toulmin, legal reasoning agents
  ├── base/               # Base agent, factory, registry
  └── orchestration/      # Message bus, coordination
gui/                      # PySide6 desktop application
  ├── professional_manager.py  # Main GUI window
  ├── tabs/               # 20+ functional tabs
  ├── ui/                 # Widgets (search, preview, tray icon)
  ├── services/           # API client, adapters
  └── core/               # Async threading, base tab
mem_db/                   # SQLite persistence, migrations, vector store
  ├── migrations/phases/  # Schema migration scripts (p1–p3)
  ├── repositories/       # Data access layer
  └── vector_store/       # Embedding storage
config/                   # Configuration manager, extraction patterns
core/                     # LLM providers, service container, tracing
diagnostics/              # Startup report, bug tracker, import analyzer
tests/                    # 100+ test files
```

### Design Principles

- Separation of UI and service layers
- Centralized API access via `gui/services/api_client.py`
- Thread-safe background workers in the GUI
- SQLite-backed persistence with versioned migrations
- Dependency injection via `ProductionServiceContainer`

## Core Capabilities

### Case Adjudication Pipeline
- 3-round analytical execution with pause/resume controls
- Human ACK gating between rounds
- Deterministic knowledge feedback

### Entity & Relationship Editor
- Versioned entity records with editable relationships
- Evidence span attachment and confidence scoring
- SQLite persistence

### Legal Reasoning Agents
- IRAC analysis (Issue, Rule, Application, Conclusion)
- Toulmin argumentation modeling
- Legal entity extraction with hybrid NLP backends

### Database Monitoring
- Live SQLite health metrics and task queue controls
- API cost visibility and structured trace inspection

### Knowledge Architecture
- Immutable document anchors with mutable analytical layer
- Versioned entity graph and human-reviewed ACK records
- Ontology registry with provenance tracking

## Installation

### Requirements

- **Python 3.10+**
- **OS**: Windows 10/11 (native or WSL), Linux, macOS

### Quick Start

```bash
git clone https://github.com/allenbenj/smart_document_organizer-main1.git
cd smart_document_organizer-main1
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

### Starting the Application

**Option A — Launcher (recommended):** Manages backend lifecycle and launches the GUI.

```bash
python launch.py              # Starts backend + opens GUI
python launch.py --modular    # Launch Modular System UI (default)
python launch.py --platform   # Launch Platform Manager UI
```

**Option B — Backend only:** Starts the FastAPI server directly.

```bash
python Start.py               # Starts on http://127.0.0.1:8000
```

**Option C — Backend verification:**

```bash
python Start.py --help        # Show backend CLI options
python launch.py --help       # Show launcher CLI options
```

### Dependency Tiers

| Tier | File | Covers |
|------|------|--------|
| **Core runtime** | `requirements.txt` | FastAPI, PySide6, document processing, NLP, persistence |
| **Optional extras** | `tools/requirements-optional.txt` | ChromaDB, advanced vector stores |
| **Development** | `pytest`, `black`, `isort` (in requirements.txt) | Testing and code quality |

### Environment Variables (optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `API_KEY` | `""` | API key for route protection |
| `STARTUP_PROFILE` | `full` | Startup profile: `api`, `minimal`, `full`, `gui` |
| `AGENTS_LAZY_INIT` | `true` | Lazy-initialize agents on first use |
| `STARTUP_OFFLINE_SAFE` | `true` | Skip network-dependent checks at startup |

## Development Guidelines

Contributors should:

- Maintain the two-tier architecture (FastAPI backend + PySide6 GUI)
- Preserve versioned entity + ACK semantics
- Keep modules modular and decomposed
- Route all external API calls through the central service layer (`gui/services/api_client.py`)
- Add tests for new services and routes under `tests/`
- Run `python -m compileall .` before committing to catch syntax errors

## Known Limitations

- Legacy Office formats (`.doc`, `.xls`, `.ppt`) are not yet fully supported; use modern formats (`.docx`, `.xlsx`, `.pptx`)
- NLP models (`sentence-transformers`, `spacy`) require initial download on first use
- The GUI requires the backend to be running for most operations
- WSL users may need to configure `WSL_DISTRO` and project path environment variables

Contributing

Pull requests are welcome.

Before submitting:

Open an issue describing the change.

Keep changes modular.

Avoid architectural drift.

Maintain backward compatibility where practical.

Disclaimer

This software is provided “as is”, without warranty of any kind, express or implied, including but not limited to fitness for a particular purpose or noninfringement.

See the MIT License for full details.
