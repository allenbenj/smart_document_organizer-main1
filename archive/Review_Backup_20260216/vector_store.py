from fastapi import APIRouter, HTTPException
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from mem_db.vector_store import get_vector_store

router = APIRouter()
logger = logging.getLogger(__name__)


class IndexPayload(BaseModel):
    content: str
    embedding: List[float]
    metadata: Optional[Dict[str, Any]] = None


class SearchPayload(BaseModel):
    embedding: List[float]
    top_k: int = 5


@router.get("/vector")
async def vector_status() -> Dict[str, Any]:
    try:
        store = get_vector_store()
        if store is None:
            return {
                "available": False,
                "initialized": False,
                "reason": "dependencies_missing",
                "degradation": {
                    "component": "vector_store",
                    "lost_features": [
                        "semantic vector search",
                        "fast similarity retrieval",
                        "vector-backed memory queries",
                    ],
                    "fits_workflow": False,
                    "suggested_actions": [
                        "Install FAISS and numpy",
                        "Ensure optional deps for UnifiedVectorStore",
                    ],
                },
            }
        state = getattr(store, "_state", "unknown")
        stats = getattr(store, "_stats", {})
        return {"available": True, "state": str(state), "stats": stats}
    except Exception as e:
        logger.error(f"Vector status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get vector status")


@router.post("/vector/init")
async def vector_init() -> Dict[str, Any]:
    try:
        store = get_vector_store()
        if store is None:
            raise HTTPException(status_code=501, detail={
                "error": "vector_store_unavailable",
                "degradation": {
                    "component": "vector_store",
                    "lost_features": ["semantic vector indexing"],
                    "fits_workflow": False,
                    "suggested_actions": ["Install FAISS and numpy"],
                },
            })
        ok = await store.initialize()
        return {"initialized": bool(ok)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vector init error: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize vector store")


@router.post("/vector/index")
async def vector_index(payload: IndexPayload) -> Dict[str, Any]:
    try:
        import numpy as np  # local import so it remains optional
        store = get_vector_store()
        if store is None:
            raise HTTPException(status_code=501, detail={
                "error": "vector_store_unavailable",
                "degradation": {
                    "component": "vector_store",
                    "lost_features": ["semantic vector search", "fast similarity"],
                    "fits_workflow": False,
                    "suggested_actions": ["Install FAISS and numpy"],
                },
            })
        if not await store.initialize():
            raise HTTPException(status_code=500, detail="Vector store not initialized")
        embedding = np.array(payload.embedding, dtype=np.float32)
        doc_id = await store.add_document(content=payload.content, embedding=embedding, metadata=payload.metadata or {})
        return {"id": doc_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vector index error: {e}")
        raise HTTPException(status_code=500, detail="Failed to index document")


@router.post("/vector/search")
async def vector_search(payload: SearchPayload) -> Dict[str, Any]:
    try:
        import numpy as np  # optional
        store = get_vector_store()
        if store is None:
            raise HTTPException(status_code=501, detail="Vector store dependencies not available")
        if not await store.initialize():
            raise HTTPException(status_code=500, detail="Vector store not initialized")

        # Use in-memory cosine similarity over stored docs (fallback approach)
        if not hasattr(store, "_documents"):
            raise HTTPException(status_code=501, detail="Search not supported by current vector store")

        query = np.array(payload.embedding, dtype=np.float32)
        if query.ndim == 1:
            query = query.reshape(1, -1)
        # Normalize for cosine
        qn = np.linalg.norm(query)
        if qn > 0:
            query = query / qn

        docs = []
        for doc_id, doc in getattr(store, "_documents", {}).items():
            emb = doc.embedding
            if emb is None:
                continue
            vec = emb if emb.ndim == 2 else emb.reshape(1, -1)
            dn = np.linalg.norm(vec)
            if dn > 0:
                vec = vec / dn
            score = float(np.dot(query, vec.T).ravel()[0])
            docs.append((doc_id, score, doc))

        docs.sort(key=lambda x: x[1], reverse=True)
        top = docs[: max(1, payload.top_k)]
        results = [
            {
                "id": d[0],
                "score": d[1],
                "metadata": getattr(d[2], "metadata", {}),
                "document_type": getattr(d[2], "document_type", "general"),
            }
            for d in top
        ]
        return {"results": results, "count": len(results)}
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=501, detail="NumPy required for search fallback")
    except Exception as e:
        logger.error(f"Vector search error: {e}")
        raise HTTPException(status_code=500, detail="Failed to search vector store")
