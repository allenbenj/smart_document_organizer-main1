"""
Unified Embedding Agent with Graph Database Integration
======================================================

Consolidates multiple embedding implementations and provides seamless integration
with the knowledge graph database (Memgraph) for complete entity-to-graph pipeline.

Features:
- Multiple embedding model support (Legal-BERT, Sentence Transformers, OpenAI)
- Vector store integration (FAISS, ChromaDB)
- Knowledge graph integration via Memgraph
- Entity relationship mapping
- Batch processing capabilities
- Comprehensive caching and optimization
"""

from __future__ import annotations

import hashlib
import json  # noqa: E402
import uuid  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from enum import Enum  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

# Core imports
from config.core.service_container import ServiceContainer  # noqa: E402
from agents.base.base_agent import BaseAgent  # noqa: E402

# Optional dependencies with graceful fallbacks
try:
    import numpy as np  # noqa: E402

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    from sentence_transformers import SentenceTransformer  # noqa: E402

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

try:
    from transformers import AutoModel, AutoTokenizer  # noqa: E402

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    AutoTokenizer = None
    AutoModel = None

try:
    import openai  # noqa: E402

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

try:
    from gqlalchemy import Memgraph, Node, Relationship  # noqa: E402

    MEMGRAPH_AVAILABLE = True
except ImportError:
    MEMGRAPH_AVAILABLE = False
    Memgraph = None
    Node = None
    Relationship = None


class EmbeddingModel(Enum):
    """Supported embedding models."""

    LEGAL_BERT = "nlpaueb/legal-bert-base-uncased"
    SENTENCE_TRANSFORMER = "all-MiniLM-L6-v2"
    MINILM_L6 = "all-MiniLM-L6-v2"
    LEGAL_SENTENCE_TRANSFORMER = "law-ai/InLegalBERT"
    NOMIC_EMBED = "nomic-ai/nomic-embed-text-v1.5"
    BGE_RERANKER = "BAAI/bge-reranker-v2-m3"
    JINA_EMBED = "jinaai/jina-embeddings-v2-base-en"
    OPENAI_ADA = "text-embedding-ada-002"
    OPENAI_3_SMALL = "text-embedding-3-small"
    OPENAI_3_LARGE = "text-embedding-3-large"


class VectorStoreType(Enum):
    """Supported vector store types."""

    FAISS = "faiss"
    CHROMADB = "chromadb"
    UNIFIED_VECTOR_STORE = "unified_vector_store"


@dataclass
class EmbeddingConfig:
    """Configuration for embedding operations."""

    model: EmbeddingModel = EmbeddingModel.LEGAL_BERT
    vector_store: VectorStoreType = VectorStoreType.UNIFIED_VECTOR_STORE
    batch_size: int = 32
    max_length: int = 512
    enable_caching: bool = True
    cache_dir: Path = Path("storage/embedding_cache")

    # Graph database integration
    enable_graph_integration: bool = True
    memgraph_host: str = "localhost"
    memgraph_port: int = 7687
    memgraph_username: str = ""
    memgraph_password: str = ""

    # Performance settings
    enable_gpu: bool = False
    normalize_embeddings: bool = True
    similarity_threshold: float = 0.8


@dataclass
class EmbeddingResult:
    """Result of embedding operation."""

    text: str
    embedding: np.ndarray
    model_used: str
    dimension: int
    processing_time: float
    confidence_score: float = 1.0

    # Graph integration fields
    entity_id: Optional[str] = None
    graph_node_id: Optional[str] = None
    relationships: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEntity:
    """Entity representation for graph database."""

    id: str
    name: str
    entity_type: str
    embedding: np.ndarray
    properties: Dict[str, Any] = field(default_factory=dict)

    # Legal-specific fields
    legal_domain: Optional[str] = None
    jurisdiction: Optional[str] = None
    authority_level: Optional[str] = None
    case_id: Optional[str] = None

    def to_graph_properties(self) -> Dict[str, Any]:
        """Convert to graph database properties."""
        props = {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "legal_domain": self.legal_domain,
            "jurisdiction": self.jurisdiction,
            "authority_level": self.authority_level,
            "case_id": self.case_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "embedding_dimension": (
                len(self.embedding) if self.embedding is not None else 0
            ),
        }
        props.update(self.properties)
        return props


class UnifiedEmbeddingAgent(BaseAgent):
    """Unified embedding agent with graph database integration."""

    def __init__(
        self, services: ServiceContainer, config: Optional[EmbeddingConfig] = None
    ):
        super().__init__(services, "UnifiedEmbeddingAgent")
        self.config = config or EmbeddingConfig()

        # Initialize components
        self._embedding_models: Dict[str, Any] = {}
        self._vector_store = None
        self._memgraph_connection: Optional[Memgraph] = None

        # Performance tracking
        self._embedding_times: List[float] = []
        self._cache_hits = 0
        self._cache_misses = 0

        # Cache setup
        if self.config.enable_caching:
            self.config.cache_dir.mkdir(parents=True, exist_ok=True)
            self._embedding_cache: Dict[str, EmbeddingResult] = {}

        self.logger.info(
            f"Initialized {self.agent_name} with model {self.config.model.value}"
        )

    async def initialize(self) -> bool:
        """Initialize the embedding agent."""
        try:
            # Initialize embedding models
            await self._init_embedding_models()

            # Initialize vector store
            await self._init_vector_store()

            # Initialize graph database connection
            if self.config.enable_graph_integration:
                await self._init_memgraph_connection()

            # Load cache if enabled
            if self.config.enable_caching:
                await self._load_cache()

            self.logger.info(f"Successfully initialized {self.agent_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize {self.agent_name}: {e}")
            return False

    async def _init_embedding_models(self):
        """Initialize embedding models based on configuration, preferring local weights."""
        model_name = self.config.model.value
        
        # Local model resolution helper
        def _get_local_path(preferred_name: str) -> str:
            # Map common names to folder names
            folder_map = {
                "all-MiniLM-L6-v2": "all-minilm-L6-v2",
                "nomic-ai/nomic-embed-text-v1.5": "nomic-embed-text",
                "BAAI/bge-reranker-v2-m3": "bge-reranker-v2-m3",
                "jinaai/jina-embeddings-v2-base-en": "jina_embeddings"
            }
            folder_name = folder_map.get(preferred_name, preferred_name.split("/")[-1])
            local_path = Path("models") / folder_name
            if local_path.exists():
                return str(local_path.absolute())
            return preferred_name

        if self.config.model in [
            EmbeddingModel.LEGAL_BERT,
            EmbeddingModel.LEGAL_SENTENCE_TRANSFORMER,
            EmbeddingModel.MINILM_L6,
            EmbeddingModel.SENTENCE_TRANSFORMER,
            EmbeddingModel.NOMIC_EMBED,
            EmbeddingModel.JINA_EMBED,
            EmbeddingModel.BGE_RERANKER
        ]:
            model_path = _get_local_path(model_name)
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                try:
                    self._embedding_models[model_name] = SentenceTransformer(model_path)
                    self.logger.info(f"Loaded model from: {model_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to load {model_name} via sentence-transformers: {e}")
                    # Fallback to manual transformers if needed
            
            if model_name not in self._embedding_models and TRANSFORMERS_AVAILABLE:
                try:
                    self._embedding_models[f"{model_name}_tokenizer"] = AutoTokenizer.from_pretrained(model_path)
                    self._embedding_models[f"{model_name}_model"] = AutoModel.from_pretrained(model_path, trust_remote_code=True)
                    self.logger.info(f"Loaded manual transformers model from: {model_path}")
                except Exception as e:
                    raise RuntimeError(f"Failed to load model {model_name}: {e}")

        elif self.config.model in [
            EmbeddingModel.OPENAI_ADA,
            EmbeddingModel.OPENAI_3_SMALL,
            EmbeddingModel.OPENAI_3_LARGE,
        ]:
            if OPENAI_AVAILABLE:
                # OpenAI models don't need local loading
                self.logger.info(f"Configured OpenAI model: {model_name}")
            else:
                raise RuntimeError("openai not available")

    async def _init_vector_store(self):
        """Initialize vector store connection."""
        try:
            if self.config.vector_store == VectorStoreType.UNIFIED_VECTOR_STORE:
                self._vector_store = self.services.get_service("unified_vector_store")
            elif self.config.vector_store == VectorStoreType.CHROMADB:
                self._vector_store = self.services.get_service("chroma_memory")
            elif self.config.vector_store == VectorStoreType.FAISS:
                self._vector_store = self.services.get_service("faiss_vector_store")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize vector store: {e}") from e

        if not self._vector_store:
            raise RuntimeError(
                f"Vector store {self.config.vector_store.value} is required but unavailable"
            )

    async def _init_memgraph_connection(self):
        """Initialize Memgraph database connection."""
        if not MEMGRAPH_AVAILABLE:
            raise RuntimeError(
                "Memgraph dependency is required for graph integration but unavailable."
            )

        try:
            self._memgraph_connection = Memgraph(
                host=self.config.memgraph_host,
                port=self.config.memgraph_port,
                username=self.config.memgraph_username,
                password=self.config.memgraph_password,
            )

            # Test connection
            result = list(
                self._memgraph_connection.execute_and_fetch("RETURN 1 as test")
            )
            if result:
                self.logger.info("Connected to Memgraph successfully")

        except Exception as e:
            self._memgraph_connection = None
            raise RuntimeError(f"Failed to connect to Memgraph: {e}") from e

    async def _load_cache(self):
        """Load embedding cache from disk."""
        cache_file = self.config.cache_dir / "embedding_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cache_data = json.load(f)

                for key, data in cache_data.items():
                    # Reconstruct numpy array
                    if NUMPY_AVAILABLE and data.get("embedding"):
                        data["embedding"] = np.array(data["embedding"])

                    self._embedding_cache[key] = EmbeddingResult(**data)

                self.logger.info(
                    f"Loaded {len(self._embedding_cache)} cached embeddings"
                )

            except Exception as e:
                self.logger.warning(f"Failed to load embedding cache: {e}")

    async def _save_cache(self):
        """Save embedding cache to disk."""
        if not self.config.enable_caching:
            return

        try:
            cache_file = self.config.cache_dir / "embedding_cache.json"
            cache_data = {}

            for key, result in self._embedding_cache.items():
                data = {
                    "text": result.text,
                    "embedding": result.embedding.tolist() if NUMPY_AVAILABLE else None,
                    "model_used": result.model_used,
                    "dimension": result.dimension,
                    "processing_time": result.processing_time,
                    "confidence_score": result.confidence_score,
                    "entity_id": result.entity_id,
                    "graph_node_id": result.graph_node_id,
                    "relationships": result.relationships,
                    "metadata": result.metadata,
                }
                cache_data[key] = data

            with open(cache_file, "w") as f:
                json.dump(cache_data, f)

            self.logger.debug(f"Saved {len(cache_data)} embeddings to cache")

        except Exception as e:
            self.logger.warning(f"Failed to save embedding cache: {e}")

    async def embed_text(
        self, text: str, entity_id: Optional[str] = None
    ) -> EmbeddingResult:
        """Generate embedding for text with optional entity tracking."""
        start_time = time.time()

        # Check cache first
        cache_key = self._generate_cache_key(text, self.config.model.value)
        if self.config.enable_caching and cache_key in self._embedding_cache:
            self._cache_hits += 1
            result = self._embedding_cache[cache_key]
            if entity_id:
                result.entity_id = entity_id
            return result

        self._cache_misses += 1

        try:
            # Generate embedding based on model type
            embedding = await self._generate_embedding(text)

            # Normalize if configured
            if self.config.normalize_embeddings and NUMPY_AVAILABLE:
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

            processing_time = time.time() - start_time
            self._embedding_times.append(processing_time)

            # Create result
            result = EmbeddingResult(
                text=text,
                embedding=embedding,
                model_used=self.config.model.value,
                dimension=len(embedding) if embedding is not None else 0,
                processing_time=processing_time,
                entity_id=entity_id,
            )

            # Cache result
            if self.config.enable_caching:
                self._embedding_cache[cache_key] = result

            # Store in vector store if available
            if self._vector_store:
                await self._store_in_vector_store(result)

            self.logger.debug(
                f"Generated embedding for text (dim={result.dimension}, time={processing_time:.3f}s)"
            )
            return result

        except Exception as e:
            self.logger.error(f"Failed to generate embedding: {e}")
            raise

    async def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using the configured model."""
        model_name = self.config.model.value

        if self.config.model in [
            EmbeddingModel.LEGAL_BERT,
            EmbeddingModel.SENTENCE_TRANSFORMER,
            EmbeddingModel.LEGAL_SENTENCE_TRANSFORMER,
        ]:
            if model_name in self._embedding_models:
                # Sentence Transformer
                model = self._embedding_models[model_name]
                embedding = model.encode(text, convert_to_tensor=False)
                return np.array(embedding) if NUMPY_AVAILABLE else embedding
            else:
                # Manual transformers
                tokenizer = self._embedding_models[f"{model_name}_tokenizer"]
                model = self._embedding_models[f"{model_name}_model"]

                inputs = tokenizer(
                    text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=self.config.max_length,
                    padding=True,
                )

                import torch  # noqa: E402

                with torch.no_grad():
                    outputs = model(**inputs)
                    # Use mean pooling
                    embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()

                return embedding

        elif self.config.model in [
            EmbeddingModel.OPENAI_ADA,
            EmbeddingModel.OPENAI_3_SMALL,
            EmbeddingModel.OPENAI_3_LARGE,
        ]:
            if OPENAI_AVAILABLE:
                response = await openai.Embedding.acreate(input=text, model=model_name)
                embedding = response["data"][0]["embedding"]
                return np.array(embedding) if NUMPY_AVAILABLE else embedding
            else:
                raise RuntimeError("OpenAI not available")

        else:
            raise ValueError(f"Unsupported embedding model: {self.config.model}")

    async def _store_in_vector_store(self, result: EmbeddingResult):
        """Store embedding in vector store."""
        try:
            if hasattr(self._vector_store, "add_document"):
                # Unified vector store
                await self._vector_store.add_document(
                    content=result.text,
                    embedding=result.embedding,
                    metadata={
                        "entity_id": result.entity_id,
                        "model_used": result.model_used,
                        "processing_time": result.processing_time,
                        **result.metadata,
                    },
                    document_type="embedding",
                    importance_score=result.confidence_score,
                )
            elif hasattr(self._vector_store, "upsert"):
                # ChromaDB
                self._vector_store.upsert(
                    documents=[result.text],
                    embeddings=[result.embedding.tolist()],
                    metadatas=[
                        {
                            "entity_id": result.entity_id,
                            "model_used": result.model_used,
                            **result.metadata,
                        }
                    ],
                    ids=[result.entity_id or f"emb_{hash(result.text)}"],
                )

        except Exception as e:
            self.logger.warning(f"Failed to store in vector store: {e}")

    async def embed_entities_to_graph(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Embed entities and store them in the knowledge graph."""
        if not self._memgraph_connection:
            raise RuntimeError(
                "Memgraph connection is required for embed_entities_to_graph."
            )

        graph_node_ids = []

        try:
            for entity_data in entities:
                # Generate embedding for entity
                entitytext = (  # noqa: F841
                    f"{entity_data.get('name', '')} {entity_data.get('content', '')}"
                )
                result = await self.embed_text(entity_text, entity_data.get("id"))  # noqa: F821

                # Create graph entity
                graph_entity = GraphEntity(
                    id=entity_data.get("id", str(uuid.uuid4())),
                    name=entity_data.get("name", ""),
                    entity_type=entity_data.get("type", "unknown"),
                    embedding=result.embedding,
                    properties=entity_data.get("metadata", {}),
                    legal_domain=entity_data.get("legal_domain"),
                    jurisdiction=entity_data.get("jurisdiction"),
                    authority_level=entity_data.get("authority_level"),
                    case_id=entity_data.get("case_id"),
                )

                # Store in graph database
                node_id = await self._store_entity_in_graph(graph_entity)
                if node_id:
                    graph_node_ids.append(node_id)
                    result.graph_node_id = node_id

            self.logger.info(
                f"Stored {len(graph_node_ids)} entities in knowledge graph"
            )
            return graph_node_ids

        except Exception as e:
            self.logger.error(f"Failed to embed entities to graph: {e}")
            raise

    async def _store_entity_in_graph(self, entity: GraphEntity) -> Optional[str]:
        """Store entity in Memgraph database."""
        try:
            # Convert embedding to string for storage
            embedding_str = (
                json.dumps(entity.embedding.tolist()) if NUMPY_AVAILABLE else "[]"
            )

            # Create node query
            query = """
            MERGE (e:LegalEntity {id: $id})
            SET e.name = $name,
                e.entity_type = $entity_type,
                e.legal_domain = $legal_domain,
                e.jurisdiction = $jurisdiction,
                e.authority_level = $authority_level,
                e.case_id = $case_id,
                e.embedding = $embedding,
                e.updated_at = $updated_at
            RETURN e.id as node_id
            """

            params = {
                "id": entity.id,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "legal_domain": entity.legal_domain,
                "jurisdiction": entity.jurisdiction,
                "authority_level": entity.authority_level,
                "case_id": entity.case_id,
                "embedding": embedding_str,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            result = list(self._memgraph_connection.execute_and_fetch(query, params))

            if result:
                return result[0]["node_id"]

        except Exception as e:
            self.logger.error(f"Failed to store entity in graph: {e}")

        return None

    async def find_similar_entities(
        self,
        query_text: str,
        top_k: int = 10,
        similarity_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Find similar entities using embedding similarity."""
        threshold = similarity_threshold or self.config.similarity_threshold

        try:
            # Generate query embedding
            query_result = await self.embed_text(query_text)
            query_embedding = query_result.embedding

            # Search in vector store first
            if self._vector_store and hasattr(self._vector_store, "search"):
                search_results = await self._vector_store.search(
                    query_embedding=query_embedding, k=top_k, min_importance=0.0
                )

                similar_entities = []
                for result in search_results:
                    if result.similarity_score >= threshold:
                        similar_entities.append(
                            {
                                "entity_id": result.document.metadata.get("entity_id"),
                                "content": result.document.content,
                                "similarity_score": result.similarity_score,
                                "metadata": result.document.metadata,
                            }
                        )

                return similar_entities

            # Search graph database if vector store search endpoint is unavailable
            elif self._memgraph_connection:
                return await self._graph_similarity_search(
                    query_embedding, top_k, threshold
                )
            raise RuntimeError(
                "No similarity search backend available (vector store or Memgraph)."
            )

        except Exception as e:
            self.logger.error(f"Failed to find similar entities: {e}")
            raise

    async def _graph_similarity_search(
        self, query_embedding: np.ndarray, top_k: int, threshold: float
    ) -> List[Dict[str, Any]]:
        """Perform similarity search in graph database."""
        try:
            # Note: This is a simplified approach. In practice, you'd want to use
            # graph database vector similarity extensions or export embeddings for comparison

            query = """
            MATCH (e:LegalEntity)
            WHERE e.embedding IS NOT NULL
            RETURN e.id as entity_id, e.name, e.entity_type, e.embedding,
                   e.legal_domain, e.jurisdiction, e.case_id
            LIMIT $limit
            """

            results = list(
                self._memgraph_connection.execute_and_fetch(query, {"limit": top_k * 2})
            )

            similar_entities = []
            for result in results:
                try:
                    # Parse stored embedding
                    stored_embedding = np.array(json.loads(result["embedding"]))

                    # Calculate similarity
                    if not NUMPY_AVAILABLE or np is None:
                        raise RuntimeError(
                            "NumPy is required for graph similarity calculations."
                        )
                    similarity = np.dot(query_embedding, stored_embedding) / (
                        np.linalg.norm(query_embedding)
                        * np.linalg.norm(stored_embedding)
                    )

                    if similarity >= threshold:
                        similar_entities.append(
                            {
                                "entity_id": result["entity_id"],
                                "name": result["name"],
                                "entity_type": result["entity_type"],
                                "similarity_score": float(similarity),
                                "legal_domain": result["legal_domain"],
                                "jurisdiction": result["jurisdiction"],
                                "case_id": result["case_id"],
                            }
                        )

                except Exception as e:
                    self.logger.warning(f"Failed to process entity similarity: {e}")
                    continue

            # Sort by similarity and limit
            similar_entities.sort(key=lambda x: x["similarity_score"], reverse=True)
            return similar_entities[:top_k]

        except Exception as e:
            self.logger.error(f"Graph similarity search failed: {e}")
            raise

    def _generate_cache_key(self, text: str, model: str) -> str:
        """Generate cache key for text and model."""
        content = f"{text}:{model}"
        return hashlib.md5(content.encode()).hexdigest()

    async def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive embedding agent statistics."""
        stats = {
            "model_used": self.config.model.value,
            "vector_store_type": self.config.vector_store.value,
            "cache_enabled": self.config.enable_caching,
            "graph_integration_enabled": self.config.enable_graph_integration,
            "memgraph_connected": self._memgraph_connection is not None,
            # Performance stats
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hits
            / max(1, self._cache_hits + self._cache_misses),
            "cached_embeddings": (
                len(self._embedding_cache) if self.config.enable_caching else 0
            ),
            # Timing stats
            "total_embeddings": len(self._embedding_times),
            "average_embedding_time": (
                sum(self._embedding_times) / len(self._embedding_times)
                if self._embedding_times
                else 0
            ),
            "max_embedding_time": (
                max(self._embedding_times) if self._embedding_times else 0
            ),
            "min_embedding_time": (
                min(self._embedding_times) if self._embedding_times else 0
            ),
        }

        return stats

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on embedding agent."""
        health = {
            "healthy": True,
            "embedding_models_loaded": len(self._embedding_models) > 0,
            "vector_store_available": self._vector_store is not None,
            "memgraph_connected": self._memgraph_connection is not None,
            "cache_operational": self.config.enable_caching,
        }

        try:
            # Test embedding generation
            test_result = await self.embed_text("test embedding health check")
            health["embedding_functional"] = test_result.embedding is not None
            health["embedding_dimension"] = test_result.dimension

            # Test vector store
            if self._vector_store:
                if hasattr(self._vector_store, "health_check"):
                    vs_health = await self._vector_store.health_check()
                    health["vector_store_healthy"] = vs_health.get("healthy", False)

            # Test Memgraph connection
            if self._memgraph_connection:
                try:
                    list(self._memgraph_connection.execute_and_fetch("RETURN 1"))
                    health["memgraph_accessible"] = True
                except Exception:
                    health["memgraph_accessible"] = False
                    health["healthy"] = False

        except Exception as e:
            health["healthy"] = False
            health["error"] = str(e)
            self.logger.error(f"Embedding agent health check failed: {e}")

        return health

    async def _process_task(
        self, task_data: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process embedding task - main entry point for base agent integration."""
        task_type = task_data.get("type", "embed_text")

        if task_type == "embed_text":
            text = task_data.get("text", "")
            entity_id = task_data.get("entity_id")

            result = await self.embed_text(text, entity_id)

            return {
                "success": True,
                "result": {
                    "embedding": result.embedding.tolist() if NUMPY_AVAILABLE else [],
                    "dimension": result.dimension,
                    "model_used": result.model_used,
                    "processing_time": result.processing_time,
                    "entity_id": result.entity_id,
                    "graph_node_id": result.graph_node_id,
                },
                "metadata": metadata,
            }

        elif task_type == "embed_entities_to_graph":
            entities = task_data.get("entities", [])
            graph_node_ids = await self.embed_entities_to_graph(entities)

            return {
                "success": True,
                "result": {
                    "graph_node_ids": graph_node_ids,
                    "entities_processed": len(entities),
                },
                "metadata": metadata,
            }

        elif task_type == "find_similar_entities":
            querytext = task_data.get("query_text", "")  # noqa: F841
            top_k = task_data.get("top_k", 10)
            threshold = task_data.get("similarity_threshold")

            similar_entities = await self.find_similar_entities(
                query_text, top_k, threshold  # noqa: F821
            )

            return {
                "success": True,
                "result": {
                    "similar_entities": similar_entities,
                    "query_text": query_text,  # noqa: F821
                    "results_count": len(similar_entities),
                },
                "metadata": metadata,
            }

        else:
            raise ValueError(f"Unknown task type: {task_type}")

    async def cleanup(self):
        """Cleanup resources."""
        # Save cache
        if self.config.enable_caching:
            await self._save_cache()

        # Close Memgraph connection
        if self._memgraph_connection:
            try:
                self._memgraph_connection.close()
            except Exception as e:
                self.logger.warning(f"Failed to close Memgraph connection: {e}")

        self.logger.info(f"Cleaned up {self.agent_name}")


# Service registration helper
def register_unified_embedding_service(
    services: ServiceContainer, config: Optional[EmbeddingConfig] = None
) -> UnifiedEmbeddingAgent:
    """Register unified embedding agent as a service."""
    agent = UnifiedEmbeddingAgent(services, config)
    services.register_service("unified_embedding_agent", agent)
    return agent
