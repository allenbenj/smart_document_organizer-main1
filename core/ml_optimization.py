"""
ML Library Optimization Module

Provides optimized machine learning utilities for document processing,
including fast similarity search, embedding caching, and clustering.

Features:
- FAISS integration for fast nearest neighbor search
- Embedding cache to avoid re-computing vectors
- Batch processing for multiple documents
- K-means clustering for entity grouping
- GPU support detection (CUDA for FAISS)
- Performance profiling and metrics
"""

import os
import json
import pickle
import hashlib
from typing import List, Dict, Optional, Tuple, Any, Union
from pathlib import Path
from datetime import datetime
import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
    # Check for GPU support
    try:
        gpu_count = faiss.get_num_gpus()
        FAISS_GPU_AVAILABLE = gpu_count > 0
    except:
        FAISS_GPU_AVAILABLE = False
except ImportError:
    FAISS_AVAILABLE = False
    FAISS_GPU_AVAILABLE = False

try:
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.metrics import silhouette_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class EmbeddingCache:
    """
    Persistent cache for text embeddings to avoid re-computation.
    
    Uses SHA-256 hashing of text for lookup and pickle for storage.
    """
    
    def __init__(self, cache_dir: str = "./cache/embeddings"):
        """
        Initialize embedding cache.
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "embedding_cache.pkl"
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        
        # Load existing cache
        self.cache: Dict[str, np.ndarray] = {}
        self.metadata: Dict = {
            "hits": 0,
            "misses": 0,
            "total_entries": 0,
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        
        self._load_cache()
        
    def _load_cache(self):
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    self.cache = pickle.load(f)
            except Exception as e:
                print(f"Warning: Failed to load cache: {e}")
                self.cache = {}
        
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    self.metadata.update(json.load(f))
            except Exception as e:
                print(f"Warning: Failed to load metadata: {e}")
        
        self.metadata["total_entries"] = len(self.cache)
        
    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
            
            self.metadata["last_updated"] = datetime.now().isoformat()
            self.metadata["total_entries"] = len(self.cache)
            
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save cache: {e}")
            
    def _get_hash(self, text: str) -> str:
        """Get SHA-256 hash of text."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
        
    def get(self, text: str) -> Optional[np.ndarray]:
        """
        Get embedding from cache.
        
        Args:
            text: Input text
            
        Returns:
            Cached embedding or None if not found
        """
        text_hash = self._get_hash(text)
        
        if text_hash in self.cache:
            self.metadata["hits"] += 1
            return self.cache[text_hash]
        
        self.metadata["misses"] += 1
        return None
        
    def put(self, text: str, embedding: np.ndarray):
        """
        Store embedding in cache.
        
        Args:
            text: Input text
            embedding: Text embedding vector
        """
        text_hash = self._get_hash(text)
        self.cache[text_hash] = embedding
        
        # Periodically save cache (every 10 new entries)
        if len(self.cache) % 10 == 0:
            self._save_cache()
            
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total_requests = self.metadata["hits"] + self.metadata["misses"]
        hit_rate = self.metadata["hits"] / total_requests if total_requests > 0 else 0.0
        
        return {
            **self.metadata,
            "hit_rate": hit_rate,
            "total_requests": total_requests
        }
        
    def clear(self):
        """Clear the cache."""
        self.cache = {}
        self.metadata["hits"] = 0
        self.metadata["misses"] = 0
        self.metadata["total_entries"] = 0
        self._save_cache()
        
    def save(self):
        """Explicitly save cache to disk."""
        self._save_cache()


class FAISSSearchEngine:
    """
    Fast similarity search engine using FAISS.
    
    Provides efficient nearest neighbor search for embeddings.
    """
    
    def __init__(
        self,
        dimension: int = 384,
        use_gpu: bool = False,
        index_type: str = "flat"
    ):
        """
        Initialize FAISS search engine.
        
        Args:
            dimension: Embedding dimension
            use_gpu: Whether to use GPU if available
            index_type: Index type ("flat", "ivf", "hnsw")
        """
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS not installed. Install with: pip install faiss-cpu or faiss-gpu")
        
        self.dimension = dimension
        self.use_gpu = use_gpu and FAISS_GPU_AVAILABLE
        self.index_type = index_type
        
        self.index = None
        self.id_to_metadata: Dict[int, Dict] = {}
        self._build_index()
        
    def _build_index(self):
        """Build FAISS index."""
        if self.index_type == "flat":
            # L2 distance (Euclidean)
            self.index = faiss.IndexFlatL2(self.dimension)
        elif self.index_type == "ivf":
            # Inverted file index (faster but approximate)
            quantizer = faiss.IndexFlatL2(self.dimension)
            self.index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)
            self.requires_training = True
        elif self.index_type == "hnsw":
            # Hierarchical Navigable Small World (fast and accurate)
            self.index = faiss.IndexHNSWFlat(self.dimension, 32)
        else:
            raise ValueError(f"Unknown index type: {self.index_type}")
        
        # Move to GPU if requested
        if self.use_gpu:
            res = faiss.StandardGpuResources()
            self.index = faiss.index_cpu_to_gpu(res, 0, self.index)
            
    def add_embeddings(
        self,
        embeddings: np.ndarray,
        metadata: Optional[List[Dict]] = None
    ):
        """
        Add embeddings to the index.
        
        Args:
            embeddings: Array of embeddings (n_samples, dimension)
            metadata: Optional metadata for each embedding
        """
        if embeddings.dtype != np.float32:
            embeddings = embeddings.astype(np.float32)
        
        # Train index if needed (IVF)
        if hasattr(self, 'requires_training') and self.requires_training:
            if self.index.is_trained:
                pass
            else:
                self.index.train(embeddings)
                self.requires_training = False
        
        # Add to index
        start_id = self.index.ntotal
        self.index.add(embeddings)
        
        # Store metadata
        if metadata:
            for i, meta in enumerate(metadata):
                self.id_to_metadata[start_id + i] = meta
                
    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Search for nearest neighbors.
        
        Args:
            query_embedding: Query embedding (dimension,) or (1, dimension)
            k: Number of nearest neighbors
            
        Returns:
            Tuple of (distances, indices)
        """
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        if query_embedding.dtype != np.float32:
            query_embedding = query_embedding.astype(np.float32)
        
        distances, indices = self.index.search(query_embedding, k)
        return distances[0], indices[0]
        
    def search_with_metadata(
        self,
        query_embedding: np.ndarray,
        k: int = 5
    ) -> List[Dict]:
        """
        Search with metadata included.
        
        Args:
            query_embedding: Query embedding
            k: Number of results
            
        Returns:
            List of results with distance and metadata
        """
        distances, indices = self.search(query_embedding, k)
        
        results = []
        for dist, idx in zip(distances, indices):
            if idx == -1:  # FAISS returns -1 for invalid results
                continue
            
            result = {
                "distance": float(dist),
                "index": int(idx),
                "metadata": self.id_to_metadata.get(int(idx), {})
            }
            results.append(result)
        
        return results
        
    def get_stats(self) -> Dict:
        """Get index statistics."""
        return {
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "index_type": self.index_type,
            "gpu_enabled": self.use_gpu,
            "is_trained": getattr(self.index, 'is_trained', True)
        }
        
    def save(self, filepath: str):
        """Save index to file."""
        # Move to CPU before saving if on GPU
        if self.use_gpu:
            cpu_index = faiss.index_gpu_to_cpu(self.index)
            faiss.write_index(cpu_index, filepath)
        else:
            faiss.write_index(self.index, filepath)
        
        # Save metadata separately
        metadata_path = filepath + ".metadata.pkl"
        with open(metadata_path, 'wb') as f:
            pickle.dump(self.id_to_metadata, f)
            
    def load(self, filepath: str):
        """Load index from file."""
        self.index = faiss.read_index(filepath)
        
        # Move to GPU if requested
        if self.use_gpu:
            res = faiss.StandardGpuResources()
            self.index = faiss.index_cpu_to_gpu(res, 0, self.index)
        
        # Load metadata
        metadata_path = filepath + ".metadata.pkl"
        if Path(metadata_path).exists():
            with open(metadata_path, 'rb') as f:
                self.id_to_metadata = pickle.load(f)


class EntityClusterer:
    """
    Clustering utilities for grouping similar entities.
    
    Uses K-means or DBSCAN for unsupervised clustering.
    """
    
    def __init__(self, algorithm: str = "kmeans"):
        """
        Initialize clusterer.
        
        Args:
            algorithm: Clustering algorithm ("kmeans" or "dbscan")
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn not installed. Install with: pip install scikit-learn")
        
        self.algorithm = algorithm
        self.model = None
        self.labels_ = None
        
    def fit(
        self,
        embeddings: np.ndarray,
        n_clusters: Optional[int] = None,
        **kwargs
    ) -> np.ndarray:
        """
        Fit clustering model.
        
        Args:
            embeddings: Array of embeddings (n_samples, dimension)
            n_clusters: Number of clusters (for k-means)
            **kwargs: Additional algorithm parameters
            
        Returns:
            Cluster labels
        """
        if self.algorithm == "kmeans":
            if n_clusters is None:
                # Auto-determine number of clusters using elbow method
                n_clusters = self._find_optimal_k(embeddings)
            
            self.model = KMeans(n_clusters=n_clusters, **kwargs)
            self.labels_ = self.model.fit_predict(embeddings)
            
        elif self.algorithm == "dbscan":
            eps = kwargs.pop('eps', 0.5)
            min_samples = kwargs.pop('min_samples', 5)
            
            self.model = DBSCAN(eps=eps, min_samples=min_samples, **kwargs)
            self.labels_ = self.model.fit_predict(embeddings)
            
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")
        
        return self.labels_
        
    def _find_optimal_k(self, embeddings: np.ndarray, max_k: int = 10) -> int:
        """
        Find optimal number of clusters using elbow method.
        
        Args:
            embeddings: Embeddings array
            max_k: Maximum number of clusters to try
            
        Returns:
            Optimal number of clusters
        """
        if len(embeddings) < max_k:
            max_k = len(embeddings)
        
        inertias = []
        k_range = range(2, min(max_k + 1, len(embeddings)))
        
        for k in k_range:
            kmeans = KMeans(n_clusters=k, random_state=42)
            kmeans.fit(embeddings)
            inertias.append(kmeans.inertia_)
        
        # Simple elbow detection: find max curvature
        if len(inertias) < 3:
            return 2
        
        diffs = np.diff(inertias)
        diff_diffs = np.diff(diffs)
        elbow_idx = np.argmax(diff_diffs) + 2
        
        return min(k_range[elbow_idx] if elbow_idx < len(k_range) else max_k, max_k)
        
    def get_cluster_info(self, embeddings: np.ndarray) -> Dict:
        """
        Get detailed cluster information.
        
        Args:
            embeddings: Original embeddings
            
        Returns:
            Dictionary with cluster statistics
        """
        if self.labels_ is None:
            return {}
        
        unique_labels = np.unique(self.labels_)
        n_clusters = len([label for label in unique_labels if label != -1])  # Exclude noise (-1)
        
        cluster_sizes = {
            label: np.sum(self.labels_ == label)
            for label in unique_labels
        }
        
        # Silhouette score (quality metric)
        if len(unique_labels) > 1 and len(embeddings) > 1:
            try:
                silhouette = silhouette_score(embeddings, self.labels_)
            except:
                silhouette = 0.0
        else:
            silhouette = 0.0
        
        return {
            "n_clusters": n_clusters,
            "cluster_sizes": cluster_sizes,
            "silhouette_score": silhouette,
            "algorithm": self.algorithm,
            "total_samples": len(self.labels_),
            "noise_points": np.sum(self.labels_ == -1) if -1 in self.labels_ else 0
        }


class BatchProcessor:
    """
    Batch processing utilities for efficient embedding generation.
    
    Processes multiple documents/texts in batches to maximize throughput.
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        batch_size: int = 32,
        cache_dir: str = "./cache/embeddings"
    ):
        """
        Initialize batch processor.
        
        Args:
            model_name: SentenceTransformer model name
            batch_size: Batch size for processing
            cache_dir: Directory for embedding cache
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model_name = model_name
        self.batch_size = batch_size
        self.model = SentenceTransformer(model_name)
        self.cache = EmbeddingCache(cache_dir)
        
    def encode_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Encode a batch of texts to embeddings.
        
        Args:
            texts: List of text strings
            use_cache: Whether to use embedding cache
            show_progress: Show progress bar
            
        Returns:
            Array of embeddings (n_texts, dimension)
        """
        if use_cache:
            # Check cache first
            embeddings = []
            uncached_texts = []
            uncached_indices = []
            
            for i, text in enumerate(texts):
                cached_emb = self.cache.get(text)
                if cached_emb is not None:
                    embeddings.append(cached_emb)
                else:
                    embeddings.append(None)
                    uncached_texts.append(text)
                    uncached_indices.append(i)
            
            # Encode uncached texts
            if uncached_texts:
                new_embeddings = self.model.encode(
                    uncached_texts,
                    batch_size=self.batch_size,
                    show_progress_bar=show_progress,
                    convert_to_numpy=True
                )
                
                # Store in cache
                for text, emb in zip(uncached_texts, new_embeddings):
                    self.cache.put(text, emb)
                
                # Insert into results
                for idx, emb in zip(uncached_indices, new_embeddings):
                    embeddings[idx] = emb
            
            # Save cache periodically
            self.cache.save()
            
            return np.array(embeddings)
        else:
            # No cache
            return self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True
            )
            
    def get_stats(self) -> Dict:
        """Get processing statistics."""
        return {
            "model_name": self.model_name,
            "batch_size": self.batch_size,
            "embedding_dimension": self.model.get_sentence_embedding_dimension(),
            "cache_stats": self.cache.get_stats()
        }


# Example usage and testing
if __name__ == "__main__":
    print("=" * 60)
    print("ML Library Optimization Module - Feature Tests")
    print("=" * 60)
    
    # Test 1: Embedding Cache
    print("\n[Test 1] Embedding Cache")
    cache = EmbeddingCache("./test_cache")
    
    test_text = "This is a test document."
    test_embedding = np.random.rand(384).astype(np.float32)
    
    # Store
    cache.put(test_text, test_embedding)
    print(f"  ✓ Stored embedding")
    
    # Retrieve
    retrieved = cache.get(test_text)
    assert retrieved is not None
    assert np.allclose(retrieved, test_embedding)
    print(f"  ✓ Retrieved embedding (match: {np.allclose(retrieved, test_embedding)})")
    
    # Stats
    stats = cache.get_stats()
    print(f"  ✓ Cache stats: {stats['hits']} hits, {stats['misses']} misses, "
          f"{stats['hit_rate']:.2%} hit rate")
    
    # Test 2: FAISS Search Engine
    if FAISS_AVAILABLE:
        print("\n[Test 2] FAISS Search Engine")
        engine = FAISSSearchEngine(dimension=384, index_type="flat")
        
        # Add some vectors
        vectors = np.random.rand(100, 384).astype(np.float32)
        metadata = [{"id": i, "text": f"Document {i}"} for i in range(100)]
        engine.add_embeddings(vectors, metadata)
        print(f"  ✓ Added {engine.index.ntotal} vectors")
        
        # Search
        query = np.random.rand(384).astype(np.float32)
        results = engine.search_with_metadata(query, k=5)
        print(f"  ✓ Found {len(results)} nearest neighbors")
        print(f"    Top result distance: {results[0]['distance']:.4f}")
        
        # Stats
        stats = engine.get_stats()
        print(f"  ✓ Index stats: {stats}")
    else:
        print("\n[Test 2] FAISS Search Engine - SKIPPED (FAISS not installed)")
    
    # Test 3: Entity Clusterer
    if SKLEARN_AVAILABLE:
        print("\n[Test 3] Entity Clusterer")
        clusterer = EntityClusterer(algorithm="kmeans")
        
        # Create some test data
        data = np.random.rand(50, 384).astype(np.float32)
        labels = clusterer.fit(data, n_clusters=5)
        print(f"  ✓ Clustered {len(data)} samples into {len(np.unique(labels))} clusters")
        
        # Cluster info
        info = clusterer.get_cluster_info(data)
        print(f"  ✓ Silhouette score: {info['silhouette_score']:.3f}")
        print(f"    Cluster sizes: {info['cluster_sizes']}")
    else:
        print("\n[Test 3] Entity Clusterer - SKIPPED (scikit-learn not installed)")
    
    # Test 4: Batch Processor
    if SENTENCE_TRANSFORMERS_AVAILABLE:
        print("\n[Test 4] Batch Processor")
        processor = BatchProcessor(batch_size=8, cache_dir="./test_cache")
        
        texts = [
            "This is document 1.",
            "This is document 2.",
            "This is document 3.",
            "This is document 1.",  # Duplicate (should hit cache)
        ]
        
        embeddings = processor.encode_batch(texts, use_cache=True)
        print(f"  ✓ Encoded {len(texts)} texts")
        print(f"    Embedding shape: {embeddings.shape}")
        
        stats = processor.get_stats()
        print(f"  ✓ Stats: {stats['cache_stats']['hits']} cache hits, "
              f"{stats['cache_stats']['misses']} misses")
    else:
        print("\n[Test 4] Batch Processor - SKIPPED (sentence-transformers not installed)")
    
    print("\n" + "=" * 60)
    print("All available tests completed!")
    print("=" * 60)
