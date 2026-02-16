"""
Production Hybrid Extractor Agent
=================================

A production-grade hybrid entity extraction agent that combines multiple extraction methods:
- SpaCy NER models
- Transformer-based models (BERT, Legal-BERT)
- Pattern-based extraction 
- TF-IDF similarity matching

Integrated with the Legal AI platform's service container architecture for production use.
"""

import asyncio
import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Production imports
from ..base_agent import BaseAgent, AgentResult, AgentStatus, TaskPriority
from ...config.core.service_container import ServiceContainer

# Optional ML dependencies with fallbacks
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None

try:
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    torch = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ExtractionResult:
    method_name: str
    entities: List[Dict[str, Any]]
    confidence_score: float
    processing_time: float
    metadata: Dict[str, Any]

@dataclass
class HygridExtractionResult:
    merged_entities: List[Dict[str, Any]]
    extraction_methods_used: List[str]
    overall_confidence: float
    consensus_score: float
    processing_time_total: float
    method_results: List[ExtractionResult]
    quality_metrics: Dict[str, float]

@dataclass
class EntityCandidate:
    text: str
    entity_type: str
    start_pos: int
    end_pos: int
    confidence: float
    source_method: str
    context: str
    attributes: Dict[str, Any]

class HybridExtractorAgent(BaseAgent):
    """Production Hybrid Extractor Agent integrated with service container architecture."""
    
    def __init__(self, services: ServiceContainer):
        super().__init__(services, "HybridExtractorAgent")
        self.config = {}
        self.spacy_models = {}
        self.transformer_models = {}
        self.pattern_extractors = {}
        self.tfidf_vectorizer = None
        self.entity_patterns = self._load_legal_patterns()
        self.is_initialized = False
        self.memory_service = services.get_optional_service("memory_manager")
        
    async def _process_task(self, task_data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> AgentResult:
        """Main processing method for BaseAgent integration."""
        try:
            text = task_data.get("text", "")
            if not text:
                raise ValueError("No text provided for hybrid extraction")

            entity_types = task_data.get("entity_types")
            confidence_threshold = task_data.get("confidence_threshold", 0.5)
            
            result = await self.extract_entities_hygrid(text, entity_types, confidence_threshold)
            
            # Store results in memory if service available
            if self.memory_service and result:
                await self._store_extraction_results(result, text[:100])
            
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data=asdict(result),
                metadata={
                    "agent_name": self.name,
                    "entity_count": len(result.merged_entities),
                    "methods_used": result.extraction_methods_used,
                    "overall_confidence": result.overall_confidence,
                    "processing_time": result.processing_time_total
                }
            )
            
        except Exception as e:
            self.logger.error(f"Hybrid extraction failed: {str(e)}")
            return AgentResult(
                status=AgentStatus.FAILURE,
                data={"error": str(e)},
                metadata={"agent_name": self.name}
            )

    async def _store_extraction_results(self, result: 'HygridExtractionResult', context: str):
        """Store extraction results in memory service."""
        try:
            memory_data = {
                "type": "hybrid_extraction",
                "entities": result.merged_entities,
                "methods_used": result.extraction_methods_used,
                "confidence": result.overall_confidence,
                "context": context,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await self.memory_service.store_memory("hybrid_extraction_results", memory_data)
        except Exception as e:
            self.logger.warning(f"Failed to store extraction results in memory: {e}")

class LegacyHygridExtractorAgent:
    """Legacy wrapper for backward compatibility."""
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.spacy_models = {}
        self.transformer_models = {}
        self.pattern_extractors = {}
        self.tfidf_vectorizer = None
        self.entity_patterns = self._load_legal_patterns()
        self.is_initialized = False

    async def initialize(self):
        if self.is_initialized:
            return

        logger.info("Initializing Hygrid Extractor Agent...")

        await self._init_spacy_models()
        await self._init_transformer_models()
        await self._init_pattern_extractors()
        await self._init_tfidf_components()

        self.is_initialized = True
        logger.info("Hygrid Extractor Agent initialized successfully")

    def _load_legal_patterns(self) -> Dict[str, List[str]]:
        return {
            "court": [
                r"\b(?:Supreme Court|District Court|Appeals Court|Court of Appeals|Federal Court|State Court|Municipal Court|Family Court|Probate Court|Bankruptcy Court)\b",
                r"\b(?:Hon\.|Judge|Justice)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",
                r"\b[A-Z][a-z]+\s+(?:County|Parish)\s+(?:Court|Courthouse)\b",
            ],
            "case_citation": [
                r"\b\d+\s+[A-Z]\.?\s*\d+d?\s*\d+\b",
                r"\b\d+\s+U\.S\.?\s+\d+\b",
                r"\b\d+\s+F\.?\s*\d+d?\s*\d+\b",
                r"\b\d+\s+S\.?\s*Ct\.?\s*\d+\b",
            ],
            "legal_party": [
                r"\b(?:Plaintiff|Defendant|Petitioner|Respondent|Appellant|Appellee)\b",
                r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+v\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",
                r"\b(?:People|State|Commonwealth|United States)\s+v\.?\s+[A-Z][a-z]+\b",
            ],
            "statute": [
                r"\b\d+\s+U\.S\.C\.?\s+§?\s*\d+\b",
                r"\b\d+\s+C\.F\.R\.?\s+§?\s*\d+\b",
                r"\bSection\s+\d+(?:\.\d+)*\b",
                r"\b§\s*\d+(?:\.\d+)*\b",
            ],
            "legal_document": [
                r"\b(?:Motion|Complaint|Answer|Brief|Memorandum|Order|Judgment|Decree|Injunction|Subpoena|Warrant|Affidavit|Deposition)\b",
                r"\b(?:Contract|Agreement|Lease|Deed|Will|Trust|Patent|Trademark|Copyright)\b",
            ],
            "monetary_amount": [
                r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b",
                r"\b\d{1,3}(?:,\d{3})*\s+dollars?\b",
                r"\b(?:million|billion|thousand)\s+dollars?\b",
            ],
            "date_legal": [
                r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
                r"\b\d{1,2}/\d{1,2}/\d{4}\b",
                r"\b\d{4}-\d{2}-\d{2}\b",
            ],
        }

    async def _init_spacy_models(self):
        if not SPACY_AVAILABLE:
            logger.warning("SpaCy not available, skipping SpaCy model initialization")
            return
            
        try:
            models_to_load = ["en_core_web_sm", "en_core_web_md", "en_core_web_lg"]

            for model_name in models_to_load:
                try:
                    self.spacy_models[model_name] = spacy.load(model_name)
                    logger.info(f"Loaded SpaCy model: {model_name}")
                except OSError:
                    logger.warning(f"SpaCy model {model_name} not found, skipping")

            if not self.spacy_models and SPACY_AVAILABLE:
                try:
                    self.spacy_models["en_core_web_sm"] = spacy.load("en_core_web_sm")
                except OSError:
                    logger.warning("No SpaCy models available")

        except Exception as e:
            logger.error(f"Failed to initialize SpaCy models: {e}")
            self.spacy_models = {}

    async def _init_transformer_models(self):
        if not TRANSFORMERS_AVAILABLE:
            logger.warning("Transformers not available, skipping transformer model initialization")
            return
            
        try:
            legal_models = [
                "nlpaueb/legal-bert-base-uncased",
                "microsoft/DialoGPT-medium", 
                "dbmdz/bert-large-cased-finetuned-conll03-english",
            ]

            for model_name in legal_models:
                try:
                    tokenizer = AutoTokenizer.from_pretrained(model_name)
                    model = AutoModelForTokenClassification.from_pretrained(model_name)

                    self.transformer_models[model_name] = {
                        "tokenizer": tokenizer,
                        "model": model,
                        "pipeline": pipeline(
                            "ner",
                            model=model,
                            tokenizer=tokenizer,
                            aggregation_strategy="simple",
                        ),
                    }
                    logger.info(f"Loaded Transformer model: {model_name}")
                    break
                except Exception as model_error:
                    logger.warning(f"Failed to load {model_name}: {model_error}")

        except Exception as e:
            logger.error(f"Failed to initialize Transformer models: {e}")
            self.transformer_models = {}

    async def _init_pattern_extractors(self):
        for entity_type, patterns in self.entity_patterns.items():
            compiled_patterns = []
            for pattern in patterns:
                try:
                    compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
                except re.error as e:
                    logger.warning(
                        f"Invalid regex pattern for {entity_type}: {pattern} - {e}"
                    )

            self.pattern_extractors[entity_type] = compiled_patterns

    async def _init_tfidf_components(self):
        if not SKLEARN_AVAILABLE:
            logger.warning("Scikit-learn not available, skipping TF-IDF initialization")
            return
            
        try:
            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=10000, ngram_range=(1, 3), stop_words="english", lowercase=True
            )
        except Exception as e:
            logger.error(f"Failed to initialize TF-IDF components: {e}")
            self.tfidf_vectorizer = None

    async def extract_entities_hygrid(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
        confidence_threshold: float = 0.5,
    ) -> HygridExtractionResult:
        start_time = datetime.now(timezone.utc)

        if not self.is_initialized:
            await self.initialize()

        extraction_tasks = [
            self._extract_with_spacy(text, entity_types),
            self._extract_with_transformers(text, entity_types),
            self._extract_with_patterns(text, entity_types),
            self._extract_with_tfidf_similarity(text, entity_types),
        ]

        method_results = []

        for task in asyncio.as_completed(extraction_tasks):
            try:
                result = await task
                if result:
                    method_results.append(result)
            except Exception as e:
                logger.error(f"Extraction method failed: {e}")

        merged_entities = await self._merge_extraction_results(
            method_results, confidence_threshold
        )

        quality_metrics = self._calculate_quality_metrics(
            method_results, merged_entities
        )

        end_time = datetime.now(timezone.utc)
        processing_time = (end_time - start_time).total_seconds()

        if NUMPY_AVAILABLE:
            overall_confidence = (
                np.mean([entity.get("confidence", 0) for entity in merged_entities])
                if merged_entities
                else 0
            )
        else:
            # Fallback without numpy
            confidences = [entity.get("confidence", 0) for entity in merged_entities]
            overall_confidence = sum(confidences) / len(confidences) if confidences else 0
        consensus_score = self._calculate_consensus_score(method_results)

        return HygridExtractionResult(
            merged_entities=merged_entities,
            extraction_methods_used=[r.method_name for r in method_results],
            overall_confidence=overall_confidence,
            consensus_score=consensus_score,
            processing_time_total=processing_time,
            method_results=method_results,
            quality_metrics=quality_metrics,
        )

    async def _extract_with_spacy(
        self, text: str, entity_types: Optional[List[str]] = None
    ) -> ExtractionResult:
        start_time = datetime.now(timezone.utc)
        entities = []

        try:
            for model_name, nlp in self.spacy_models.items():
                doc = nlp(text)

                for ent in doc.ents:
                    if entity_types is None or ent.label_.lower() in [
                        et.lower() for et in entity_types
                    ]:
                        entities.append(
                            {
                                "text": ent.text,
                                "entity_type": ent.label_,
                                "start_pos": ent.start_char,
                                "end_pos": ent.end_char,
                                "confidence": 0.8,
                                "source_method": f"spacy_{model_name}",
                                "context": text[
                                    max(0, ent.start_char - 50) : min(
                                        len(text), ent.end_char + 50
                                    )
                                ],
                                "attributes": {
                                    "label": ent.label_,
                                    "lemma": (
                                        ent.lemma_ if hasattr(ent, "lemma_") else None
                                    ),
                                },
                            }
                        )

        except Exception as e:
            logger.error(f"SpaCy extraction failed: {e}")

        end_time = datetime.now(timezone.utc)
        processing_time = (end_time - start_time).total_seconds()

        return ExtractionResult(
            method_name="spacy_ensemble",
            entities=entities,
            confidence_score=0.8,
            processing_time=processing_time,
            metadata={"models_used": list(self.spacy_models.keys())},
        )

    async def _extract_with_transformers(
        self, text: str, entity_types: Optional[List[str]] = None
    ) -> ExtractionResult:
        start_time = datetime.now(timezone.utc)
        entities = []

        try:
            for model_name, model_info in self.transformer_models.items():
                pipe = model_info["pipeline"]

                chunks = self._chunk_text(text, max_length=512)

                for chunk_start, chunk_text in chunks:
                    ner_results = pipe(chunk_text)

                    for result in ner_results:
                        if entity_types is None or result["entity_group"].lower() in [
                            et.lower() for et in entity_types
                        ]:
                            entities.append(
                                {
                                    "text": result["word"],
                                    "entity_type": result["entity_group"],
                                    "start_pos": chunk_start + result["start"],
                                    "end_pos": chunk_start + result["end"],
                                    "confidence": result["score"],
                                    "source_method": f'transformer_{model_name.split("/")[-1]}',
                                    "context": chunk_text[
                                        max(0, result["start"] - 50) : min(
                                            len(chunk_text), result["end"] + 50
                                        )
                                    ],
                                    "attributes": {
                                        "raw_entity": result.get("entity", ""),
                                        "aggregation_score": result["score"],
                                    },
                                }
                            )

        except Exception as e:
            logger.error(f"Transformer extraction failed: {e}")

        end_time = datetime.now(timezone.utc)
        processing_time = (end_time - start_time).total_seconds()

        return ExtractionResult(
            method_name="transformers_ensemble",
            entities=entities,
            confidence_score=0.85,
            processing_time=processing_time,
            metadata={"models_used": list(self.transformer_models.keys())},
        )

    async def _extract_with_patterns(
        self, text: str, entity_types: Optional[List[str]] = None
    ) -> ExtractionResult:
        start_time = datetime.now(timezone.utc)
        entities = []

        try:
            for entity_type, patterns in self.pattern_extractors.items():
                if entity_types is None or entity_type in entity_types:
                    for pattern in patterns:
                        for match in pattern.finditer(text):
                            entities.append(
                                {
                                    "text": match.group(),
                                    "entity_type": entity_type,
                                    "start_pos": match.start(),
                                    "end_pos": match.end(),
                                    "confidence": 0.9,
                                    "source_method": "pattern_matching",
                                    "context": text[
                                        max(0, match.start() - 50) : min(
                                            len(text), match.end() + 50
                                        )
                                    ],
                                    "attributes": {
                                        "pattern_used": pattern.pattern,
                                        "match_groups": match.groups(),
                                    },
                                }
                            )

        except Exception as e:
            logger.error(f"Pattern extraction failed: {e}")

        end_time = datetime.now(timezone.utc)
        processing_time = (end_time - start_time).total_seconds()

        return ExtractionResult(
            method_name="pattern_matching",
            entities=entities,
            confidence_score=0.9,
            processing_time=processing_time,
            metadata={"patterns_used": len(self.pattern_extractors)},
        )

    async def _extract_with_tfidf_similarity(
        self, text: str, entity_types: Optional[List[str]] = None
    ) -> ExtractionResult:
        start_time = datetime.now(timezone.utc)
        entities = []

        try:
            legal_terms = {
                "court": [
                    "supreme court",
                    "district court",
                    "appellate court",
                    "federal court",
                ],
                "legal_document": ["complaint", "motion", "brief", "order", "judgment"],
                "legal_party": ["plaintiff", "defendant", "petitioner", "respondent"],
                "statute": ["section", "subsection", "code", "regulation"],
            }

            sentences = text.split(".")

            for sentence in sentences:
                if len(sentence.strip()) < 10:
                    continue

                words = sentence.split()
                for i in range(len(words)):
                    for j in range(
                        i + 1, min(i + 5, len(words) + 1)
                    ):
                        phrase = " ".join(words[i:j]).lower().strip()

                        if len(phrase) < 3:
                            continue

                        best_match = None
                        best_score = 0

                        for entity_type, terms in legal_terms.items():
                            if entity_types is None or entity_type in entity_types:
                                for term in terms:
                                    similarity = self._calculate_text_similarity(
                                        phrase, term
                                    )
                                    if similarity > best_score and similarity > 0.7:
                                        best_score = similarity
                                        best_match = entity_type

                        if best_match:
                            start_pos = text.find(phrase)
                            if start_pos != -1:
                                entities.append(
                                    {
                                        "text": phrase,
                                        "entity_type": best_match,
                                        "start_pos": start_pos,
                                        "end_pos": start_pos + len(phrase),
                                        "confidence": best_score,
                                        "source_method": "tfidf_similarity",
                                        "context": sentence,
                                        "attributes": {
                                            "similarity_score": best_score,
                                            "matched_term": best_match,
                                        },
                                    }
                                )

        except Exception as e:
            logger.error(f"TF-IDF similarity extraction failed: {e}")

        end_time = datetime.now(timezone.utc)
        processing_time = (end_time - start_time).total_seconds()

        return ExtractionResult(
            method_name="tfidf_similarity",
            entities=entities,
            confidence_score=0.75,
            processing_time=processing_time,
            metadata={"similarity_threshold": 0.7},
        )

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        try:
            set1 = set(text1.lower().split())
            set2 = set(text2.lower().split())

            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))

            return intersection / union if union > 0 else 0
        except:
            return 0

    async def _merge_extraction_results(
        self, method_results: List[ExtractionResult], confidence_threshold: float
    ) -> List[Dict[str, Any]]:
        if not method_results:
            return []

        all_candidates = []

        for result in method_results:
            for entity in result.entities:
                if entity.get("confidence", 0) >= confidence_threshold:
                    candidate = EntityCandidate(
                        text=entity["text"],
                        entity_type=entity["entity_type"],
                        start_pos=entity["start_pos"],
                        end_pos=entity["end_pos"],
                        confidence=entity["confidence"],
                        source_method=entity["source_method"],
                        context=entity.get("context", ""),
                        attributes=entity.get("attributes", {}),
                    )
                    all_candidates.append(candidate)

        grouped_entities = self._group_overlapping_entities(all_candidates)

        final_entities = []
        for group in grouped_entities:
            merged_entity = self._apply_ensemble_voting(group)
            if merged_entity:
                merged_entities.append(merged_entity)

        return merged_entities

    def _group_overlapping_entities(
        self, candidates: List[EntityCandidate]
    ) -> List[List[EntityCandidate]]:
        groups = []

        for candidate in candidates:
            assigned = False
            for group in groups:
                for existing in group:
                    if self._entities_overlap(candidate, existing):
                        group.append(candidate)
                        assigned = True
                        break
                if assigned:
                    break

            if not assigned:
                groups.append([candidate])

        return groups

    def _entities_overlap(
        self, entity1: EntityCandidate, entity2: EntityCandidate
    ) -> bool:
        return not (
            entity1.end_pos <= entity2.start_pos or entity2.end_pos <= entity1.start_pos
        )

    def _apply_ensemble_voting(
        self, group: List[EntityCandidate]
    ) -> Optional[Dict[str, Any]]:
        if not group:
            return None

        method_weights = {
            "pattern_matching": 1.0,
            "transformers_ensemble": 0.9,
            "spacy_ensemble": 0.8,
            "tfidf_similarity": 0.7,
        }

        type_votes = {}
        total_weight = 0

        for candidate in group:
            method_weight = method_weights.get(
                candidate.source_method.split("_")[0], 0.5
            )
            weight = candidate.confidence * method_weight

            if candidate.entity_type not in type_votes:
                type_votes[candidate.entity_type] = 0

            type_votes[candidate.entity_type] += weight
            total_weight += weight

        if total_weight == 0:
            return None

        winning_type = max(type_votes.keys(), key=lambda k: type_votes[k])

        best_candidate = max(
            [c for c in group if c.entity_type == winning_type],
            key=lambda c: c.confidence,
        )

        ensemble_confidence = type_votes[winning_type] / total_weight

        return {
            "text": best_candidate.text,
            "entity_type": winning_type,
            "start_pos": best_candidate.start_pos,
            "end_pos": best_candidate.end_pos,
            "confidence": ensemble_confidence,
            "source_methods": [c.source_method for c in group],
            "context": best_candidate.context,
            "attributes": {
                "ensemble_votes": type_votes,
                "candidate_count": len(group),
                "method_agreement": len(set(c.entity_type for c in group)) == 1,
                **best_candidate.attributes,
            },
        }

    def _calculate_consensus_score(
        self, method_results: List[ExtractionResult]
    ) -> float:
        if len(method_results) < 2:
            return 1.0

        entity_sets = []
        for result in method_results:
            entity_set = set()
            for entity in result.entities:
                normalized = f"{entity['text'].lower()}:{entity['entity_type'].lower()}"
                entity_set.add(normalized)
            entity_sets.append(entity_set)

        similarities = []
        for i in range(len(entity_sets)):
            for j in range(i + 1, len(entity_sets)):
                intersection = len(entity_sets[i].intersection(entity_sets[j]))
                union = len(entity_sets[i].union(entity_sets[j]))
                similarity = intersection / union if union > 0 else 0
                similarities.append(similarity)

        if NUMPY_AVAILABLE:
            return np.mean(similarities) if similarities else 0
        else:
            return sum(similarities) / len(similarities) if similarities else 0

    def _calculate_quality_metrics(
        self,
        method_results: List[ExtractionResult],
        merged_entities: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        total_entities = sum(len(result.entities) for result in method_results)
        merged_count = len(merged_entities)

        coverage = merged_count / total_entities if total_entities > 0 else 0

        entity_types = set()
        for entity in merged_entities:
            entity_types.add(entity["entity_type"])
        diversity = len(entity_types)

        if NUMPY_AVAILABLE:
            avg_confidence = (
                np.mean([e.get("confidence", 0) for e in merged_entities])
                if merged_entities
                else 0
            )
        else:
            confidences = [e.get("confidence", 0) for e in merged_entities]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        agreement_count = sum(
            1
            for e in merged_entities
            if e.get("attributes", {}).get("method_agreement", False)
        )
        agreement_rate = agreement_count / merged_count if merged_count > 0 else 0

        return {
            "coverage": coverage,
            "diversity": diversity,
            "average_confidence": avg_confidence,
            "method_agreement_rate": agreement_rate,
            "total_entities_found": merged_count,
            "processing_efficiency": (
                merged_count / sum(r.processing_time for r in method_results)
                if method_results
                else 0
            ),
        }

    def _chunk_text(self, text: str, max_length: int = 512) -> List[Tuple[int, str]]:
        chunks = []
        words = text.split()

        current_chunk = []
        current_length = 0
        chunk_start = 0

        for word in words:
            word_length = len(word) + 1

            if current_length + word_length > max_length and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append((chunk_start, chunk_text))

                chunk_start += len(chunk_text) + 1
                current_chunk = [word]
                current_length = word_length
            else:
                current_chunk.append(word)
                current_length += word_length

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append((chunk_start, chunk_text))

        return chunks

    async def get_extraction_statistics(self) -> Dict[str, Any]:
        return {
            "hygrid_extractor_info": {
                "version": "1.0.0",
                "methods_available": [
                    "spacy_ensemble",
                    "transformers_ensemble",
                    "pattern_matching",
                    "tfidf_similarity",
                ],
                "spacy_models_loaded": list(self.spacy_models.keys()),
                "transformer_models_loaded": list(self.transformer_models.keys()),
                "pattern_types_available": list(self.pattern_extractors.keys()),
                "entity_patterns_count": sum(
                    len(patterns) for patterns in self.entity_patterns.values()
                ),
                "is_initialized": self.is_initialized,
            }
        }
