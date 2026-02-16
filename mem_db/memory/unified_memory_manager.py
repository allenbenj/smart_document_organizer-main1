"""
Unified Memory Manager - Core of the Shared Memory System
==========================================================

This is the heart of what makes this Legal AI platform unique: a unified memory
system that enables all agents to share knowledge and collectively become smarter.

This shared memory is the key differentiator that transforms individual agents
into a collectively intelligent legal AI platform.

Features:
- SQLite-backed persistent storage with async support (via aiosqlite)
- Vector-based semantic search (via ChromaDB or FAISS)
- In-memory caching for fast access
- Thread-safe operations
- Service container integration
- Agent-specific memory isolation and cross-agent knowledge sharing
- Comprehensive error handling and monitoring
"""

import asyncio
import json  # noqa: E402
import logging  # noqa: E402
import sqlite3  # noqa: E402
import uuid  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional, Union  # noqa: E402

# Optional dependencies
try:
    import chromadb  # noqa: E402
    from chromadb.config import Settings  # noqa: E402

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None

try:
    import faiss  # noqa: E402
    import numpy as np  # noqa: E402

    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None
    np = None

try:
    import aiosqlite  # noqa: E402

    AIOSQLITE_AVAILABLE = True
except ImportError:
    AIOSQLITE_AVAILABLE = False
    aiosqlite = None

from .memory_interfaces import (  # noqa: E402
    MemoryProvider,
    MemoryQuery,
    MemoryRecord,
    MemoryType,
    SearchResult,
)

logger = logging.getLogger(__name__)


class UnifiedMemoryManager(MemoryProvider):
    """
    Unified memory manager that provides shared memory capabilities across all agents.
    This is the core component that enables collective intelligence.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        vector_store_path: Optional[Path] = None,
        vector_backend: str = "chromadb",  # 'chromadb' or 'faiss'
        embedding_dim: int = 384,  # Sentence transformer dimension
    ):
        self.db_path = db_path or Path("databases") / "unified_memory.db"
        self.vector_store_path = (
            vector_store_path or Path("databases") / "vector_memory"
        )
        self.vector_backend = vector_backend
        self.embedding_dim = embedding_dim

        if self.vector_backend == "chromadb" and not CHROMADB_AVAILABLE:
            logger.info("ChromaDB not available, vector search disabled (optional dependency).")
            self.enable_vector_search = False
        elif self.vector_backend == "faiss" and not FAISS_AVAILABLE:
            logger.warning("FAISS not available, vector search will be disabled.")
            self.enable_vector_search = False
        else:
            self.enable_vector_search = True
        self._async_db = AIOSQLITE_AVAILABLE

        # Storage components
        self._db_connection: Optional[
            Union[sqlite3.Connection, aiosqlite.Connection]
        ] = None
        self._vector_store = None
        self._vector_collection = None  # For ChromaDB

        # In-memory caches
        self._record_cache: Dict[str, MemoryRecord] = {}
        self._search_cache: Dict[str, List[SearchResult]] = {}
        self._cache_max_size = 1000

        # Statistics tracking
        self._stats = {
            "total_stores": 0,
            "total_searches": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        self._initialized = False
        self._lock = asyncio.Lock()

        logger.info(
            f"UnifiedMemoryManager initialized with db={self.db_path}, vector_backend={self.vector_backend}"
        )

    @asynccontextmanager
    async def _get_db_connection(self):
        if AIOSQLITE_AVAILABLE:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                yield db
        else:
            # This part is tricky because the rest of the code uses async.
            # A proper solution would be to use a thread pool for sync operations.
            # For now, we'll just connect directly, but this will block.
            logger.warning(
                "aiosqlite not found, using synchronous sqlite3 which will block."
            )
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()

    async def initialize(self) -> bool:
        """Initialize the unified memory system."""
        async with self._lock:
            if self._initialized:
                return True

            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    from opentelemetry import trace as _otel_trace  # type: ignore
                    _um_tracer = _otel_trace.get_tracer(__name__)
                except Exception:
                    _um_tracer = None

                if _um_tracer:
                    with _um_tracer.start_as_current_span("unified_memory._init_sqlite", attributes={"db_path": str(self.db_path)}):
                        await self._init_sqlite()
                else:
                    await self._init_sqlite()

                if self.enable_vector_search:
                    self.vector_store_path.mkdir(parents=True, exist_ok=True)
                    if self.vector_backend == "chromadb":
                        if _um_tracer:
                            with _um_tracer.start_as_current_span("unified_memory._init_chromadb"):
                                await self._init_chromadb()
                        else:
                            await self._init_chromadb()
                    elif self.vector_backend == "faiss":
                        if _um_tracer:
                            with _um_tracer.start_as_current_span("unified_memory._init_faiss"):
                                await self._init_faiss()
                        else:
                            await self._init_faiss()

                self._initialized = True
                logger.info("UnifiedMemoryManager successfully initialized")
                return True

            except Exception as e:
                logger.error(
                    f"Failed to initialize UnifiedMemoryManager: {e}", exc_info=True
                )
                return False

    async def _init_sqlite(self) -> None:
        """Initialize SQLite database with unified schema."""
        schema = """
        CREATE TABLE IF NOT EXISTS memory_records (
            record_id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            key TEXT NOT NULL,
            content TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            agent_id TEXT,
            document_id TEXT,
            metadata TEXT,
            importance_score REAL DEFAULT 1.0,
            confidence_score REAL DEFAULT 1.0,
            access_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_records(memory_type);
        CREATE INDEX IF NOT EXISTS idx_namespace ON memory_records(namespace);
        CREATE INDEX IF NOT EXISTS idx_agent_id ON memory_records(agent_id);
        CREATE INDEX IF NOT EXISTS idx_document_id ON memory_records(document_id);

        CREATE TABLE IF NOT EXISTS knowledge_sharing (
            source_record_id TEXT,
            target_agent_id TEXT,
            shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            relevance_score REAL DEFAULT 1.0,
            FOREIGN KEY (source_record_id) REFERENCES memory_records(record_id)
        );
        """
        async with self._get_db_connection() as db:
            if self._async_db:
                await db.executescript(schema)
                await db.commit()
            else:
                db.executescript(schema)
                db.commit()
        logger.debug("SQLite schema initialized for unified memory")

    async def _init_chromadb(self) -> None:
        """Initialize ChromaDB for vector-based semantic search."""
        try:
            self._vector_store = chromadb.PersistentClient(
                path=str(self.vector_store_path),
                settings=Settings(anonymized_telemetry=False),
            )
            self._vector_collection = self._vector_store.get_or_create_collection(
                name="unified_legal_memory",
                metadata={"description": "Unified memory for Legal AI Platform"},
            )
            logger.debug("ChromaDB initialized for vector search")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}", exc_info=True)
            self.enable_vector_search = False

    async def _init_faiss(self) -> None:
        """Initialize FAISS for vector search."""
        try:
            self._vector_store = faiss.IndexFlatIP(self.embedding_dim)
            logger.debug("FAISS index initialized")
        except Exception as e:
            logger.error(f"Failed to initialize FAISS: {e}", exc_info=True)
            self.enable_vector_search = False

    async def store(self, record: MemoryRecord) -> str:
        """Store a memory record in the unified system."""
        if not self._initialized:
            await self.initialize()

        try:
            from opentelemetry import trace as _otel_trace  # type: ignore
            _um_tracer = _otel_trace.get_tracer(__name__)
        except Exception:
            _um_tracer = None

        record.record_id = record.record_id or str(uuid.uuid4())

        async with self._get_db_connection() as db:
            if _um_tracer:
                with _um_tracer.start_as_current_span("unified_memory._store_sqlite", attributes={"record_id": record.record_id, "namespace": record.namespace}):
                    await self._store_sqlite(db, record)
            else:
                await self._store_sqlite(db, record)
            await db.commit()

        if self.enable_vector_search:
            if _um_tracer:
                with _um_tracer.start_as_current_span("unified_memory._store_vector", attributes={"record_id": record.record_id}):
                    await self._store_vector(record)
            else:
                await self._store_vector(record)

        self._record_cache[record.record_id] = record
        self._manage_cache()
        self._stats["total_stores"] += 1

        logger.debug(f"Stored memory record {record.record_id} in unified system")
        return record.record_id

    async def _store_sqlite(self, db, record: MemoryRecord) -> None:
        query = """
        INSERT OR REPLACE INTO memory_records
        (record_id, namespace, key, content, memory_type, agent_id, document_id,
         metadata, importance_score, confidence_score, access_count, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            record.record_id,
            record.namespace,
            record.key,
            record.content,
            record.memory_type.value,
            record.agent_id,
            record.document_id,
            json.dumps(record.metadata or {}),
            record.importance_score,
            record.confidence_score,
            record.access_count,
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
        )
        await db.execute(query, params)

    async def _store_vector(self, record: MemoryRecord) -> None:
        if self.vector_backend == "chromadb":
            await self._store_chromadb(record)
        elif self.vector_backend == "faiss":
            await self._store_faiss(record)

    async def _store_chromadb(self, record: MemoryRecord) -> None:
        metadata = {
            "namespace": record.namespace,
            "memory_type": record.memory_type.value,
            "agent_id": record.agent_id or "",
            "document_id": record.document_id or "",
        }
        self._vector_collection.upsert(
            documents=[record.content], metadatas=[metadata], ids=[record.record_id]
        )

    async def _store_faiss(self, record: MemoryRecord) -> None:
        # This requires an embedding function to be available
        # For now, this is a placeholder for the logic.
        # embeddings = self._get_embedding(record.content)
        # self._vector_store.add(embeddings)
        logger.warning("FAISS storage logic is not fully implemented.")

    async def retrieve(self, record_id: str) -> Optional[MemoryRecord]:
        if record_id in self._record_cache:
            self._stats["cache_hits"] += 1
            return self._record_cache[record_id]

        self._stats["cache_misses"] += 1

        async with self._get_db_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM memory_records WHERE record_id = ?", (record_id,)
            )
            row = await cursor.fetchone()

        if not row:
            return None

        record = self._row_to_record(row)
        self._record_cache[record_id] = record
        return record

    async def search(
        self,
        query: Union[MemoryQuery, str],
        memory_type: Optional[MemoryType] = None,
        namespace: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.6,
    ) -> List[SearchResult]:
        self._stats["total_searches"] += 1

        try:
            from opentelemetry import trace as _otel_trace  # type: ignore
            _um_tracer = _otel_trace.get_tracer(__name__)
        except Exception:
            _um_tracer = None

        _span_ctx = None
        if _um_tracer:
            try:
                _span_ctx = _um_tracer.start_as_current_span("unified_memory.search", attributes={"query": (query if isinstance(query, str) else getattr(query, 'query_text', None))})
                _span_ctx.__enter__()
            except Exception:
                _span_ctx = None

        try:
            if isinstance(query, str):
                class _Q:
                    pass

                q = _Q()
                q.query_text = query
                q.memory_type = memory_type
                q.namespace = namespace
                q.agent_id = agent_id
                q.limit = limit
                q.min_similarity = min_similarity
                query = q

            # Keyword search from SQLite
            keyword_results = await self._search_sqlite(query)

            # Semantic search from vector store
            semantic_results = []
            if self.enable_vector_search and query.query_text:
                semantic_results = await self._search_vector(query)

            # Combine and rank results
            combined_results = self._combine_search_results(
                keyword_results, semantic_results
            )
            combined_results.sort(key=lambda x: x.combined_score, reverse=True)

            return combined_results[: query.limit]
        finally:
            if _span_ctx is not None:
                try:
                    _span_ctx.__exit__(None, None, None)
                except Exception:
                    pass

    async def _search_sqlite(self, query: MemoryQuery) -> List[SearchResult]:
        conditions = []
        params = []

        if query.query_text:
            conditions.append("content LIKE ?")
            params.append(f"%{query.query_text}%")
        if query.memory_type:
            conditions.append("memory_type = ?")
            params.append(query.memory_type.value)
        if query.namespace:
            conditions.append("namespace = ?")
            params.append(query.namespace)
        if query.agent_id:
            conditions.append("agent_id = ?")
            params.append(query.agent_id)

        if not conditions:
            return []

        sql_query = f"SELECT * FROM memory_records WHERE {' AND '.join(conditions)} ORDER BY importance_score DESC LIMIT ?"
        params.append(query.limit)

        results = []
        async with self._get_db_connection() as db:
            cursor = await db.execute(sql_query, params)
            rows = await cursor.fetchall()
            for row in rows:
                record = self._row_to_record(row)
                similarity = (
                    self._calculate_keyword_similarity(query.query_text, record.content)
                    if query.query_text
                    else 1.0
                )
                results.append(
                    SearchResult(
                        record=record,
                        similarity_score=similarity,
                        relevance_score=float(record.confidence_score or 0.5),
                        match_type="keyword",
                    )
                )
        return results

    async def _search_vector(self, query: MemoryQuery) -> List[SearchResult]:
        if self.vector_backend == "chromadb":
            return await self._search_chromadb(query)
        elif self.vector_backend == "faiss":
            return await self._search_faiss(query)
        return []

    async def _search_chromadb(self, query: MemoryQuery) -> List[SearchResult]:
        where_clause = {}
        if query.memory_type:
            where_clause["memory_type"] = query.memory_type.value
        if query.namespace:
            where_clause["namespace"] = query.namespace
        if query.agent_id:
            where_clause["agent_id"] = query.agent_id

        chroma_results = self._vector_collection.query(
            query_texts=[query.query_text],
            n_results=query.limit,
            where=where_clause if where_clause else None,
        )

        results = []
        if chroma_results and chroma_results["ids"][0]:
            for i, doc_id in enumerate(chroma_results["ids"][0]):
                record = await self.retrieve(doc_id)
                if record:
                    similarity = 1.0 - chroma_results["distances"][0][i]
                    results.append(
                        SearchResult(
                            record=record,
                            similarity_score=similarity,
                            relevance_score=float(record.confidence_score or 0.5),
                            match_type="semantic",
                        )
                    )
        return results

    async def _search_faiss(self, query: MemoryQuery) -> List[SearchResult]:
        logger.warning("FAISS search logic is not fully implemented.")
        return []

    def _combine_search_results(
        self, list1: List[SearchResult], list2: List[SearchResult]
    ) -> List[SearchResult]:
        combined = {res.record.record_id: res for res in list1}
        for res in list2:
            if res.record.record_id in combined:
                combined[res.record.record_id].similarity_score = max(
                    combined[res.record.record_id].similarity_score,
                    res.similarity_score,
                )
                combined[res.record.record_id].match_type = "hybrid"
            else:
                combined[res.record.record_id] = res
        return list(combined.values())

    def _calculate_keyword_similarity(self, query: str, content: str) -> float:
        q_words = set(query.lower().split())
        c_words = set(content.lower().split())
        if not q_words:
            return 0.0
        return len(q_words.intersection(c_words)) / len(q_words)

    def _row_to_record(self, row) -> MemoryRecord:
        return MemoryRecord(
            record_id=row["record_id"],
            namespace=row["namespace"],
            key=row["key"],
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            agent_id=row["agent_id"],
            document_id=row["document_id"],
            metadata=json.loads(row["metadata"] or "{}"),
            importance_score=row["importance_score"],
            confidence_score=row["confidence_score"],
            access_count=row["access_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _manage_cache(self):
        if len(self._record_cache) > self._cache_max_size:
            # Simple FIFO cache eviction
            num_to_remove = len(self._record_cache) - self._cache_max_size
            for _ in range(num_to_remove):
                self._record_cache.pop(next(iter(self._record_cache)))


    async def update(self, record: MemoryRecord) -> bool:
        if not self._initialized:
            await self.initialize()
        record.updated_at = datetime.now()
        async with self._get_db_connection() as db:
            cur = await db.execute("SELECT 1 FROM memory_records WHERE record_id = ?", (record.record_id,))
            if not await cur.fetchone():
                return False
            await self._store_sqlite(db, record)
            await db.commit()
        self._record_cache[record.record_id] = record
        return True

    async def delete(self, record_id: str) -> bool:
        if not self._initialized:
            await self.initialize()
        async with self._get_db_connection() as db:
            cur = await db.execute("DELETE FROM memory_records WHERE record_id = ?", (record_id,))
            await db.commit()
            deleted = cur.rowcount > 0
        self._record_cache.pop(record_id, None)
        return deleted

    async def cleanup_expired(self) -> int:
        return 0

    async def get_all_records(
        self,
        memory_type: Optional[MemoryType] = None,
        namespace: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[MemoryRecord]:
        conditions = []
        params = []
        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type.value)
        if namespace:
            conditions.append("namespace = ?")
            params.append(namespace)
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        sql = "SELECT * FROM memory_records"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        out=[]
        async with self._get_db_connection() as db:
            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
        for row in rows:
            out.append(self._row_to_record(row))
        return out

    async def batch_store(self, records: List[MemoryRecord]) -> List[str]:
        ids=[]
        for r in records:
            ids.append(await self.store(r))
        return ids

    async def batch_delete(self, record_ids: List[str]) -> int:
        n=0
        for rid in record_ids:
            if await self.delete(rid):
                n+=1
        return n

    async def export_data(self, format: str = "json") -> bytes:
        recs = await self.get_all_records(limit=100000)
        if format != "json":
            raise ValueError("Only json export is supported")
        payload=[]
        for r in recs:
            payload.append({
                "record_id": r.record_id, "namespace": r.namespace, "key": r.key, "content": r.content,
                "memory_type": r.memory_type.value, "agent_id": r.agent_id, "document_id": r.document_id,
                "metadata": r.metadata, "importance_score": r.importance_score, "confidence_score": r.confidence_score,
                "access_count": r.access_count, "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(),
            })
        return json.dumps(payload).encode("utf-8")

    async def import_data(self, data: bytes, format: str = "json") -> int:
        if format != "json":
            raise ValueError("Only json import is supported")
        arr = json.loads(data.decode("utf-8"))
        count=0
        for obj in arr:
            rec = MemoryRecord(
                record_id=obj.get("record_id") or "",
                namespace=obj.get("namespace") or "import",
                key=obj.get("key") or "import",
                content=obj.get("content") or "",
                memory_type=MemoryType(obj.get("memory_type") or MemoryType.AGENT.value),
                agent_id=obj.get("agent_id"),
                document_id=obj.get("document_id"),
                metadata=obj.get("metadata") or {},
                importance_score=float(obj.get("importance_score",1.0)),
                confidence_score=float(obj.get("confidence_score",1.0)),
                access_count=int(obj.get("access_count",0)),
                created_at=datetime.fromisoformat(obj.get("created_at")) if obj.get("created_at") else datetime.now(),
                updated_at=datetime.fromisoformat(obj.get("updated_at")) if obj.get("updated_at") else datetime.now(),
            )
            await self.store(rec)
            count += 1
        return count

    async def get_shared_knowledge(self, agent_id: str, limit: int = 20) -> List[MemoryRecord]:
        recs = await self.get_all_records(limit=limit*5)
        out=[r for r in recs if r.agent_id and r.agent_id != agent_id]
        return out[:limit]

    async def get_statistics(self) -> Dict[str, Any]:
        async with self._get_db_connection() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM memory_records")
            total_records = (await cursor.fetchone())[0]
        return {
            "total_records": total_records,
            "cache_size": len(self._record_cache),
            "vector_search_enabled": self.enable_vector_search,
            "vector_backend": (
                self.vector_backend if self.enable_vector_search else None
            ),
            "system_stats": self._stats,
        }

    async def close(self) -> None:
        async with self._lock:
            if self._db_connection and AIOSQLITE_AVAILABLE:
                await self._db_connection.close()
            self._initialized = False
            logger.info("UnifiedMemoryManager closed")


# Factory function for easy initialization
async def create_unified_memory_manager(
    db_path: Optional[Path] = None,
    vector_store_path: Optional[Path] = None,
    vector_backend: str = "chromadb",
) -> UnifiedMemoryManager:
    """Create and initialize a UnifiedMemoryManager instance."""
    manager = UnifiedMemoryManager(db_path, vector_store_path, vector_backend)
    if await manager.initialize():
        return manager
    else:
        raise RuntimeError("Failed to initialize UnifiedMemoryManager")
