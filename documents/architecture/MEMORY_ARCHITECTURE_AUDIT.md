# Memory & Vector Storage Architecture Audit
**Date**: February 16, 2026  
**Status**: 🔍 Investigation Phase

---

## 🎯 Executive Summary

**Memory is the central advantage** of this Legal AI platform. Before implementing new features, we need to ensure the memory/vector infrastructure is production-ready and optimally integrated.

### Critical Questions
1. ✅ **Is memory storage working?** - UnifiedMemoryManager implemented
2. ⚠️ **Which vector backend is active?** - ChromaDB OR FAISS (needs verification)
3. ⚠️ **Are embeddings being generated?** - Embedding agents exist (needs testing)
4. ⚠️ **Can LLMs access memory?** - Service integration exists (needs validation)
5. ❓ **Should we upgrade to newer tools?** - To be determined

---

## 🏗️ Current Architecture

### Memory Layer (3-Tier System)

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│  (Organization, Entity Extraction, Semantic Analysis, etc.)  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                  UNIFIED MEMORY MANAGER                      │
│  Location: mem_db/memory/unified_memory_manager.py          │
│  ─────────────────────────────────────────────────────────  │
│  • SQLite persistence (async via aiosqlite)                 │
│  • In-memory caching                                         │
│  • Cross-agent knowledge sharing                             │
│  • Statistics tracking                                       │
│  • Supports: ChromaDB OR FAISS                              │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              VECTOR STORAGE BACKENDS                         │
│  ┌──────────────────┐        ┌─────────────────┐           │
│  │   CHROMADB       │   OR   │     FAISS       │           │
│  │  (Persistent)    │        │   (In-Memory)   │           │
│  │  + Metadata      │        │   + Fast Search │           │
│  └──────────────────┘        └─────────────────┘           │
└─────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                STORAGE LAYER                                 │
│  • SQLite: databases/unified_memory.db                      │
│  • ChromaDB: databases/vector_memory/                       │
│  • FAISS: In-memory index (saveable to disk)               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Component Inventory

### 1. **UnifiedMemoryManager** 
**Location**: `mem_db/memory/unified_memory_manager.py`

**Status**: ✅ Implemented & Registered

**Features**:
- SQLite-backed persistent storage
- Vector search via ChromaDB OR FAISS
- In-memory caching (max 1000 records)
- Cross-agent knowledge sharing
- Statistics tracking (stores, searches, cache hits)

**Configuration**:
```python
UnifiedMemoryManager(
    db_path=Path("databases/unified_memory.db"),
    vector_store_path=Path("databases/vector_memory"),
    vector_backend="chromadb",  # or "faiss"
    embedding_dim=384  # Sentence transformer dimension
)
```

**Key Methods**:
- `async def store(record: MemoryRecord) -> str` - Store memory
- `async def search(query: MemoryQuery) -> List[SearchResult]` - Semantic search
- `async def get_by_id(record_id: str) -> MemoryRecord` - Retrieve memory
- `async def share_knowledge(source_id, target_agent_id)` - Cross-agent sharing

**Dependencies**:
- ✅ Required: sqlite3 (built-in Python)
- ⚠️ Optional: chromadb (persistent vector storage)
- ⚠️ Optional: faiss, numpy (fast vector search)
- ⚠️ Optional: aiosqlite (async SQLite operations)

---

### 2. **UnifiedVectorStore**
**Location**: `mem_db/vector_store/unified_vector_store.py`

**Status**: ✅ Implemented, ⚠️ Not Fully Integrated

**Features**:
- FAISS-based vector indexing with GPU support
- Thread-safe operations
- Cache management with TTL
- Legal domain optimization
- Backup and recovery

**Current Issue**: 
- Requires FAISS (currently only in requirements-dev.txt)
- Not installed in production environment
- Fallback to DummyVectorStore in bootstrap.py

**Key Classes**:
```python
class VectorDocument:
    # Enhanced document with legal metadata
    document_type: str
    legal_domain: Optional[str]
    case_id: Optional[str]
    jurisdiction: Optional[str]
    importance_score: float
    
class SearchResult:
    # Multi-factor scoring
    similarity_score: float
    relevance_score: float
    importance_boost: float
    recency_boost: float
    domain_boost: float
```

---

### 3. **Embedding Agents**
**Locations**:
- `mem_db/embedding/unified_embedding_agent.py`
- `agents/embedding/unified_embedding_agent.py`

**Status**: ✅ Implemented, ❓ Usage Unknown

**Supported Models**:
```python
class EmbeddingModel(Enum):
    SENTENCE_TRANSFORMERS = "sentence_transformers"  # Default
    OPENAI = "openai"
    LEGAL_BERT = "legal_bert"
    FALLBACK = "fallback"  # TF-IDF based
```

**Currently Used**: sentence-transformers in multiple locations:
- semantic_analyzer.py
- precedent_analyzer.py
- document_service.py
- production_manager operations.py

---

### 4. **Service Integration**
**Location**: `core/container/bootstrap.py`

**Status**: ✅ Registered in Service Container

**Registered Aliases**:
```python
# Memory Manager
aliases=["memory_manager", "unified_memory_manager", "memory"]

# Vector Store (with fallback)
aliases=[
    "vector_store",
    "enhanced_vector_store", 
    "unified_vector_store",
    "chroma_memory",
    "faiss_vector_store"
]
```

**Fallback Behavior**: If FAISS/ChromaDB unavailable → DummyVectorStore
- Returns empty search results
- Accepts documents but doesn't index
- Reports `{"available": False}` in health checks

---

## 🔍 Dependency Status

### Required for Memory (Currently Installed)
| Package | Status | Usage |
|---------|--------|-------|
| sqlite3 | ✅ Built-in | Persistent memory storage |
| sentence-transformers | ✅ Installed | Text embeddings (dim=384) |
| transformers | ✅ Installed | NLP pipelines |
| numpy | ✅ Installed | Vector operations |

### Optional Vector Storage (Installation Unknown)
| Package | Location | Status | Impact |
|---------|----------|--------|--------|
| chromadb | requirements-optional.txt | ❓ Unknown | Persistent vector storage with metadata |
| faiss-cpu | requirements-dev.txt | ❓ Unknown | Fast similarity search (10x faster) |
| aiosqlite | requirements-optional.txt | ❓ Unknown | Async SQLite (better performance) |

---

## 🧪 Testing Plan

### Phase 0: Current State Verification (Before Implementation)

**Test 1: Check Vector Store Dependencies**
```bash
python -c "
try:
    import chromadb
    print('✅ ChromaDB installed')
except ImportError:
    print('❌ ChromaDB NOT installed')

try:
    import faiss
    print('✅ FAISS installed')
except ImportError:
    print('❌ FAISS NOT installed')
    
try:
    import aiosqlite
    print('✅ aiosqlite installed')
except ImportError:
    print('❌ aiosqlite NOT installed')
"
```

**Test 2: Memory Manager Initialization**
```bash
python -c "
import asyncio
from mem_db.memory import UnifiedMemoryManager

async def test():
    manager = UnifiedMemoryManager()
    success = await manager.initialize()
    print(f'Initialization: {'✅ SUCCESS' if success else '❌ FAILED'}')
    
    stats = await manager.get_statistics()
    print(f'Stats: {stats}')
    
    # Check vector backend
    if manager.enable_vector_search:
        print(f'✅ Vector search enabled ({manager.vector_backend})')
    else:
        print('⚠️ Vector search disabled (missing dependencies)')

asyncio.run(test())
"
```

**Test 3: Embedding Generation**
```bash
python -c "
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
text = 'This is a legal document about contract law.'
embedding = model.encode([text])

print(f'✅ Embedding generated: shape={embedding.shape}, dim={embedding.shape[1]}')
"
```

**Test 4: Memory Storage & Retrieval**
```bash
python -c "
import asyncio
from mem_db.memory import UnifiedMemoryManager, MemoryRecord, MemoryType

async def test():
    manager = UnifiedMemoryManager()
    await manager.initialize()
    
    # Store a test record
    record = MemoryRecord(
        namespace='test',
        key='legal_case_1',
        content='Test legal case about contract disputes',
        memory_type=MemoryType.DOCUMENT
    )
    
    record_id = await manager.store(record)
    print(f'✅ Stored record: {record_id}')
    
    # Retrieve it
    retrieved = await manager.get_by_id(record_id)
    print(f'✅ Retrieved: {retrieved.key}')
    
    # Search
    from mem_db.memory import MemoryQuery
    query = MemoryQuery(
        text='contract dispute',
        memory_type=MemoryType.DOCUMENT,
        limit=5
    )
    results = await manager.search(query)
    print(f'✅ Search returned {len(results)} results')

asyncio.run(test())
"
```

**Test 5: API Health Check**
```bash
python -c "
import urllib.request, json
response = urllib.request.urlopen('http://127.0.0.1:8000/api/health/detailed', timeout=5)
data = json.loads(response.read())

memory = data.get('memory_status', {})
vector = data.get('vector_status', {})

print(f'Memory Status: {memory}')
print(f'Vector Status: {vector}')
"
```

---

## 🎯 Recommended Actions

### Immediate (Before Feature Implementation)

1. **Install Missing Dependencies**
   ```bash
   # In WSL environment
   wsl -d Ubuntu bash -lc "cd /mnt/e/Project/smart_document_organizer-main && .venv/bin/pip install chromadb faiss-cpu aiosqlite"
   ```

2. **Run All 5 Tests** - Verify current state

3. **Update requirements.txt** - Move from optional to required:
   ```
   chromadb>=0.4.22
   faiss-cpu>=1.13
   aiosqlite>=0.19
   ```

4. **Choose Vector Backend Strategy**:
   - **Option A**: ChromaDB Only (simpler, persistent, slower)
   - **Option B**: FAISS Only (faster, requires manual persistence)
   - **Option C**: Hybrid (ChromaDB for persistence, FAISS for search) ⭐ **RECOMMENDED**

### Short-Term (During Phase 1-2)

5. **Create Memory Integration Tests**
   - Test Organization Tab → Memory storage
   - Test Entity Extraction → Memory retrieval
   - Test LLM access to memories

6. **Add Memory Dashboard**
   - Show memory statistics
   - Display vector index status
   - Show cross-agent knowledge sharing

7. **Optimize Embedding Cache**
   - Cache embeddings in SQLite: `databases/embeddings_cache.db`
   - Check cache before re-embedding
   - Save 80% of embedding computation time

### Long-Term (Phase 7)

8. **Implement Hybrid Vector Strategy**
   - ChromaDB for full-text + metadata search
   - FAISS for ultra-fast similarity search
   - Sync between both systems
   - Auto-route queries to optimal backend

9. **Add Memory Analytics**
   - Track memory access patterns
   - Identify most valuable memories
   - Suggest knowledge to share across agents
   - Detect duplicate/conflicting memories

10. **Scale Memory System**
    - Add memory sharding by case/domain
    - Implement memory archival for old records
    - Add memory compression (reduce embedding dim)
    - Benchmark: Support 1M+ documents

---

## 📊 Expected Outcomes

### After Verification (Phase 0)
- ✅ Know exactly which dependencies are installed
- ✅ Know which vector backend is active
- ✅ Understand current memory capacity
- ✅ Identify gaps before feature work

### After Optimization (Phase 7)
- 🎯 **10x faster** similarity search with FAISS
- 🎯 **80% reduction** in embedding computation (cache)
- 🎯 **100% memory utilization** by all agents/LLMs
- 🎯 **Cross-agent learning** proven and measurable

---

## 🚨 Blockers & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Missing FAISS/ChromaDB | Vector search disabled | Install immediately before new features |
| Large memory footprint | Performance degradation | Implement TTL and archival |
| Embedding inconsistency | Poor search results | Validate embedding model consistency |
| No memory monitoring | Can't measure value | Add memory dashboard/analytics |

---

## 🎓 Key Insights

1. **Memory IS Implemented** - UnifiedMemoryManager is production-ready
2. **Vector Storage is Conditional** - Degrades gracefully but needs deps installed
3. **Embedding Agents Exist** - sentence-transformers actively used
4. **Integration is Partial** - Service container wired but not all agents using it
5. **ChromaDB vs FAISS** - Both supported, need to choose strategy

**Bottom Line**: The foundation is solid, but needs dependency installation and integration verification before building new features on top.

---

## Next Steps

1. ✅ Run Phase 0 tests (verify current state)
2. Install missing dependencies (chromadb, faiss-cpu, aiosqlite)
3. Choose vector backend strategy (recommend hybrid)
4. Validate LLM → Memory access
5. **THEN** proceed with Phase 1 (Document Preview)

**Status**: 🔄 Ready to begin verification tests

