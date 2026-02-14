from pathlib import Path
from typing import Optional  # noqa: E402

_knowledge_manager_singleton = None


def get_knowledge_manager(graph_dir: Optional[str] = None):
    """Return a singleton UnifiedKnowledgeGraphManager if dependencies are available.

    Falls back to None when required optional deps are missing.
    """
    global _knowledge_manager_singleton
    if _knowledge_manager_singleton is not None:
        return _knowledge_manager_singleton

    try:
        from .unified_knowledge_graph_manager import UnifiedKnowledgeGraphManager  # noqa: E402
    except Exception:
        return None

    base = (
        Path(graph_dir)
        if graph_dir
        else Path(__file__).parent.parent / "data" / "knowledge_graph"
    )
    _knowledge_manager_singleton = UnifiedKnowledgeGraphManager(graph_path=base)
    return _knowledge_manager_singleton


__all__ = ["get_knowledge_manager"]
