from pathlib import Path
from typing import Optional  # noqa: E402

_vector_store_singleton = None


def get_vector_store(store_dir: Optional[str] = None):
    """Return a singleton UnifiedVectorStore if optional deps are available.

    Returns None if FAISS/numpy are unavailable.
    """
    global _vector_store_singleton
    if _vector_store_singleton is not None:
        return _vector_store_singleton

    try:
        from .unified_vector_store import UnifiedVectorStore  # noqa: E402
    except Exception:
        return None

    base = (
        Path(store_dir)
        if store_dir
        else Path(__file__).parent.parent / "data" / "vector_store"
    )
    _vector_store_singleton = UnifiedVectorStore(store_path=base)
    return _vector_store_singleton


__all__ = ["get_vector_store"]
