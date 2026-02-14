import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request  # noqa: E402

from mem_db.database import DatabaseManager  # noqa: E402
from services.dependencies import (
    get_database_manager_strict_dep,
    get_vector_store_strict_dep,
    get_knowledge_manager_strict_dep,
)
from services.search_service import SearchService
from utils.models import SearchQuery, SearchResponse, SearchSuggestionResponse  # noqa: E402

router = APIRouter()
logger = logging.getLogger(__name__)


# Dependency Injection (strict container-backed)
from services.dependencies import (
    get_database_manager_strict_dep,
    get_vector_store_strict_dep,
    get_knowledge_manager_strict_dep,
)

async def get_search_service(request: Request) -> SearchService:
    """Strict DI-backed dependency to get SearchService instance."""
    db_manager = await get_database_manager_strict_dep(request)
    vector_store = await get_vector_store_strict_dep(request)
    knowledge_graph = await get_knowledge_manager_strict_dep(request)

    return SearchService(
        db_manager=db_manager,
        vector_store=vector_store,
        knowledge_graph=knowledge_graph,
    )


@router.post("/", response_model=SearchResponse)
async def search_documents(
    search_query: SearchQuery, service: SearchService = Depends(get_search_service)
):
    """Search documents with optional filtering and pagination"""
    try:
        # Service handles logging and timing
        return await service.search(search_query)

    except Exception as e:
        logger.error(f"Error executing search: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to execute search: {str(e)}"
        )


@router.get("/suggestions", response_model=SearchSuggestionResponse)
async def get_search_suggestions(
    query: str = Query(
        ..., min_length=1, max_length=50, description="Partial search query"
    ),
    service: SearchService = Depends(get_search_service),
):
    """Get search suggestions based on partial query"""
    try:
        logger.info(f"Getting search suggestions for: '{query}'")

        # Get suggestions from service
        suggestion_data = await service.suggest(query)

        return SearchSuggestionResponse(
            suggestions=suggestion_data.get("suggestions", []),
            categories=suggestion_data.get("categories", []),
            tags=suggestion_data.get("tags", []),
        )

    except Exception as e:
        logger.error(f"Error generating search suggestions: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate search suggestions: {str(e)}"
        )
