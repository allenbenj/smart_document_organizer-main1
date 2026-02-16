"""
ML Optimizer - Machine Learning Parameter Optimization
=====================================================
ML-powered optimization for processing parameters with intelligent
parameter tuning and document similarity analysis.
"""

import json
from pathlib import Path

# Import numpy with fallback
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    # Fallback numpy-like functionality for basic operations
    class FakeLinalg:
        """Minimal linalg module with norm function."""

        @staticmethod
        def norm(vec):
            if isinstance(vec, list):
                return (sum(x * x for x in vec)) ** 0.5
            return 1.0

    class FakeNumPy:
        """Simplified NumPy replacement used when real NumPy is unavailable."""

        linalg = FakeLinalg()

        @staticmethod
        def array(data):
            return data

        @staticmethod
        def dot(a, b):
            if isinstance(a, list) and isinstance(b, list):
                return sum(x * y for x, y in zip(a, b))
            return 0

        @staticmethod
        def var(data):
            if not data:
                return 0.0
            mean = sum(data) / len(data)
            return sum((x - mean) ** 2 for x in data) / len(data)

    np = FakeNumPy()
    HAS_NUMPY = False
import hashlib
import sqlite3
import threading
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from datetime import datetime, timedelta, timezone

from smart_document_organizer.utils.config_models import MLOptimizerConfig
from smart_document_organizer.utils.constants import Constants

# Import detailed logging
from smart_document_organizer.utils.detailed_logging import LogCategory, detailed_log_function, get_detailed_logger


class OptimizationObjective(Enum):
    """Optimization objectives for parameter tuning."""

    SPEED = "speed"  # Minimize processing time
    ACCURACY = "accuracy"  # Maximize extraction accuracy
    COST = "cost"  # Minimize API costs
    BALANCED = "balanced"  # Balance speed, accuracy, and cost
    MEMORY = "memory"  # Minimize memory usage


class DocumentCategory(Enum):
    """Document categories for targeted optimization."""

    LEGAL_BRIEF = "legal_brief"
    CONTRACT = "contract"
    STATUTE = "statute"
    CASE_LAW = "case_law"
    REGULATION = "regulation"
    MEMO = "memo"
    EMAIL = "email"
    GENERIC = "generic"


@dataclass
class ProcessingParameters:
    """Processing parameters that can be optimized."""

    chunk_size: int = 3000
    chunk_overlap: int = 200
    temperature: float = 0.1
    max_tokens: int = 2000
    confidence_threshold: float = 0.7
    model_name: str = "gpt-4"
    batch_size: int = 1
    timeout_seconds: int = 300
    retry_attempts: int = 3
    use_cache: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessingParameters":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class PerformanceMetrics:
    """Performance metrics for optimization analysis."""

    processing_time: float
    accuracy_score: float = 0.0
    f1_score: float = 0.0
    entities_extracted: int = 0
    api_cost: float = 0.0
    memory_usage_mb: float = 0.0
    success: bool = True
    error_message: Optional[str] = None

    def get_composite_score(self, objective: OptimizationObjective) -> float:
        """Calculate composite score based on optimization objective."""
        if objective == OptimizationObjective.SPEED:
            return 1.0 / max(0.1, self.processing_time)
        elif objective == OptimizationObjective.ACCURACY:
            return (self.accuracy_score + self.f1_score) / 2
        elif objective == OptimizationObjective.COST:
            return 1.0 / max(0.01, self.api_cost)
        elif objective == OptimizationObjective.MEMORY:
            return 1.0 / max(1.0, self.memory_usage_mb)
        elif objective == OptimizationObjective.BALANCED:
            speed_score = 1.0 / max(0.1, self.processing_time)
            accuracy_score = (self.accuracy_score + self.f1_score) / 2
            cost_score = 1.0 / max(0.01, self.api_cost)
            return speed_score * 0.4 + accuracy_score * 0.4 + cost_score * 0.2
        else:
            return 0.0


@dataclass
class DocumentFeatures:
    """Document features for similarity analysis."""

    file_size_mb: float
    page_count: int = 0
    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0
    table_count: int = 0
    image_count: int = 0
    complexity_score: float = 0.0
    language: str = "en"
    has_legal_terminology: bool = False

    def to_vector(self):
        """Convert features to vector for similarity calculation."""
        vector_data = [
            self.file_size_mb,
            self.page_count,
            self.word_count / 1000.0,  # Normalize
            self.sentence_count / 100.0,  # Normalize
            self.paragraph_count / 10.0,  # Normalize
            self.table_count,
            self.image_count,
            self.complexity_score,
            1.0 if self.has_legal_terminology else 0.0,
        ]
        return np.array(vector_data)


@dataclass
class OptimizationResult:
    """Result of parameter optimization."""

    optimized_parameters: ProcessingParameters
    expected_improvement: float
    confidence: float
    optimization_reason: str
    based_on_samples: int


@dataclass
class TokenUsageRecord:
    """Record of token usage for a session."""

    session_id: str
    tokens_used: int
    timestamp: datetime


@dataclass
class ThresholdModel:
    """Model-derived confidence thresholds."""

    auto_approve_threshold: float
    review_threshold: float
    reject_threshold: float
    updated_at: str


@dataclass

class MLOptimizer:
    """
    Machine learning optimizer for processing parameters.

    Features:
    - Performance history tracking with SQLite storage
    - Document similarity analysis using feature vectors
    - Parameter optimization using statistical analysis
    - Multi-objective optimization (speed, accuracy, cost, etc.)
    - Automated parameter suggestions with confidence scores
    """

    @detailed_log_function(LogCategory.SYSTEM)
    def __init__(
        self,
        storage_dir: str = "./storage/databases",
        service_config: Optional[MLOptimizerConfig] = None,
    ):
        """Initialize ML optimizer with performance tracking."""
        ml_logger.info("=== INITIALIZING ML OPTIMIZER ===")

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.config = service_config or MLOptimizerConfig()
        self.db_path = self.storage_dir / "ml_optimizer.db"

        # Initialize database
        self._init_database()

        # In-memory caches
        self.performance_history: deque = deque(maxlen=10000)
        self.document_features_cache: Dict[str, DocumentFeatures] = {}
        self.optimization_cache: Dict[str, OptimizationResult] = {}
        self.token_usage_history: deque = deque(maxlen=10000)
        self.feedback_history: deque = deque(maxlen=10000)
        self.threshold_model: Optional[ThresholdModel] = None
        # Analysis settings
        self.min_samples_for_optimization = self.config.min_samples
        self.similarity_threshold = self.config.similarity_threshold
        self.max_optimization_age_hours = self.config.max_optimization_age_hours

        # Load recent performance data
        self._load_recent_performance()
        self._load_recent_token_usage()
        self._load_recent_feedback()

        # Threading
        self._lock = threading.RLock()

        ml_logger.info(
            "ML optimizer initialization complete",
            parameters={
                "db_path": str(self.db_path),
                "min_samples": self.min_samples_for_optimization,
                "similarity_threshold": self.similarity_threshold,
                "performance_history_size": len(self.performance_history),
                "token_usage_records": len(self.token_usage_history),
            },
        )

    @detailed_log_function(LogCategory.SYSTEM)
    def _init_database(self):
        """Initialize SQLite database for performance tracking."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS performance_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_path TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    document_hash TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    features_json TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    composite_score REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_perf_type ON performance_records(document_type);
                CREATE INDEX IF NOT EXISTS idx_perf_hash ON performance_records(document_hash);
                CREATE INDEX IF NOT EXISTS idx_perf_score ON performance_records(composite_score);
                CREATE INDEX IF NOT EXISTS idx_perf_created ON performance_records(created_at);
                
                CREATE TABLE IF NOT EXISTS optimization_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE NOT NULL,
                    parameters_json TEXT NOT NULL,
                    expected_improvement REAL NOT NULL,
                    confidence REAL NOT NULL,
                    reason TEXT NOT NULL,
                    samples_count INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_cache_key ON optimization_cache(cache_key);
                CREATE INDEX IF NOT EXISTS idx_cache_expires ON optimization_cache(expires_at);

            """
            )

        ml_logger.info("ML optimizer database initialized")

    @detailed_log_function(LogCategory.SYSTEM)
    def _load_recent_performance(self):
        """Load recent performance data into memory cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT document_path, document_type, parameters_json, metrics_json, 
                           features_json, objective, composite_score, created_at
                    FROM performance_records 
                    WHERE created_at > datetime('now', '-7 days')
                    ORDER BY created_at DESC
                    LIMIT 5000
                """
                )

                for row in cursor.fetchall():
                    record = {
                        "document_path": row[0],
                        "document_type": row[1],
                        "parameters": json.loads(row[2]),
                        "metrics": json.loads(row[3]),
                        "features": json.loads(row[4]),
                        "objective": row[5],
                        "composite_score": row[6],
                        "timestamp": datetime.fromisoformat(row[7]),
                    }
                    self.performance_history.append(record)

            ml_logger.info(
                f"Loaded {len(self.performance_history)} recent performance records"
            )

        except Exception as e:
            ml_logger.error("Failed to load recent performance data", exception=e)

    @detailed_log_function(LogCategory.SYSTEM)
    def _load_recent_token_usage(self):
        """Load recent token usage data into memory cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT session_id, tokens_used, created_at
                    FROM session_token_usage
                    WHERE created_at > datetime('now', '-7 days')
                    ORDER BY created_at DESC
                    LIMIT 5000
                """
                )

                for row in cursor.fetchall():
                    record = TokenUsageRecord(
                        session_id=row[0],
                        tokens_used=row[1],
                        timestamp=datetime.fromisoformat(row[2]),
                    )
                    self.token_usage_history.append(record)

            ml_logger.info(
                f"Loaded {len(self.token_usage_history)} recent token usage records"
            )

        except Exception as e:
            ml_logger.error("Failed to load recent token usage", exception=e)

    @detailed_log_function(LogCategory.SYSTEM)
    def _load_recent_feedback(self):
        """Load recent review feedback for threshold optimization."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT item_id, item_type, original_confidence, review_decision,
                           confidence_adjustment, notes, user_id, created_at
                    FROM feedback_records
                    WHERE created_at > datetime('now', '-30 days')
                    ORDER BY created_at DESC
                    LIMIT 5000
                """
                )

                for row in cursor.fetchall():
                    record = {
                        "item_id": row[0],
                        "item_type": row[1],
                        "original_confidence": row[2],
                        "review_decision": row[3],
                        "confidence_adjustment": row[4],
                        "notes": row[5],
                        "user_id": row[6],
                        "timestamp": datetime.fromisoformat(row[7]),
                    }
                    self.feedback_history.append(record)

            ml_logger.info(
                f"Loaded {len(self.feedback_history)} recent feedback records"
            )
        except Exception as e:
            ml_logger.error("Failed to load recent feedback data", exception=e)

    @detailed_log_function(LogCategory.PERFORMANCE)
    def record_performance(
        self,
        document_path: str,
        document_type: DocumentCategory,
        parameters: ProcessingParameters,
        metrics: PerformanceMetrics,
        features: DocumentFeatures,
        objective: OptimizationObjective = OptimizationObjective.BALANCED,
    ):
        """Record processing performance for ML training."""

        performance_logger.info(f"Recording performance for {document_path}")

        try:
            with self._lock:
                # Calculate document hash for similarity tracking
                doc_hash = self._calculate_document_hash(document_path, features)

                # Calculate composite score
                composite_score = metrics.get_composite_score(objective)

                # Create record
                record = {
                    "document_path": document_path,
                    "document_type": document_type.value,
                    "document_hash": doc_hash,
                    "parameters": parameters.to_dict(),
                    "metrics": asdict(metrics),
                    "features": asdict(features),
                    "objective": objective.value,
                    "composite_score": composite_score,
                    "timestamp": datetime.now(),
                }

                # Store in database
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT INTO performance_records 
                        (document_path, document_type, document_hash, parameters_json, 
                         metrics_json, features_json, objective, composite_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            document_path,
                            document_type.value,
                            doc_hash,
                            json.dumps(parameters.to_dict()),
                            json.dumps(asdict(metrics)),
                            json.dumps(asdict(features)),
                            objective.value,
                            composite_score,
                        ),
                    )

                # Add to memory cache
                self.performance_history.append(record)

                # Cache document features
                self.document_features_cache[doc_hash] = features

                # Invalidate optimization cache for this document type
                cache_key = f"{document_type.value}_{objective.value}"
                if cache_key in self.optimization_cache:
                    del self.optimization_cache[cache_key]

                performance_logger.info(
                    f"Performance recorded",
                    parameters={
                        "document_type": document_type.value,
                        "composite_score": composite_score,
                        "processing_time": metrics.processing_time,
                        "accuracy_score": metrics.accuracy_score,
                    },
                )

        except Exception as e:
            performance_logger.error(
                f"Failed to record performance for {document_path}", exception=e
            )

    @detailed_log_function(LogCategory.PERFORMANCE)
    def record_step_metrics(
        self, document_path: str, step_name: str, metrics: PerformanceMetrics
    ) -> None:
        """Record metrics for individual workflow steps."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO step_performance_records
                    (document_path, step_name, metrics_json)
                    VALUES (?, ?, ?)
                """,
                    (
                        document_path,
                        step_name,
                        json.dumps(asdict(metrics)),
                    ),
                )
        except Exception as exc:  # pragma: no cover - best effort
            performance_logger.error("Failed to record step metrics", exception=exc)

    @detailed_log_function(LogCategory.SYSTEM)
    def record_review_feedback(
        self,
        item_id: str,
        item_type: str,
        original_confidence: float,
        decision: str,
        confidence_adjustment: float,
        notes: str = "",
        user_id: Optional[str] = None,
    ) -> None:
        """Store reviewer feedback for threshold optimization."""
        record = {
            "item_id": item_id,
            "item_type": item_type,
            "original_confidence": original_confidence,
            "review_decision": decision,
            "confidence_adjustment": confidence_adjustment,
            "notes": notes,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc),
        }
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO feedback_records
                    (item_id, item_type, original_confidence, review_decision,
                     confidence_adjustment, notes, user_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        item_id,
                        item_type,
                        original_confidence,
                        decision,
                        confidence_adjustment,
                        notes,
                        user_id,
                        record["timestamp"].isoformat(),
                    ),
                )
            self.feedback_history.append(record)
        except Exception as e:
            ml_logger.error("Failed to record review feedback", exception=e)

    @detailed_log_function(LogCategory.SYSTEM)
    def record_token_usage(self, session_id: str, tokens_used: int) -> None:
        """Record token usage for a session."""
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO session_token_usage (session_id, tokens_used) VALUES (?, ?)",
                    (session_id, tokens_used),
                )
                conn.commit()

            self.token_usage_history.append(
                TokenUsageRecord(
                    session_id=session_id,
                    tokens_used=tokens_used,
                    timestamp=datetime.now(),
                )
            )

        except Exception as e:
            ml_logger.error("Failed to record token usage", exception=e)

    @detailed_log_function(LogCategory.SYSTEM)
    async def get_optimal_parameters(
        self,
        document_type: DocumentCategory,
        document_features: DocumentFeatures,
        objective: OptimizationObjective = OptimizationObjective.BALANCED,
        force_refresh: bool = False,
    ) -> OptimizationResult:
        """Get ML-optimized processing parameters for document."""

        optimization_logger.info(
            f"Getting optimal parameters for {document_type.value}"
        )

        # Check cache first
        cache_key = self._generate_cache_key(
            document_type, document_features, objective
        )

        if not force_refresh and cache_key in self.optimization_cache:
            cached_result = self.optimization_cache[cache_key]
            optimization_logger.info("Returning cached optimization result")
            return cached_result

        # Check database cache
        if not force_refresh:
            db_result = self._get_cached_optimization(cache_key)
            if db_result:
                self.optimization_cache[cache_key] = db_result
                optimization_logger.info(
                    "Returning database cached optimization result"
                )
                return db_result

        # Find similar documents
        similar_docs = self._find_similar_documents(
            document_type, document_features, objective
        )

        if len(similar_docs) < self.min_samples_for_optimization:
            optimization_logger.warning(
                f"Insufficient samples for optimization: {len(similar_docs)} < {self.min_samples_for_optimization}"
            )
            return self._get_default_optimization_result(document_type, objective)

        # Analyze best performing parameters
        optimal_params, improvement, confidence, reason = self._optimize_parameters(
            similar_docs, objective
        )

        # Create optimization result
        result = OptimizationResult(
            optimized_parameters=optimal_params,
            expected_improvement=improvement,
            confidence=confidence,
            optimization_reason=reason,
            based_on_samples=len(similar_docs),
        )

        # Cache result
        self.optimization_cache[cache_key] = result
        self._cache_optimization_result(cache_key, result)

        optimization_logger.info(
            f"Optimization complete",
            parameters={
                "document_type": document_type.value,
                "samples_used": len(similar_docs),
                "expected_improvement": improvement,
                "confidence": confidence,
            },
        )

        return result

    def _calculate_document_hash(
        self, document_path: str, features: DocumentFeatures
    ) -> str:
        """Calculate hash for document similarity tracking."""
        content = f"{Path(document_path).name}_{features.file_size_mb}_{features.word_count}_{features.complexity_score}"
        return hashlib.md5(content.encode()).hexdigest()

    def _find_similar_documents(
        self,
        document_type: DocumentCategory,
        document_features: DocumentFeatures,
        objective: OptimizationObjective,
    ) -> List[Dict[str, Any]]:
        """Find similar documents based on features and type."""

        target_vector = document_features.to_vector()
        similar_docs = []

        for record in self.performance_history:
            # Filter by document type and objective
            if (
                record["document_type"] != document_type.value
                or record["objective"] != objective.value
            ):
                continue

            # Calculate similarity
            record_features = DocumentFeatures(**record["features"])
            record_vector = record_features.to_vector()

            # Cosine similarity
            similarity = self._cosine_similarity(target_vector, record_vector)

            if similarity >= self.similarity_threshold:
                record["similarity"] = similarity
                similar_docs.append(record)

        # Sort by similarity and composite score
        similar_docs.sort(
            key=lambda x: (x["similarity"], x["composite_score"]), reverse=True
        )

        optimization_logger.trace(
            f"Found {len(similar_docs)} similar documents",
            parameters={
                "document_type": document_type.value,
                "similarity_threshold": self.similarity_threshold,
            },
        )

        return similar_docs

    def _cosine_similarity(self, vec1, vec2) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return float(np.dot(vec1, vec2) / (norm1 * norm2))
        except Exception:
            return 0.0

    def _optimize_parameters(
        self,
        similar_docs: List[Dict[str, Any]],
        objective: OptimizationObjective,
    ) -> Tuple[ProcessingParameters, float, float, str]:
        """Optimize parameters based on similar documents performance."""

        _ = objective  # reserved for future objective-specific logic

        # Sort by performance score
        sorted_docs = sorted(
            similar_docs, key=lambda x: x["composite_score"], reverse=True
        )

        # Take top 25% performers
        top_performers = sorted_docs[: max(1, len(sorted_docs) // 4)]

        # Calculate average parameters from top performers
        param_sums = defaultdict(float)
        param_counts = defaultdict(int)

        for doc in top_performers:
            params = doc["parameters"]
            for key, value in params.items():
                if isinstance(value, (int, float)):
                    param_sums[key] += value
                    param_counts[key] += 1

        # Calculate optimized parameters
        optimized_params_dict = {}
        for key in param_sums:
            if param_counts[key] > 0:
                optimized_params_dict[key] = param_sums[key] / param_counts[key]

        # Handle non-numeric parameters (use mode)
        string_params = defaultdict(list)
        for doc in top_performers:
            params = doc["parameters"]
            for key, value in params.items():
                if isinstance(value, (str, bool)):
                    string_params[key].append(value)

        for key, values in string_params.items():
            if values:
                # Use most common value
                optimized_params_dict[key] = max(set(values), key=values.count)

        # Create ProcessingParameters object
        optimal_params = ProcessingParameters()
        for key, value in optimized_params_dict.items():
            if hasattr(optimal_params, key):
                setattr(optimal_params, key, value)

        # Calculate expected improvement
        top_score = top_performers[0]["composite_score"]
        avg_score = sum(doc["composite_score"] for doc in similar_docs) / len(
            similar_docs
        )
        expected_improvement = float((top_score - avg_score) / max(0.01, avg_score))

        # Calculate confidence based on sample size and score variance
        score_variance = float(np.var([doc["composite_score"] for doc in similar_docs]))
        sample_confidence = min(1.0, len(similar_docs) / 100.0)
        variance_confidence = 1.0 / (1.0 + score_variance)
        confidence = (sample_confidence + variance_confidence) / 2

        reason = f"Optimized based on top {len(top_performers)} performers from {len(similar_docs)} similar documents"

        return optimal_params, expected_improvement, confidence, reason

    def _generate_cache_key(
        self,
        document_type: DocumentCategory,
        document_features: DocumentFeatures,
        objective: OptimizationObjective,
    ) -> str:
        """Generate cache key for optimization results."""
        feature_hash = hashlib.md5(
            str(document_features.to_vector()).encode()
        ).hexdigest()[:8]
        return f"{document_type.value}_{objective.value}_{feature_hash}"

    def _get_cached_optimization(self, cache_key: str) -> Optional[OptimizationResult]:
        """Get optimization result from database cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT parameters_json, expected_improvement, confidence, reason, samples_count
                    FROM optimization_cache 
                    WHERE cache_key = ? AND expires_at > datetime('now')
                """,
                    (cache_key,),
                )

                row = cursor.fetchone()
                if row:
                    return OptimizationResult(
                        optimized_parameters=ProcessingParameters.from_dict(
                            json.loads(row[0])
                        ),
                        expected_improvement=row[1],
                        confidence=row[2],
                        optimization_reason=row[3],
                        based_on_samples=row[4],
                    )
        except Exception as e:
            optimization_logger.error("Failed to get cached optimization", exception=e)

        return None

    def _cache_optimization_result(self, cache_key: str, result: OptimizationResult):
        """Cache optimization result in database."""
        try:
            expires_at = datetime.now() + timedelta(
                hours=self.max_optimization_age_hours
            )

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO optimization_cache 
                    (cache_key, parameters_json, expected_improvement, confidence, reason, samples_count, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        cache_key,
                        json.dumps(result.optimized_parameters.to_dict()),
                        result.expected_improvement,
                        result.confidence,
                        result.optimization_reason,
                        result.based_on_samples,
                        expires_at.isoformat(),
                    ),
                )
        except Exception as e:
            optimization_logger.error(
                "Failed to cache optimization result", exception=e
            )

    def _get_default_optimization_result(
        self, document_type: DocumentCategory, objective: OptimizationObjective
    ) -> OptimizationResult:
        """Get default optimization result when insufficient data."""
        default_params = ProcessingParameters()

        # Adjust defaults based on document type
        if document_type == DocumentCategory.LEGAL_BRIEF:
            default_params.chunk_size = 4000
            default_params.confidence_threshold = 0.8
        elif document_type == DocumentCategory.CONTRACT:
            default_params.chunk_size = 3500
            default_params.confidence_threshold = 0.75
        elif document_type == DocumentCategory.MEMO:
            default_params.chunk_size = 2000
            default_params.temperature = 0.2

        # Adjust for objective
        if objective == OptimizationObjective.SPEED:
            default_params.chunk_size = 2000
            default_params.max_tokens = 1500
        elif objective == OptimizationObjective.ACCURACY:
            default_params.chunk_size = 4000
            default_params.confidence_threshold = 0.9

        return OptimizationResult(
            optimized_parameters=default_params,
            expected_improvement=0.0,
            confidence=0.1,
            optimization_reason="Default parameters - insufficient training data",
            based_on_samples=0,
        )

    @detailed_log_function(LogCategory.SYSTEM)
    def predict_optimal_context_tokens(
        self, default: int = Constants.Size.MAX_CONTEXT_TOKENS
    ) -> int:
        """Predict an optimal max_context_tokens value based on usage history."""
        try:
            tokens = [record.tokens_used for record in self.token_usage_history]
            if not tokens:
                return default

            tokens.sort()
            index = max(0, int(0.9 * len(tokens)) - 1)
            predicted = int(tokens[index] * 1.1)
            return min(predicted, Constants.Size.MAX_CONTEXT_TOKENS)
        except Exception as e:
            ml_logger.error("Failed to predict context tokens", exception=e)
            return default

    @detailed_log_function(LogCategory.SYSTEM)
    def get_optimization_statistics(self) -> Dict[str, Any]:
        """Get comprehensive optimization statistics."""
        stats = {
            "total_performance_records": len(self.performance_history),
            "cache_size": len(self.optimization_cache),
            "document_types": {},
            "objectives": {},
            "avg_composite_scores": {},
            "parameter_distributions": {},
        }

        # Analyze by document type
        type_counts = defaultdict(int)
        objective_counts = defaultdict(int)
        type_scores = defaultdict(list)

        for record in self.performance_history:
            doc_type = record["document_type"]
            objective = record["objective"]
            score = record["composite_score"]

            type_counts[doc_type] += 1
            objective_counts[objective] += 1
            type_scores[doc_type].append(score)

        stats["document_types"] = dict(type_counts)
        stats["objectives"] = dict(objective_counts)
        stats["avg_composite_scores"] = {
            doc_type: sum(scores) / len(scores) if scores else 0
            for doc_type, scores in type_scores.items()
        }

        # Parameter analysis
        if self.performance_history:
            recent_params = [
                record["parameters"] for record in list(self.performance_history)[-100:]
            ]

            for param_name in ["chunk_size", "temperature", "confidence_threshold"]:
                values = [
                    p.get(param_name)
                    for p in recent_params
                    if p.get(param_name) is not None
                ]
                if values:
                    stats["parameter_distributions"][param_name] = {
                        "mean": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "samples": len(values),
                    }

        ml_logger.info("Optimization statistics generated", parameters=stats)
        return stats

    @detailed_log_function(LogCategory.SYSTEM)
    def train_threshold_model(self, min_samples: int = 50) -> Optional[ThresholdModel]:
        """Derive confidence thresholds from reviewer feedback."""
        approved = []
        rejected = []
        for record in self.feedback_history:
            adjusted_conf = (record["original_confidence"] or 0.0) + (
                record["confidence_adjustment"] or 0.0
            )
            decision = record["review_decision"].upper()
            if decision in {"APPROVED", "AUTO_APPROVED", "MODIFIED", "CONFIRMED"}:
                approved.append(adjusted_conf)
            elif decision in {"REJECTED", "DISMISSED"}:
                rejected.append(adjusted_conf)

        if len(approved) + len(rejected) < min_samples or not approved or not rejected:
            ml_logger.warning(
                "Insufficient feedback samples for threshold optimization",
                parameters={"sample_count": len(self.feedback_history)},
            )
            return None

        X = np.array(approved + rejected).reshape(-1, 1)
        y = np.array([1] * len(approved) + [0] * len(rejected))

        try:
            from sklearn.linear_model import LogisticRegression

            model = LogisticRegression()
            model.fit(X, y)

            def prob_to_threshold(p: float) -> float:
                val = (-model.intercept_[0] + np.log(p / (1 - p))) / model.coef_[0][0]
                return max(0.0, min(1.0, float(val)))

            thresholds = ThresholdModel(
                auto_approve_threshold=prob_to_threshold(0.9),
                review_threshold=prob_to_threshold(0.5),
                reject_threshold=prob_to_threshold(0.2),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

            self.threshold_model = thresholds
            ml_logger.info("Threshold model trained", parameters=asdict(thresholds))
            return thresholds

        except Exception as e:
            ml_logger.error("Threshold model training failed", exception=e)
            return None

    async def initialize(self):
        """Async initialization for service container compatibility."""
        ml_logger.info("ML optimizer async initialization complete")
        return self

    def health_check(self) -> Dict[str, Any]:
        """Health check for service container monitoring."""
        return {
            "healthy": True,
            "performance_records": len(self.performance_history),
            "optimization_cache_size": len(self.optimization_cache),
            "database_path": str(self.db_path),
            "min_samples_threshold": self.min_samples_for_optimization,
        }


# Service container factory function
def create_ml_optimizer(config: Optional[MLOptimizerConfig] = None) -> MLOptimizer:
    """Factory function for service container integration."""
    return MLOptimizer(service_config=config or MLOptimizerConfig())
