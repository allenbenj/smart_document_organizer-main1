import logging
from typing import Any, Dict, List, Optional  # noqa: E402

from fastapi import APIRouter, Depends, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from services.dependencies import (
    get_vector_store_dep,
    get_vector_store_strict_dep,
)  # noqa: E402

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
async def vector_status(store=Depends(get_vector_store_dep)) -> Dict[str, Any]:
    try:
        if store is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "vector_store_unavailable",
                    "required_dependencies": ["faiss", "numpy"],
                },
            )
        health = await store.health_check()
        stats = await store.get_statistics()
        return {
            "available": True,
            "state": health.get("state", "unknown"),
            "healthy": bool(health.get("healthy", False)),
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Vector status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get vector status")


@router.post("/vector/init")
async def vector_init(store=Depends(get_vector_store_strict_dep)) -> Dict[str, Any]:
    try:
        if store is None:
            raise HTTPException(
                status_code=501,
                detail={
                    "error": "vector_store_unavailable",
                    "required_dependencies": ["faiss", "numpy"],
                },
            )
        ok = await store.initialize()
        return {"initialized": bool(ok)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vector init error: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize vector store")


@router.post("/vector/index")
async def vector_index(
    payload: IndexPayload, store=Depends(get_vector_store_strict_dep)
) -> Dict[str, Any]:
    try:
        import numpy as np

        if store is None:
            raise HTTPException(
                status_code=501,
                detail={
                    "error": "vector_store_unavailable",
                    "required_dependencies": ["faiss", "numpy"],
                },
            )
        if not await store.initialize():
            raise HTTPException(status_code=500, detail="Vector store not initialized")
        embedding = np.array(payload.embedding, dtype=np.float32)  # noqa: F821
        doc_id = await store.add_document(
            content=payload.content,
            embedding=embedding,
            metadata=payload.metadata or {},
        )
        return {"id": doc_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vector index error: {e}")
        raise HTTPException(status_code=500, detail="Failed to index document")


@router.post("/vector/search")
async def vector_search(
    payload: SearchPayload, store=Depends(get_vector_store_strict_dep)
) -> Dict[str, Any]:  # noqa: C901
    try:
        import numpy as np

        if store is None:
            raise HTTPException(
                status_code=501,
                detail={
                    "error": "vector_store_unavailable",
                    "required_dependencies": ["faiss", "numpy"],
                },
            )
        if not await store.initialize():
            raise HTTPException(status_code=500, detail="Vector store not initialized")

        query = np.array(payload.embedding, dtype=np.float32)  # noqa: F821
        search_results = await store.search(query_embedding=query, k=max(1, payload.top_k))
        results = [
            {
                "id": result.document.id,
                "score": result.combined_score,
                "similarity_score": result.similarity_score,
                "metadata": result.document.metadata,
                "document_type": result.document.document_type,
            }
            for result in search_results
        ]
        return {"results": results, "count": len(results)}
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(
            status_code=501, detail="NumPy is required for vector search"
        )
    except Exception as e:
        logger.error(f"Vector search error: {e}")
        raise HTTPException(status_code=500, detail="Failed to search vector store")
