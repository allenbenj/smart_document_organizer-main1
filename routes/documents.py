from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from services.dependencies import (
    get_database_manager_strict_dep,
    get_vector_store_strict_dep,
    get_agent_manager_strict_dep,
    get_config_manager_dep,
)
from services.document_service import DocumentService
from utils.models import DocumentCreate, DocumentResponse, DocumentUpdate

router = APIRouter()

# Dependency Injection (strict container-backed)

async def get_document_service(request: Request) -> DocumentService:
    """Strict DI-backed dependency to get DocumentService instance."""
    config_manager = await get_config_manager_dep(request)
    db_manager = await get_database_manager_strict_dep(request)
    vector_store = await get_vector_store_strict_dep(request)
    agent_manager = await get_agent_manager_strict_dep(request)

    return DocumentService(
        db_manager=db_manager,
        vector_store=vector_store,
        agent_manager=agent_manager,
        config_manager=config_manager,
    )

@router.post("/", response_model=DocumentResponse)
async def create_document(
    document: DocumentCreate,
    service: DocumentService = Depends(get_document_service)
):
    """Create a new document"""
    return await service.create_document(document)

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    service: DocumentService = Depends(get_document_service)
):
    """Get a document by ID"""
    return await service.get_document(document_id)

@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of documents to return"
    ),
    category: Optional[str] = Query(None, description="Filter by category"),
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    service: DocumentService = Depends(get_document_service)
):
    """List documents with optional filtering and pagination"""
    return await service.list_documents(skip=skip, limit=limit, category=category, file_type=file_type)

@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int, 
    document_update: DocumentUpdate,
    service: DocumentService = Depends(get_document_service)
):
    """Update a document"""
    return await service.update_document(document_id, document_update)

@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    service: DocumentService = Depends(get_document_service)
):
    """Delete a document"""
    await service.delete_document(document_id)
    return {"message": f"Document {document_id} deleted successfully"}

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service)
):
    """Upload and process a document file"""
    return await service.upload_document(file)

@router.post("/upload-multiple")
async def upload_multiple_documents(
    files: List[UploadFile] = File(...),
    service: DocumentService = Depends(get_document_service)
):
    """Upload and process multiple document files (folder upload)"""
    return await service.upload_multiple_documents(files)
