#!/usr/bin/env python3
"""
Production GLiNER NER Entity Agent
==================================

A production-grade named entity recognition agent using GLiNER model,
integrated with the Legal AI platform's service container architecture.

Features:
- GLiNER model integration with fallback to rule-based extraction
- Legal entity types optimized for legal documents
- Async processing with proper error handling
- Service container integration for dependencies
- Relationship extraction between entities
"""

import logging
import re  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

from config.core.service_container import ServiceContainer  # noqa: E402

# Production imports
from agents.base.base_agent import BaseAgent  # noqa: E402
from agents.core.models import AgentResult  # noqa: E402

logger = logging.getLogger(__name__)


@dataclass
class NERResult:
    """Result from NER processing"""

    entities: List[Dict[str, Any]]
    confidence_scores: List[float]
    processing_time: float
    model_used: str


@dataclass
class LegalEntity:
    """Legal entity extracted by GLiNER"""

    text: str
    label: str
    start: int
    end: int
    confidence: float
    context: Optional[str] = None


class GLiNERModel:
    """GLiNER model wrapper for legal entity recognition"""

    def __init__(self, model_path: Optional[str] = None):
        """Initialize GLiNER model

        Args:
            model_path: Path to custom GLiNER model, uses default if None
        """
        self.model_path = model_path or "urchade/gliner_mediumv2.1"
        self.model = None
        self.is_loaded = False

        # Legal entity types for GLiNER
        self.legal_entity_types = [
            "person",
            "organization",
            "location",
            "date",
            "money",
            "case_citation",
            "statute",
            "regulation",
            "court",
            "judge",
            "lawyer",
            "plainti",
            "defendant",
            "contract",
            "evidence",
            "crime",
            "penalty",
        ]

    def load_model(self) -> bool:
        """Load the GLiNER model

        Returns:
            True if successful, False otherwise
        """
        try:
            from gliner import GLiNER  # noqa: E402

            self.model = GLiNER.from_pretrained(self.model_path)
            self.is_loaded = True
            logger.info(f"GLiNER model loaded successfully from {self.model_path}")
            return True
        except ImportError:
            logger.warning("GLiNER not available, using fallback implementation")
            self.model = None
            self.is_loaded = False
            return False
        except Exception as e:
            logger.error(f"Failed to load GLiNER model: {e}")
            self.model = None
            self.is_loaded = False
            return False

    def extract_entities(
        self, text: str, entity_types: Optional[List[str]] = None
    ) -> NERResult:
        """Extract entities from text

        Args:
            text: Input text to process
            entity_types: List of entity types to extract, uses default if None

        Returns:
            NERResult with extracted entities
        """
        start_time = time.time()

        if not self.is_loaded:
            if not self.load_model():
                return self._fallback_extraction(text, entity_types)

        try:
            entity_types = entity_types or self.legal_entity_types

            if self.model:
                entities = self.model.predict_entities(text, entity_types)

                formatted_entities = [
                    {
                        "text": entity["text"],
                        "label": entity["label"],
                        "start": entity["start"],
                        "end": entity["end"],
                        "confidence": entity.get("score", 0.5),
                    }
                    for entity in entities
                ]

                confidence_scores = [entity.get("score", 0.5) for entity in entities]
                processing_time = time.time() - start_time

                return NERResult(
                    entities=formatted_entities,
                    confidence_scores=confidence_scores,
                    processing_time=processing_time,
                    model_used="GLiNER",
                )
            else:
                return self._fallback_extraction(text, entity_types)

        except Exception as e:
            logger.error(f"Error in GLiNER extraction: {e}")
            return self._fallback_extraction(text, entity_types)

    def _fallback_extraction(
        self, text: str, entity_types: Optional[List[str]] = None
    ) -> NERResult:
        """Fallback rule-based entity extraction

        Args:
            text: Input text
            entity_types: Entity types to extract

        Returns:
            NERResult with basic extracted entities
        """
        start_time = time.time()
        entities = []
        confidence_scores = []

        patterns = {
            "case_citation": r"\b\d+\s+[A-Za-z\.]+\s+\d+\b",
            "statute": r"\b\d+\s+U\.?S\.?C\.?\s+§?\s*\d+\b",
            "date": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\w+\s+\d{1,2},?\s+\d{4}\b",
            "money": r"\$[\d,]+\.?\d*",
            "court": r"\b\w+\s+Court\b|\bSupreme Court\b",
        }

        for entity_type, pattern in patterns.items():
            if entity_types is None or entity_type in entity_types:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    entity = {
                        "text": match.group(),
                        "label": entity_type,
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.6,
                    }
                    entities.append(entity)
                    confidence_scores.append(0.6)

        processing_time = time.time() - start_time

        return NERResult(
            entities=entities,
            confidence_scores=confidence_scores,
            processing_time=processing_time,
            model_used="Fallback_Rules",
        )


class LegalNERAgent(BaseAgent):
    """Production Legal NER Agent integrated with service container architecture."""

    def __init__(self, services: ServiceContainer):
        super().__init__(services, "LegalNERAgent")
        self.gliner_model = GLiNERModel()
        self.pipeline_loaded = False
        self.memory_service = services.get_optional_service("memory_manager")

    async def _process_task(
        self, task_data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """Main processing method for BaseAgent integration."""
        try:
            text = task_data.get("text", "")
            if not text:
                raise ValueError("No text provided for NER processing")

            extract_relationships = task_data.get("extract_relationships", False)
            entity_types = task_data.get("entity_types")

            result = await self.process_document_async(
                text, extract_relationships, entity_types
            )

            # Store in memory if service available
            if self.memory_service and result:
                await self._store_entities_in_memory(result["entities"], text[:100])

            return AgentResult(
                success=True,
                data=result,
                processing_time=float(result.get("processing_time", 0) or 0),
                agent_type=getattr(self, "agent_type", "entity_extractor"),
                metadata={
                    "agent_name": self.name,
                    "entity_count": result.get("entity_count", 0),
                    "model_used": result.get("model_used", "unknown"),
                },
            )

        except Exception as e:
            self.logger.error(f"NER processing failed: {str(e)}")
            return AgentResult(
                success=False,
                error=str(e),
                agent_type=getattr(self, "agent_type", "entity_extractor"),
                metadata={"agent_name": self.name},
            )

    async def process_document_async(
        self,
        text: str,
        extract_relationships: bool = False,
        entity_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Async wrapper for document processing."""
        return self.process_document(text, extract_relationships, entity_types)

    async def _store_entities_in_memory(
        self, entities: List[Dict[str, Any]], context: str
    ):
        """Store extracted entities in memory service."""
        try:
            memory_data = {
                "type": "ner_entities",
                "entities": entities,
                "context": context,
                "timestamp": time.time(),
            }
            await self.memory_service.store_memory("ner_results", memory_data)
        except Exception as e:
            self.logger.warning(f"Failed to store entities in memory: {e}")


class LegalNERPipeline:
    """Pipeline for legal NER processing with multiple models"""

    def __init__(self):
        """Initialize the legal NER pipeline"""
        self.gliner_model = GLiNERModel()
        self.pipeline_loaded = False

    def initialize(self) -> bool:  # noqa: C901
        """Initialize the pipeline

        Returns:
            True if successful
        """
        try:
            self.gliner_model.load_model()
            self.pipeline_loaded = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize legal NER pipeline: {e}")
            return False

    def process_document(
        self, text: str, extract_relationships: bool = False
    ) -> Dict[str, Any]:
        """Process a legal document for entities and optionally relationships

        Args:
            text: Document text
            extract_relationships: Whether to extract entity relationships

        Returns:
            Processing results with entities and optional relationships
        """
        if not self.pipeline_loaded:
            self.initialize()

        ner_result = self.gliner_model.extract_entities(text)

        result = {
            "entities": ner_result.entities,
            "confidence_scores": ner_result.confidence_scores,
            "processing_time": ner_result.processing_time,
            "model_used": ner_result.model_used,
            "entity_count": len(ner_result.entities),
        }

        if extract_relationships:
            relationships = self._extract_entity_relationships(
                ner_result.entities, text
            )
            result["relationships"] = relationships

        return result

    def _extract_entity_relationships(
        self, entities: List[Dict[str, Any]], text: str
    ) -> List[Dict[str, Any]]:
        """Extract relationships between entities

        Args:
            entities: List of extracted entities
            text: Original text

        Returns:
            List of entity relationships
        """
        relationships = []

        for i, entity1 in enumerate(entities):
            for j, entity2 in enumerate(entities[i + 1 :], i + 1):
                distance = abs(entity1["start"] - entity2["start"])
                if distance < 100:
                    relationship = {
                        "entity1": entity1["text"],
                        "entity1_type": entity1["label"],
                        "entity2": entity2["text"],
                        "entity2_type": entity2["label"],
                        "relationship_type": "co_occurrence",
                        "confidence": 0.5,
                        "distance": distance,
                    }
                    relationships.append(relationship)

        return relationships
