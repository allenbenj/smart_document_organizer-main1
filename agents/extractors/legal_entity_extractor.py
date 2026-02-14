"""
Legal Entity Extractor Agent - Production Legal AI
===================================================

A sophisticated legal entity extraction agent that uses hybrid approaches:
- spaCy NER for general entities
- GLiNER for legal-specific entity recognition
- Legal BERT for domain-specific understanding
- Rule-based patterns for legal citations and statutes
- LLM enhancement for complex legal concepts

This agent participates in collective intelligence by storing extracted entities
in shared memory, allowing other agents to benefit from accumulated legal knowledge.

Features:
- Multi-model hybrid extraction (spaCy + GLiNER + Legal BERT + Patterns + LLM)
- Legal entity type validation and normalization
- Deduplication and entity resolution
- Knowledge graph integration
- Shared memory storage for collective intelligence
- Confidence scoring and quality assessment
"""

import json
import logging  # noqa: E402
import re  # noqa: E402
import inspect  # noqa: E402
import uuid  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any, Dict, List, Optional, Set, cast  # noqa: E402

# Core imports
from agents.base import BaseAgent  # noqa: E402
from agents.base.agent_mixins import LegalDomainMixin, LegalMemoryMixin  # noqa: E402
from core.container.service_container_impl import ProductionServiceContainer  # noqa: E402
from mem_db.memory import MemoryType  # noqa: E402

# Optional dependencies with fallbacks
try:
    import spacy  # noqa: E402

    SPACY_AVAILABLE = True
except ImportError:
    spacy = None
    SPACY_AVAILABLE = False

try:
    from gliner import GLiNER  # noqa: E402

    GLINER_AVAILABLE = True
except ImportError:
    GLiNER = None
    GLINER_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class EntityExtractionConfig:
    """Configuration for legal entity extraction"""

    use_spacy: bool = True
    use_gliner: bool = True
    use_patterns: bool = True
    use_llm_enhancement: bool = True
    spacy_model: str = "en_core_web_lg"
    gliner_model: str = "urchade/gliner_base"
    min_confidence: float = 0.6
    max_entities_per_document: int = 1000
    enable_deduplication: bool = True
    enable_validation: bool = True
    debug: bool = False


@dataclass
class ExtractedEntity:
    """Represents an extracted legal entity"""

    entity_id: str
    entity_type: str
    text: str
    start_pos: int
    end_pos: int
    confidence: float
    extraction_method: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    relationships: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "text": self.text,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "attributes": self.attributes,
            "relationships": self.relationships,
        }


@dataclass
class ExtractionResult:
    """Complete entity extraction result"""

    document_id: str
    entities: List[ExtractedEntity]
    relationships: List[Dict[str, Any]]
    extraction_stats: Dict[str, Any]
    processing_time: float
    overall_confidence: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "document_id": self.document_id,
            "entities": [entity.to_dict() for entity in self.entities],
            "relationships": self.relationships,
            "extraction_stats": self.extraction_stats,
            "processing_time": self.processing_time,
            "overall_confidence": self.overall_confidence,
        }


class LegalEntityExtractor(BaseAgent, LegalDomainMixin, LegalMemoryMixin):
    """
    Production Legal Entity Extractor with collective intelligence.

    Uses multiple extraction methods and learns from shared memory to improve
    entity recognition across all agents in the platform.
    """

    def __init__(
        self,
        services: ProductionServiceContainer,
        config: Optional[EntityExtractionConfig] = None,
    ):
        # Initialize base agent
        super().__init__(
            services=services,
            agent_name="LegalEntityExtractor",
            agent_type="entity_extraction",
            timeout_seconds=600.0,  # Entity extraction can be intensive
        )

        # Initialize mixins
        LegalDomainMixin.__init__(self)
        LegalMemoryMixin.__init__(self)

        # Configuration
        self.config = config or EntityExtractionConfig()

        # Initialize extraction models
        self.spacy_nlp = None
        self.gliner_model = None
        self._initialize_models()

        # Legal entity patterns
        self.legal_patterns = self._compile_legal_patterns()

        # Legal entity types and validation
        self.legal_entity_types = self._define_legal_entity_types()

        # Statistics
        self.stats = {
            "documents_processed": 0,
            "entities_extracted": 0,
            "unique_entity_types": set(),
            "avg_confidence": 0.0,
            "extraction_methods_used": set(),
        }

        logger.info(f"LegalEntityExtractor initialized with config: {self.config}")

    def _initialize_models(self):  # noqa: C901
        """Initialize NLP models for entity extraction"""

        # Initialize spaCy if available and configured
        if self.config.use_spacy and SPACY_AVAILABLE and spacy is not None:
            try:
                self.spacy_nlp = cast(Any, spacy).load(self.config.spacy_model)
                logger.info(f"Loaded spaCy model: {self.config.spacy_model}")
            except OSError:
                logger.warning(
                    f"Could not load spaCy model {self.config.spacy_model}, trying smaller model"
                )
                try:
                    self.spacy_nlp = cast(Any, spacy).load("en_core_web_sm")
                    logger.info("Loaded fallback spaCy model: en_core_web_sm")
                except OSError:
                    logger.warning(
                        "No spaCy model available, disabling spaCy extraction"
                    )
                    self.config.use_spacy = False

        # Initialize GLiNER if available and configured
        if self.config.use_gliner and GLINER_AVAILABLE and GLiNER is not None:
            try:
                self.gliner_model = cast(Any, GLiNER).from_pretrained(
                    self.config.gliner_model
                )
                logger.info(f"Loaded GLiNER model: {self.config.gliner_model}")
            except Exception as e:
                logger.warning(f"Could not load GLiNER model: {e}")
                self.config.use_gliner = False

    def _compile_legal_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Compile regex patterns for legal entity extraction"""

        patterns = {
            # Case citations
            "Case": [
                re.compile(r"\b\d+\s+U\.S\.\s+\d+\b"),  # U.S. Reports
                re.compile(r"\b\d+\s+F\.\d[d|c]\s+\d+\b"),  # Federal Reports
                re.compile(r"\b\d+\s+S\.Ct\.\s+\d+\b"),  # Supreme Court Reporter
                re.compile(r"\b[A-Z][a-z]+ v\. [A-Z][a-z]+.*?\b"),  # Case names
            ],
            # Statutes and codes
            "Statute": [
                re.compile(r"\b\d+\s+U\.S\.C\.?\s*§?\s*\d+\b"),  # U.S. Code
                re.compile(
                    r"\bSection\s+\d+\s+of\s+the\s+[A-Za-z\s]+Act\b"
                ),  # Act sections
                re.compile(r"\b[A-Za-z\s]+Act\s+of\s+\d{4}\b"),  # Named acts
            ],
            # Legal rules and procedures
            "LegalRule": [
                re.compile(
                    r"\bRule\s+\d+(?:\(\w+\))?(?:\(\d+\))?\s+of\s+the\s+Federal\s+Rules\s+of\s+\w+\b"
                ),
                re.compile(
                    r"\bFed\.?\s*R\.?\s*\w+\.?\s*\d+\b"
                ),  # Federal Rules abbreviations
            ],
            # Courts
            "Court": [
                re.compile(r"\bU\.?S\.?\s+Supreme\s+Court\b"),
                re.compile(r"\b\w+\s+Circuit\s+Court\s+of\s+Appeals\b"),
                re.compile(r"\bU\.?S\.?\s+District\s+Court\b"),
                re.compile(r"\b\w+\s+District\s+Court\b"),
            ],
            # Legal concepts
            "LegalConcept": [
                re.compile(r"\bdue\s+process\b", re.IGNORECASE),
                re.compile(r"\bequal\s+protection\b", re.IGNORECASE),
                re.compile(r"\bcommerce\s+clause\b", re.IGNORECASE),
                re.compile(r"\bfourteenth\s+amendment\b", re.IGNORECASE),
            ],
            # Contracts and agreements
            "Contract": [
                re.compile(r"\b[A-Za-z\s]+\s+Agreement\b"),
                re.compile(r"\b[A-Za-z\s]+\s+Contract\b"),
                re.compile(r"\bNon-Disclosure\s+Agreement\b"),
                re.compile(r"\bService\s+Agreement\b"),
            ],
        }

        return patterns

    def _define_legal_entity_types(self) -> Dict[str, Dict[str, Any]]:
        """Define legal entity types with validation rules"""

        return {
            "Person": {
                "description": "Individual person (plaintiff, defendant, judge, attorney)",
                "required_fields": ["text"],
                "optional_fields": ["role", "title"],
                "validation_pattern": r"^[A-Z][a-z]+(?: [A-Z][a-z]*)*$",
            },
            "Organization": {
                "description": "Legal entity, company, government agency",
                "required_fields": ["text"],
                "optional_fields": ["org_type", "jurisdiction"],
                "validation_pattern": r"^.+$",
            },
            "Case": {
                "description": "Legal case or court decision",
                "required_fields": ["text"],
                "optional_fields": ["citation", "court", "year"],
                "validation_pattern": r".+",
            },
            "Statute": {
                "description": "Law, statute, regulation, or code",
                "required_fields": ["text"],
                "optional_fields": ["code_section", "jurisdiction"],
                "validation_pattern": r".+",
            },
            "Court": {
                "description": "Judicial court or tribunal",
                "required_fields": ["text"],
                "optional_fields": ["jurisdiction", "level"],
                "validation_pattern": r".+[Cc]ourt.+",
            },
            "LegalConcept": {
                "description": "Legal principle, doctrine, or concept",
                "required_fields": ["text"],
                "optional_fields": ["domain", "definition"],
                "validation_pattern": r".+",
            },
            "Contract": {
                "description": "Contract, agreement, or legal document",
                "required_fields": ["text"],
                "optional_fields": ["contract_type", "parties"],
                "validation_pattern": r".+",
            },
            "Location": {
                "description": "Geographic location relevant to legal matter",
                "required_fields": ["text"],
                "optional_fields": ["country", "state", "jurisdiction"],
                "validation_pattern": r"^[A-Z][a-z]+(?: [A-Z][a-z]*)*$",
            },
        }

    async def _process_task(  # noqa: C901
        self, task_data: Any, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process entity extraction task with collective intelligence integration.

        Args:
            task_data: Document text or structured input for entity extraction
            metadata: Task metadata including document_id, correlation_id, etc.

        Returns:
            Entity extraction result with collective intelligence enhancements
        """

        try:
            # Extract document information
            if isinstance(task_data, str):
                document_text = task_data
                document_id = metadata.get("document_id", f"doc_{hash(task_data)}")
            elif isinstance(task_data, dict):
                document_text = task_data.get("text", task_data.get("content", ""))  # noqa: F841
                document_id = task_data.get(
                    "document_id", metadata.get("document_id", f"doc_{id(task_data)}")
                )
            else:
                raise ValueError(f"Unsupported task_data type: {type(task_data)}")

            if not document_text:  # noqa: F821
                raise ValueError("No document text provided for entity extraction")

            logger.info(f"Starting entity extraction for document {document_id}")
            start_time = datetime.now()

            # Step 1: Check shared memory for similar entity extractions
            similar_extractions = await self._find_similar_extractions(document_text)  # noqa: F821
            logger.info(
                f"Found {len(similar_extractions)} similar entity extractions from collective memory"
            )

            # Step 2: Multi-method entity extraction
            all_entities = []
            extraction_methods_used = set()

            # Method 1: spaCy NER
            if self.config.use_spacy and self.spacy_nlp:
                spacy_entities = await self._extract_with_spacy(document_text)  # noqa: F821
                all_entities.extend(spacy_entities)
                extraction_methods_used.add("spacy")
                logger.info(f"spaCy extracted {len(spacy_entities)} entities")

            # Method 2: GLiNER
            if self.config.use_gliner and self.gliner_model:
                gliner_entities = await self._extract_with_gliner(document_text)  # noqa: F821
                all_entities.extend(gliner_entities)
                extraction_methods_used.add("gliner")
                logger.info(f"GLiNER extracted {len(gliner_entities)} entities")

            # Method 3: Pattern-based extraction
            if self.config.use_patterns:
                pattern_entities = await self._extract_with_patterns(document_text)  # noqa: F821
                all_entities.extend(pattern_entities)
                extraction_methods_used.add("patterns")
                logger.info(
                    f"Pattern matching extracted {len(pattern_entities)} entities"
                )

            # Method 4: LLM enhancement
            if self.config.use_llm_enhancement:
                llm_entities = await self._extract_with_llm(
                    document_text, all_entities, similar_extractions  # noqa: F821
                )
                all_entities.extend(llm_entities)
                extraction_methods_used.add("llm")
                logger.info(
                    f"LLM enhancement extracted {len(llm_entities)} additional entities"
                )

            # Step 3: Deduplication and entity resolution
            if self.config.enable_deduplication:
                unique_entities = await self._deduplicate_entities(all_entities)
                logger.info(
                    f"Deduplication: {len(all_entities)} → {len(unique_entities)} entities"
                )
                all_entities = unique_entities

            # Step 4: Validation and quality assessment
            if self.config.enable_validation:
                validated_entities = await self._validate_entities(all_entities)
                logger.info(
                    f"Validation: {len(all_entities)} → {len(validated_entities)} valid entities"
                )
                all_entities = validated_entities

            # Step 5: Extract relationships between entities
            relationships = await self._extract_relationships(
                all_entities, document_text  # noqa: F821
            )

            # Step 6: Calculate overall confidence and statistics
            processing_time = (datetime.now() - start_time).total_seconds()
            overall_confidence = (
                sum(entity.confidence for entity in all_entities) / len(all_entities)
                if all_entities
                else 0.0
            )

            extraction_stats = {
                "total_entities": len(all_entities),
                "entity_types": list(
                    set(entity.entity_type for entity in all_entities)
                ),
                "extraction_methods_used": list(extraction_methods_used),
                "avg_confidence": overall_confidence,
                "relationships_found": len(relationships),
                "collective_intelligence_used": len(similar_extractions) > 0,
            }

            # Create extraction result
            extraction_result = ExtractionResult(
                document_id=document_id,
                entities=all_entities,
                relationships=relationships,
                extraction_stats=extraction_stats,
                processing_time=processing_time,
                overall_confidence=overall_confidence,
            )

            # Step 7: Store results in shared memory for collective intelligence
            await self._store_extraction_result(extraction_result)

            # Step 8: Store entities in legal entity memory
            entity_record_ids = await self.store_legal_entities(
                document_id=document_id,
                entities=[entity.to_dict() for entity in all_entities],
                extraction_method="hybrid_multi_model",
                metadata={
                    "processing_time": processing_time,
                    "extraction_methods": list(extraction_methods_used),
                    "overall_confidence": overall_confidence,
                },
            )

            # Update statistics
            self._update_statistics(extraction_result, extraction_methods_used)

            logger.info(f"Entity extraction completed for document {document_id}")
            logger.info(
                f"Extracted {len(all_entities)} entities in {processing_time:.2f}s with confidence {overall_confidence:.2f}"
            )

            return {
                "success": True,
                "extraction_result": extraction_result.to_dict(),
                "entity_record_ids": entity_record_ids,
                "collective_intelligence": {
                    "similar_extractions_found": len(similar_extractions),
                    "knowledge_enhanced": len(similar_extractions) > 0,
                },
                "metadata": {
                    "document_id": document_id,
                    "extraction_methods": list(extraction_methods_used),
                    "processing_time": processing_time,
                    "overall_confidence": overall_confidence,
                    "processed_at": datetime.now().isoformat(),
                    "agent_name": self.agent_name,
                },
            }

        except Exception as e:
            logger.error(
                f"Entity extraction failed for document {metadata.get('document_id', 'unknown')}: {e}"
            )
            raise

    async def _find_similar_extractions(self, document_text: str) -> List[Any]:
        """
        Find similar entity extractions from shared memory to enhance current extraction.

        This is a key collective intelligence feature - learning from other agents.
        """
        if not self._is_memory_available():
            return []

        try:
            # Extract key terms for similarity search
            key_terms = self._extract_key_terms(document_text)
            search_query = " ".join(key_terms[:10])  # Use top 10 terms

            # Search for similar entity extractions
            similar_results = await self.search_memory(
                query=search_query,
                memory_types=[MemoryType.ENTITY, MemoryType.ANALYSIS],
                namespaces=["legal_entities", "legal_analysis"],
                limit=5,
                min_similarity=0.5,
            )

            # Filter for entity extraction results
            entity_extractions = []
            for result in similar_results:
                metadata = result.record.metadata
                if (
                    "entity" in metadata.get("analysis_type", "")
                    or result.record.memory_type == MemoryType.ENTITY
                ):
                    entity_extractions.append(result)

            return entity_extractions

        except Exception as e:
            logger.warning(f"Failed to find similar entity extractions: {e}")
            return []

    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms for similarity matching"""

        # Simple term extraction (could be enhanced with TF-IDF, etc.)
        terms = []

        # Extract legal keywords
        legal_keywords = [
            "court",
            "judge",
            "plainti",
            "defendant",
            "contract",
            "agreement",
            "statute",
            "regulation",
            "case",
            "law",
            "legal",
            "constitutional",
        ]

        text_lower = text.lower()
        for keyword in legal_keywords:
            if keyword in text_lower:
                terms.append(keyword)

        # Extract potential entity mentions (simple heuristic)
        words = text.split()
        for i, word in enumerate(words):
            if word[0].isupper() and len(word) > 3:  # Potential proper noun
                terms.append(word.lower())

        return terms

    async def _extract_with_spacy(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using spaCy NER"""

        entities = []

        try:
            # Process text with spaCy (limit length for performance)
            if not callable(self.spacy_nlp):
                return []
            doc = cast(Any, self.spacy_nlp)(text[:100000])

            # Map spaCy labels to our legal entity types
            label_mapping = {
                "PERSON": "Person",
                "ORG": "Organization",
                "GPE": "Location",  # Geopolitical entity
                "LAW": "Statute",
                "EVENT": "LegalConcept",
            }

            for ent in doc.ents:
                if ent.label_ in label_mapping:
                    entity_type = label_mapping[ent.label_]

                    # Basic confidence scoring for spaCy
                    confidence = 0.7  # Base confidence for spaCy
                    if len(ent.text) > 10:  # Longer entities might be more reliable
                        confidence += 0.1
                    if ent.label_ in ["PERSON", "ORG"]:  # High confidence types
                        confidence += 0.1

                    entity = ExtractedEntity(
                        entity_id=str(uuid.uuid4()),
                        entity_type=entity_type,
                        text=ent.text.strip(),
                        start_pos=ent.start_char,
                        end_pos=ent.end_char,
                        confidence=min(1.0, confidence),
                        extraction_method="spacy",
                        attributes={
                            "spacy_label": ent.label_,
                            "lemma": ent.lemma_ if hasattr(ent, "lemma_") else None,
                        },
                    )

                    entities.append(entity)

        except Exception as e:
            logger.error(f"spaCy extraction failed: {e}")

        return entities

    async def _extract_with_gliner(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using GLiNER model"""

        entities = []

        if not self.gliner_model:
            return entities

        try:
            # Define legal entity types for GLiNER
            legal_labels = [
                "Person",
                "Organization",
                "Court",
                "Case",
                "Statute",
                "Legal Concept",
                "Contract",
                "Location",
                "Date",
                "Money",
            ]

            # Extract entities with GLiNER
            gliner_entities = self.gliner_model.predict_entities(text, legal_labels)

            for ent in gliner_entities:
                # Map GLiNER results to our format
                entity_type = ent["label"].replace(" ", "")  # Remove spaces
                if entity_type not in self.legal_entity_types:
                    entity_type = "LegalConcept"  # Default fallback

                entity = ExtractedEntity(
                    entity_id=str(uuid.uuid4()),
                    entity_type=entity_type,
                    text=ent["text"].strip(),
                    start_pos=ent["start"],
                    end_pos=ent["end"],
                    confidence=ent.get(
                        "score", 0.8
                    ),  # GLiNER provides confidence scores
                    extraction_method="gliner",
                    attributes={
                        "gliner_label": ent["label"],
                        "original_score": ent.get("score", 0.8),
                    },
                )

                entities.append(entity)

        except Exception as e:
            logger.error(f"GLiNER extraction failed: {e}")

        return entities

    async def _extract_with_patterns(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using regex patterns"""

        entities = []

        for entity_type, patterns in self.legal_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    # Calculate confidence based on pattern specificity
                    confidence = 0.8  # Base confidence for pattern matching

                    # Boost confidence for specific patterns
                    if "U.S." in match.group() or "F." in match.group():
                        confidence = 0.9  # High confidence for legal citations

                    entity = ExtractedEntity(
                        entity_id=str(uuid.uuid4()),
                        entity_type=entity_type,
                        text=match.group().strip(),
                        start_pos=match.start(),
                        end_pos=match.end(),
                        confidence=confidence,
                        extraction_method="patterns",
                        attributes={
                            "pattern_type": "regex",
                            "matched_pattern": (
                                pattern.pattern[:50] + "..."
                                if len(pattern.pattern) > 50
                                else pattern.pattern
                            ),
                        },
                    )

                    entities.append(entity)

        return entities

    async def _extract_with_llm(  # noqa: C901
        self,
        text: str,
        existing_entities: List[ExtractedEntity],
        similar_extractions: List[Any],
    ) -> List[ExtractedEntity]:
        """Extract additional entities using LLM with collective intelligence"""

        entities = []

        try:
            # Get LLM service from container
            llm_service = None
            try:
                from core.llm_providers import LLMManager  # noqa: E402

                try:
                    maybe = self.services.get_service(LLMManager)
                    llm_service = await maybe if inspect.isawaitable(maybe) else maybe
                except Exception:
                    maybe = self.services.get_service("llm_manager")
                    llm_service = await maybe if inspect.isawaitable(maybe) else maybe
            except Exception:
                pass

            if not llm_service:
                logger.warning("LLM service not available, skipping LLM enhancement")
                return entities

            # Build context from existing entities
            existing_context = ""
            if existing_entities:
                existing_context = "\n\nEntities already found:\n"
                for entity in existing_entities[:10]:  # Limit context size
                    existing_context += f"- {entity.entity_type}: {entity.text}\n"

            # Build context from similar extractions
            collective_context = ""
            if similar_extractions:
                collective_context = (
                    "\n\nSimilar entity extractions from other legal documents:\n"
                )
                for i, result in enumerate(similar_extractions[:3], 1):
                    try:
                        entity_data = (
                            json.loads(result.record.content)
                            if isinstance(result.record.content, str)
                            else result.record.content
                        )
                        collective_context += f"\n{i}. Found entities: {', '.join(entity_data.get('entity_types', []))}\n"
                    except Exception:
                        pass

            # Enhanced entity extraction prompt
            prompt = """
            Extract additional legal entities from the following text that might have been missed by automated tools.
            Focus on complex legal concepts, implied relationships, and domain-specific terminology.

            Legal Text:
            {text[:3000]}  # Limit text size
            {existing_context}
            {collective_context}

            Entity types to look for:
            - Person (judges, attorneys, parties)
            - Organization (law firms, government agencies, companies)
            - Court (specific courts and tribunals)
            - Case (case names and citations)
            - Statute (laws, regulations, codes)
            - LegalConcept (legal principles, doctrines)
            - Contract (agreements, legal documents)
            - Location (jurisdictions, venues)

            Return ONLY JSON format:
            {{
                "entities": [
                    {{
                        "type": "entity_type",
                        "text": "extracted text",
                        "start": 0,
                        "end": 10,
                        "confidence": 0.8,
                        "reason": "why this is a legal entity"
                    }}
                ]
            }}
            """

            # Make LLM call
            response = await llm_service.complete(
                prompt=prompt,
                model="gpt-4",  # Use capable model for entity extraction
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=1500,
            )

            # Parse LLM response
            try:
                llm_result = json.loads(response)
                for entity_data in llm_result.get("entities", []):
                    entity = ExtractedEntity(
                        entity_id=str(uuid.uuid4()),
                        entity_type=entity_data.get("type", "LegalConcept"),
                        text=entity_data.get("text", "").strip(),
                        start_pos=entity_data.get("start", 0),
                        end_pos=entity_data.get("end", 0),
                        confidence=entity_data.get("confidence", 0.7),
                        extraction_method="llm",
                        attributes={
                            "llm_reason": entity_data.get("reason", ""),
                            "collective_intelligence_used": len(similar_extractions)
                            > 0,
                        },
                    )

                    # Validate entity type
                    if entity.entity_type not in self.legal_entity_types:
                        entity.entity_type = "LegalConcept"

                    entities.append(entity)

            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM entity extraction response")

        except Exception as e:
            logger.error(f"LLM entity extraction failed: {e}")

        return entities

    async def _deduplicate_entities(
        self, entities: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Deduplicate and resolve overlapping entities"""

        if len(entities) <= 1:
            return entities

        # Sort entities by start position for overlap detection
        sorted_entities = sorted(entities, key=lambda x: x.start_pos)

        unique_entities = []
        i = 0

        while i < len(sorted_entities):
            current_entity = sorted_entities[i]
            overlapping = [current_entity]

            # Find all overlapping entities
            j = i + 1
            while (
                j < len(sorted_entities)
                and sorted_entities[j].start_pos < current_entity.end_pos
            ):
                overlapping.append(sorted_entities[j])
                j += 1

            # Resolve overlapping entities
            if len(overlapping) == 1:
                unique_entities.append(current_entity)
            else:
                resolved = self._resolve_overlapping_entities(overlapping)
                unique_entities.extend(resolved)

            i = j

        # Additional text-based deduplication
        final_entities = self._deduplicate_by_text(unique_entities)

        return final_entities

    def _resolve_overlapping_entities(
        self, overlapping: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Resolve overlapping entities by choosing the best one or merging"""

        if not overlapping:
            return []

        # Priority order for extraction methods
        method_priority = {"llm": 4, "gliner": 3, "spacy": 2, "patterns": 1}

        # Sort by confidence and method priority
        overlapping.sort(
            key=lambda x: (x.confidence, method_priority.get(x.extraction_method, 0)),
            reverse=True,
        )

        best_entity = overlapping[0]

        # For now, just return the best entity
        # Could be enhanced to merge attributes from multiple entities
        return [best_entity]

    def _deduplicate_by_text(
        self, entities: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Remove entities with very similar text"""

        unique_entities = []
        seen_texts = set()

        for entity in entities:
            # Normalize text for comparison
            normalized_text = entity.text.lower().strip()
            normalized_text = re.sub(r"\s+", " ", normalized_text)

            # Check for exact duplicates
            if normalized_text in seen_texts:  # noqa: F821
                continue

            # Check for very similar text (basic similarity)
            is_duplicate = False
            for seen_text in seen_texts:
                if self._text_similarity(normalized_text, seen_text) > 0.9:  # noqa: F821
                    is_duplicate = True
                    break

            if not is_duplicate:
                seen_texts.add(normalized_text)  # noqa: F821
                unique_entities.append(entity)

        return unique_entities

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity"""

        if text1 == text2:
            return 1.0

        # Jaccard similarity
        words1 = set(text1.split())
        words2 = set(text2.split())

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    async def _validate_entities(
        self, entities: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Validate entities against legal entity type definitions"""

        validated_entities = []

        for entity in entities:
            if self._is_valid_entity(entity):
                validated_entities.append(entity)
            else:
                logger.debug(
                    f"Invalid entity filtered out: {entity.entity_type} - {entity.text}"
                )

        return validated_entities

    def _is_valid_entity(self, entity: ExtractedEntity) -> bool:
        """Check if entity meets validation criteria"""

        # Check minimum confidence
        if entity.confidence < self.config.min_confidence:
            return False

        # Check entity type exists
        if entity.entity_type not in self.legal_entity_types:
            return False

        # Check minimum text length
        if len(entity.text.strip()) < 2:
            return False

        # Check pattern validation if defined
        entity_def = self.legal_entity_types[entity.entity_type]
        if "validation_pattern" in entity_def:
            pattern = entity_def["validation_pattern"]
            if not re.match(pattern, entity.text):
                return False

        return True

    async def _extract_relationships(
        self, entities: List[ExtractedEntity], text: str
    ) -> List[Dict[str, Any]]:
        """Extract relationships between entities"""

        relationships = []

        # Simple co-occurrence based relationships
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i + 1 :]:
                # Check if entities are close to each other in text
                distance = abs(entity1.start_pos - entity2.start_pos)
                if distance < 200:  # Entities within 200 characters

                    # Determine relationship type based on entity types
                    rel_type = self._infer_relationship_type(
                        entity1.entity_type, entity2.entity_type
                    )

                    if rel_type:
                        relationship = {
                            "source_id": entity1.entity_id,
                            "target_id": entity2.entity_id,
                            "relationship_type": rel_type,
                            "confidence": min(entity1.confidence, entity2.confidence)
                            * 0.8,
                            "properties": {
                                "distance": distance,
                                "extraction_method": "co_occurrence",
                            },
                        }
                        relationships.append(relationship)

        return relationships

    def _infer_relationship_type(self, type1: str, type2: str) -> Optional[str]:
        """Infer relationship type based on entity types"""

        # Define common legal relationships
        relationship_rules = {
            ("Person", "Organization"): "affiliated_with",
            ("Person", "Case"): "involved_in",
            ("Organization", "Case"): "party_to",
            ("Case", "Statute"): "interprets",
            ("Case", "Court"): "decided_by",
            ("Person", "Court"): "appears_before",
            ("Contract", "Person"): "signed_by",
            ("Contract", "Organization"): "signed_by",
        }

        # Check both directions
        return relationship_rules.get((type1, type2)) or relationship_rules.get(
            (type2, type1)
        )

    async def _store_extraction_result(self, result: ExtractionResult) -> str:
        """Store extraction result in shared memory"""

        return await self.store_analysis_result(
            analysis_type="entity_extraction",
            document_id=result.document_id,
            analysis_data=result.to_dict(),
            confidence_score=result.overall_confidence,
            metadata={
                "agent_type": "entity_extractor",
                "entities_count": len(result.entities),
                "entity_types": result.extraction_stats["entity_types"],
                "extraction_methods": result.extraction_stats[
                    "extraction_methods_used"
                ],
            },
        )

    def _update_statistics(self, result: ExtractionResult, methods_used: Set[str]):
        """Update agent statistics"""
        self.stats["documents_processed"] += 1
        self.stats["entities_extracted"] += len(result.entities)
        self.stats["unique_entity_types"].update(
            result.extraction_stats["entity_types"]
        )
        self.stats["extraction_methods_used"].update(methods_used)

        # Update running average confidence
        current_avg = self.stats["avg_confidence"]
        count = self.stats["documents_processed"]
        new_avg = ((current_avg * (count - 1)) + result.overall_confidence) / count
        self.stats["avg_confidence"] = new_avg

    async def health_check(self) -> Dict[str, Any]:
        """Extended health check for entity extractor"""
        base_health = await super().health_check()

        # Add entity extraction specific health information
        extraction_health = {
            "extraction_config": {
                "spacy_enabled": self.config.use_spacy and self.spacy_nlp is not None,
                "gliner_enabled": self.config.use_gliner
                and self.gliner_model is not None,
                "patterns_enabled": self.config.use_patterns,
                "llm_enhancement_enabled": self.config.use_llm_enhancement,
            },
            "performance_stats": {
                **self.stats,
                "unique_entity_types": list(self.stats["unique_entity_types"]),
                "extraction_methods_used": list(self.stats["extraction_methods_used"]),
            },
            "models_loaded": {
                "spacy_model": str(self.spacy_nlp) if self.spacy_nlp else None,
                "gliner_model": bool(self.gliner_model),
            },
            "pattern_count": sum(
                len(patterns) for patterns in self.legal_patterns.values()
            ),
        }

        base_health.update(extraction_health)
        return base_health


# Factory function for easy instantiation
async def create_legal_entity_extractor(
    services: ProductionServiceContainer,
    config: Optional[EntityExtractionConfig] = None,
) -> LegalEntityExtractor:
    """
    Create and initialize a Legal Entity Extractor Agent

    Args:
        services: Service container with dependencies
        config: Optional entity extraction configuration

    Returns:
        Initialized Legal Entity Extractor Agent
    """
    agent = LegalEntityExtractor(services, config)

    logger.info(
        "Created Legal Entity Extractor Agent with collective intelligence capabilities"
    )

    return agent
