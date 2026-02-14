import logging
from typing import List  # noqa: E402

from fastapi import APIRouter, Depends, HTTPException, status, Request  # noqa: E402

from mem_db.database import DatabaseManager  # noqa: E402
from services.dependencies import get_database_manager_strict_dep  # noqa: E402
from utils.models import DocumentResponse, TagCreate, TagResponse  # noqa: E402

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_db_manager_dep(request: Request) -> DatabaseManager:
    return await get_database_manager_strict_dep(request)


@router.get("/tags/", response_model=List[TagResponse])
async def list_tags(db_manager: DatabaseManager = Depends(get_db_manager_dep)):
    """List all available tags"""
    try:
        tags = db_manager.get_all_tags()
        return [
            TagResponse(
                id=i, document_id=0, tag_name=t, created_at="2025-01-01T00:00:00Z"
            )
            for i, t in enumerate(tags)
        ]
    except Exception as e:
        logger.error(f"Error listing tags: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tags",
        )


@router.post(
    "/documents/{document_id}/tags",
    status_code=status.HTTP_201_CREATED,
    response_model=List[TagResponse],
)
async def add_tag_to_document(
    document_id: int,
    tags: List[TagCreate],
    db_manager: DatabaseManager = Depends(get_db_manager_dep),
):
    """Add a tag to a specific document"""
    try:
        created_tags = db_manager.add_document_tags(document_id, tags)
        return created_tags
    except Exception as e:
        logger.error(f"Error adding tag to document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add tag to document",
        )


@router.get("/documents/{document_id}/tags", response_model=List[TagResponse])
async def get_document_tags(
    document_id: int, db_manager: DatabaseManager = Depends(get_db_manager_dep)
):
    """Get all tags for a specific document"""
    try:
        tags = db_manager.get_document_tags(document_id)
        return tags
    except Exception as e:
        logger.error(f"Error retrieving tags for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document tags",
        )


@router.delete(
    "/documents/{document_id}/tags/{tag_name}", status_code=status.HTTP_200_OK
)
async def remove_tag_from_document(
    document_id: int,
    tag_name: str,
    db_manager: DatabaseManager = Depends(get_db_manager_dep),
):
    """Remove a tag from a specific document"""
    try:
        success = db_manager.delete_document_tag(document_id, tag_name)
        if not success:
            raise HTTPException(status_code=404, detail="Tag not found on document")
        return {
            "message": f"Tag {tag_name} removed from document {document_id} successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing tag from document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove tag from document",
        )


@router.get("/tags/{tag_name}/documents", response_model=List[DocumentResponse])
async def get_documents_by_tag(
    tag_name: str,
    limit: int = 20,
    offset: int = 0,
    db_manager: DatabaseManager = Depends(get_db_manager_dep),
):
    """Get all documents with a specific tag"""
    try:
        documents, _ = db_manager.get_documents_by_tag(tag_name, limit, offset)
        return documents
    except Exception as e:
        logger.error(f"Error retrieving documents for tag {tag_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents for tag",
        )
