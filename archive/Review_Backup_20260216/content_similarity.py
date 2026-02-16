"""
Content Similarity and Clustering Module

This module implements:
- Document embedding generation (using sentence transformers)
- Semantic similarity calculation
- Document clustering
- Topic extraction and modeling
- Content-based grouping

Uses sentence-transformers for embeddings and scikit-learn for clustering.
"""

import logging
import numpy as np
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import sqlite3

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.info("sentence-transformers not available. Install with: pip install sentence-transformers")

try:
    from sklearn.cluster import DBSCAN, KMeans
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.info("scikit-learn not available. Install with: pip install scikit-learn")

try:
    from sklearn.decomposition import LatentDirichletAllocation
    from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
    TOPIC_MODELING_AVAILABLE = True
except ImportError:
    TOPIC_MODELING_AVAILABLE = False


@dataclass
class DocumentEmbedding:
    """A document's embedding vector"""
    embedding_id: str
    file_id: str
    embedding_model: str
    embedding_vector: np.ndarray
    created_timestamp: str


@dataclass
class SimilarityCluster:
    """A cluster of similar documents"""
    cluster_id: str
    cluster_name: str
    cluster_type: str
    file_ids: List[str]
    avg_similarity: float
    centroid_embedding: Optional[np.ndarray] = None


class ContentSimilarityEngine:
    """
    Engine for calculating content similarity and clustering documents.
    
    Features:
    - Generate embeddings for documents
    - Calculate semantic similarity
    - Cluster similar documents
    - Extract topics
    - Group documents by content
    """
    
    def __init__(self, db_conn: sqlite3.Connection, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize similarity engine.
        
        Args:
            db_conn: Database connection
            model_name: Sentence transformer model to use
        """
        self.conn = db_conn
        self.model_name = model_name
        self.model = None
        self.embeddings_generated = 0
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.model = SentenceTransformer(model_name)
                logger.info(f"Loaded sentence transformer model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load model {model_name}: {e}")
        else:
            logger.warning("Sentence transformers not available. Similarity features disabled.")
    
    def clear_memory_cache(self):
        """Clear any cached data to free memory"""
        import gc
        gc.collect()
        
        # Clear any cached embeddings in the model if possible
        if self.model and hasattr(self.model, '_cache'):
            try:
                self.model._cache.clear()
            except:
                pass
        
        logger.debug("Memory cache cleared")
    
    def generate_embedding(self, text: str, file_id: str) -> Optional[DocumentEmbedding]:
        """
        Generate embedding for a document.
        
        Args:
            text: Document text content
            file_id: File identifier
            
        Returns:
            DocumentEmbedding or None
        """
        if not self.model:
            logger.warning("Model not loaded, cannot generate embedding")
            return None
        
        if not text or len(text.strip()) < 10:
            logger.debug(f"Text too short for {file_id}, skipping embedding")
            return None
        
        try:
            # Truncate very long texts
            max_length = 10000
            if len(text) > max_length:
                text = text[:max_length]
            
            # Generate embedding
            vector = self.model.encode(text, convert_to_numpy=True)
            
            # Track embeddings generated and clear cache periodically
            self.embeddings_generated += 1
            if self.embeddings_generated % 50 == 0:
                self.clear_memory_cache()
                logger.debug(f"Generated {self.embeddings_generated} embeddings, cleared cache")
            
            embedding_id = hashlib.md5(f"{file_id}_{self.model_name}".encode()).hexdigest()
            
            return DocumentEmbedding(
                embedding_id=embedding_id,
                file_id=file_id,
                embedding_model=self.model_name,
                embedding_vector=vector,
                created_timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"Failed to generate embedding for {file_id}: {e}")
            return None
    
    def store_embedding(self, embedding: DocumentEmbedding):
        """Store embedding in database"""
        cursor = self.conn.cursor()
        
        # Serialize numpy array
        vector_bytes = embedding.embedding_vector.tobytes()
        
        cursor.execute("""
            INSERT OR REPLACE INTO document_embeddings (
                embedding_id, file_id, embedding_model, embedding_vector,
                embedding_dimension, created_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            embedding.embedding_id,
            embedding.file_id,
            embedding.embedding_model,
            vector_bytes,
            len(embedding.embedding_vector),
            embedding.created_timestamp
        ))
        
        self.conn.commit()
        logger.debug(f"Stored embedding for {embedding.file_id}")
    
    def get_embedding(self, file_id: str) -> Optional[np.ndarray]:
        """Retrieve embedding for a file"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT embedding_vector, embedding_dimension
            FROM document_embeddings
            WHERE file_id = ? AND embedding_model = ?
        """, (file_id, self.model_name))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        # Deserialize numpy array
        vector_bytes = row['embedding_vector']
        dimension = row['embedding_dimension']
        
        return np.frombuffer(vector_bytes, dtype=np.float32).reshape(dimension)
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts.
        
        Args:
            text1: First document text
            text2: Second document text
            
        Returns:
            Similarity score (0-1)
        """
        if not self.model:
            # Fallback to simple word overlap
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0.0
            intersection = words1 & words2
            union = words1 | words2
            return len(intersection) / len(union) if union else 0.0
        
        try:
            # Generate embeddings
            embeddings = self.model.encode([text1, text2], convert_to_numpy=True)
            
            # Calculate cosine similarity
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            
            return float(similarity)
        except Exception as e:
            logger.error(f"Failed to calculate similarity: {e}")
            return 0.0
    
    def find_similar_documents(
        self,
        file_id: str,
        threshold: float = 0.7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find documents similar to a given file.
        
        Args:
            file_id: File to find similar documents for
            threshold: Minimum similarity score
            limit: Maximum number of results
            
        Returns:
            List of similar documents with scores
        """
        # Get embedding for target file
        target_embedding = self.get_embedding(file_id)
        if target_embedding is None:
            logger.warning(f"No embedding found for {file_id}")
            return []
        
        # Get all other embeddings
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT file_id, embedding_vector, embedding_dimension
            FROM document_embeddings
            WHERE file_id != ? AND embedding_model = ?
        """, (file_id, self.model_name))
        
        similar_docs = []
        
        for row in cursor.fetchall():
            other_file_id = row['file_id']
            vector_bytes = row['embedding_vector']
            dimension = row['embedding_dimension']
            
            other_embedding = np.frombuffer(vector_bytes, dtype=np.float32).reshape(dimension)
            
            # Calculate similarity
            similarity = cosine_similarity([target_embedding], [other_embedding])[0][0]
            
            if similarity >= threshold:
                similar_docs.append({
                    'file_id': other_file_id,
                    'similarity_score': float(similarity)
                })
        
        # Sort by similarity and limit
        similar_docs.sort(key=lambda x: x['similarity_score'], reverse=True)
        return similar_docs[:limit]
    
    def cluster_documents(
        self,
        file_ids: List[str],
        method: str = "dbscan",
        n_clusters: Optional[int] = None
    ) -> List[SimilarityCluster]:
        """
        Cluster documents by semantic similarity.
        
        Args:
            file_ids: List of file IDs to cluster
            method: Clustering method ("dbscan" or "kmeans")
            n_clusters: Number of clusters (for kmeans)
            
        Returns:
            List of clusters
        """
        if not SKLEARN_AVAILABLE:
            logger.error("scikit-learn not available, cannot cluster")
            return []
        
        # Collect embeddings
        embeddings = []
        valid_file_ids = []
        
        for file_id in file_ids:
            emb = self.get_embedding(file_id)
            if emb is not None:
                embeddings.append(emb)
                valid_file_ids.append(file_id)
        
        if len(embeddings) < 2:
            logger.warning("Not enough embeddings to cluster")
            return []
        
        embeddings_matrix = np.array(embeddings)
        
        # Cluster
        if method == "dbscan":
            clusterer = DBSCAN(eps=0.3, min_samples=2, metric='cosine')
            labels = clusterer.fit_predict(embeddings_matrix)
        elif method == "kmeans":
            if n_clusters is None:
                n_clusters = min(5, len(embeddings) // 2)
            clusterer = KMeans(n_clusters=n_clusters, random_state=42)
            labels = clusterer.fit_predict(embeddings_matrix)
        else:
            logger.error(f"Unknown clustering method: {method}")
            return []
        
        # Group into clusters
        clusters_dict = {}
        for file_id, label in zip(valid_file_ids, labels):
            if label == -1:  # Noise in DBSCAN
                continue
            if label not in clusters_dict:
                clusters_dict[label] = []
            clusters_dict[label].append(file_id)
        
        # Create cluster objects
        clusters = []
        for cluster_id, members in clusters_dict.items():
            if len(members) < 2:
                continue
            
            # Calculate centroid
            member_embeddings = [embeddings_matrix[valid_file_ids.index(fid)] for fid in members]
            centroid = np.mean(member_embeddings, axis=0)
            
            # Calculate avg similarity to centroid
            similarities = [cosine_similarity([emb], [centroid])[0][0] for emb in member_embeddings]
            avg_sim = float(np.mean(similarities))
            
            cluster = SimilarityCluster(
                cluster_id=f"cluster_{cluster_id}_{datetime.now().timestamp()}",
                cluster_name=f"Cluster {cluster_id + 1}",
                cluster_type="semantic",
                file_ids=members,
                avg_similarity=avg_sim,
                centroid_embedding=centroid
            )
            clusters.append(cluster)
        
        # Store clusters in database
        for cluster in clusters:
            self._store_cluster(cluster)
        
        logger.info(f"Created {len(clusters)} clusters from {len(file_ids)} documents")
        return clusters
    
    def _store_cluster(self, cluster: SimilarityCluster):
        """Store cluster in database"""
        cursor = self.conn.cursor()
        
        # Store cluster
        centroid_bytes = cluster.centroid_embedding.tobytes() if cluster.centroid_embedding is not None else None
        
        cursor.execute("""
            INSERT OR REPLACE INTO similarity_clusters (
                cluster_id, cluster_name, cluster_type, centroid_embedding,
                file_count, avg_similarity, created_timestamp, updated_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cluster.cluster_id,
            cluster.cluster_name,
            cluster.cluster_type,
            centroid_bytes,
            len(cluster.file_ids),
            cluster.avg_similarity,
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        # Store cluster members
        for file_id in cluster.file_ids:
            membership_id = hashlib.md5(f"{cluster.cluster_id}_{file_id}".encode()).hexdigest()
            cursor.execute("""
                INSERT OR REPLACE INTO cluster_members (
                    membership_id, cluster_id, file_id, similarity_score,
                    distance_to_centroid, added_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                membership_id,
                cluster.cluster_id,
                file_id,
                cluster.avg_similarity,
                0.0,  # Could calculate actual distance
                datetime.now().isoformat()
            ))
        
        self.conn.commit()
    
    def extract_topics(
        self,
        documents: List[Tuple[str, str]],  # [(file_id, text), ...]
        n_topics: int = 5,
        n_keywords: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Extract topics from a collection of documents using LDA.
        
        Args:
            documents: List of (file_id, text) tuples
            n_topics: Number of topics to extract
            n_keywords: Number of keywords per topic
            
        Returns:
            List of topics with keywords and document assignments
        """
        if not TOPIC_MODELING_AVAILABLE:
            logger.error("Topic modeling dependencies not available")
            return []
        
        if len(documents) < n_topics:
            logger.warning(f"Not enough documents ({len(documents)}) for {n_topics} topics")
            return []
        
        try:
            # Extract texts
            file_ids = [fid for fid, _ in documents]
            texts = [text for _, text in documents]
            
            # Vectorize
            vectorizer = CountVectorizer(
                max_df=0.85,
                min_df=2,
                max_features=1000,
                stop_words='english'
            )
            doc_term_matrix = vectorizer.fit_transform(texts)
            
            # LDA
            lda = LatentDirichletAllocation(
                n_components=n_topics,
                random_state=42,
                max_iter=20
            )
            doc_topics = lda.fit_transform(doc_term_matrix)
            
            # Extract topic keywords
            feature_names = vectorizer.get_feature_names_out()
            topics = []
            
            for topic_idx, topic in enumerate(lda.components_):
                top_indices = topic.argsort()[-n_keywords:][::-1]
                keywords = [feature_names[i] for i in top_indices]
                
                topic_id = f"topic_{topic_idx}_{datetime.now().timestamp()}"
                topic_data = {
                    'topic_id': topic_id,
                    'topic_name': f"Topic {topic_idx + 1}: {', '.join(keywords[:3])}",
                    'keywords': keywords,
                    'documents': []
                }
                
                # Find documents strongly associated with this topic
                for doc_idx, doc_topic_dist in enumerate(doc_topics):
                    relevance = doc_topic_dist[topic_idx]
                    if relevance > 0.3:  # Threshold for relevance
                        topic_data['documents'].append({
                            'file_id': file_ids[doc_idx],
                            'relevance_score': float(relevance)
                        })
                
                topics.append(topic_data)
                
                # Store in database
                self._store_topic(topic_data)
            
            logger.info(f"Extracted {len(topics)} topics from {len(documents)} documents")
            return topics
            
        except Exception as e:
            logger.error(f"Topic extraction failed: {e}")
            return []
    
    def _store_topic(self, topic_data: Dict[str, Any]):
        """Store topic in database"""
        cursor = self.conn.cursor()
        
        # Store topic
        cursor.execute("""
            INSERT OR REPLACE INTO topics (
                topic_id, topic_name, topic_keywords, topic_description,
                document_count, created_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            topic_data['topic_id'],
            topic_data['topic_name'],
            json.dumps(topic_data['keywords']),
            f"Topic with keywords: {', '.join(topic_data['keywords'][:5])}",
            len(topic_data['documents']),
            datetime.now().isoformat()
        ))
        
        # Store document-topic associations
        for doc in topic_data['documents']:
            doc_topic_id = hashlib.md5(
                f"{doc['file_id']}_{topic_data['topic_id']}".encode()
            ).hexdigest()
            
            cursor.execute("""
                INSERT OR REPLACE INTO document_topics (
                    doc_topic_id, file_id, topic_id, relevance_score,
                    extraction_method, created_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                doc_topic_id,
                doc['file_id'],
                topic_data['topic_id'],
                doc['relevance_score'],
                'lda',
                datetime.now().isoformat()
            ))
        
        self.conn.commit()


__all__ = [
    'ContentSimilarityEngine',
    'DocumentEmbedding',
    'SimilarityCluster',
]
