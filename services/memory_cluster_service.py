"""Service for memory clustering and summary-ready metadata."""

import logging
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from mem_db.memory.unified_memory_manager import UnifiedMemoryManager, MemoryType

logger = logging.getLogger(__name__)

class MemoryClusterService:
    async def generate_clusters(
        self,
        memory_manager: UnifiedMemoryManager,
        limit: int = 200,
        min_cluster_size: int = 2,
        n_clusters: int = 5,
        memory_type: Optional[MemoryType] = None,
        namespace: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generates clusters of memories using the UnifiedMemoryManager.
        """
        if not memory_manager.enable_vector_search:
            logger.warning("Vector search is disabled, cannot perform clustering.")
            return []

        try:
            clusters = await memory_manager.cluster_memories(
                n_clusters=n_clusters,
                limit=limit,
                memory_type=memory_type,
                namespace=namespace,
            )
            
            # Post-process clusters to include size, memory_ids, and simplified summaries
            clustered_results = []
            for cluster in clusters:
                memories = cluster.get("memories", [])
                if len(memories) >= min_cluster_size:
                    memory_ids = [m.get("record_id", "") for m in memories]
                    memory_types = list(set([m.get("memory_type", "") for m in memories]))
                    
                    top_terms = self._extract_top_terms(memories)
                    summary_content = f"Cluster of {len(memories)} memories. " \
                                      f"Types: {', '.join(memory_types)}. " \
                                      f"Example: {memories[0].get('content', '')[:100]}..." if memories else ""

                    clustered_results.append({
                        "cluster_id": cluster.get("cluster_id", "unknown"),
                        "size": len(memories),
                        "memory_ids": memory_ids,
                        "memory_types": memory_types,
                        "top_terms": top_terms,
                        "summary": summary_content,
                    })
            return clustered_results

        except Exception as e:
            logger.error(f"Failed to generate memory clusters: {e}", exc_info=True)
            return []

    def _extract_top_terms(
        self,
        memories: List[Dict[str, Any]],
        max_terms: int = 6,
    ) -> List[str]:
        stop_words = {
            "the",
            "and",
            "for",
            "that",
            "with",
            "from",
            "this",
            "have",
            "were",
            "into",
            "your",
            "about",
        }
        counter: Counter[str] = Counter()
        for memory in memories:
            content = str(memory.get("content") or "").lower()
            words = re.findall(r"[a-zA-Z0-9_]{3,}", content)
            for word in words:
                if word not in stop_words:
                    counter[word] += 1
        return [term for term, _ in counter.most_common(max_terms)]

memory_cluster_service = MemoryClusterService()
