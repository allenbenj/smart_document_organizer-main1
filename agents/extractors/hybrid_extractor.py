# legal_ai_system/extraction/hybrid_extractor.py
"""
Hybrid Legal Entity Extractor
=============================
Combines multiple extraction methods for comprehensive legal entity extraction.
"""

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

from ..core.base_agent import AgentResult, BaseAgent  # noqa: E402
from utils.logging import (  # noqa: E402
    LogCategory,
    detailed_log_function,
    get_detailed_logger,
)
from ..core.models import (  # noqa: E402
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    LegalDocument,
)
from ..core.unified_exceptions import AgentError  # noqa: E402

# Initialize logger
hybrid_extractor_logger = get_detailed_logger("HybridLegalExtractor", LogCategory.AGENT)


@dataclass
class HybridExtractionResult:
    """Result from hybrid legal extraction process."""

    document_id: str
    document_path: str

    # Extracted content
    entities: List[ExtractedEntity] = field(default_factory=list)
    relationships: List[ExtractedRelationship] = field(default_factory=list)
    validated_entities: List[ExtractedEntity] = field(default_factory=list)

    # Processing metadata
    extraction_methods_used: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    confidence_scores: Dict[str, float] = field(default_factory=dict)

    # Quality metrics
    total_entities_found: int = 0
    high_confidence_entities: int = 0
    validation_results: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Calculate derived metrics."""
        self.total_entities_found = len(self.entities)
        self.high_confidence_entities = len(
            [e for e in self.entities if e.confidence >= 0.8]
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class HybridLegalExtractor(BaseAgent):
    """
    Hybrid extractor combining multiple extraction methods for legal documents.
    """

    @detailed_log_function(LogCategory.AGENT)
    def __init__(self, service_container: Optional[Any] = None, **kwargs):
        super().__init__(
            service_container, name="HybridLegalExtractor", agent_type="extraction"
        )

        # Configuration
        self.enable_ner = kwargs.get("enable_ner", True)
        self.enable_llm_extraction = kwargs.get("enable_llm_extraction", True)
        self.enable_confidence_calibration = kwargs.get(
            "enable_confidence_calibration", True
        )
        self.confidence_threshold = kwargs.get("confidence_threshold", 0.7)

        # Extraction methods
        self.extraction_methods: List[str] = []
        if self.enable_ner:
            self.extraction_methods.append("named_entity_recognition")
        if self.enable_llm_extraction:
            self.extraction_methods.append("llm_extraction")

        hybrid_extractor_logger.info(
            "HybridLegalExtractor initialized",
            parameters={
                "methods": self.extraction_methods,
                "threshold": self.confidence_threshold,
            },
        )

    @detailed_log_function(LogCategory.AGENT)
    async def extract_from_document(
        self, document: LegalDocument
    ) -> HybridExtractionResult:
        """
        Extract entities and relationships from a legal document using hybrid methods.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            hybrid_extractor_logger.info(
                "Starting hybrid extraction",
                parameters={"document_id": document.id, "filename": document.filename},
            )

            result = HybridExtractionResult(
                document_id=document.id,
                document_path=str(document.file_path) if document.file_path else "",
                extraction_methods_used=self.extraction_methods.copy(),
            )

            # Extract using different methods
            all_entities = []

            if self.enable_ner and document.content:
                ner_entities = await self._extract_with_ner(document.content)
                all_entities.extend(ner_entities)
                hybrid_extractor_logger.debug(
                    f"NER extraction found {len(ner_entities)} entities"
                )

            if self.enable_llm_extraction and document.content:
                llm_entities = await self._extract_with_llm(document.content)
                all_entities.extend(llm_entities)
                hybrid_extractor_logger.debug(
                    f"LLM extraction found {len(llm_entities)} entities"
                )

            # Merge and validate entities
            result.entities = all_entities
            result.validated_entities = await self._validate_entities(all_entities)

            # Extract relationships
            if result.validated_entities:
                result.relationships = await self._extract_relationships(
                    result.validated_entities, document.content or ""
                )

            # Calculate metrics
            result.processing_time = asyncio.get_event_loop().time() - start_time
            result.confidence_scores = self._calculate_confidence_scores(
                result.entities
            )

            hybrid_extractor_logger.info(
                "Hybrid extraction completed",
                parameters={
                    "document_id": document.id,
                    "total_entities": result.total_entities_found,
                    "high_confidence": result.high_confidence_entities,
                    "processing_time": result.processing_time,
                },
            )

            return result

        except Exception as e:
            hybrid_extractor_logger.error(
                "Hybrid extraction failed",
                parameters={"document_id": document.id},
                exception=e,
            )
            raise AgentError(f"Hybrid extraction failed: {str(e)}")

    async def _extract_with_ner(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using Named Entity Recognition.

        .. deprecated::
            NOT IMPLEMENTED - This is a placeholder/mock implementation.

            TODO: Integrate with actual NER library (spaCy, transformers, etc.)

            Current behavior: Simple keyword matching for 'contract' and 'agreement'.
            This does NOT perform actual named entity recognition.

            Required for production:
            - Install spaCy or transformers library
            - Load legal NER model
            - Implement proper entity span detection
            - Add confidence calibration based on model outputs
        """
        import warnings  # noqa: E402

        warnings.warn(
            "_extract_with_ner is a mock implementation. "
            "Returns hardcoded keyword matches instead of actual NER.",
            UserWarning,
            stacklevel=2,
        )

        entities = []

        # MOCK: Simple keyword matching - NOT actual NER
        if "contract" in text.lower():
            entities.append(
                ExtractedEntity(
                    text="contract",
                    entity_type=EntityType.CONTRACT,
                    confidence=0.85,
                    source="ner_mock",
                )
            )

        if "agreement" in text.lower():
            entities.append(
                ExtractedEntity(
                    text="agreement",
                    entity_type=EntityType.CONTRACT,
                    confidence=0.80,
                    source="ner_mock",
                )
            )

        return entities

    async def _extract_with_llm(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using LLM-based extraction.

        .. deprecated::
            NOT IMPLEMENTED - This is a placeholder/mock implementation.

            TODO: Integrate with actual LLM provider (OpenAI, Anthropic, local models)

            Current behavior: Simple keyword matching for 'shall' and 'must'.
            This does NOT perform actual LLM-based extraction.

            Required for production:
            - Configure LLM provider in service container
            - Implement prompt engineering for legal entity extraction
            - Add response parsing and validation
            - Implement retry logic and error handling
        """
        import warnings  # noqa: E402

        warnings.warn(
            "_extract_with_llm is a mock implementation. "
            "Returns hardcoded keyword matches instead of actual LLM extraction.",
            UserWarning,
            stacklevel=2,
        )

        entities = []

        # MOCK: Simple keyword matching - NOT actual LLM extraction
        if "shall" in text.lower() or "must" in text.lower():
            entities.append(
                ExtractedEntity(
                    text="obligation",
                    entity_type=EntityType.OBLIGATION,
                    confidence=0.75,
                    source="llm_mock",
                )
            )

        return entities

    async def _validate_entities(
        self, entities: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Validate and filter entities based on confidence threshold."""
        validated = []

        for entity in entities:
            if entity.confidence >= self.confidence_threshold:
                validated.append(entity)

        return validated

    async def _extract_relationships(
        self, entities: List[ExtractedEntity], text: str
    ) -> List[ExtractedRelationship]:
        """Extract relationships between entities.

        The ``text`` argument is reserved for future use when more
        sophisticated relationship extraction strategies leverage the
        source document text. It is currently unused.
        """
        relationships = []

        # Simple relationship extraction based on proximity and patterns
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i + 1 :]:
                # Mock relationship extraction
                if (
                    entity1.entity_type == EntityType.PERSON
                    and entity2.entity_type == EntityType.ORGANIZATION
                ):
                    relationships.append(
                        ExtractedRelationship(
                            source_entity_id=entity1.id,
                            target_entity_id=entity2.id,
                            relationship_type="works_for",
                            confidence=0.7,
                        )
                    )

        return relationships

    def _calculate_confidence_scores(
        self, entities: List[ExtractedEntity]
    ) -> Dict[str, float]:
        """Calculate aggregate confidence scores."""
        if not entities:
            return {}

        total_confidence = sum(e.confidence for e in entities)
        avg_confidence = total_confidence / len(entities)

        return {
            "average_confidence": avg_confidence,
            "total_entities": len(entities),
            "high_confidence_ratio": len([e for e in entities if e.confidence >= 0.8])
            / len(entities),
        }

    async def process(
        self, data: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """BaseAgent interface implementation."""
        try:
            if isinstance(data, LegalDocument):
                result = await self.extract_from_document(data)
                return AgentResult(
                    success=True,
                    data=result.to_dict(),
                    agent_type=self.agent_type,
                    metadata={"agent_name": self.name},
                )
            else:
                raise AgentError("Invalid input data type for HybridLegalExtractor")

        except Exception as e:
            return AgentResult(
                success=False,
                error=str(e),
                agent_type=self.agent_type,
                metadata={"agent_name": self.name},
            )

    async def _process_task(
        self, task_data: Any, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Implementation of abstract method from :class:`BaseAgent`."""
        if isinstance(task_data, LegalDocument):
            result = await self.extract_from_document(task_data)
            return result.to_dict()
        raise AgentError("Invalid task data type for HybridLegalExtractor")

    async def initialize(self):
        """Placeholder async initializer for interface compatibility."""
        hybrid_extractor_logger.info("HybridLegalExtractor initialize called")

    async def close(self):
        """Placeholder async close method."""
        hybrid_extractor_logger.info("HybridLegalExtractor close called")
