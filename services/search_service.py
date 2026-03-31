"""
Search Service
==============
Unifies search capabilities: keyword, vector, and knowledge graph search.
"""
import logging
import time
from typing import Dict, Any, List, Optional

from utils.models import SearchQuery, SearchResponse, DocumentResponse

logger = logging.getLogger(__name__)

class SearchService:
    """
    Unified search service.
    Orchestrates search across Database (metadata/keyword), Vector Store (semantic), 
    and Knowledge Graph (relational).
    """
    def __init__(self, db_manager, vector_store=None, knowledge_graph=None):
        self.db_manager = db_manager
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph

    async def search(self, query: SearchQuery) -> SearchResponse:
        """
        Perform a unified search across all indices.
        Merges keyword (DB) results and vector (semantic) results by score.
        """
        start_time = time.time()
        logger.info(
            f"Searching: query='{query.query}', category={query.category}"
        )

        try:
            # 1. Primary Search (Database/Keyword)
            documents, total_count = self.db_manager.search_documents(query)

            # 2. Vector Search (Hybrid Merge)
            if self.vector_store and query.query and len(query.query) > 3:
                vector_docs = await self._vector_search(query)
                if vector_docs:
                    documents, total_count = self._merge_results(
                        keyword_docs=documents,
                        vector_docs=vector_docs,
                        limit=query.limit or 20,
                    )

            execution_time = time.time() - start_time

            # Build filters dict for response
            filters: Dict[str, Any] = {}
            if query.category:
                filters["category"] = query.category
            if query.file_type:
                filters["file_type"] = query.file_type
            if query.tags:
                filters["tags"] = query.tags

            return SearchResponse(
                documents=documents,
                total_count=total_count,
                query=query.query,
                filters=filters,
                execution_time=execution_time,
            )
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise e

    async def _vector_search(
        self, query: SearchQuery
    ) -> List[DocumentResponse]:
        """Run vector similarity search and convert results to DocumentResponse."""
        try:
            query_embedding = await self._get_query_embedding(query.query)
            if query_embedding is None:
                return []

            results = await self.vector_store.search(
                query_embedding=query_embedding,
                k=query.limit or 20,
            )

            vector_docs: List[DocumentResponse] = []
            for result in results:
                doc = result.document
                metadata = getattr(doc, "metadata", {}) or {}
                try:
                    vector_docs.append(DocumentResponse(
                        id=metadata.get("id", 0),
                        file_name=metadata.get("file_name", getattr(doc, "doc_id", "unknown")),
                        file_type=metadata.get("file_type", "txt"),
                        category=metadata.get("category", "uncategorized"),
                        file_path=metadata.get("file_path"),
                        primary_purpose=metadata.get("primary_purpose"),
                        created_at=metadata.get("created_at", "1970-01-01T00:00:00"),
                    ))
                except Exception:
                    continue

            return vector_docs

        except Exception as e:
            logger.warning(f"Vector search failed (falling back to keyword only): {e}")
            return []

    async def _get_query_embedding(self, text: str):
        """Get embedding for query text. Returns numpy array or None."""
        try:
            # Try using the vector store's own embedding capability
            if hasattr(self.vector_store, "embed_text"):
                return await self.vector_store.embed_text(text)

            # Try sentence-transformers if available
            from sentence_transformers import SentenceTransformer
            import numpy as np
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding
        except ImportError:
            logger.debug("sentence-transformers not available for query embedding")
            return None
        except Exception as e:
            logger.warning(f"Failed to generate query embedding: {e}")
            return None

    @staticmethod
    def _merge_results(
        keyword_docs: List[DocumentResponse],
        vector_docs: List[DocumentResponse],
        limit: int = 20,
    ) -> tuple:
        """Merge keyword and vector results, deduplicating by document id.

        Strategy: keyword results get a base score by rank position,
        vector results get a base score by rank position, then results
        are sorted by combined score. Documents appearing in both lists
        get a bonus.
        """
        scored: Dict[int, Dict[str, Any]] = {}

        # Score keyword results (higher rank = higher score)
        for rank, doc in enumerate(keyword_docs):
            score = 1.0 / (rank + 1)  # reciprocal rank
            scored[doc.id] = {"doc": doc, "keyword_score": score, "vector_score": 0.0}

        # Score vector results and merge
        for rank, doc in enumerate(vector_docs):
            score = 1.0 / (rank + 1)
            if doc.id in scored:
                # Boost: document found by both keyword and vector
                scored[doc.id]["vector_score"] = score
            else:
                scored[doc.id] = {"doc": doc, "keyword_score": 0.0, "vector_score": score}

        # Sort by combined score (keyword weight 0.6 + vector weight 0.4)
        ranked = sorted(
            scored.values(),
            key=lambda x: x["keyword_score"] * 0.6 + x["vector_score"] * 0.4,
            reverse=True,
        )

        merged_docs = [entry["doc"] for entry in ranked[:limit]]
        return merged_docs, len(scored)

    async def suggest(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """
        Provide search suggestions based on query prefix.
        Delegate to DB manager which implements the suggestion logic.
        """
        if self.db_manager:
            return self.db_manager.get_search_suggestions(query)
        return {"suggestions": [], "categories": [], "tags": []}
