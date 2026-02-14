"""
Document Service
================
Handles document lifecycle: upload, processing, indexing, and storage.
"""
import logging
import os
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from fastapi import UploadFile, HTTPException

from utils.models import DocumentCreate, DocumentResponse, DocumentUpdate
from agents.processors.simple_document_processor import SimpleDocumentProcessor

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

# Global for sentence transformer cache
_EMBED_MODEL = None
_EMBED_MODEL_NAME = None

logger = logging.getLogger(__name__)

class DocumentService:
    """
    Orchestrates document operations.
    """
    def __init__(self, db_manager, vector_store, agent_manager, config_manager=None):
        self.db_manager = db_manager
        self.vector_store = vector_store
        self.agent_manager = agent_manager
        self._config_manager = config_manager  # Optional, for indexing config
        self.simple_processor = SimpleDocumentProcessor()

    async def upload_document(self, file: UploadFile) -> Dict[str, Any]:
        """
        Upload and process a document file.
        Returns a dict with success details.
        """
        logger.info(f"Uploading file: {file.filename}")

        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        # Process the uploaded file
        processing_result = await self._process_with_advanced(file)

        if not processing_result.get("success", False):
            error_msg = processing_result.get('error', 'Unknown error')
            logger.error(f"Document processing failed: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Document processing failed: {error_msg}",
            )

        # Create document record in database
        document_data = DocumentCreate(
            file_name=processing_result["filename"],
            file_path=f"uploads/{processing_result['filename']}",
            file_type=processing_result["file_type"].lstrip("."),
            category=processing_result["category"],
            primary_purpose=f"Processed via {processing_result['processing_method']}",
            content_text=processing_result["content"],
            content_type=processing_result.get("mime_type", "text/plain"),
        )

        try:
            created_document = self.db_manager.create_document(document_data)
        except Exception as e:
            logger.error(f"Error creating document record: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")

        # Index content
        try:
            meta = {
                "document_id": created_document.id,
                "file_name": created_document.file_name,
                "category": created_document.category,
                "file_type": created_document.file_type,
            }
            await self._maybe_index_document(processing_result["content"] or "", meta)
        except Exception:
            pass

        logger.info(
            f"Document {file.filename} processed and saved with ID: {created_document.id}"
        )

        return {
            "success": True,
            "message": f"File {file.filename} uploaded and processed successfully",
            "document_id": created_document.id,
            "filename": processing_result["filename"],
            "file_type": processing_result["file_type"],
            "category": processing_result["category"],
            "content_preview": (
                processing_result["content"][:200] + "..."
                if len(processing_result["content"]) > 200
                else processing_result["content"]
            ),
            "processing_info": {
                "method": processing_result["processing_method"],
                "confidence": processing_result["confidence"],
                "processed_at": processing_result["processed_at"],
            },
        }

    async def upload_multiple_documents(self, files: List[UploadFile]) -> List[Dict[str, Any]]:
        """
        Upload and process multiple document files.
        """
        logger.info(f"Uploading {len(files)} files")
        
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        results = []
        for file in files:
            try:
                result = await self.upload_document(file)
                results.append(result)
            except Exception as e:
                logger.error(f"Error uploading file {file.filename}: {e}")
                results.append({
                    "success": False, 
                    "filename": file.filename, 
                    "error": str(e)
                })
        return results

    async def create_document(self, document: DocumentCreate) -> DocumentResponse:
        """Create a new document manually."""
        try:
            logger.info(f"Creating document: {document.file_name}")
            created_doc = self.db_manager.create_document(document)
            
            # Fire-and-forget indexing
            try:
                content = document.content_text or ""
                meta = {
                    "document_id": created_doc.id,
                    "file_name": created_doc.file_name,
                    "category": created_doc.category,
                    "file_type": created_doc.file_type,
                }
                await self._maybe_index_document(content, meta)
            except Exception:
                pass
            return created_doc
        except Exception as e:
            logger.error(f"Error creating document: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")

    async def get_document(self, document_id: int) -> DocumentResponse:
        """Get a document by ID"""
        try:
            document = self.db_manager.get_document(document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            return document
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving document {document_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to retrieve document: {str(e)}")

    async def list_documents(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        category: Optional[str] = None, 
        file_type: Optional[str] = None
    ) -> List[DocumentResponse]:
        """List documents"""
        try:
            documents, _total = self.db_manager.list_documents(
                offset=skip, limit=limit, category=category, file_type=file_type
            )
            return documents
        except Exception as e:
            logger.error(f"Error listing documents: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

    async def update_document(self, document_id: int, document_update: DocumentUpdate) -> DocumentResponse:
        """Update a document"""
        try:
            logger.info(f"Updating document: {document_id}")
            updated_doc = self.db_manager.update_document(document_id, document_update)
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
                    await self._maybe_index_document(document_update.content_text, meta)
            except Exception:
                pass
            return updated_doc
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating document {document_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to update document: {str(e)}")

    async def delete_document(self, document_id: int) -> bool:
        """Delete a document"""
        try:
            logger.info(f"Deleting document: {document_id}")
            success = self.db_manager.delete_document(document_id)
            if not success:
                raise HTTPException(status_code=404, detail="Document not found")
            return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

    # Internal / Helper methods
    
    async def _process_with_advanced(self, file: UploadFile) -> dict:
        tmp_file_path = None
        try:
            # Save to temp file
            filename = file.filename if file.filename is not None else "tempfile"
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(filename).suffix
            ) as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                tmp_file_path = tmp_file.name
            
            # Try production agent manager
            try:
                res = await self.agent_manager.process_document(tmp_file_path)
                if not res or not res.success:
                    detail = {
                        "error": "advanced_processing_failed",
                        "agent_type": getattr(res, "agent_type", None) if res else None,
                        "message": getattr(res, "error", None) if res else "no result",
                        "processing_time": (
                            getattr(res, "processing_time", None) if res else None
                        ),
                        "metadata": getattr(res, "metadata", {}) if res else {},
                    }
                    return {
                        "success": False,
                        "filename": file.filename,
                        **detail
                    }

                data = res.data or {}
                content_text = data.get("content") or data.get("text") or ""
                category = (
                    (data.get("metadata", {}) or {}).get("category")
                    or data.get("document_format")
                    or "document"
                )
                
                return {
                    "success": True,
                    "filename": file.filename,
                    "file_size": len(content),
                    "file_type": Path(file.filename or "").suffix.lower(),
                    "mime_type": file.content_type,
                    "content": content_text,
                    "category": str(category),
                    "processing_method": data.get(
                        "processing_method", "advanced_document_processor"
                    ),
                    "confidence": (
                        float(data.get("confidence", 0.8))
                        if isinstance(data.get("confidence", 0.8), (int, float))
                        else 0.8
                    ),
                    "processed_at": datetime.now().isoformat(),
                }
            except Exception as e:
                logger.error(f"Advanced processor exception: {e}")
                return {
                    "success": False,
                    "filename": file.filename,
                    "error": "advanced_processor_exception",
                    "message": str(e)
                }

        finally:
            try:
                if tmp_file_path and os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
            except Exception:
                pass

    async def _maybe_index_document(self, content: str, metadata: dict) -> None:
        """Best-effort indexing into vector store if available."""
        try:
            if self.vector_store is None:
                return
            ok = await self.vector_store.initialize()
            if not ok or not NUMPY_AVAILABLE:
                return
                
            # Try to use sentence-transformers if configured and available
            embedding = None
            try:
                cfg = self._config_manager
                use_st = False
                model_name = "sentence-transformers/all-MiniLM-L6-v2"
                if cfg is not None:
                    try:
                        # Assuming config manager interface similar to what was implied
                        use_st = bool(
                            getattr(cfg, "get_bool", lambda *a, **k: False)(
                                "vector.use_sentence_transformers", False
                            )
                        )
                        model_name = getattr(cfg, "get_str", lambda *a, **k: model_name)(
                            "vector.embedding_model", model_name
                        )
                    except Exception:
                        pass
                else:
                    use_st = os.getenv("VECTOR_USE_ST", "0").lower() in {
                        "1", "true", "yes", "on",
                    }
                    model_name = os.getenv("VECTOR_EMBEDDING_MODEL", model_name)
                    
                if use_st:
                    global _EMBED_MODEL, _EMBED_MODEL_NAME
                    if _EMBED_MODEL is None or _EMBED_MODEL_NAME != model_name:
                        from sentence_transformers import SentenceTransformer
                        _EMBED_MODEL = SentenceTransformer(model_name)
                        _EMBED_MODEL_NAME = model_name
                    vec = _EMBED_MODEL.encode([content], normalize_embeddings=True)
                    embedding = np.array(vec[0], dtype=np.float32).reshape(1, -1)
            except Exception:
                embedding = None
                
            if embedding is None:
                # Create a deterministic pseudo-embedding from content
                dim = getattr(self.vector_store, "dimension", 384)
                seed = abs(hash(content)) % (2**32)
                rng = np.random.default_rng(seed)
                embedding = rng.standard_normal(dim, dtype=np.float32)
                
            await self.vector_store.add_document(
                content=content, embedding=embedding, metadata=metadata
            )
        except Exception:
            # Do not block API on indexing errors
            logger.debug("Vector indexing skipped or failed", exc_info=False)
