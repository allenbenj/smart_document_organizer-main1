"""
Pattern-Based Extraction Mixin
==============================

Mixin class that adds YAML pattern-based extraction capabilities to legal agents.
This mixin integrates the YAML-based entity and relationship patterns with agent functionality.

Features:
- Load patterns from YAML configuration files
- Extract entities using regex patterns with context scoring
- Extract relationships with property mapping
- Confidence scoring based on pattern matches and context
- Integration with agent memory and service container
"""

import logging
from abc import ABC  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

from config.extraction_patterns import PatternLoader, get_pattern_loader  # noqa: E402

logger = logging.getLogger(__name__)


@dataclass
class PatternExtractionResult:
    """Result from pattern-based extraction."""

    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    confidence_score: float
    pattern_matches: int
    processing_time: float


class PatternExtractionMixin(ABC):
    """Mixin to add pattern-based extraction capabilities to agents."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pattern_loader: Optional[PatternLoader] = None
        self._pattern_extraction_enabled = True
        self.logger = getattr(self, "logger", logger)

    @property
    def pattern_loader(self) -> PatternLoader:
        """Get or initialize the pattern loader."""
        if self._pattern_loader is None:
            self._pattern_loader = get_pattern_loader()
        return self._pattern_loader

    def enable_pattern_extraction(self, enabled: bool = True) -> None:
        """Enable or disable pattern-based extraction."""
        self._pattern_extraction_enabled = enabled
        if hasattr(self, "logger"):
            self.logger.info(
                f"Pattern extraction {'enabled' if enabled else 'disabled'}"
            )

    def extract_entities_with_patterns(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Extract entities using YAML patterns.

        Args:
            text: Text to extract entities from
            entity_types: Specific entity types to extract (None for all)
            min_confidence: Minimum confidence threshold

        Returns:
            List of extracted entities with metadata
        """
        if not self._pattern_extraction_enabled:
            return []

        try:
            entities = self.pattern_loader.extract_entities_from_text(
                text, entity_types
            )

            # Filter by confidence if threshold is set
            if min_confidence > 0.0:
                entities = [
                    e for e in entities if e.get("context_score", 0.0) >= min_confidence
                ]

            # Add extraction metadata
            for entity in entities:
                entity["extraction_method"] = "yaml_pattern"
                entity["extracted_at"] = self._get_current_timestamp()
                entity["agent_id"] = getattr(self, "agent_id", "unknown")

            if hasattr(self, "logger"):
                self.logger.debug(f"Extracted {len(entities)} entities using patterns")

            return entities

        except Exception as e:
            if hasattr(self, "logger"):
                self.logger.error(f"Error in pattern-based entity extraction: {e}")
            return []

    def extract_relationships_with_patterns(
        self, text: str, relationship_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Extract relationships using YAML patterns.

        Args:
            text: Text to extract relationships from
            relationship_types: Specific relationship types to extract (None for all)

        Returns:
            List of extracted relationships with metadata
        """
        if not self._pattern_extraction_enabled:
            return []

        try:
            relationships = self.pattern_loader.extract_relationships_from_text(
                text, relationship_types
            )

            # Add extraction metadata
            for relationship in relationships:
                relationship["extraction_method"] = "yaml_pattern"
                relationship["extracted_at"] = self._get_current_timestamp()
                relationship["agent_id"] = getattr(self, "agent_id", "unknown")

            if hasattr(self, "logger"):
                self.logger.debug(
                    f"Extracted {len(relationships)} relationships using patterns"
                )

            return relationships

        except Exception as e:
            if hasattr(self, "logger"):
                self.logger.error(
                    f"Error in pattern-based relationship extraction: {e}"
                )
            return []

    def extract_with_patterns(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
        relationship_types: Optional[List[str]] = None,
        min_confidence: float = 0.0,
    ) -> PatternExtractionResult:
        """Extract both entities and relationships using patterns.

        Args:
            text: Text to process
            entity_types: Entity types to extract (None for all)
            relationship_types: Relationship types to extract (None for all)
            min_confidence: Minimum confidence threshold for entities

        Returns:
            PatternExtractionResult with all extracted data
        """
        import time  # noqa: E402

        start_time = time.time()

        entities = self.extract_entities_with_patterns(
            text, entity_types, min_confidence
        )
        relationships = self.extract_relationships_with_patterns(
            text, relationship_types
        )

        processing_time = time.time() - start_time
        pattern_matches = len(entities) + len(relationships)

        # Calculate overall confidence score
        confidence_score = self._calculate_overall_confidence(entities, relationships)

        return PatternExtractionResult(
            entities=entities,
            relationships=relationships,
            confidence_score=confidence_score,
            pattern_matches=pattern_matches,
            processing_time=processing_time,
        )

    def get_supported_entity_types(self) -> List[str]:
        """Get list of entity types supported by loaded patterns."""
        return list(self.pattern_loader.get_entity_patterns().keys())

    def get_supported_relationship_types(self) -> List[str]:
        """Get list of relationship types supported by loaded patterns."""
        return list(self.pattern_loader.get_relationship_patterns().keys())

    def validate_pattern_coverage(self, text: str) -> Dict[str, Any]:
        """Analyze pattern coverage for a text sample.

        Args:
            text: Text to analyze

        Returns:
            Analysis of pattern coverage and matches
        """
        result = self.extract_with_patterns(text)

        entity_types_found = set(e["type"] for e in result.entities)
        relationship_types_found = set(r["type"] for r in result.relationships)

        total_entity_types = len(self.get_supported_entity_types())
        total_relationship_types = len(self.get_supported_relationship_types())

        return {
            "entity_coverage": len(entity_types_found) / max(total_entity_types, 1),
            "relationship_coverage": len(relationship_types_found)
            / max(total_relationship_types, 1),
            "entities_found": len(result.entities),
            "relationships_found": len(result.relationships),
            "entity_types_found": list(entity_types_found),
            "relationship_types_found": list(relationship_types_found),
            "processing_time": result.processing_time,
            "confidence_score": result.confidence_score,
        }

    def reload_patterns(self) -> None:
        """Reload patterns from YAML files."""
        if self._pattern_loader:
            self._pattern_loader.reload_patterns()
            if hasattr(self, "logger"):
                self.logger.info("Patterns reloaded from YAML files")

    def _calculate_overall_confidence(
        self, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]
    ) -> float:
        """Calculate overall confidence score for extraction results.

        Args:
            entities: Extracted entities
            relationships: Extracted relationships

        Returns:
            Overall confidence score between 0.0 and 1.0
        """
        if not entities and not relationships:
            return 0.0

        # Calculate average entity confidence
        entity_scores = [e.get("context_score", 0.0) for e in entities]
        avg_entity_confidence = (
            sum(entity_scores) / len(entity_scores) if entity_scores else 0.0
        )

        # Relationships get a base confidence since they matched patterns
        relationship_confidence = 0.7 if relationships else 0.0

        # Weight entities and relationships
        entity_weight = (
            len(entities) / (len(entities) + len(relationships))
            if (entities or relationships)
            else 0.0
        )
        relationship_weight = 1.0 - entity_weight

        overall_confidence = (
            avg_entity_confidence * entity_weight
            + relationship_confidence * relationship_weight
        )

        return min(1.0, max(0.0, overall_confidence))

    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string."""
        from datetime import datetime  # noqa: E402

        return datetime.now().isoformat()

    def enhance_extraction_with_patterns(
        self, base_entities: List[Dict[str, Any]], text: str
    ) -> List[Dict[str, Any]]:
        """Enhance existing entity extraction with pattern-based results.

        Args:
            base_entities: Entities from other extraction methods
            text: Original text

        Returns:
            Combined and deduplicated entity list
        """
        pattern_entities = self.extract_entities_with_patterns(text)

        # Combine entities and deduplicate
        combined = base_entities.copy()

        for pattern_entity in pattern_entities:
            # Check for overlap with existing entities
            is_duplicate = False
            for existing in base_entities:
                if self._entities_overlap(existing, pattern_entity):
                    # Update existing entity with pattern information
                    existing.setdefault("extraction_methods", []).append("yaml_pattern")
                    existing.setdefault("pattern_info", {}).update(
                        {
                            "pattern_matched": pattern_entity.get("pattern_matched"),
                            "context_score": pattern_entity.get("context_score", 0.0),
                        }
                    )
                    is_duplicate = True
                    break

            if not is_duplicate:
                combined.append(pattern_entity)

        return combined

    def _entities_overlap(
        self, entity1: Dict[str, Any], entity2: Dict[str, Any]
    ) -> bool:
        """Check if two entities overlap in text."""
        start1, end1 = entity1.get("start", 0), entity1.get("end", 0)
        start2, end2 = entity2.get("start", 0), entity2.get("end", 0)

        # Calculate overlap
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        overlap_length = max(0, overlap_end - overlap_start)

        # Consider entities overlapping if they share more than 50% of their text
        min_length = min(end1 - start1, end2 - start2)
        return overlap_length > (min_length * 0.5) if min_length > 0 else False
