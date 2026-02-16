from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi import Request
from typing import List, Optional
import logging
import tempfile
import os
from pathlib import Path
from datetime import datetime
from utils.models import DocumentCreate, DocumentUpdate, DocumentResponse
from mem_db.database import get_database_manager
from agents.processors.document_processor import DocumentProcessor
from core.container.service_container_impl import ProductionServiceContainer
from agents import get_agent_manager
from mem_db.vector_store import get_vector_store

try:
    import numpy as np  # optional
    NUMPY_AVAILABLE = True
except Exception:
    NUMPY_AVAILABLE = False

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize database manager
db_manager = get_database_manager()

# Document processor integration (simplified for FastAPI backend)
class SimpleDocumentProcessor:
    """Simplified document processor for FastAPI backend integration"""
    
    def __init__(self):
        self.supported_extensions = {
            '.pdf', '.docx', '.doc', '.txt', '.html', '.htm', '.rtf', '.md',
            '.xlsx', '.xls', '.csv', '.pptx', '.ppt',
            '.png', '.jpg', '.jpeg', '.tiff', '.bmp'
        }
                
        async def process(self, file: UploadFile) -> dict:
            """Process a document file and extract content and metadata"""
            tmp_file_path = None
            try:
                # Save to temp file
                filename = file.filename if file.filename is not None else "tempfile"
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp_file:
                    content = await file.read()
                    tmp_file.write(content)
                    tmp_file_path = tmp_file.name
                    file_size = len(content)
                    file_extension = Path(file.filename or "").suffix.lower()
                    if file_extension not in self.supported_extensions:
                        raise Exception(f"Unsupported file type: {file_extension}")
                    extracted_content = await self._extract_content(tmp_file_path, file_extension, content)
                    category = self._determine_category(file_extension, extracted_content)
                    return {
                        'success': True,
                        'filename': file.filename,
                        'file_size': file_size,
                        'file_type': file_extension,
                        'mime_type': file.content_type,
                        'content': extracted_content,
                        'category': category,
                        'processing_method': 'simple_extraction',
                        'confidence': 0.8,
                        'processed_at': datetime.now().isoformat()
                    }
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {e}")
                return {
                    'success': False,
                    'filename': file.filename,
                    'error': str(e),
                    'processing_method': 'failed',
                    'confidence': 0.0
                }
            finally:
                # Clean up temporary file
                if tmp_file_path and os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
    
    async def _extract_content(self, file_path: str, file_extension: str, content_bytes: bytes) -> str:
        """Extract text content from file based on type"""
        try:
            if file_extension in ['.txt', '.md', '.html', '.htm']:
                # Try different encodings for text files
                for encoding in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        return content_bytes.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                return content_bytes.decode('utf-8', errors='ignore')
            
            elif file_extension == '.pdf':
                return await self._extract_pdf_content(file_path)
            
            elif file_extension in ['.docx', '.doc']:
                return await self._extract_docx_content(file_path)
            
            elif file_extension in ['.xlsx', '.xls', '.csv']:
                return await self._extract_spreadsheet_content(file_path, file_extension)
            
            else:
                return f"Binary file: {Path(file_path).name} (content extraction not supported)"
                
        except Exception as e:
            logger.warning(f"Content extraction failed for {file_path}: {e}")
            return f"File: {Path(file_path).name} (content extraction failed)"
    
    async def _extract_pdf_content(self, file_path: str) -> str:
        """Extract content from PDF file"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            content = []
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                # Use get_text() without parameters or with specific format
                content.append(f"\n--- Page {page_num + 1} ---\n{page.get_text('text')}")
            doc.close()
            return "\n".join(content).strip()
        except ImportError:
            return f"PDF file: {Path(file_path).name} (PyMuPDF not available for text extraction)"
        except Exception as e:
            return f"PDF file: {Path(file_path).name} (extraction failed: {e})"
    
    async def _extract_docx_content(self, file_path: str) -> str:
        """Extract content from DOCX file"""
        try:
            from docx import Document
            doc = Document(file_path)
            content = ""
            for paragraph in doc.paragraphs:
                content += paragraph.text + "\n"
            return content.strip()
        except ImportError:
            return f"DOCX file: {Path(file_path).name} (python-docx not available for text extraction)"
        except Exception as e:
            return f"DOCX file: {Path(file_path).name} (extraction failed: {e})"
    
    async def _extract_spreadsheet_content(self, file_path: str, file_extension: str) -> str:
        """Extract content from spreadsheet files"""
        try:
            import pandas as pd
            if file_extension == '.csv':
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            content = f"Spreadsheet with {len(df)} rows and {len(df.columns)} columns\n"
            content += f"Columns: {', '.join(df.columns)}\n\n"
            content += df.head(10).to_string()  # First 10 rows
            return content
        except ImportError:
            return f"Spreadsheet file: {Path(file_path).name} (pandas not available for data extraction)"
        except Exception as e:
            return f"Spreadsheet file: {Path(file_path).name} (extraction failed: {e})"
    
    def _determine_category(self, file_extension: str, content: str) -> str:
        """Determine document category based on file type and content"""
        # Basic categorization logic
        if file_extension in ['.pdf', '.docx', '.doc', '.txt', '.md']:
            if any(keyword in content.lower() for keyword in ['contract', 'agreement', 'legal', 'terms']):
                return 'legal'
            elif any(keyword in content.lower() for keyword in ['report', 'analysis', 'summary']):
                return 'report'
            else:
                return 'document'
        elif file_extension in ['.xlsx', '.xls', '.csv']:
            return 'spreadsheet'
        elif file_extension in ['.pptx', '.ppt']:
            return 'presentation'
        elif file_extension in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            return 'image'
        else:
            return 'other'

# Initialize document processor
async def _process_with_advanced(file: UploadFile) -> dict:
    tmp_file_path = None
    try:
        # Save to temp file
        filename = file.filename if file.filename is not None else "tempfile"
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        # Try production agent manager
        try:
            manager = get_agent_manager()
            res = await manager.process_document(tmp_file_path)
            if not res or not res.success:
                detail = {
                    "error": "advanced_processing_failed",
                    "agent_type": getattr(res, 'agent_type', None) if res else None,
                    "message": getattr(res, 'error', None) if res else "no result",
                    "processing_time": getattr(res, 'processing_time', None) if res else None,
                    "metadata": getattr(res, 'metadata', {}) if res else {},
                }
                raise HTTPException(status_code=500, detail=detail)
            data = res.data or {}
            try:
                logger.info(
                    "Advanced document processing success",
                    extra={
                        "filename": file.filename,
                        "agent_type": getattr(res, 'agent_type', None),
                        "processing_time": getattr(res, 'processing_time', None),
                        "document_format": (data.get("document_format") or (data.get("metadata", {}) or {}).get("document_format")),
                    },
                )
            except Exception:
                pass
            content_text = data.get("content") or data.get("text") or ""
            category = (data.get("metadata", {}) or {}).get("category") or data.get("document_format") or "document"
            return {
                'success': True,
                'filename': file.filename,
                'file_size': len(content),
                'file_type': Path(file.filename or "").suffix.lower(),
                'mime_type': file.content_type,
                'content': content_text,
                'category': str(category),
                'processing_method': data.get("processing_method", "advanced_document_processor"),
                'confidence': float(data.get("confidence", 0.8)) if isinstance(data.get("confidence", 0.8), (int, float)) else 0.8,
                'processed_at': datetime.now().isoformat()
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail={"error": "advanced_processor_exception", "message": str(e)})
    finally:
        try:
            if tmp_file_path and os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
        except Exception:
            pass


_EMBED_MODEL = None
_EMBED_MODEL_NAME = None


async def _maybe_index_document(request: Request, content: str, metadata: dict) -> None:
    """Best-effort indexing into vector store if available.

    Skips silently if vector store or numpy/FAISS are not available.
    """
    try:
        store = get_vector_store()
        if store is None:
            return
        ok = await store.initialize()
        if not ok or not NUMPY_AVAILABLE:
            return
        # Try to use sentence-transformers if configured and available
        embedding = None
        try:
            services = getattr(request.app.state, "services", None)
            cfg = None
            if services and hasattr(services, "get_service"):
                try:
                    cfg = await services.get_service("config_manager")
                except Exception:
                    cfg = None
            use_st = False
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            if cfg is not None:
                use_st = bool(getattr(cfg, "get_bool", lambda *a, **k: False)("vector.use_sentence_transformers", False))
                model_name = getattr(cfg, "get_str", lambda *a, **k: model_name)("vector.embedding_model", model_name)
            else:
                # Fall back to env vars
                import os
                use_st = os.getenv("VECTOR_USE_ST", "0").lower() in {"1", "true", "yes", "on"}
                model_name = os.getenv("VECTOR_EMBEDDING_MODEL", model_name)
            if use_st:
                global _EMBED_MODEL, _EMBED_MODEL_NAME
                if _EMBED_MODEL is None or _EMBED_MODEL_NAME != model_name:
                    from sentence_transformers import SentenceTransformer  # type: ignore
                    _EMBED_MODEL = SentenceTransformer(model_name)
                    _EMBED_MODEL_NAME = model_name
                vec = _EMBED_MODEL.encode([content], normalize_embeddings=True)
                import numpy as np  # Ensure numpy is imported
                embedding = np.array(vec[0], dtype=np.float32).reshape(1, -1)
        except Exception:
            embedding = None
        if embedding is None:
            # Create a deterministic pseudo-embedding from content
            dim = getattr(store, "dimension", 384)
            seed = abs(hash(content)) % (2**32)
            import numpy as np  # Ensure numpy is imported before use
            rng = np.random.default_rng(seed)
            embedding = rng.standard_normal(dim, dtype=np.float32)
        await store.add_document(content=content, embedding=embedding, metadata=metadata)
    except Exception:
        # Do not block API on indexing errors
        logger.debug("Vector indexing skipped or failed", exc_info=False)

@router.post("/", response_model=DocumentResponse)
async def create_document(request: Request, document: DocumentCreate):
    """Create a new document"""
    try:
        logger.info(f"Creating document: {document.file_name}")
        
        created_doc = db_manager.create_document(document)
        # Fire-and-forget indexing
        try:
            content = document.content_text or ""
            meta = {
                "document_id": created_doc.id,
                "file_name": created_doc.file_name,
                "category": created_doc.category,
                "file_type": created_doc.file_type,
            }
            await _maybe_index_document(request, content, meta)
        except Exception:
            pass
        return created_doc
        
    except Exception as e:
        logger.error(f"Error creating document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: int):
    """Get a document by ID"""
    try:
        logger.info(f"Retrieving document: {document_id}")
        
        document = db_manager.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve document: {str(e)}")

@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of documents to return"),
    category: Optional[str] = Query(None, description="Filter by category"),
    file_type: Optional[str] = Query(None, description="Filter by file type")
):
    """List documents with optional filtering and pagination"""
    try:
        logger.info(f"Listing documents: skip={skip}, limit={limit}, category={category}, file_type={file_type}")
        
        documents = db_manager.list_documents(offset=skip, limit=limit, category=category, file_type=file_type)
        return documents
        
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(request: Request, document_id: int, document_update: DocumentUpdate):
    """Update a document"""
    try:
        logger.info(f"Updating document: {document_id}")
        
        updated_doc = db_manager.update_document(document_id, document_update)
        if not updated_doc:
            raise HTTPException(status_code=404, detail="Document not found")
        # Index new content if provided
        try:
            if document_update.content_text:
                meta = {
                    "document_id": updated_doc.id,
                    "file_name": updated_doc.file_name,
                    "category": updated_doc.category,
                    "file_type": updated_doc.file_type,
                }
                await _maybe_index_document(request, document_update.content_text, meta)
        except Exception:
            pass
        return updated_doc
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update document: {str(e)}")

@router.delete("/{document_id}")
async def delete_document(document_id: int):
    """Delete a document"""
    try:
        logger.info(f"Deleting document: {document_id}")
        
        success = db_manager.delete_document(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"message": f"Document {document_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

@router.post("/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    """Upload and process a document file"""
    try:
        logger.info(f"Uploading file: {file.filename}")
        
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Process the uploaded file (advanced preferred, fallback to simple)
        processing_result = await _process_with_advanced(file)
        
        if not processing_result.get('success', False):
            logger.error(f"Document processing failed: {processing_result.get('error', 'Unknown error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Document processing failed: {processing_result.get('error', 'Unknown error')}"
            )
        
        # Create document record in database
        document_data = DocumentCreate(
            file_name=processing_result['filename'],
            file_path=f"uploads/{processing_result['filename']}",  # Virtual path for now
            file_type=processing_result['file_type'].lstrip('.'),  # Remove leading dot for validation
            category=processing_result['category'],
            primary_purpose=f"Processed via {processing_result['processing_method']}",
            content_text=processing_result['content'],
            content_type=processing_result.get('mime_type', 'text/plain')
        )
        
        # Save to database
        created_document = db_manager.create_document(document_data)
        # Index content
        try:
            meta = {
                "document_id": created_document.id,
                "file_name": created_document.file_name,
                "category": created_document.category,
                "file_type": created_document.file_type,
            }
            await _maybe_index_document(request, processing_result['content'] or "", meta)
        except Exception:
            pass
        
        logger.info(f"Document {file.filename} processed and saved with ID: {created_document.id}")
        
        return {
            "success": True,
            "message": f"File {file.filename} uploaded and processed successfully",
            "document_id": created_document.id,
            "filename": processing_result['filename'],
            "file_type": processing_result['file_type'],
            "category": processing_result['category'],
            "content_preview": processing_result['content'][:200] + "..." if len(processing_result['content']) > 200 else processing_result['content'],
            "processing_info": {
                "method": processing_result['processing_method'],
                "confidence": processing_result['confidence'],
                "processed_at": processing_result['processed_at']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

@router.post("/upload-multiple")
async def upload_multiple_documents(request: Request, files: List[UploadFile] = File(...)):
    """Upload and process multiple document files (folder upload)"""
    try:
        logger.info(f"Uploading {len(files)} files")
        
        if not files or len(files) == 0:
            raise HTTPException(status_code=400, detail="No files provided")
        
        results = []
        successful_uploads = 0
        failed_uploads = 0
        
        for file in files:
            try:
                # Skip empty files or directories
                if not file.filename or file.filename.endswith('/'):
                    continue
                
                logger.info(f"Processing file: {file.filename}")
                
                # Process each file (advanced preferred)
                processing_result = await _process_with_advanced(file)
                
                if processing_result.get('success', False):
                    # Create document record in database
                    document_data = DocumentCreate(
                        file_name=processing_result['filename'],
                        file_path=f"uploads/{processing_result['filename']}",
                        file_type=processing_result['file_type'].lstrip('.'),
                        category=processing_result['category'],
                        primary_purpose=f"Batch processed via {processing_result['processing_method']}",
                        content_text=processing_result['content'],
                        content_type=processing_result.get('mime_type', 'text/plain')
                    )
                    
                    created_document = db_manager.create_document(document_data)
                    successful_uploads += 1
                    try:
                        meta = {
                            "document_id": created_document.id,
                            "file_name": created_document.file_name,
                            "category": created_document.category,
                            "file_type": created_document.file_type,
                        }
                        await _maybe_index_document(request, processing_result['content'] or "", meta)
                    except Exception:
                        pass
                    
                    results.append({
                        "success": True,
                        "filename": processing_result['filename'],
                        "document_id": created_document.id,
                        "file_type": processing_result['file_type'],
                        "category": processing_result['category'],
                        "message": f"Successfully processed {file.filename}"
                    })
                    
                else:
                    failed_uploads += 1
                    results.append({
                        "success": False,
                        "filename": file.filename,
                        "error": processing_result.get('error', 'Processing failed'),
                        "message": f"Failed to process {file.filename}"
                    })
                    
            except Exception as file_error:
                failed_uploads += 1
                logger.error(f"Error processing file {file.filename}: {str(file_error)}")
                results.append({
                    "success": False,
                    "filename": file.filename,
                    "error": str(file_error),
                    "message": f"Error processing {file.filename}"
                })
        
        logger.info(f"Batch upload completed: {successful_uploads} successful, {failed_uploads} failed")
        
        return {
            "success": True,
            "message": f"Batch upload completed: {successful_uploads} successful, {failed_uploads} failed",
            "total_files": len(files),
            "successful_uploads": successful_uploads,
            "failed_uploads": failed_uploads,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process batch upload: {str(e)}")
