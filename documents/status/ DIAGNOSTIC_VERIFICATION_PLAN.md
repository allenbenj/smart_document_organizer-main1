# Smart Document Organizer - Comprehensive Diagnostic & Verification Plan

**Created**: February 16, 2026  
**Purpose**: End 4 days of startup frustration with systematic diagnostics, bug tracking, and verification

## TL;DR

After 4 days of fighting startup failures, we're implementing **diagnostics-first development**. New tools give you visibility into every startup step, every API call, and every failure. Track bugs without losing context. Test systematically with full observability. No more guessing - see exactly what's breaking and when.

**Immediate Actions**:
1. ✅ **DONE**: Created diagnostic logging system (GUI, backend, API communication, bug tracker)
2. **NOW**: Integrate diagnostics into startup sequence  
3. **NEXT**: Fix violations tab bug with full visibility
4. **THEN**: Test all 15 tabs systematically with logs

---

## Phase 0: Observability Infrastructure (DIAGNOSTIC-FIRST) 🔍

**Goal**: Never debug blind again. Every startup, every API call, every failure is logged.

### ✅ Completed: Diagnostic Tools Created

**New Files**:
- [diagnostics/gui_startup_log.py](diagnostics/gui_startup_log.py) - Detailed GUI startup tracking
- [diagnostics/backend_startup_log.py](diagnostics/backend_startup_log.py) - Backend initialization logging
- [diagnostics/api_communication_log.py](diagnostics/api_communication_log.py) - Request/response tracking  
- [diagnostics/bug_tracker.py](diagnostics/bug_tracker.py) - In-app bug tracking system
- [gui/tabs/diagnostics_tab.py](gui/tabs/diagnostics_tab.py) - GUI tab to view logs & bugs

**What These Do**:
1. **GUI Startup Logger**: Tracks every step of GUI initialization
   - Module imports (which failed?)
   - Component initialization (which tab crashed?)
   - Backend health checks (is it even running?)
   - Tab creation (which 15 tabs succeeded?)
   - Writes to: `logs/gui_startup_YYYYMMDD_HHMMSS.log`

2. **Backend Startup Logger**: Tracks FastAPI/Uvicorn startup
   - Environment variables
   - Agent loading (which agents failed?)
   - Route registration (which endpoints are missing?)
   - Database connections
   - Model loading (GLiNER, BERT, etc.)
   - Writes to: `logs/backend_startup_YYYYMMDD_HHMMSS.log`

3. **API Communication Logger**: Tracks every GUI ↔ Backend request
   - Request method, URL, payload
   - Response status, timing, errors
   - Connection failures
   - Timeouts
   - Statistics (success rate, avg response time)
   - Writes to: `logs/api_communication_YYYYMMDD_HHMMSS.log`

4. **Bug Tracker**: Persistent bug tracking without losing context
   - In-app bug reporting
   - Severity, category, component tracking
   - Reproduction steps
   - Stack traces  
   - Status updates (Open → In Progress → Fixed)
   - Export to markdown reports
   - Stores in: `logs/bugs.json`

### 🔨 TODO: Integration Steps

**Step 1: Integrate GUI Startup Logging**
- File: [gui/gui_dashboard.py](gui/gui_dashboard.py)
- Changes needed:
  ```python
  # Import at top
  from diagnostics.gui_startup_log import get_startup_logger
  
  # In __init__:
  self.startup_log = get_startup_logger()
  self.startup_log.step("Initializing GUI Dashboard")
  
  # Before each major step:
  self.startup_log.step("Loading API Client")
  self.startup_log.component_init("ApiClient", success=True)
  
  # For backend health check:
  self.startup_log.backend_check(url, healthy=True, response_time_ms=elapsed)
  
  # For each tab:
  self.startup_log.tab_creation("Organization Tab", success=True)
  
  # At end:
  self.startup_log.finalize(success=True)
  ```

**Step 2: Integrate Backend Startup Logging**
- File: [Start.py](Start.py)
- Changes needed:
  ```python
  # Import
  from diagnostics.backend_startup_log import get_backend_logger
  
  # In _startup_services():
  logger = get_backend_logger()
  logger.step("Starting Services")
  logger.agent_loaded("document_processor", success=True, load_time_s=2.5)
  logger.database_check(db_path, exists=True, size_mb=15.2)
  logger.finalize(success=True, server_url="http://127.0.0.1:8000")
  ```

**Step 3: Integrate API Communication Logging**
- File: [gui/services/__init__.py](gui/services/__init__.py) (ApiClient class)
- Changes needed:
  ```python
  # Import
  from diagnostics.api_communication_log import get_api_logger
  
  # In _make_request():
  api_log = get_api_logger()
  request_id = api_log.log_request(method, url, headers, payload)
  
  # After response:
  api_log.log_response(request_id, status_code, response_time_ms, response_body)
  
  # On error:
  api_log.log_connection_error(request_id, url, error)
  ```

**Step 4: Add Diagnostics Tab to GUI**
- File: [gui/gui_dashboard.py](gui/gui_dashboard.py)
- Changes needed:
  ```python
  # Import
  from gui.tabs.diagnostics_tab import DiagnosticsTab
  
  # In _build_analysis_tabs():
  diag_tab = DiagnosticsTab()
  self.analysis_tabs.addTab(diag_tab, "🔍 Diagnostics")
  ```

**Verification**:
- ✅ GUI starts → Check `logs/gui_startup_*.log` for detailed trace
- ✅ Backend starts → Check `logs/backend_startup_*.log` for agent loading
- ✅ GUI makes API call → Check `logs/api_communication_*.log` for request/response
- ✅ Open Diagnostics tab → See all logs, can report bugs

**Deliverable**: Full observability. When something fails, you know exactly what, when, and why.

---

## Phase 1: Fix Known Critical Bugs 🐛

**Goal**: Fix the 1 critical bug blocking verification testing.

### Bug #1: Violations Tab - AttributeError (CRITICAL)

**File**: [gui/violations_tab.py](gui/violations_tab.py)  
**Line**: 81  
**Issue**: References `self.output` but widget is named `self.result`

**Error**:
```
AttributeError: 'ViolationsTab' object has no attribute 'output'
```

**Fix**:
```python
# BEFORE (line 81):
self.output.setPlainText(str(result))

# AFTER:
self.result.setPlainText(str(result))
```

**Impact**: Violations tab completely broken - crashes when Analyze button clicked.

**Test After Fix**:
1. Start backend + GUI
2. Open Violations tab
3. Load sample text
4. Click "Analyze"
5. ✅ Should see results without crash
6. Document in Bug Tracker if fails

---

## Phase 2: Systematic Tab Verification 🧪

**Goal**: Test all 15 GUI tabs methodically with full diagnostic visibility.

### Core Workflow Tabs (Test First)

**Test Data**: `E:\Organization_Folder\02_Working_Folder\02_Analysis\08_Interviews`

#### 1. Organization Tab
- **Purpose**: AI-powered document organization with ontology
- **API Endpoints**: `/api/organization/*`
- **Worker**: ProposalGeneratorWorker
- **Test Steps**:
  1. Click "Load Current LLM Provider" → Should show provider (OpenAI/Groq)
  2. Select test folder
  3. Click "Generate Proposals" → Worker starts
  4. Wait for completion → Check proposals in text area
  5. ✅ Success: Proposals generated
  6. ❌ Failure: Check `api_communication` log for endpoint errors

#### 2. Document Processing Tab
- **Purpose**: Upload, process, extract content from documents
- **API Endpoints**: `/api/agents/upload-many`, `/api/agents/extract`, `/api/agents/index-document`
- **Workers**: UploadManyFilesWorker, ContentExtractorWorker, VectorIndexWorker
- **Test Steps**:
  1. Click "📂 Add Folder" → Select test folder
  2. Files should populate list
  3. Check options: "🔍 Extract Content", "🧠 Generate Summary", "📊 Index to Vector Store"
  4. Click "▶ Start Processing"
  5. Monitor progress bar
  6. ✅ Success: All files processed, summaries shown
  7. ❌ Failure: Check which worker failed in logs

#### 3. Memory Review Tab
- **Purpose**: Review AI proposals, approve/reject
- **API Endpoints**: `/api/knowledge/proposals`, `/api/knowledge/approve`, `/api/knowledge/reject`
- **Test Steps**:
  1. Click "Load Proposals" → Should fetch from Organization tab
  2. Review proposals in table
  3. Select proposal → Click "Approve" or "Reject"
  4. ✅ Success: Proposal status updated
  5. Check Memory Analytics tab for statistics

### Analysis Tabs (Core Functionality)

#### 4. Semantic Analysis Tab
- **Endpoint**: `/api/agents/semantic-analysis`
- **Test**: Load doc → Analyze → Check summary, topics, sentiment, key phrases
- **Success Criteria**: JSON results with all 4 sections

#### 5. Entity Extraction Tab
- **Endpoint**: `/api/agents/extract-entities`
- **Test**: Fetch ontology → Extract entities → Verify confidence scores
- **Success Criteria**: Entities extracted with types from ontology

#### 6. Legal Reasoning Tab
- **Endpoints**: `/api/agents/irac-analysis`, `/api/agents/toulmin-analysis`
- **Test**: Run both IRAC and Toulmin → Check structured output
- **Success Criteria**: Issue, Rule, Application, Conclusion fields populated

#### 7. Classification Tab
- **Endpoint**: `/api/agents/classify-zero-shot`
- **Test**: Multiple labels → Test different models → Verify scores
- **Success Criteria**: Label scores sum to ~1.0

#### 8. Violations Tab (After Fix)
- **Endpoint**: `/api/agents/violations`
- **Test**: Load text → Analyze → Check violations list
- **Success Criteria**: No AttributeError, violations displayed

### Advanced Feature Tabs

#### 9. Embedding Operations Tab
- **Endpoints**: `/api/agents/generate-embedding`, `/api/agents/semantic-similarity`
- **Test**: Generate embeddings → Compare similarity → Visualize
- **Dependencies**: Optional (sentence-transformers)

#### 10. Knowledge Graph Tab
- **Endpoints**: `/api/knowledge/entities`, `/api/knowledge/relationships`
- **Test**: Build graph → Export → Visualize
- **Success Criteria**: Nodes and edges created

#### 11. Vector Search Tab
- **Endpoint**: `/api/vector/search`
- **Test**: Search query → Results with scores
- **Dependencies**: ChromaDB (optional)
- **Expected**: May be degraded if ChromaDB not installed

#### 12. Pipelines Tab
- **Endpoint**: `/api/pipeline/run`
- **Worker**: PipelineRunnerWorker
- **Test**: Select pipeline → Run → Monitor progress
- **Known Issue**: Pipeline router may have message_bus dependency issue (P1)

#### 13. Expert Prompts Tab
- **Endpoint**: `/api/agents/expert-prompt`
- **Test**: Run expert system prompts → Check responses

#### 14. Contradictions Tab
- **Endpoint**: `/api/knowledge/contradictions`
- **Test**: Load → Analyze → Export
- **Success Criteria**: Contradiction pairs identified

#### 15. Memory Analytics Tab
- **Endpoint**: `/api/knowledge/analytics`
- **Test**: Load stats → View charts → Export
- **Success Criteria**: Graphs render, statistics accurate

### Verification Checklist

For EACH tab, document in Bug Tracker if any test fails:

- [ ] Tab loads without crash
- [ ] API endpoint responds (check `api_communication` log)
- [ ] Worker completes (check GUI logs)
- [ ] Results displayed correctly
- [ ] No console errors
- [ ] Performance acceptable (<5s for simple operations)

### Bug Reporting Template

When a test fails, immediately report in Diagnostics tab:

**Title**: "{Tab Name} - {Failure Description}"  
**Severity**: Critical/High/Medium/Low  
**Category**: UI/API/Processing  
**Component**: {Tab Name}  
**Reproduction Steps**:
1. Start backend + GUI
2. Navigate to {Tab Name}
3. {Specific action that triggers failure}
4. Observe: {Error message / behavior}

**Attach Logs**:
- `logs/gui_startup_*.log`
- `logs/api_communication_*.log`
- Stack trace from console

---

## Phase 3: End-to-End Integration Testing 🔗

**Goal**: Test data flow across multiple tabs (full pipeline).

### Workflow 1: Organization → Processing → Memory

**Scenario**: Organize documents, process them, review proposals

**Steps**:
1. **Organization Tab**: Generate proposals for test folder
2. **Document Processing Tab**: Process same documents (extract + summarize + index)
3. **Memory Review Tab**: Load proposals → Verify they match documents → Approve some
4. **Memory Analytics Tab**: Check stats → Should show approved proposals

**Success Criteria**:
- Proposals generated match documents processed
- Memory system persists approved proposals
- Analytics reflect approved count
- Vector store indexed documents (if ChromaDB available)

### Workflow 2: Document → Extract → Graph → Search

**Scenario**: Full analysis pipeline

**Steps**:
1. **Document Processing Tab**: Upload doc → Extract content
2. **Entity Extraction Tab**: Extract entities from doc
3. **Knowledge Graph Tab**: Build graph from entities
4. **Vector Search Tab**: Search for doc content

**Success Criteria**:
- Entities extracted appear in knowledge graph
- Vector search finds processed document
- Graph visualization renders

### Workflow 3: Legal Analysis Chain

**Scenario**: Comprehensive legal document analysis

**Steps**:
1. **Semantic Analysis Tab**: Analyze legal doc → Get summary + sentiment
2. **Legal Reasoning Tab**: Run IRAC analysis → Get structured reasoning
3. **Violations Tab**: Check for violations → Get violation list
4. **Contradictions Tab**: Find contradictions → Cross-reference

**Success Criteria**:
- All tabs process same document successfully
- Results are coherent (e.g., violent clauses in violations match IRAC issues)
- No data loss between steps

---

## Phase 4: Automated Testing (Future-Proofing) 🤖

**Goal**: Create test suite so we never repeat 4 days of manual debugging.

### Test Suite Structure

**File**: `tests/test_gui_smoke.py`
```python
"""Smoke tests - Does the GUI start without crashing?"""

def test_gui_starts():
    """GUI launches and shows main window."""
    
def test_all_tabs_load():
    """All 15 tabs can be created without exceptions."""
    
def test_backend_connection():
    """GUI can connect to backend health endpoint."""
```

**File**: `tests/test_tab_functionality.py`
```python
"""Functional tests - Do primary buttons work?"""

def test_organization_tab_generate_proposals():
    """Organization tab can generate proposals."""
    
def test_document_processing_upload():
    """Document processing tab can upload files."""
    
# ... one test per tab primary function
```

**File**: `tests/test_gui_integration.py`
```python
"""Integration tests - Do workflows complete end-to-end?"""

def test_organization_to_memory_workflow():
    """Full workflow: generate → process → review → approve."""
```

---

## Immediate Next Actions (Priority Order)

### 🔥 P0 - Critical Path

1. **Integrate Diagnostics** (30 minutes)
   - Add startup logging to [gui_dashboard.py](gui/gui_dashboard.py)
   - Add startup logging to [Start.py](Start.py)
   - Add API logging to [ApiClient](gui/services/__init__.py)
   - Add Diagnostics tab to GUI
   - **Deliverable**: Can see detailed logs on next startup

2. **Fix Violations Bug** (5 minutes)
   - Change `self.output` → `self.result` in line 81
   - Test Violations tab
   - **Deliverable**: Violations tab works

3. **First Startup with Full Diagnostics** (15 minutes)
   - Run `.\run_clean.ps1`
   - Open GUI → Check Diagnostics tab
   - Review `logs/gui_startup_*.log`
   - Review `logs/backend_startup_*.log`
   - **Deliverable**: Complete visibility into startup process

### 🎯 P1 - Core Verification

4. **Test Core Workflow** (1 hour)
   - Organization tab → Generate proposals
   - Document Processing tab → Process folder
   - Memory Review tab → Approve proposals
   - Document in Bug Tracker if anything fails
   - **Deliverable**: Core 3-tab workflow verified

5. **Test All Analysis Tabs** (2 hours)
   - Systematically test tabs 4-15
   - Use test folder for each
   - Report bugs for each failure
   - **Deliverable**: Complete status of all 15 tabs

6. **Export Bug Report** (15 minutes)
   - Diagnostics tab → Bug Tracker → Export Report
   - Review all discovered bugs
   - Prioritize fixes
   - **Deliverable**: Markdown report of all issues

---

## Success Criteria

### Day 1 (Today)
- ✅ Diagnostic system implemented (DONE!)
- ✅ Diagnostics integrated into GUI and backend
- ✅ Violations bug fixed
- ✅ Can start application with full log visibility
- ✅ Core 3-tab workflow tested

### Day 2
- ✅ All 15 tabs tested and status documented
- ✅ Bug report exported with prioritization
- ✅ Critical P0 bugs fixed
- ✅ Integration workflows tested

### Day 3
- ✅ All P1 bugs fixed
- ✅ Automated test suite basic version
- ✅ Performance benchmarks established
- ✅ Documentation complete

### End State
- ✅ **Application reliably starts** (no guessing if backend is ready)
- ✅ **All tabs functional** (or documented as degraded with workaround)
- ✅ **Bug tracking operational** (never lose context on failures again)
- ✅ **Logs provide answers** (no more debugging blind)
- ✅ **Tests prevent regression** (catch breaks before user sees them)

---

## Addressing Your Concerns

### "4 days trying to get this thing to start up"

**Why It Happened**:
- No visibility into startup sequence
- Couldn't tell if backend was ready before GUI started
- API client errors gave no context
- Each failure lost in console noise

**How Diagnostics Fix This**:
- `gui_startup_*.log` shows exact step where GUI fails
- `backend_startup_*.log` shows which agents/routes failed to load
- `api_communication_*.log` shows exact request/response for failures
- Bug Tracker persists failures so you never lose context

**Example - Before Diagnostics**:
```
Error: Cannot connect to backend
(Which endpoint? When? Why? No idea. Try again.)
```

**Example - With Diagnostics**:
```
[gui_startup.log]
[0.50s] STEP: Checking backend health
[0.51s] ✗ ERROR: Backend UNAVAILABLE at http://127.0.0.1:8000/api/health
  Exception: Connection refused

[backend_startup.log]
[15.23s] ✗ ERROR: Agent FAILED to load: document_processor
  Exception: Model file not found: models/gliner-large
  Type: FileNotFoundError
```
**Now you know**: Backend crashed loading GLiNER model. Fix: download model or use smaller version.

### "We've tried so many things and still don't have an answer"

**What's Different Now**:
1. **Searchable History**: All startup attempts logged to `logs/` folder
2. **Bug Database**: `logs/bugs.json` tracks every issue with timestamps
3. **Statistics**: API logger shows success rates, response times
4. **Systematic Testing**: Checklist ensures we test everything once, not same thing repeatedly

### "Just watching the tool fail over and over"

**Failure Visibility**:
- Diagnostics tab shows real-time logs
- Bug tracker shows all failures in one place
- Export bug report → Get markdown summary
- Each failure captured with reproduction steps

**Stop Repeating**:
- Before each fix, check Bug Tracker: "Have we tried this?"
- After each fix, log result: "Did it work? Why/why not?"
- Test suite prevents fixed bugs from coming back

---

## Emergency Fallback Plan

If even with diagnostics the application won't start:

### Minimal Startup Mode

Create `run_minimal.ps1`:
```powershell
# Start ONLY backend, NO agent loading
$env:STRICT_PRODUCTION_STARTUP = "0"
$env:REQUIRED_PRODUCTION_AGENTS = ""
python Start.py
```

This gets backend running for GUI to connect, even if all agents fail.

### Incremental Agent Loading

Start backend with 1 agent at a time:
```powershell
$env:REQUIRED_PRODUCTION_AGENTS = "document_processor"  # Add one by one
```

Find which agent is causing startup crash.

---

## What We Just Created (Summary)

**4 New Diagnostic Modules** (Already Implemented):
1. [diagnostics/gui_startup_log.py](diagnostics/gui_startup_log.py) - 250 lines
2. [diagnostics/backend_startup_log.py](diagnostics/backend_startup_log.py) - 270 lines
3. [diagnostics/api_communication_log.py](diagnostics/api_communication_log.py) - 200 lines
4. [diagnostics/bug_tracker.py](diagnostics/bug_tracker.py) - 350 lines
5. [gui/tabs/diagnostics_tab.py](gui/tabs/diagnostics_tab.py) - 450 lines

**Total**: ~1,520 lines of diagnostic infrastructure

**Next Steps**: Integration (30 min) → Testing (2 hours) → Never be blind again

Let's end the guesswork and start shipping. 🚀
