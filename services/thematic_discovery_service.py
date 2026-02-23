"""
Thematic Discovery Service - AEDIS Intelligence Layer
=====================================================
Orchestrates high-fidelity clustering and zero-shot entity extraction
to discover strategic themes in legal documents.
"""

import logging
import uuid
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from agents.utils.evidence_clusterer import EvidenceClusterer
from services.agent_service import AgentService
from mem_db.memory import proposals_db

logger = logging.getLogger(__name__)

class ThematicDiscoveryService:
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        self.clusterer = EvidenceClusterer()

    async def discover_strategic_themes(self, text: str, document_id: str, num_clusters: int = 5) -> Dict[str, Any]:
        """
        Perform an end-to-end thematic audit and persist the findings.
        """
        logger.info(f"Starting discovery for document: {document_id}")
        
        # 1. Generate Semantic Clusters (Local MiniLM)
        clusters = self.clusterer.cluster_document(text, num_clusters=num_clusters)
        
        # 2. Deploy Oracle for each cluster (Agent Service)
        discovery_results = []
        agent_service = AgentService(self.agent_manager) if self.agent_manager else None
        
        for theme_idx, items in clusters.items():
            # Use representative sample for labeling
            sample_text = "\n".join(items[:3])
            entities = []
            
            # Only attempt entity extraction if manager is available
            if agent_service:
                try:
                    oracle_task = {
                        "type": "entity_extraction",
                        "text": sample_text,
                        "extra_options": {
                            "extraction_model": "gliner_zero_shot",
                            "labels": ["Prosecutor", "Witness", "Misconduct Action", "Violation", "Key Document"]
                        }
                    }
                    oracle_res = await agent_service.dispatch_task("extract_entities", oracle_task)
                    if isinstance(oracle_res, dict):
                        entities = oracle_res.get("data", {}).get("entities", [])
                except Exception as e:
                    logger.warning(f"Thematic Oracle extraction failed for cluster {theme_idx}: {e}")
            
            # Create a 'Theme Artifact'
            theme_record = {
                "theme_id": str(uuid.uuid4()),
                "document_id": document_id,
                "theme_label": f"Strategic Theme {theme_idx + 1}",
                "evidence_count": len(items),
                "key_identifiers": [e.get("text") for e in entities],
                "summary": sample_text[:200] + "...",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            discovery_results.append(theme_record)
            
            # Persist to database as an 'Analysis Proposal'
            await self._persist_theme(theme_record, items)

        return {
            "document_id": document_id,
            "themes_discovered": len(discovery_results),
            "results": discovery_results
        }

    async def _persist_theme(self, theme_record: Dict, items: List[str]):
        """Save findings to the proposals database for GUI review."""
        try:
            # We treat each theme as a 'Strategic Proposal' for the Knowledge Graph
            proposal_data = {
                "namespace": "thematic_discovery",
                "key": f"theme_{theme_record['document_id']}_{theme_record['theme_id']}",
                "content": json.dumps({
                    "label": theme_record["theme_label"],
                    "identifiers": theme_record["key_identifiers"],
                    "evidence_items": items,
                    "summary": theme_record["summary"]
                }),
                "memory_type": "analysis",
                "agent_id": "thematic_discovery_service",
                "document_id": theme_record["document_id"],
                "metadata": {
                    "theme_label": theme_record["theme_label"],
                    "evidence_count": theme_record["evidence_count"]
                },
                "confidence_score": 0.95,
                "import