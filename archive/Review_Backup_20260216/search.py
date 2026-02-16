from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging
import time
from utils.models import SearchQuery, SearchResponse, SearchSuggestionResponse
from mem_db.database import get_database_manager

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize database manager
db_manager = get_database_manager()

@router.post("/", response_model=SearchResponse)
async def search_documents(search_query: SearchQuery):
    """Search documents with optional filtering and pagination"""
    try:
        start_time = time.time()
        logger.info(f"Searching documents: query='{search_query.query}', category={search_query.category}, file_type={search_query.file_type}")
        
        # Execute search using database manager
        documents, total_count = db_manager.search_documents(search_query)
        
        execution_time = time.time() - start_time
        
        # Build filters dict
        filters = {}
        if search_query.category:
            filters["category"] = search_query.category
        if search_query.file_type:
            filters["file_type"] = search_query.file_type
        if search_query.tags:
            filters["tags"] = search_query.tags
        
        return SearchResponse(
            documents=documents,
            total_count=total_count,
            query=search_query.query,
            filters=filters,
            execution_time=execution_time
        )
        
    except Exception as e:
        logger.error(f"Error executing search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to execute search: {str(e)}")

@router.get("/suggestions", response_model=SearchSuggestionResponse)
async def get_search_suggestions(
    query: str = Query(..., min_length=1, max_length=50, description="Partial search query")
):
    """Get search suggestions based on partial query"""
    try:
        logger.info(f"Getting search suggestions for: '{query}'")
        
        # Get suggestions from database manager
        suggestion_data = db_manager.get_search_suggestions(query)
        
        return SearchSuggestionResponse(
            suggestions=suggestion_data.get('suggestions', []),
            categories=suggestion_data.get('categories', []),
            tags=suggestion_data.get('tags', [])
        )
        
    except Exception as e:
        logger.error(f"Error generating search suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate search suggestions: {str(e)}")
