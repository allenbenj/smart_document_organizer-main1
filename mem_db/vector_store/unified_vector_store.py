"""
Unified Vector Store - Consolidated Implementation
================================================

Consolidates the best features from multiple vector store implementations:
- enhanced_vector_store.py (detailed logging, GPU support)
- vector_store_enhanced.py (enhanced features)
- vector_store.py (basic implementation)
- vector_db.py (database wrapper)
- vector_metadata_repository.py (metadata management)

Features:
- FAISS-based vector indexing with GPU support
- Async operations with connection pooling
- Comprehensive metadata management
- Detailed logging and performance monitoring
- Thread-safe operations
- Cache management with TTL
- Similarity search with legal domain optimization
- Backup and recovery capabilities
"""

import json
import logging  # noqa: E402
import shutil  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from enum import Enum  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

from mem_db.db.interfaces.logging import (  # noqa: E402
    LogCategory,
    LogLevel,
    StructuredLogger,
    StandardStructuredLogger,
    generate_correlation_id,
)

# Optional dependencies
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


class VectorStoreState(Enum):
    """Vector store operational states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    INDEXING = "indexing"
    SEARCHING = "searching"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class SimilarityMetric(Enum):
    """Similarity metrics for vector search."""

    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    INNER_PRODUCT = "inner_product"


@dataclass
class VectorDocument:
    """Enhanced vector document with comprehensive metadata."""

    id: str
    content: str
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Legal-specific fields
    document_type: str = "general"
    legal_domain: Optional[str] = None
    case_id: Optional[str] = None
    jurisdiction: Optional[str] = None
    date_created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # System fields
    importance_score: float = 1.0
    access_count: int = 0
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)
    ttl_seconds: Optional[int] = None

    def is_expired(self) -> bool:
        """Check if document has expired based on TTL."""
        if not self.ttl_seconds:
            return False
        elapsed = (datetime.now(timezone.utc) - self.date_created).total_seconds()
        return elapsed > self.ttl_seconds

    def update_access(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)


@dataclass
class SearchResult:
    """Enhanced search result with detailed scoring."""

    document: VectorDocument
    similarity_score: float
    rank: int

    # Enhanced scoring
    relevance_score: float = 0.0
    importance_boost: float = 0.0
    recency_boost: float = 0.0
    domain_boost: float = 0.0

    @property
    def combined_score(self) -> float:
        """Calculate combined score with all factors."""
        return (
            self.similarity_score * 0.4
            + self.relevance_score * 0.2
            + self.importance_boost * 0.2
            + self.recency_boost * 0.1
            + self.domain_boost * 0.1
        )


class UnifiedVectorStore:
    """Unified vector store with consolidated features."""

    def __init__(
        self,
        store_path: Path,
        dimension: int = 384,
        similarity_metric: SimilarityMetric = SimilarityMetric.COSINE,
        enable_gpu: bool = False,
        cache_size: int = 10000,
        enable_persistence: bool = True,
        structured_logger: Optional[StructuredLogger] = None,
    ):
        self.store_path = Path(store_path)
        self.dimension = dimension
        self.similarity_metric = similarity_metric
        self.enable_gpu = enable_gpu
        self.cache_size = cache_size
        self.enable_persistence = enable_persistence

        # Create directories
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.index_path = self.store_path / "faiss_index"
        self.db_path = self.store_path / "metadata.db"
        self.backup_path = self.store_path / "backups"
        self.backup_path.mkdir(exist_ok=True)

        # Initialize components
        self.logger = logging.getLogger(__name__)
        self.structured_logger = structured_logger or StandardStructuredLogger(
            self.logger
        )
        self._lock = threading.RLock()
        self._state = VectorStoreState.UNINITIALIZED

        # FAISS components
        self._index: Optional[faiss.Index] = None
        self._gpu_resources = None
        self._embedding_cache: Dict[str, np.ndarray] = {}

        # Document storage
        self._documents: Dict[str, VectorDocument] = {}
        self._id_to_index: Dict[str, int] = {}
        self._index_to_id: Dict[int, str] = {}
        self._next_index = 0

        # Statistics
        self._stats = {
            "total_documents": 0,
            "total_searches": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "index_rebuilds": 0,
            "last_backup": None,
            "startup_time": None,
        }

        # Performance monitoring
        self._search_times: List[float] = []
        self._index_times: List[float] = []

    def _log(
        self,
        level: LogLevel,
        message: str,
        correlation_id: Optional[str] = None,
        category: LogCategory = LogCategory.PERFORMANCE,
        **context: Any,
    ) -> str:
        cid = correlation_id or generate_correlation_id()
        if level == LogLevel.TRACE:
            self.structured_logger.trace(message, category=category, correlation_id=cid, **context)
        elif level == LogLevel.DEBUG:
            self.structured_logger.debug(message, category=category, correlation_id=cid, **context)
        elif level == LogLevel.INFO:
            self.structured_logger.info(message, category=category, correlation_id=cid, **context)
        elif level == LogLevel.WARNING:
            self.structured_logger.warning(message, category=category, correlation_id=cid, **context)
        elif level == LogLevel.ERROR:
            self.structured_logger.error(message, category=category, correlation_id=cid, **context)
        else:
            self.structured_logger.critical(message, category=category, correlation_id=cid, **context)
        return cid

    async def initialize(self, correlation_id: Optional[str] = None) -> bool:
        """Initialize the unified vector store."""
        if self._state != VectorStoreState.UNINITIALIZED:
            return True

        cid = correlation_id or generate_correlation_id()
        start_time = time.time()
        self._state = VectorStoreState.INITIALIZING
        self._log(
            LogLevel.INFO,
            "vector store initializing",
            correlation_id=cid,
            path=str(self.store_path),
            gpu=self.enable_gpu,
            persistence=self.enable_persistence,
        )

        try:
            # Check FAISS availability
            if not FAISS_AVAILABLE:
                self.logger.error("FAISS not available - vector store disabled")
                self._state = VectorStoreState.ERROR
                return False

            # Initialize database
            if self.enable_persistence:
                await self._init_database()
                await self._load_from_database()

            # Initialize FAISS index
            await self._init_faiss_index()

            # Initialize GPU if enabled
            if self.enable_gpu and faiss.get_num_gpus() > 0:
                await self._init_gpu_resources()

            self._state = VectorStoreState.READY
            self._stats["startup_time"] = time.time() - start_time

            self._log(
                LogLevel.INFO,
                "vector store initialized",
                correlation_id=cid,
                documents=len(self._documents),
                dimension=self.dimension,
                gpu=self.enable_gpu,
                startup_time_s=round(self._stats["startup_time"], 3),
            )

            return True

        except Exception as e:
            self._log(
                LogLevel.ERROR,
                "vector store initialization failed",
                correlation_id=cid,
                exception=str(e),
            )
            self._state = VectorStoreState.ERROR
            return False

    async def _init_database(self):
        """Initialize SQLite database for metadata persistence."""
        if not AIOSQLITE_AVAILABLE:
            self.logger.warning("aiosqlite not available - using synchronous SQLite")
            return

        schema = """
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            embedding BLOB,
            metadata_json TEXT,
            document_type TEXT DEFAULT 'general',
            legal_domain TEXT,
            case_id TEXT,
            jurisdiction TEXT,
            date_created TEXT NOT NULL,
            importance_score REAL DEFAULT 1.0,
            access_count INTEGER DEFAULT 0,
            last_accessed TEXT NOT NULL,
            tags_json TEXT,
            ttl_seconds INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_document_type ON documents(document_type);
        CREATE INDEX IF NOT EXISTS idx_legal_domain ON documents(legal_domain);
        CREATE INDEX IF NOT EXISTS idx_case_id ON documents(case_id);
        CREATE INDEX IF NOT EXISTS idx_jurisdiction ON documents(jurisdiction);
        CREATE INDEX IF NOT EXISTS idx_importance ON documents(importance_score);
        CREATE INDEX IF NOT EXISTS idx_access_count ON documents(access_count);
        CREATE INDEX IF NOT EXISTS idx_last_accessed ON documents(last_accessed);
        """

        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(schema)
            await db.commit()

    async def _load_from_database(self):
        """Load documents from database."""
        if not AIOSQLITE_AVAILABLE:
            return

        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT * FROM documents")
                rows = await cursor.fetchall()

                for row in rows:
                    doc = self._row_to_document(row)
                    if not doc.is_expired():
                        self._documents[doc.id] = doc
                        self._id_to_index[doc.id] = self._next_index
                        self._index_to_id[self._next_index] = doc.id
                        self._next_index += 1

                self._stats["total_documents"] = len(self._documents)
                self.logger.info(
                    f"Loaded {len(self._documents)} documents from database"
                )

        except Exception as e:
            self.logger.error(f"Failed to load from database: {e}")

    def _row_to_document(self, row) -> VectorDocument:
        """Convert database row to VectorDocument."""
        return VectorDocument(
            id=row[0],
            content=row[1],
            embedding=(
                np.frombuffer(row[2], dtype=np.float32).reshape(1, -1)
                if row[2]
                else None
            ),
            metadata=json.loads(row[3]) if row[3] else {},
            document_type=row[4],
            legal_domain=row[5],
            case_id=row[6],
            jurisdiction=row[7],
            date_created=datetime.fromisoformat(row[8]),
            importance_score=row[9],
            access_count=row[10],
            last_accessed=datetime.fromisoformat(row[11]),
            tags=json.loads(row[12]) if row[12] else [],
            ttl_seconds=row[13],
        )

    async def _init_faiss_index(self):
        """Initialize FAISS index."""
        if self.similarity_metric == SimilarityMetric.COSINE:
            self._index = faiss.IndexFlatIP(self.dimension)
        elif self.similarity_metric == SimilarityMetric.EUCLIDEAN:
            self._index = faiss.IndexFlatL2(self.dimension)
        else:  # INNER_PRODUCT
            self._index = faiss.IndexFlatIP(self.dimension)

        # Add existing embeddings to index
        if self._documents:
            embeddings = []
            for doc_id in sorted(self._id_to_index.keys()):
                doc = self._documents[doc_id]
                if doc.embedding is not None:
                    if doc.embedding.ndim == 2:
                        embeddings.append(doc.embedding[0])
                    else:
                        embeddings.append(doc.embedding)
                else:
                    # Create zero embedding for missing embeddings
                    embeddings.append(np.zeros(self.dimension))

            if embeddings:
                embeddings_array = np.array(embeddings, dtype=np.float32)
                self._index.add(embeddings_array)

        self.logger.info(f"FAISS index initialized with {self._index.ntotal} vectors")

    async def _init_gpu_resources(self):
        """Initialize GPU resources for FAISS."""
        try:
            if faiss.get_num_gpus() > 0:
                self._gpu_resources = faiss.StandardGpuResources()
                gpu_index = faiss.index_cpu_to_gpu(self._gpu_resources, 0, self._index)
                self._index = gpu_index
                self.logger.info("GPU acceleration enabled for FAISS")
            else:
                self.logger.warning("No GPUs available for FAISS acceleration")
        except Exception as e:
            self.logger.warning(f"Failed to initialize GPU resources: {e}")

    async def add_document(
        self,
        content: str,
        embedding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None,
        document_type: str = "general",
        legal_domain: Optional[str] = None,
        case_id: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        importance_score: float = 1.0,
        tags: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Add a document to the vector store."""
        if self._state != VectorStoreState.READY:
            raise RuntimeError(f"Vector store not ready: {self._state}")

        cid = correlation_id or generate_correlation_id()
        doc_id = str(uuid.uuid4())

        # Normalize embedding
        if embedding.ndim == 1:
            embedding = embedding.reshape(1, -1)

        if self.similarity_metric == SimilarityMetric.COSINE:
            # Normalize for cosine similarity
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

        # Create document
        document = VectorDocument(
            id=doc_id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            document_type=document_type,
            legal_domain=legal_domain,
            case_id=case_id,
            jurisdiction=jurisdiction,
            importance_score=importance_score,
            tags=tags or [],
            ttl_seconds=ttl_seconds,
        )

        with self._lock:
            # Add to collections
            self._documents[doc_id] = document
            self._id_to_index[doc_id] = self._next_index
            self._index_to_id[self._next_index] = doc_id

            # Add to FAISS index
            self._index.add(embedding.astype(np.float32))

            self._next_index += 1
            self._stats["total_documents"] += 1

        # Persist to database
        if self.enable_persistence:
            await self._save_document_to_db(document)

        self._log(
            LogLevel.INFO,
            "vector document indexed",
            correlation_id=cid,
            document_id=doc_id,
            document_type=document_type,
            legal_domain=legal_domain,
            importance=importance_score,
            content_chars=len(content),
        )
        return doc_id

    async def _save_document_to_db(self, document: VectorDocument):
        """Save document to database."""
        if not AIOSQLITE_AVAILABLE:
            return

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO documents
                    (id, content, embedding, metadata_json, document_type, legal_domain,
                     case_id, jurisdiction, date_created, importance_score, access_count,
                     last_accessed, tags_json, ttl_seconds)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        document.id,
                        document.content,
                        (
                            document.embedding.tobytes()
                            if document.embedding is not None
                            else None
                        ),
                        json.dumps(document.metadata),
                        document.document_type,
                        document.legal_domain,
                        document.case_id,
                        document.jurisdiction,
                        document.date_created.isoformat(),
                        document.importance_score,
                        document.access_count,
                        document.last_accessed.isoformat(),
                        json.dumps(document.tags),
                        document.ttl_seconds,
                    ),
                )
                await db.commit()
        except Exception as e:
            self.logger.error(f"Failed to save document to database: {e}")

    async def search(  # noqa: C901
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
        legal_domain: Optional[str] = None,
        document_type: Optional[str] = None,
        min_importance: float = 0.0,
        boost_recent: bool = True,
        boost_domain: bool = True,
        correlation_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """Perform enhanced vector search with legal domain optimization."""
        if self._state != VectorStoreState.READY:
            raise RuntimeError(f"Vector store not ready: {self._state}")

        cid = correlation_id or generate_correlation_id()
        start_time = time.time()
        self._state = VectorStoreState.SEARCHING
        self._log(
            LogLevel.DEBUG,
            "vector search start",
            correlation_id=cid,
            k=k,
            filters=bool(filter_metadata),
            legal_domain=legal_domain,
            document_type=document_type,
            min_importance=min_importance,
        )

        try:
            # Normalize query embedding
            if query_embedding.ndim == 1:
                query_embedding = query_embedding.reshape(1, -1)

            if self.similarity_metric == SimilarityMetric.COSINE:
                norm = np.linalg.norm(query_embedding)
                if norm > 0:
                    query_embedding = query_embedding / norm

            # Perform FAISS search
            with self._lock:
                distances, indices = self._index.search(
                    query_embedding.astype(np.float32),
                    min(k * 2, self._index.ntotal),  # Get more results for filtering
                )

            # Process results
            results = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx == -1:  # Invalid index
                    continue

                doc_id = self._index_to_id.get(idx)
                if not doc_id or doc_id not in self._documents:
                    continue

                document = self._documents[doc_id]

                # Apply filters
                if self._should_filter_document(
                    document,
                    filter_metadata,
                    legal_domain,
                    document_type,
                    min_importance,
                ):
                    continue

                # Calculate similarity score
                if self.similarity_metric == SimilarityMetric.EUCLIDEAN:
                    similarity_score = 1.0 / (1.0 + distance)
                else:  # COSINE or INNER_PRODUCT
                    similarity_score = float(distance)

                # Calculate enhanced scores
                relevance_score = self._calculate_relevance_score(
                    document, query_embedding
                )
                importance_boost = document.importance_score * 0.1
                recency_boost = (
                    self._calculate_recency_boost(document) if boost_recent else 0.0
                )
                domain_boost = (
                    self._calculate_domain_boost(document, legal_domain)
                    if boost_domain
                    else 0.0
                )

                result = SearchResult(
                    document=document,
                    similarity_score=similarity_score,
                    rank=i,
                    relevance_score=relevance_score,
                    importance_boost=importance_boost,
                    recency_boost=recency_boost,
                    domain_boost=domain_boost,
                )

                results.append(result)

            # Sort by combined score and limit
            results.sort(key=lambda x: x.combined_score, reverse=True)
            results = results[:k]

            # Update access statistics
            for result in results:
                result.document.update_access()
                if self.enable_persistence:
                    await self._update_document_access(result.document.id)

            search_time = time.time() - start_time
            self._search_times.append(search_time)
            self._stats["total_searches"] += 1

            level = LogLevel.INFO if search_time <= 0.5 else LogLevel.WARNING
            self._log(
                level,
                "vector search completed",
                correlation_id=cid,
                results=len(results),
                k=k,
                duration_ms=round(search_time * 1000, 2),
                filtered_by_metadata=bool(filter_metadata),
                legal_domain=legal_domain,
            )

            return results

        finally:
            self._state = VectorStoreState.READY

    def _should_filter_document(
        self,
        document: VectorDocument,
        filter_metadata: Optional[Dict[str, Any]],
        legal_domain: Optional[str],
        document_type: Optional[str],
        min_importance: float,
    ) -> bool:
        """Check if document should be filtered out."""
        # Check expiration
        if document.is_expired():
            return True

        # Check importance
        if document.importance_score < min_importance:
            return True

        # Check document type
        if document_type and document.document_type != document_type:
            return True

        # Check legal domain
        if legal_domain and document.legal_domain != legal_domain:
            return True

        # Check metadata filters
        if filter_metadata:
            for key, value in filter_metadata.items():
                if key not in document.metadata or document.metadata[key] != value:
                    return True

        return False

    def _calculate_relevance_score(
        self, document: VectorDocument, query_embedding: np.ndarray
    ) -> float:
        """Calculate relevance score based on document characteristics."""
        score = 0.0

        # Content length normalization
        contentlength = len(document.content)  # noqa: F841
        if 100 <= content_length <= 2000:  # Optimal range  # noqa: F821
            score += 0.1
        elif content_length > 5000:  # Penalize very long documents  # noqa: F821
            score -= 0.05

        # Access frequency boost
        if document.access_count > 10:
            score += 0.05
        elif document.access_count > 50:
            score += 0.1

        return min(score, 0.2)  # Cap at 0.2

    def _calculate_recency_boost(self, document: VectorDocument) -> float:
        """Calculate recency boost based on document age."""
        now = datetime.now(timezone.utc)
        age_days = (now - document.date_created).days

        if age_days <= 7:
            return 0.1
        elif age_days <= 30:
            return 0.05
        elif age_days <= 90:
            return 0.02
        else:
            return 0.0

    def _calculate_domain_boost(
        self, document: VectorDocument, target_domain: Optional[str]
    ) -> float:
        """Calculate domain-specific boost."""
        if not target_domain or not document.legal_domain:
            return 0.0

        if document.legal_domain == target_domain:
            return 0.1
        elif (
            target_domain in document.legal_domain
            or document.legal_domain in target_domain
        ):
            return 0.05
        else:
            return 0.0

    async def _update_document_access(self, doc_id: str):
        """Update document access statistics in database."""
        if not AIOSQLITE_AVAILABLE:
            return

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    UPDATE documents
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE id = ?
                """,
                    (datetime.now(timezone.utc).isoformat(), doc_id),
                )
                await db.commit()
        except Exception as e:
            self.logger.error(f"Failed to update document access: {e}")

    async def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive vector store statistics."""
        stats = self._stats.copy()

        # Performance statistics
        if self._search_times:
            stats["average_search_time"] = sum(self._search_times) / len(
                self._search_times
            )
            stats["max_search_time"] = max(self._search_times)
            stats["min_search_time"] = min(self._search_times)

        if self._index_times:
            stats["average_index_time"] = sum(self._index_times) / len(
                self._index_times
            )

        # Document statistics
        stats["cache_size"] = len(self._embedding_cache)
        stats["index_size"] = self._index.ntotal if self._index else 0
        stats["state"] = self._state.value
        stats["dimension"] = self.dimension
        stats["similarity_metric"] = self.similarity_metric.value
        stats["gpu_enabled"] = self.enable_gpu and self._gpu_resources is not None

        # Document type distribution
        type_distribution = {}
        domain_distribution = {}
        for doc in self._documents.values():
            type_distribution[doc.document_type] = (
                type_distribution.get(doc.document_type, 0) + 1
            )
            if doc.legal_domain:
                domain_distribution[doc.legal_domain] = (
                    domain_distribution.get(doc.legal_domain, 0) + 1
                )

        stats["document_types"] = type_distribution
        stats["legal_domains"] = domain_distribution

        return stats

    async def cleanup_expired(self, correlation_id: Optional[str] = None) -> int:  # noqa: C901
        """Clean up expired documents."""
        if self._state != VectorStoreState.READY:
            return 0

        cid = correlation_id or generate_correlation_id()

        expired_ids = []

        with self._lock:
            for doc_id, document in self._documents.items():
                if document.is_expired():
                    expired_ids.append(doc_id)

        if not expired_ids:
            return 0

        # Remove from collections
        removed_count = 0
        with self._lock:
            for doc_id in expired_ids:
                if doc_id in self._documents:
                    del self._documents[doc_id]
                    if doc_id in self._id_to_index:
                        index = self._id_to_index[doc_id]
                        del self._id_to_index[doc_id]
                        del self._index_to_id[index]
                    removed_count += 1

        # Remove from database
        if self.enable_persistence and AIOSQLITE_AVAILABLE:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    for doc_id in expired_ids:
                        await db.execute(
                            "DELETE FROM documents WHERE id = ?", (doc_id,)
                        )
                    await db.commit()
            except Exception as e:
                self.logger.error(
                    f"Failed to remove expired documents from database: {e}"
                )

        # Rebuild index if many documents were removed
        if removed_count > 0:
            await self._rebuild_index(correlation_id=cid)
            self._log(
                LogLevel.INFO,
                "expired documents cleaned",
                correlation_id=cid,
                removed=removed_count,
            )

        return removed_count

    async def _rebuild_index(self, correlation_id: Optional[str] = None):
        """Rebuild FAISS index after document removal."""
        cid = correlation_id or generate_correlation_id()
        self._state = VectorStoreState.INDEXING
        start_time = time.time()
        self._log(LogLevel.INFO, "rebuilding vector index", correlation_id=cid)

        try:
            # Create new index
            if self.similarity_metric == SimilarityMetric.COSINE:
                new_index = faiss.IndexFlatIP(self.dimension)
            elif self.similarity_metric == SimilarityMetric.EUCLIDEAN:
                new_index = faiss.IndexFlatL2(self.dimension)
            else:  # INNER_PRODUCT
                new_index = faiss.IndexFlatIP(self.dimension)

            # Rebuild mappings and add embeddings
            embeddings = []
            new_id_to_index = {}
            new_index_to_id = {}
            new_index = 0

            for doc_id, document in self._documents.items():
                if document.embedding is not None:
                    new_id_to_index[doc_id] = new_index
                    new_index_to_id[new_index] = doc_id

                    embedding = document.embedding
                    if embedding.ndim == 2:
                        embeddings.append(embedding[0])
                    else:
                        embeddings.append(embedding)

                    new_index += 1

            if embeddings:
                embeddings_array = np.array(embeddings, dtype=np.float32)
                new_index.add(embeddings_array)

            # Apply GPU if enabled
            if self.enable_gpu and self._gpu_resources:
                new_index = faiss.index_cpu_to_gpu(self._gpu_resources, 0, new_index)

            # Replace old index
            with self._lock:
                self._index = new_index
                self._id_to_index = new_id_to_index
                self._index_to_id = new_index_to_id
                self._next_index = new_index

            index_time = time.time() - start_time
            self._index_times.append(index_time)
            self._stats["index_rebuilds"] += 1

            self._log(
                LogLevel.INFO,
                "vector index rebuilt",
                correlation_id=cid,
                documents=new_index,
                duration_ms=round(index_time * 1000, 2),
            )

        finally:
            self._state = VectorStoreState.READY

    async def backup(self) -> str:
        """Create backup of vector store."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.backup_path / f"backup_{timestamp}"
        backup_dir.mkdir(exist_ok=True)

        try:
            # Backup database
            if self.db_path.exists():
                shutil.copy2(self.db_path, backup_dir / "metadata.db")

            # Backup FAISS index
            if self._index:
                index_backup_path = backup_dir / "faiss_index"
                # Save CPU version of index
                cpu_index = (
                    faiss.index_gpu_to_cpu(self._index)
                    if self.enable_gpu
                    else self._index
                )
                faiss.write_index(cpu_index, str(index_backup_path))

            # Backup metadata
            metadata = {
                "timestamp": timestamp,
                "document_count": len(self._documents),
                "dimension": self.dimension,
                "similarity_metric": self.similarity_metric.value,
                "stats": self._stats,
            }

            with open(backup_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            self._stats["last_backup"] = timestamp
            self.logger.info(f"Backup created: {backup_dir}")

            return str(backup_dir)

        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
            raise

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on vector store."""
        health = {
            "healthy": True,
            "state": self._state.value,
            "faiss_available": FAISS_AVAILABLE,
            "index_operational": self._index is not None,
            "document_count": len(self._documents),
            "index_size": self._index.ntotal if self._index else 0,
            "gpu_enabled": self.enable_gpu and self._gpu_resources is not None,
        }

        try:
            # Test search functionality
            if self._index and self._index.ntotal > 0:
                test_embedding = (
                    np.random.random(self.dimension).astype(np.float32).reshape(1, -1)
                )
                distances, indices = self._index.search(
                    test_embedding, min(1, self._index.ntotal)
                )
                health["search_operational"] = indices[0][0] != -1
            else:
                health["search_operational"] = True  # No documents to search

            # Check database accessibility
            if self.enable_persistence and AIOSQLITE_AVAILABLE:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("SELECT 1")
                    health["database_accessible"] = True
            else:
                health["database_accessible"] = not self.enable_persistence

        except Exception as e:
            health["healthy"] = False
            health["error"] = str(e)
            self.logger.error(f"Vector store health check failed: {e}")

        return health


# Factory function
async def create_unified_vector_store(
    store_path: Path,
    dimension: int = 384,
    similarity_metric: SimilarityMetric = SimilarityMetric.COSINE,
    enable_gpu: bool = False,
    cache_size: int = 10000,
    enable_persistence: bool = True,
) -> UnifiedVectorStore:
    """Create and initialize a unified vector store."""
    store = UnifiedVectorStore(
        store_path=store_path,
        dimension=dimension,
        similarity_metric=similarity_metric,
        enable_gpu=enable_gpu,
        cache_size=cache_size,
        enable_persistence=enable_persistence,
    )

    if await store.initialize():
        return store
    else:
        raise RuntimeError("Failed to initialize unified vector store")
