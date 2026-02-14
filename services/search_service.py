"""
Search Service
==============
Unifies search capabilities: keyword, vector, and knowledge graph search.
"""
import logging
import time
from typing import Dict, Any

from utils.models import SearchQuery, SearchResponse

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
        Current implementation focuses on DB metadata/keyword search, 
        but is structured to mix in vector/graph results.
        """
        start_time = time.time()
        logger.info(
            f"Searching: query='{query.query}', category={query.category}"
        )

        try:
            # 1. Primary Search (Database/Keyword for now)
            # In SVC-5/Future, we will add parallel calls to vector_store.search()
            documents, total_count = self.db_manager.search_documents(query)
            
            # 2. Vector Search (Hybrid Logic Placeholder)
            if self.vector_store and query.query and len(query.query) > 3:
                # TODO: Implement vector hybrid merge
                pass

            execution_time = time.time() - start_time

            # Build filters dict for response
            filters = {}
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

    async def suggest(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """
        Provide search suggestions based on query prefix.
        Delegate to DB manager which implements the suggestion logic.
        """
        if self.db_manager:
            return self.db_manager.get_search_suggestions(query)
        return {"suggestions": [], "categories": [], "tags": []}
