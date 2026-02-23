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
import os  # noqa: E402
import re  # noqa: E402
import inspect  # noqa: E402
import uuid  # noqa: E402
from pathlib import Path  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any, Dict, List, Optional, Set, Tuple, cast  # noqa: E402

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

try:
    from transformers import (  # noqa: E402
        AutoModelForTokenClassification,
        AutoTokenizer,
        pipeline as transformers_pipeline,
    )

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    AutoModelForTokenClassification = None
    AutoTokenizer = None
    transformers_pipeline = None
    TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class EntityExtractionConfig:
    """Configuration for legal entity extraction"""

    use_spacy: bool = True
    use_gliner: bool = True
    use_patterns: bool = True
    use_llm_enhancement: bool = True
    use_hf_ner: bool = True
    spacy_model: str = "en_core_web_lg"
    gliner_model: str = "urchade/gliner_medium-v2.1"
    hf_ner_model: str = "dslim/bert-base-NER"
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
        self.hf_ner_pipeline = None
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
                model_ref = self._resolve_local_model_ref(
                    preferred=self.config.gliner_model,
                    candidates=["gliner_zero_shot", "gliner", "gliner_medium-v2.1", "gliner_large-v2.1"],
                )
                self.gliner_model = cast(Any, GLiNER).from_pretrained(model_ref)
                logger.info(f"Loaded GLiNER model: {model_ref}")
            except Exception as e:
                logger.warning(f"Could not load GLiNER model: {e}")
                self.config.use_gliner = False

        # Initialize HuggingFace token-classification NER pipelines.
        if (
            self.config.use_hf_ner
            and TRANSFORMERS_AVAILABLE
            and AutoTokenizer is not None
            and AutoModelForTokenClassification is not None
            and transformers_pipeline is not None
        ):
            self.hf_pipelines = {}
            # Initialize BART-large-NER (High Fidelity)
            try:
                bart_ref = self._resolve_local_model_ref(
                    preferred="facebook/bart-large-ner",
                    candidates=["bart-large-NER"]
                )
                self.hf_pipelines["bart"] = transformers_pipeline(
                    "token-classification",
                    model=bart_ref,
                    tokenizer=bart_ref,
                    aggregation_strategy="simple",
                )
                logger.info(f"Loaded BART-large-NER from: {bart_ref}")
            except Exception as e:
                logger.warning(f"Could not load BART NER: {e}")

            # Initialize REBEL for Relation Extraction
            try:
                rebel_ref = self._resolve_local_model_ref(
                    preferred="Babelscape/rebel-large",
                    candidates=["rebel-large"]
                )
                # Do not pass `trust_remote_code` through model_kwargs here.
                # Newer transformers pipeline forwards trust/code kwargs internally
                # into AutoConfig.from_pretrained(...), and duplicating them via
                # model_kwargs causes: "got multiple values for keyword argument
                # 'trust_remote_code'".
                self.rebel_pipeline = transformers_pipeline(
                    "text2text-generation",
                    model=rebel_ref,
                    tokenizer=rebel_ref,
                )
                logger.info(f"Loaded REBEL Relationship Extraction from: {rebel_ref}")
            except Exception as e:
                logger.warning(f"Could not load REBEL: {e}. Relationship extraction will use co-occurrence fallback.")
                self.rebel_pipeline = None

            # Initialize BERT baseline
            try:
                model_ref = self._resolve_local_model_ref(
                    preferred=self.config.hf_ner_model,
                    candidates=[
                        "distilbert-NER",
                        "bert-base-NER",
                        "bert-large-NER",
                        "bert-legal",
                        "bert-legal-uncased",
                        "deberta-v3-large",
                    ],
                )
                self.hf_ner_pipeline = transformers_pipeline(
                    "token-classification",
                    model=model_ref,
                    tokenizer=model_ref,
                    aggregation_strategy="simple",
                )
                self.hf_pipelines["bert"] = self.hf_ner_pipeline
                logger.info("Loaded HF BERT NER model: %s", model_ref)
            except Exception as e:
                logger.warning("Could not load HF BERT NER model: %s", e)
                if not self.hf_pipelines:
                    self.config.use_hf_ner = False

    @staticmethod
    def _model_roots() -> List[Path]:
        """Resolve local model roots, preferring configured model directories."""
        roots: List[Path] = []
        env_value = (
            os.getenv("SDO_MODEL_DIR")
            or os.getenv("MODEL_DIR")
            or r"E:\Project\smart_document_organizer-main\models"
        )
        candidates = [env_value]
        # Support WSL/Linux execution when a Windows path is provided.
        if len(env_value) > 2 and env_value[1:3] == ":\\":
            drive = env_value[0].lower()
            tail = env_value[2:].replace("\\", "/").lstrip("/")
            candidates.append(f"/mnt/{drive}/{tail}")
        for raw in candidates:
            try:
                p = Path(raw)
                if p.exists() and p.is_dir():
                    roots.append(p)
            except Exception:
                continue
        try:
            repo_root = Path(__file__).resolve().parents[2]
            fallback = repo_root / "models"
            if fallback.exists() and fallback.is_dir():
                roots.append(fallback)
        except Exception:
            pass
        # Keep order, remove duplicates.
        unique: List[Path] = []
        seen = set()
        for root in roots:
            key = str(root.resolve()) if root.exists() else str(root)
            if key not in seen:
                seen.add(key)
                unique.append(root)
        return unique

    @staticmethod
    def _resolve_local_model_ref(preferred: str, candidates: List[str]) -> str:
        """Prefer local model directory under ./models when available."""
        for root in LegalEntityExtractor._model_roots():
            for name in candidates:
                p = root / name
                if p.exists() and p.is_dir():
                    # GLiNER cache layouts often store real artifacts under snapshots/<hash>/.
                    snapshots = p / "snapshots"
                    if snapshots.exists() and snapshots.is_dir():
                        for sub in sorted(snapshots.iterdir()):
                            if not sub.is_dir():
                                continue
                            if (
                                (sub / "gliner_config.json").exists()
                                and (sub / "pytorch_model.bin").exists()
                            ):
                                return str(sub)
                    return str(p)
        return preferred

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
        """Define legal entity types with ontology-first validation rules."""
        types: Dict[str, Dict[str, Any]] = {}

        # Core contract: ontology labels are the primary source of entity types.
        try:
            from agents.extractors.ontology import LegalEntityType

            for et in LegalEntityType:
                canonical = str(et.value.label).replace(" ", "")
                attrs = list(getattr(et.value, "attributes", []) or [])
                types[canonical] = {
                    "description": str(getattr(et.value, "prompt_hint", "") or f"Ontology entity: {canonical}"),
                    "required_fields": ["text"],
                    "optional_fields": attrs,
                    "validation_pattern": r".+",
                }
        except Exception:
            logger.warning("Ontology types unavailable in LegalEntityExtractor; using fallback core types")

        # Extensions remain supported, but ontology stays the baseline contract.
        extras = {
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
                "validation_pattern": r".+",
            },
        }
        for k, v in extras.items():
            types.setdefault(k, v)

        # Hard fallback in case ontology import failed.
        if not types:
            types = {
                "Person": {"description": "Individual person", "required_fields": ["text"], "optional_fields": ["role"], "validation_pattern": r".+"},
                "Organization": {"description": "Legal entity or agency", "required_fields": ["text"], "optional_fields": ["jurisdiction"], "validation_pattern": r".+"},
                "Case": {"description": "Legal case", "required_fields": ["text"], "optional_fields": ["citation"], "validation_pattern": r".+"},
                "Statute": {"description": "Law or code", "required_fields": ["text"], "optional_fields": ["code_section"], "validation_pattern": r".+"},
            }

        return types

    def _canonical_entity_type(self, raw_label: str) -> Optional[str]:
        """Map incoming labels to a known canonical entity type key."""
        if not raw_label:
            return None
        normalized = re.sub(r"[^a-z0-9]+", "", str(raw_label).strip().lower())
        if not normalized:
            return None
        for canonical in self.legal_entity_types.keys():
            ck = re.sub(r"[^a-z0-9]+", "", str(canonical).strip().lower())
            if ck == normalized:
                return canonical
        return None

    def _requested_entity_types(self, metadata: Dict[str, Any]) -> Optional[Set[str]]:
        """Resolve requested filter labels into canonical entity type keys."""
        requested = metadata.get("entity_types")
        if not isinstance(requested, list) or not requested:
            return None
        out: Set[str] = set()
        for item in requested:
            canonical = self._canonical_entity_type(str(item))
            if canonical:
                out.add(canonical)
        return out or None

    @staticmethod
    def _requested_extraction_model(metadata: Dict[str, Any]) -> str:
        value = str(metadata.get("extraction_model", "auto") or "auto").strip().lower()
        aliases = {
            "hf ner": "hf_ner",
            "hf_ner": "hf_ner",
            "gliner": "gliner",
            "spacy": "spacy",
            "patterns": "patterns",
            "llm": "llm",
            "auto": "auto",
            "hybrid": "auto",
        }
        return aliases.get(value, "auto")

    async def _process_task(  # noqa: C901
        self, task_data: Any, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process entity extraction task with collective intelligence and Memory Anchoring.
        """

        try:
            # Extract document information
            if isinstance(task_data, str):
                document_text = task_data
                document_id = metadata.get("document_id", f"doc_{hash(task_data)}")
            elif isinstance(task_data, dict):
                document_text = task_data.get("text", task_data.get("content", ""))
                document_id = task_data.get(
                    "document_id", metadata.get("document_id", f"doc_{id(task_data)}")
                )
            else:
                raise ValueError(f"Unsupported task_data type: {type(task_data)}")

            if not document_text:
                raise ValueError("No document text provided for entity extraction")

            logger.info(f"Starting entity extraction for document {document_id}")
            start_time = datetime.now()

            # Step 1: Memory Bootstrap - Retrieve Ground Truth from Knowledge Graph
            all_entities = []
            similar_extractions = await self._find_similar_extractions(document_text)
            
            # Find entities already verified by the expert
            anchors = []
            for result in similar_extractions:
                if result.record.metadata.get("expert_verified") is True:
                    # Capture name and type from ground truth
                    name = result.record.key.split("_")[-1] # Simple heuristic for entity name
                    etype = result.record.metadata.get("entity_type")
                    if name and etype and name in document_text:
                        # Auto-extract based on verified anchor
                        matches = re.finditer(re.escape(name), document_text)
                        for m in matches:
                            anchors.append(ExtractedEntity(
                                entity_id=str(uuid.uuid4()),
                                entity_type=etype,
                                text=name,
                                start_pos=m.start(),
                                end_pos=m.end(),
                                confidence=1.0, # Ground truth
                                extraction_method="memory_anchor",
                                attributes={"expert_verified": True}
                            ))
            
            if anchors:
                logger.info(f"Bootstrapped {len(anchors)} entities from Expert Ground Truth")
                all_entities.extend(anchors)

            # Step 2: Multi-method entity extraction
            extraction_methods_used = set(e.extraction_method for e in all_entities)
            requested_types = self._requested_entity_types(metadata)
            requested_model = self._requested_extraction_model(metadata)

            # Method 1: spaCy NER
            if (
                requested_model in {"auto", "spacy"}
                and self.config.use_spacy
                and self.spacy_nlp
            ):
                spacy_entities = await self._extract_with_spacy(document_text)  # noqa: F821
                all_entities.extend(spacy_entities)
                extraction_methods_used.add("spacy")
                logger.info(f"spaCy extracted {len(spacy_entities)} entities")

            # Method 2: GLiNER
            if (
                requested_model in {"auto", "gliner"}
                and self.config.use_gliner
                and self.gliner_model
            ):
                gliner_entities = await self._extract_with_gliner(document_text)  # noqa: F821
                all_entities.extend(gliner_entities)
                extraction_methods_used.add("gliner")
                logger.info(f"GLiNER extracted {len(gliner_entities)} entities")

            # Method 3: Pattern-based extraction
            if requested_model in {"auto", "patterns"} and self.config.use_patterns:
                pattern_entities = await self._extract_with_patterns(document_text)  # noqa: F821
                all_entities.extend(pattern_entities)
                extraction_methods_used.add("patterns")
                logger.info(
                    f"Pattern matching extracted {len(pattern_entities)} entities"
                )

            # Method 4: HF NER fallback/augmentation
            if (
                requested_model in {"auto", "hf_ner"}
                and self.config.use_hf_ner
                and self.hf_ner_pipeline
            ):
                hf_entities = await self._extract_with_hf_ner(document_text)
                all_entities.extend(hf_entities)
                extraction_methods_used.add("hf_ner")
                logger.info("HF NER extracted %s entities", len(hf_entities))

            # Method 5: LLM enhancement
            if (
                requested_model in {"auto", "llm"}
                and self.config.use_llm_enhancement
            ):
                llm_entities = await self._extract_with_llm(
                    document_text, all_entities, similar_extractions, metadata
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

            if requested_types:
                before = len(all_entities)
                all_entities = [
                    e for e in all_entities if e.entity_type in requested_types
                ]
                logger.info(
                    "Applied requested ontology type filter: %s -> %s entities",
                    before,
                    len(all_entities),
                )

            # Step 6: Extract relationships between entities
            relationships = await self._extract_relationships(
                all_entities, document_text  # noqa: F821
            )

            # Step 7: Calculate overall confidence and statistics
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

            # Step 8: Store results in shared memory for collective intelligence
            await self._store_extraction_result(extraction_result)

            # Step 9: Store entities as Proposals for Expert Review
            entity_record_ids = await self._propose_legal_entities(
                document_id=document_id,
                entities=all_entities,
                extraction_methods=list(extraction_methods_used)
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
        Find similar entity extractions from shared memory, prioritizing expert-verified ones.
        """
        if not self._is_memory_available():
            return []

        try:
            # Extract key terms for similarity search
            key_terms = self._extract_key_terms(document_text)
            search_query = " ".join(key_terms[:10])

            # Search for similar entity extractions
            similar_results = await self.search_memory(
                query=search_query,
                memory_types=[MemoryType.ENTITY, MemoryType.ANALYSIS],
                namespaces=["legal_entities", "legal_analysis"],
                limit=10, # Get more to allow filtering for verified ones
                min_similarity=0.5,
            )

            # Separate into verified and unverified
            verified = []
            unverified = []
            for result in similar_results:
                metadata = result.record.metadata
                if (
                    "entity" in metadata.get("analysis_type", "")
                    or result.record.memory_type == MemoryType.ENTITY
                ):
                    if metadata.get("expert_verified") is True:
                        verified.append(result)
                    else:
                        unverified.append(result)

            # Prioritize verified ones in the final list
            return verified + unverified

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
        """Extract entities using the Multi-Task GLiNER Oracle."""
        entities = []
        if not self.gliner_model:
            return entities

        try:
            # High-Resolution Label Mapping
            label_map = {}
            try:
                from agents.extractors.ontology import LegalEntityType
                for et in LegalEntityType:
                    label_map[et.value.label] = str(et.value.label).replace(" ", "")
            except Exception:
                for k in self.legal_entity_types.keys():
                    label_map[k] = k

            legal_labels = list(label_map.keys())
            
            # Process in high-fidelity chunks (1024 chars for GLiNER)
            max_chunk = 1024
            chunks = [text[i : i + max_chunk] for i in range(0, len(text), max_chunk)]
            
            for i, chunk in enumerate(chunks):
                offset = i * max_chunk
                gliner_entities = self.gliner_model.predict_entities(chunk, legal_labels, threshold=self.config.min_confidence)
                
                for ent in gliner_entities:
                    raw_label = ent.get("label", "")
                    text = ent["text"].strip()
                    start = ent["start"]
                    end = ent["end"]
                    
                    # 1. Natural Boundary Check: Extraction must be a whole word
                    # Check character BEFORE start
                    if start > 0:
                        char_before = chunk[start-1]
                        if char_before.isalnum(): # If it's a letter/number, this is a fragment
                            continue
                    
                    # Check character AFTER end
                    if end < len(chunk):
                        char_after = chunk[end]
                        if char_after.isalnum(): # If it's a letter/number, this is a fragment
                            continue
    
                    # 2. Fragment Shield: Reject known noise tokens
                    noise_blacklist = {"rose", "cut", "ion", "bol", "ster", "me", "ift", "our", "teen", "fa", "ls", "eh", "ood", "dant", "fu", "rth", "er"}
                    if text.lower() in noise_blacklist or len(text) < 3:
                        continue
                        
                    canonical_type = label_map.get(raw_label) or self._canonical_entity_type(raw_label)
                    
                    if canonical_type:
                        entities.append(ExtractedEntity(
                            entity_id=str(uuid.uuid4()),
                            entity_type=canonical_type,
                            text=text,
                            start_pos=start + offset,
                            end_pos=end + offset,
                            confidence=float(ent.get("score", 0.8)),
                            extraction_method="gliner_multi_task",
                            attributes={"raw_label": raw_label}
                        ))
            
            # 2. Span Re-stitching: Merge adjacent fragments of the same type
            entities = self._restitch_shredded_spans(entities)
            logger.info(f"GLiNER Multi-Task Oracle found {len(entities)} entities")

        except Exception as e:
            logger.error(f"GLiNER Oracle failed: {e}")

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

    async def _extract_with_hf_ner(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using the HuggingFace ensemble (BART, BERT, etc.)"""
        if not self.config.use_hf_ner or not hasattr(self, "hf_pipelines"):
            return []

        all_hf_entities = []
        label_mapping = {
            "PER": "Person", "PERSON": "Person", "ORG": "Organization",
            "LOC": "Location", "GPE": "Location", "MISC": "LegalConcept",
        }
        
        for name, pipeline in self.hf_pipelines.items():
            try:
                # Process in chunks if text is long
                max_chunk = 512
                chunks = [text[i : i + max_chunk] for i in range(0, len(text), max_chunk)]
                
                for chunk_idx, chunk in enumerate(chunks):
                    try:
                        offset = chunk_idx * max_chunk
                        results = pipeline(chunk)
                        
                        for res in results:
                            raw_label = str(res.get("entity_group") or res.get("entity") or "").upper()
                            ctype = label_mapping.get(raw_label)
                            if ctype:
                                all_hf_entities.append(ExtractedEntity(
                                    entity_id=str(uuid.uuid4()),
                                    entity_type=ctype,
                                    text=res["word"].replace("##", "").strip(),
                                    start_pos=res["start"] + offset,
                                    end_pos=res["end"] + offset,
                                    confidence=float(res["score"]),
                                    extraction_method=f"hf_{name}",
                                    attributes={"model": name, "hf_label": raw_label}
                                ))
                    except Exception as chunk_err:
                        logger.debug(f"HF pipeline '{name}' failed on chunk {chunk_idx}: {chunk_err}")
                        continue
            except Exception as e:
                logger.warning(f"HF pipeline '{name}' critically failed: {e}")
        return all_hf_entities

    async def _extract_with_llm(
        self,
        text: str,
        existing_entities: List[ExtractedEntity],
        similar_extractions: List[Any],
        metadata: Dict[str, Any],
    ) -> List[ExtractedEntity]:
        """Extract additional entities using LLM with collective intelligence, prioritizing expert truth."""
        entities = []
        try:
            # Resolve LLM Service
            llm_service = None
            try:
                from core.llm_providers import LLMManager
                maybe = self.services.get_service(LLMManager)
                llm_service = await maybe if inspect.isawaitable(maybe) else maybe
            except Exception:
                maybe = self.services.get_service("llm_manager")
                llm_service = await maybe if inspect.isawaitable(maybe) else maybe

            if not llm_service:
                logger.warning("LLM service not available, skipping LLM enhancement")
                return entities

            # Build collective context with Expert Truth priority
            verified_context = ""
            general_context = ""
            
            for i, result in enumerate(similar_extractions):
                try:
                    content = result.record.content
                    entity_data = json.loads(content) if isinstance(content, str) else content
                    if isinstance(entity_data, dict) and "extraction_result" in entity_data:
                        entity_data = entity_data["extraction_result"]
                    
                    labels = entity_data.get("entity_types") or [e.get("type") for e in entity_data.get("entities", [])]
                    summary = f"({', '.join(filter(None, labels))})"
                    
                    if result.record.metadata.get("expert_verified") is True:
                        verified_context += f"\n- [VERIFIED TRUTH]: {summary}"
                    else:
                        general_context += f"\n- [COLLECTIVE]: {summary}"
                except Exception as exc:
                    logger.warning(
                        "Skipping malformed similar extraction at index=%s: %s",
                        i,
                        exc,
                    )

            # Build Local Context
            local_context = ""
            if existing_entities:
                local_context = "\nAlready found by local models: " + ", ".join([f"{e.entity_type}:{e.text}" for e in existing_entities[:15]])

            # USE THE ROBUST ONTOLOGY PROMPT
            from agents.extractors.ontology import get_extraction_prompt
            base_instructions = get_extraction_prompt()

            prompt = f"""
            {base_instructions}
            
            IMPORTANT: Use the following [VERIFIED TRUTH] examples as high-confidence guidance for your reasoning. 
            They represent manual corrections made by a legal expert.

            COLLECTIVE INTELLIGENCE (Past Examples):
            {verified_context if verified_context else "None available yet."}
            {general_context}

            LOCAL CONTEXT:
            {local_context}

            Legal Text to Analyze:
            \"\"\"{text[:4000]}\"\"\"

            Return your findings in the following JSON format:
            {{
                "entities": [
                    {{
                        "type": "entity_type_label",
                        "text": "verbatim text",
                        "start_char": 0,
                        "end_char": 10,
                        "confidence": 0.95,
                        "reason": "why this matches the ontology and verified patterns"
                    }}
                ]
            }}
            """

            response = await llm_service.complete(
                prompt=prompt, 
                model="gpt-4",
                temperature=0.1,
                max_tokens=2000
            )
            
            # Parse and validate against canonical types
            try:
                raw_json = str(response).strip()
                if "```" in raw_json: raw_json = raw_json.split("```")[1].replace("json", "").strip()
                data = json.loads(raw_json)
                for ent in data.get("entities", []):
                    ctype = self._canonical_entity_type(ent.get("type"))
                    if ctype:
                        entities.append(ExtractedEntity(
                            entity_id=str(uuid.uuid4()),
                            entity_type=ctype,
                            text=ent["text"],
                            start_pos=int(ent.get("start_char", ent.get("start", 0))),
                            end_pos=int(ent.get("end_char", ent.get("end", 0))),
                            confidence=float(ent.get("confidence", 0.7)),
                            extraction_method="llm",
                            attributes={
                                "llm_reason": ent.get("reason", ""), 
                                "ontology_aligned": True,
                                "collective_intelligence_used": bool(similar_extractions),
                                "guided_by_expert_truth": bool(verified_context)
                            }
                        ))
            except Exception as e:
                logger.warning(f"LLM Parse Error: {e}")

        except Exception as e:
            logger.error(f"LLM Extraction logic failure: {e}")
        return entities

    def _restitch_shredded_spans(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Merges adjacent fragments (e.g. 'wi' + 'ness' -> 'witness') into single entities."""
        if not entities:
            return []
            
        # Sort by start position
        sorted_ents = sorted(entities, key=lambda x: x.start_pos)
        merged = []
        
        if not sorted_ents:
            return []
            
        current = sorted_ents[0]
        
        for next_ent in sorted_ents[1:]:
            # If they are very close (0-2 chars) and have the same type, merge them
            gap = next_ent.start_pos - current.end_pos
            if gap <= 2 and next_ent.entity_type == current.entity_type:
                # Update current with combined text and new end position
                current.text = current.text + next_ent.text
                current.end_pos = next_ent.end_pos
                current.confidence = (current.confidence + next_ent.confidence) / 2
            else:
                merged.append(current)
                current = next_ent
                
        merged.append(current)
        return merged

    async def _deduplicate_entities(
        self, entities: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Aggressive deduplication: If entities overlap, the longest one always wins."""
        if len(entities) <= 1:
            return entities

        # Sort by start position, then by length (longest first)
        sorted_entities = sorted(entities, key=lambda x: (x.start_pos, -(x.end_pos - x.start_pos)))

        unique_entities = []
        
        for current in sorted_entities:
            is_fragment = False
            for existing in unique_entities:
                # Check for overlap
                if (current.start_pos < existing.end_pos and current.end_pos > existing.start_pos):
                    # Overlap detected. Since we sorted by length, 'existing' is better.
                    is_fragment = True
                    break
            
            if not is_fragment:
                unique_entities.append(current)

        return unique_entities

    def _resolve_overlapping_entities(
        self, overlapping: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Resolve overlapping entities by choosing the best one or merging"""

        if not overlapping:
            return []

        # Priority order for extraction methods
        method_priority = {"llm": 4, "gliner": 3, "spacy": 2, "hf_ner": 1.5, "patterns": 1}

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
        """
        High-Resolution Validation: Rejects 'Mad Lib' abstract nouns.
        Every entity must be specific or anchored to a proper noun.
        """
        # Phase 1 Stoplist: Reject non-specific roles masquerading as insight
        stoplist = {"defendant", "witness", "judge", "case", "law", "court", "matter", "proceeding", "regulation", "prosecutor", "officer"}
        
        text_lower = entity.text.lower().strip()
        
        # 1. Reject if the entity is JUST a stoplist word
        if text_lower in stoplist:
            return False

        # 2. Minimum confidence and length
        if entity.confidence < self.config.min_confidence or len(text_lower) < 2:
            return False

        # 3. Check entity type exists
        if entity.entity_type not in self.legal_entity_types:
            return False

        # 4. Pattern validation (e.g., for citations)
        entity_def = self.legal_entity_types[entity.entity_type]
        if "validation_pattern" in entity_def:
            pattern = entity_def["validation_pattern"]
            if not re.match(pattern, entity.text):
                return False

        return True

    async def _extract_relationships(
        self, entities: List[ExtractedEntity], text: str
    ) -> List[Dict[str, Any]]:
        """Extract relationships between entities using REBEL and co-occurrence."""
        relationships = []
        
        # 1. High-Fidelity REBEL Extraction
        if hasattr(self, "rebel_pipeline") and self.rebel_pipeline:
            try:
                # REBEL works best on smaller chunks
                max_chunk = 512
                chunks = [text[i : i + max_chunk] for i in range(0, len(text), max_chunk)]
                
                for chunk in chunks:
                    # REBEL outputs triplets in a special string format
                    gen_kwargs = {"max_length": 128, "length_penalty": 0, "num_beams": 3, "early_stopping": True}
                    out = self.rebel_pipeline(chunk, **gen_kwargs)
                    extracted_text = out[0]["generated_text"]
                    
                    # Parse REBEL triplets: <obj> subject <rel> relation <subj> object
                    triplets = self._parse_rebel_output(extracted_text)
                    for subj, rel, obj in triplets:
                        # Match REBEL text to our extracted entities
                        s_ent = next((e for e in entities if subj.lower() in e.text.lower()), None)
                        o_ent = next((e for e in entities if obj.lower() in e.text.lower()), None)
                        
                        if s_ent and o_ent:
                            relationships.append({
                                "source_id": s_ent.entity_id,
                                "target_id": o_ent.entity_id,
                                "relationship_type": rel.upper().replace(" ", "_"),
                                "confidence": 0.9,
                                "properties": {"extraction_method": "rebel", "raw_relation": rel}
                            })
            except Exception as e:
                logger.warning(f"REBEL extraction failed: {e}")

        # 2. Fallback to co-occurrence if list is still small
        if len(relationships) < 5:
            for i, entity1 in enumerate(entities):
                for entity2 in entities[i + 1 :]:
                    distance = abs(entity1.start_pos - entity2.start_pos)
                    if distance < 150: 
                        rel_type = self._infer_relationship_type(entity1.entity_type, entity2.entity_type)
                        if rel_type:
                            relationships.append({
                                "source_id": entity1.entity_id,
                                "target_id": entity2.entity_id,
                                "relationship_type": rel_type,
                                "confidence": min(entity1.confidence, entity2.confidence) * 0.7,
                                "properties": {"distance": distance, "extraction_method": "co_occurrence"}
                            })

        return relationships

    def _parse_rebel_output(self, text: str) -> List[Tuple[str, str, str]]:
        """Parse the special tokenized output of REBEL into (subj, rel, obj) triplets."""
        triplets = []
        relation, subject, object_ = '', '', ''
        text = text.strip()
        current = 'x'
        for token in text.replace("<s>", "").replace("</s>", "").split():
            if token == "<triplet>":
                current = 't'
                if relation:
                    triplets.append((subject.strip(), relation.strip(), object_.strip()))
                    relation, subject, object_ = '', '', ''
                subject = ''
            elif token == "<subj>":
                current = 's'
                if relation:
                    triplets.append((subject.strip(), relation.strip(), object_.strip()))
                    relation, subject, object_ = '', '', ''
                object_ = ''
            elif token == "<obj>":
                current = 'o'
                object_ = ''
            else:
                if current == 't': subject += ' ' + token
                elif current == 's': object_ += ' ' + token
                elif current == 'o': relation += ' ' + token
        if relation:
            triplets.append((subject.strip(), relation.strip(), object_.strip()))
        return triplets

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

    async def _propose_legal_entities(self, document_id: str, entities: List[ExtractedEntity], extraction_methods: List[str]) -> List[int]:
        """Save extracted entities as proposals for expert review, skipping already verified ones."""
        from mem_db.memory import proposals_db
        proposal_ids = []
        
        for entity in entities:
            # SKIP if this entity was already verified (don't propose what is already known)
            if entity.extraction_method == "memory_anchor" or entity.attributes.get("expert_verified"):
                continue
                
            try:
                proposal_data = {
                    "namespace": "legal_entities",
                    "key": f"entity_{document_id}_{entity.entity_id}",
                    "content": json.dumps(entity.to_dict()),
                    "memory_type": "entity",
                    "agent_id": self.agent_name,
                    "document_id": document_id,
                    "metadata": {
                        "entity_type": entity.entity_type,
                        "extraction_method": entity.extraction_method,
                        "original_text": entity.text
                    },
                    "confidence_score": entity.confidence,
                    "importance_score": 0.7,
                    "status": "pending",
                    "created_at": datetime.now().isoformat()
                }
                pid = proposals_db.add_proposal(proposal_data)
                proposal_ids.append(pid)
            except Exception as e:
                logger.error(f"Failed to propose entity {entity.text}: {e}")
                
        return proposal_ids

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
                "hf_ner_enabled": self.config.use_hf_ner
                and self.hf_ner_pipeline is not None,
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
                "hf_ner_model": bool(self.hf_ner_pipeline),
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
