"""
Agent Mixins for Legal AI Platform
===================================

Provides specialized mixins for legal domain agents that enhance the base
agent with domain-specific capabilities and shared patterns.
"""

import json
import logging  # noqa: E402
import re  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any, Dict, List, Optional, Protocol, cast, runtime_checkable  # noqa: E402

from mem_db.memory.memory_interfaces import MemoryType  # noqa: E402

logger = logging.getLogger(__name__)


@runtime_checkable
class _MemoryCapable(Protocol):
    async def store_memory(
        self,
        namespace: str,
        key: str,
        content: str,
        memory_type: MemoryType = MemoryType.AGENT,
        metadata: Optional[Dict[str, Any]] = None,
        importance_score: float = 1.0,
        confidence_score: float = 1.0,
        document_id: Optional[str] = None,
    ) -> str: ...

    async def search_memory(
        self,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        namespaces: Optional[List[str]] = None,
        include_own_memories: bool = True,
        limit: int = 10,
        min_similarity: float = 0.6,
    ) -> List[Any]: ...


def _memory_host(obj: Any) -> Optional[_MemoryCapable]:
    if hasattr(obj, "store_memory") and hasattr(obj, "search_memory"):
        return cast(_MemoryCapable, obj)
    return None


class LegalMemoryMixin:
    """
    Mixin that ensures proper memory integration for legal-domain agents.

    This mixin provides enhanced memory capabilities beyond the basic
    MemoryMixin, with specific support for legal AI workflows.
    """

    async def store_analysis_result(
        self,
        analysis_type: str,
        document_id: str,
        analysis_data: Dict[str, Any],
        confidence_score: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store analysis results with standardized metadata.

        Args:
            analysis_type: Type of analysis (e.g., "irac", "entity_extraction")
            document_id: Document being analyzed
            analysis_data: Analysis results
            confidence_score: Confidence in the analysis
            metadata: Additional metadata

        Returns:
            Record ID of stored analysis
        """
        memory = _memory_host(self)
        if memory is None:
            logger.warning(
                f"Agent {getattr(self, 'agent_name', 'unknown')} does not have memory capabilities"
            )
            return ""

        enhanced_metadata = metadata or {}
        enhanced_metadata.update(
            {
                "analysis_type": analysis_type,
                "document_id": document_id,
                "analyzed_by": getattr(self, "agent_name", "unknown"),
                "analyzed_at": datetime.now().isoformat(),
                "confidence_score": confidence_score,
            }
        )

        content = json.dumps(analysis_data, default=str, indent=2)

        return await memory.store_memory(
            namespace="legal_analysis",
            key=f"{document_id}_{analysis_type}",
            content=content,
            memory_type=MemoryType.ANALYSIS,
            metadata=enhanced_metadata,
            importance_score=confidence_score,
            confidence_score=confidence_score,
            document_id=document_id,
        )

    async def find_related_analysis(
        self, analysis_type: str, query_text: str, limit: int = 5
    ) -> List[Any]:
        """
        Find related analysis from other agents.

        Args:
            analysis_type: Type of analysis to search for
            query_text: Query text for similarity search
            limit: Maximum number of results

        Returns:
            List of related analysis results
        """
        memory = _memory_host(self)
        if memory is None:
            logger.warning(
                f"Agent {getattr(self, 'agent_name', 'unknown')} does not have memory capabilities"
            )
            return []

        results = await memory.search_memory(
            query=query_text,
            memory_types=[MemoryType.ANALYSIS],
            namespaces=["legal_analysis"],
            limit=limit,
        )

        # Filter by analysis type
        filtered_results = []
        for result in results:
            metadata = result.record.metadata
            if metadata.get("analysis_type") == analysis_type:
                filtered_results.append(result)

        return filtered_results


# Backward-compatible alias during migration.
MemoryEnabledMixin = LegalMemoryMixin


class LegalDomainMixin:
    """
    Mixin that provides legal domain-specific capabilities and patterns.

    This mixin includes common legal AI functionality like IRAC analysis,
    case law handling, and legal entity management.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Legal domain configuration
        self.legal_config = {
            "enable_irac_analysis": True,
            "enable_precedent_matching": True,
            "enable_legal_entity_extraction": True,
            "min_confidence_threshold": 0.7,
        }

    async def store_legal_precedent(
        self,
        case_citation: str,
        case_summary: str,
        legal_principles: List[str],
        precedent_strength: float,
        jurisdiction: str = "federal",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store legal precedent information in shared memory.

        Args:
            case_citation: Citation for the case
            case_summary: Summary of the case
            legal_principles: Legal principles established
            precedent_strength: Strength of precedent (0.0-1.0)
            jurisdiction: Jurisdiction of the case
            metadata: Additional metadata

        Returns:
            Record ID of stored precedent
        """
        memory = _memory_host(self)
        if memory is None:
            logger.warning(
                f"Agent {getattr(self, 'agent_name', 'unknown')} does not have memory capabilities"
            )
            return ""

        precedent_metadata = metadata or {}
        precedent_metadata.update(
            {
                "case_citation": case_citation,
                "legal_principles": legal_principles,
                "precedent_strength": precedent_strength,
                "jurisdiction": jurisdiction,
                "stored_by": getattr(self, "agent_name", "unknown"),
                "stored_at": datetime.now().isoformat(),
            }
        )

        return await memory.store_memory(
            namespace="case_law",
            key=case_citation,
            content=case_summary,
            memory_type=MemoryType.CASE_LAW,
            metadata=precedent_metadata,
            importance_score=precedent_strength,
            confidence_score=0.9,  # High confidence for established case law
        )

    async def find_similar_precedents(
        self,
        legal_issue: str,
        jurisdiction: Optional[str] = None,
        min_strength: float = 0.5,
        limit: int = 5,
    ) -> List[Any]:
        """
        Find similar legal precedents based on legal issues.

        Args:
            legal_issue: Description of the legal issue
            jurisdiction: Optional jurisdiction filter
            min_strength: Minimum precedent strength
            limit: Maximum number of precedents

        Returns:
            List of similar precedents
        """
        memory = _memory_host(self)
        if memory is None:
            logger.warning(
                f"Agent {getattr(self, 'agent_name', 'unknown')} does not have memory capabilities"
            )
            return []

        # Build search query
        search_query = legal_issue
        if jurisdiction:
            search_query += f" jurisdiction:{jurisdiction}"

        results = await memory.search_memory(
            query=search_query,
            memory_types=[MemoryType.CASE_LAW],
            namespaces=["case_law"],
            limit=limit * 2,  # Get more results for filtering
        )

        # Filter by precedent strength
        filtered_results = []
        for result in results:
            metadata = result.record.metadata
            precedent_strength = metadata.get("precedent_strength", 0.0)
            if precedent_strength >= min_strength:
                filtered_results.append(result)

        # Sort by precedent strength and limit
        filtered_results.sort(
            key=lambda x: x.record.metadata.get("precedent_strength", 0.0), reverse=True
        )

        return filtered_results[:limit]

    async def store_legal_entities(
        self,
        document_id: str,
        entities: List[Dict[str, Any]],
        extraction_method: str = "hybrid",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Store extracted legal entities in shared memory.

        Args:
            document_id: Document from which entities were extracted
            entities: List of entity dictionaries
            extraction_method: Method used for extraction
            metadata: Additional metadata

        Returns:
            List of record IDs for stored entities
        """
        memory = _memory_host(self)
        if memory is None:
            logger.warning(
                f"Agent {getattr(self, 'agent_name', 'unknown')} does not have memory capabilities"
            )
            return []

        record_ids = []

        for i, entity in enumerate(entities):
            entity_metadata = metadata or {}
            entity_metadata.update(
                {
                    "document_id": document_id,
                    "extraction_method": extraction_method,
                    "entity_type": entity.get("type", "unknown"),
                    "confidence": entity.get("confidence", 1.0),
                    "extracted_by": getattr(self, "agent_name", "unknown"),
                    "extracted_at": datetime.now().isoformat(),
                }
            )

            entity_content = json.dumps(entity, default=str)

            record_id = await memory.store_memory(
                namespace="legal_entities",
                key=f"{document_id}_entity_{i}",
                content=entity_content,
                memory_type=MemoryType.ENTITY,
                metadata=entity_metadata,
                importance_score=entity.get("confidence", 1.0),
                confidence_score=entity.get("confidence", 1.0),
                document_id=document_id,
            )

            if record_id:
                record_ids.append(record_id)

        logger.info(
            f"Stored {len(record_ids)} legal entities for document {document_id}"
        )
        return record_ids

    def _extract_irac_components(self, text: str) -> Dict[str, str]:
        """
        Basic IRAC component extraction using pattern matching.

        Args:
            text: Text to analyze for IRAC components

        Returns:
            Dictionary with IRAC components
        """
        irac_components = {"issue": "", "rule": "", "application": "", "conclusion": ""}

        # Simple pattern-based extraction (can be enhanced)
        issue_patterns = [
            r"(?i)(?:issue|question|problem):\s*(.+?)(?:\n\n|\n(?=[A-Z])|$)",
            r"(?i)the\s+(?:issue|question)\s+is\s+(.+?)(?:\.|;|\n)",
        ]

        rule_patterns = [
            r"(?i)(?:rule|law|statute|regulation):\s*(.+?)(?:\n\n|\n(?=[A-Z])|$)",
            r"(?i)the\s+(?:rule|law)\s+(?:states|provides)\s+(.+?)(?:\.|;|\n)",
        ]

        # Extract components using patterns
        for pattern in issue_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                irac_components["issue"] = match.group(1).strip()
                break

        for pattern in rule_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                irac_components["rule"] = match.group(1).strip()
                break

        return irac_components

    def _calculate_legal_confidence(
        self,
        analysis_result: Dict[str, Any],
        factors: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Calculate confidence score for legal analysis.

        Args:
            analysis_result: Analysis result to score
            factors: Confidence factors and weights

        Returns:
            Confidence score between 0.0 and 1.0
        """
        default_factors = {
            "completeness": 0.3,  # How complete is the analysis
            "precedent_support": 0.3,  # Support from precedents
            "consistency": 0.2,  # Internal consistency
            "citation_quality": 0.2,  # Quality of citations
        }

        factors = factors or default_factors
        confidence_score = 0.0

        # Completeness: Check if all expected components are present
        expected_components = ["issue", "rule", "application", "conclusion"]
        present_components = sum(
            1 for comp in expected_components if analysis_result.get(comp)
        )
        completeness = present_components / len(expected_components)
        confidence_score += completeness * factors.get("completeness", 0.3)

        # Precedent support: Check for citations and precedents
        precedents = analysis_result.get("precedents", [])
        citations = analysis_result.get("citations", [])
        precedent_support = min(1.0, (len(precedents) + len(citations)) / 3)
        confidence_score += precedent_support * factors.get("precedent_support", 0.3)

        # Basic consistency check
        consistency = 1.0  # Would implement actual consistency checking
        confidence_score += consistency * factors.get("consistency", 0.2)

        # Citation quality (basic check for proper format)
        citation_quality = 1.0 if citations else 0.5
        confidence_score += citation_quality * factors.get("citation_quality", 0.2)

        return min(1.0, confidence_score)


class DocumentProcessingMixin:
    """
    Mixin for agents that process legal documents.

    Provides common document processing patterns and utilities.
    """

    async def store_document_metadata(
        self, document_id: str, document_type: str, metadata: Dict[str, Any]
    ) -> str:
        """
        Store document metadata for future reference.

        Args:
            document_id: Unique document identifier
            document_type: Type of document (e.g., "contract", "case_law", "statute")
            metadata: Document metadata

        Returns:
            Record ID of stored metadata
        """
        memory = _memory_host(self)
        if memory is None:
            logger.warning(
                f"Agent {getattr(self, 'agent_name', 'unknown')} does not have memory capabilities"
            )
            return ""

        enhanced_metadata = metadata.copy()
        enhanced_metadata.update(
            {
                "document_type": document_type,
                "processed_by": getattr(self, "agent_name", "unknown"),
                "processed_at": datetime.now().isoformat(),
            }
        )

        content = json.dumps(metadata, default=str, indent=2)

        return await memory.store_memory(
            namespace="document_metadata",
            key=document_id,
            content=content,
            memory_type=MemoryType.DOCUMENT,
            metadata=enhanced_metadata,
            importance_score=0.8,
            document_id=document_id,
        )

    def _extract_document_structure(self, text: str) -> Dict[str, Any]:
        """
        Extract basic document structure information.

        Args:
            text: Document text

        Returns:
            Dictionary with structure information
        """
        structure = {
            "sections": [],
            "headings": [],
            "paragraphs": 0,
            "estimated_reading_time": 0,
        }

        # Extract headings (simple pattern)
        headings = re.findall(r"^[A-Z][A-Z\s]+$", text, re.MULTILINE)
        structure["headings"] = headings[:10]  # Limit to first 10

        # Count paragraphs
        paragraphs = text.split("\n\n")
        structure["paragraphs"] = len([p for p in paragraphs if p.strip()])

        # Estimate reading time (average 200 words per minute)
        words = len(text.split())
        structure["estimated_reading_time"] = max(1, words // 200)

        return structure
