"""
Unified Legal Semantic Analyzer Agent - Production Legal AI
===========================================================

A comprehensive semantic analysis agent that consolidates multiple approaches
for understanding legal document meaning and integrates with collective intelligence.

This agent combines the best features from existing semantic analysis implementations:
- semantic_analysis_agent.py (document summarization and topic identification)
- document_semantic_processing_agent.py (advanced semantic processing)
- nlp_topic_modeling_agent.py (topic modeling capabilities)

Key Features:
- Advanced document summarization with legal context awareness
- Legal topic identification and classification
- Semantic concept extraction and relationship mapping
- Legal ontology-guided analysis
- Multi-model approach (BERT, transformers, topic modeling)
- Integration with shared memory for collective intelligence
- Content classification and categorization
- Contextual understanding with legal domain expertise
- Production-grade error handling and performance optimization

Legal Semantic Capabilities:
- Legal document type classification (briefs, motions, contracts, etc.)
- Key legal concept identification (jurisdiction, liability, damages, etc.)
- Legal relationship extraction (plaintiff-defendant, cause-effect, etc.)
- Precedent relevance analysis
- Legal argument structure identification
- Temporal legal reasoning (statute of limitations, deadlines)
- Regulatory compliance identification
- Contract term analysis and risk assessment
"""

import json
import logging  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any, Dict, List, Optional, cast  # noqa: E402

# Core imports
from agents.base import BaseAgent  # noqa: E402
from agents.base.agent_mixins import LegalMemoryMixin  # noqa: E402
from core.container.service_container_impl import (  # noqa: E402
    ProductionServiceContainer,
)
from mem_db.memory.memory_interfaces import MemoryType  # noqa: E402

# Optional NLP dependencies with graceful degradation
try:
    from transformers import AutoModel, AutoTokenizer, pipeline  # noqa: E402

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    pipeline = None
    AutoTokenizer = None
    AutoModel = None
    TRANSFORMERS_AVAILABLE = False

try:
    import spacy  # noqa: E402
    from spacy.matcher import Matcher  # noqa: E402

    SPACY_AVAILABLE = True
except ImportError:
    spacy = None
    Matcher = None
    SPACY_AVAILABLE = False

try:
    import numpy as np  # noqa: E402
    from sklearn.cluster import KMeans  # noqa: E402
    from sklearn.decomposition import LatentDirichletAllocation  # noqa: E402
    from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402

    SKLEARN_AVAILABLE = True
except ImportError:
    TfidfVectorizer = None
    LatentDirichletAllocation = None
    KMeans = None
    np = None
    SKLEARN_AVAILABLE = False

try:
    import nltk  # noqa: E402
    from nltk.tokenize import sent_tokenize, word_tokenize  # noqa: E402

    NLTK_AVAILABLE = True
except ImportError:
    nltk = None
    sent_tokenize = None
    word_tokenize = None
    NLTK_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class SemanticConcept:
    """Represents a semantic concept extracted from text"""

    concept: str
    concept_type: str  # legal, factual, procedural, temporal
    confidence: float
    context: str
    legal_domain: Optional[str] = None  # contracts, litigation, criminal, etc.
    relationships: List[str] = field(default_factory=list)
    importance_score: float = 0.0


@dataclass
class LegalTopic:
    """Represents a legal topic identified in the document"""

    topic_name: str
    topic_category: str  # jurisdiction, liability, damages, procedure, etc.
    keywords: List[str]
    confidence: float
    relevance_score: float
    supporting_text: List[str] = field(default_factory=list)
    legal_framework: Optional[str] = None  # IRAC, Toulmin, etc.


@dataclass
class DocumentClassification:
    """Represents document classification results"""

    document_type: str  # brief, motion, contract, statute, etc.
    legal_domain: str  # litigation, contracts, criminal, regulatory, etc.
    jurisdiction: Optional[str] = None
    practice_area: Optional[str] = None
    confidence: float = 0.0
    classification_features: List[str] = field(default_factory=list)


@dataclass
class SemanticAnalysisConfig:
    """Configuration for semantic analysis"""

    # Model configurations
    summarization_model: str = "facebook/bart-large-cnn"
    legal_bert_model: str = "nlpaueb/legal-bert-base-uncased"
    classification_model: str = "microsoft/DialoGPT-medium"

    # Analysis settings
    enable_summarization: bool = True
    enable_topic_modeling: bool = True
    enable_concept_extraction: bool = True
    enable_classification: bool = True
    enable_relationship_extraction: bool = True

    # Topic modeling
    num_topics: int = 10
    topic_coherence_threshold: float = 0.4

    # Summarization
    summary_max_length: int = 500
    summary_min_length: int = 100

    # Concept extraction
    min_concept_confidence: float = 0.3
    max_concepts_per_category: int = 20

    # Performance settings
    batch_size: int = 16
    max_sequence_length: int = 512
    enable_caching: bool = True


@dataclass
class SemanticAnalysisResult:
    """Result from semantic analysis"""

    document_summary: str
    key_topics: List[LegalTopic]
    legal_concepts: List[SemanticConcept]
    document_classification: DocumentClassification
    semantic_relationships: List[Dict[str, Any]]
    content_structure: Dict[str, Any]
    processing_time: float
    confidence_score: float
    model_used: str
    collective_intelligence_enhanced: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class LegalSemanticAnalyzer(BaseAgent, LegalMemoryMixin):
    """
    Production Legal Semantic Analyzer with collective intelligence.

    Provides comprehensive semantic analysis of legal documents while
    contributing to the shared knowledge base for collective intelligence.
    """

    def __init__(
        self,
        services: ProductionServiceContainer,
        config: Optional[SemanticAnalysisConfig] = None,
    ):
        # Initialize base agent
        super().__init__(
            services=services,
            agent_name="LegalSemanticAnalyzer",
            agent_type="semantic_analysis",
            timeout_seconds=600.0,  # Semantic analysis can take time
        )

        # Initialize memory mixin
        LegalMemoryMixin.__init__(self)

        # Configuration
        self.config = config or SemanticAnalysisConfig()

        # Processing statistics
        self.stats = {
            "documents_analyzed": 0,
            "summaries_generated": 0,
            "topics_identified": 0,
            "concepts_extracted": 0,
            "total_processing_time": 0.0,
            "avg_processing_time": 0.0,
            "document_type_counts": {},
            "legal_domain_counts": {},
            "collective_intelligence_hits": 0,
            "cache_hits": 0,
            "errors_encountered": 0,
        }

        # Initialize models and components
        self.models = {}
        self.legal_patterns = {}
        self._initialize_models()
        self._initialize_legal_patterns()

        # Legal document type patterns
        self.document_type_indicators = {
            "brie": ["brie", "memorandum", "argument", "statement of facts"],
            "motion": ["motion to", "moves", "respectfully moves", "movant"],
            "complaint": ["complaint", "plainti", "comes now", "cause of action"],
            "contract": ["agreement", "party", "covenant", "consideration", "whereas"],
            "statute": ["shall", "enacted", "legislature", "section", "subsection"],
            "regulation": ["cfr", "regulation", "rule", "administrative"],
            "opinion": ["court", "held", "opinion", "decided", "judgment"],
            "order": ["ordered", "adjudged", "decreed", "so ordered"],
        }

        # Legal domain patterns
        self.legal_domain_indicators = {
            "litigation": ["lawsuit", "court", "trial", "discovery", "motion", "brie"],
            "contracts": [
                "agreement",
                "contract",
                "breach",
                "consideration",
                "covenant",
            ],
            "criminal": [
                "criminal",
                "felony",
                "misdemeanor",
                "prosecution",
                "defendant",
            ],
            "corporate": [
                "corporation",
                "merger",
                "acquisition",
                "securities",
                "board",
            ],
            "intellectual_property": [
                "patent",
                "trademark",
                "copyright",
                "trade secret",
            ],
            "employment": ["employee", "employer", "discrimination", "harassment"],
            "real_estate": ["property", "deed", "mortgage", "lease", "zoning"],
            "family": ["divorce", "custody", "alimony", "marriage", "adoption"],
            "tax": ["tax", "irs", "deduction", "exemption", "audit"],
            "regulatory": ["regulation", "compliance", "administrative", "agency"],
        }

        logger.info(f"LegalSemanticAnalyzer initialized with config: {self.config}")
        self._log_available_models()

    def _initialize_models(self):  # noqa: C901
        """Initialize available NLP models for semantic analysis"""

        # Initialize summarization pipeline
        if TRANSFORMERS_AVAILABLE and pipeline is not None:
            try:
                hf_pipeline = cast(Any, pipeline)
                self.models["summarizer"] = hf_pipeline(
                    "summarization",
                    model=self.config.summarization_model,
                    tokenizer=self.config.summarization_model,
                )
                logger.info(
                    f"Loaded summarization model: {self.config.summarization_model}"
                )
            except Exception as e:
                logger.warning(f"Failed to load summarization model: {e}")

        # Initialize Legal-BERT for legal text understanding
        if (
            TRANSFORMERS_AVAILABLE
            and AutoTokenizer is not None
            and AutoModel is not None
        ):
            try:
                self.models["legal_bert_tokenizer"] = cast(
                    Any, AutoTokenizer
                ).from_pretrained(self.config.legal_bert_model)
                self.models["legal_bert_model"] = cast(Any, AutoModel).from_pretrained(
                    self.config.legal_bert_model
                )
                logger.info(f"Loaded Legal-BERT model: {self.config.legal_bert_model}")
            except Exception as e:
                logger.warning(f"Failed to load Legal-BERT: {e}")

        # Initialize spaCy for linguistic processing
        if SPACY_AVAILABLE and spacy is not None:
            try:
                self.models["spacy"] = cast(Any, spacy).load("en_core_web_sm")
                logger.info("Loaded spaCy model for linguistic processing")
            except OSError:
                logger.warning("spaCy model not found")

        # Initialize topic modeling components
        if (
            SKLEARN_AVAILABLE
            and TfidfVectorizer is not None
            and LatentDirichletAllocation is not None
        ):
            try:
                self.models["tfidf_vectorizer"] = cast(Any, TfidfVectorizer)(
                    max_features=1000, stop_words="english", ngram_range=(1, 3)
                )
                self.models["lda_model"] = cast(Any, LatentDirichletAllocation)(
                    n_components=self.config.num_topics, random_state=42
                )
                logger.info("Initialized topic modeling components")
            except Exception as e:
                logger.warning(f"Failed to initialize topic modeling: {e}")

    def _initialize_legal_patterns(self):
        """Initialize legal linguistic patterns"""

        if not SPACY_AVAILABLE or "spacy" not in self.models or Matcher is None:
            return

        nlp = self.models["spacy"]
        self.legal_patterns["matcher"] = cast(Any, Matcher)(nlp.vocab)

        # Legal reasoning patterns
        legal_reasoning_patterns = [
            # IRAC patterns
            [
                {"LOWER": {"IN": ["issue", "question", "problem"]}},
                {"IS_ALPHA": True, "OP": "*"},
            ],
            [
                {"LOWER": {"IN": ["rule", "law", "statute", "regulation"]}},
                {"IS_ALPHA": True, "OP": "*"},
            ],
            [
                {"LOWER": {"IN": ["application", "analysis", "apply"]}},
                {"IS_ALPHA": True, "OP": "*"},
            ],
            [
                {"LOWER": {"IN": ["conclusion", "holding", "therefore"]}},
                {"IS_ALPHA": True, "OP": "*"},
            ],
            # Legal relationships
            [{"LOWER": "plaintiff"}, {"LOWER": "v."}, {"LOWER": "defendant"}],
            [
                {"LOWER": {"IN": ["breach", "violated", "infringed"]}},
                {"IS_ALPHA": True, "OP": "*"},
            ],
            [
                {"LOWER": {"IN": ["damages", "relief", "remedy"]}},
                {"IS_ALPHA": True, "OP": "*"},
            ],
        ]

        # Procedural patterns
        procedural_patterns = [
            [{"LOWER": "motion"}, {"LOWER": "to"}, {"IS_ALPHA": True}],
            [{"LOWER": {"IN": ["granted", "denied", "sustained", "overruled"]}}],
            [
                {"LOWER": {"IN": ["discovery", "deposition", "interrogatory"]}},
                {"IS_ALPHA": True, "OP": "*"},
            ],
        ]

        # Add patterns to matcher
        self.legal_patterns["matcher"].add("LEGAL_REASONING", legal_reasoning_patterns)
        self.legal_patterns["matcher"].add("PROCEDURAL", procedural_patterns)

        logger.info(
            f"Initialized {len(legal_reasoning_patterns + procedural_patterns)} legal patterns"
        )

    def _log_available_models(self):
        """Log available models for semantic analysis"""

        models_status = {
            "Transformers (Summarization)": TRANSFORMERS_AVAILABLE
            and "summarizer" in self.models,
            "Legal-BERT": TRANSFORMERS_AVAILABLE and "legal_bert_model" in self.models,
            "spaCy": SPACY_AVAILABLE and "spacy" in self.models,
            "scikit-learn (Topic Modeling)": SKLEARN_AVAILABLE
            and "tfidf_vectorizer" in self.models,
            "NLTK": NLTK_AVAILABLE,
        }

        available = [name for name, status in models_status.items() if status]
        unavailable = [name for name, status in models_status.items() if not status]

        logger.info(
            f"Available models: {', '.join(available) if available else 'None'}"
        )
        if unavailable:
            logger.info(f"Unavailable optional models: {', '.join(unavailable)}")

    async def _process_task(
        self, task_data: Any, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process semantic analysis task.

        Args:
            task_data: Text content for semantic analysis
            metadata: Task metadata including document_id, analysis_options, etc.

        Returns:
            Semantic analysis result with collective intelligence integration
        """

        try:
            # Extract text content
            if isinstance(task_data, str):
                text = task_data
                raw_document_id = metadata.get("document_id", f"text_{hash(task_data)}")
            elif isinstance(task_data, dict):
                text = task_data.get("content", task_data.get("text", ""))
                raw_document_id = task_data.get(
                    "document_id", metadata.get("document_id")
                )
            else:
                raise ValueError(f"Unsupported task_data type: {type(task_data)}")

            document_id = str(raw_document_id or f"doc_{hash(text)}")

            if not text or not text.strip():
                raise ValueError("No text content provided for semantic analysis")

            logger.info(f"Starting semantic analysis for document {document_id}")
            start_time = datetime.now()

            # Step 1: Check collective memory for similar semantic analyses
            similar_analyses = await self._find_similar_semantic_analyses(
                text, document_id
            )
            logger.info(
                f"Found {len(similar_analyses)} similar semantic analyses in collective memory"
            )

            # Step 2: Perform comprehensive semantic analysis
            analysis_result = await self._analyze_document_semantics(text, document_id)

            # Step 3: Enhance with collective intelligence insights
            if similar_analyses:
                analysis_result = await self._enhance_with_collective_intelligence(
                    analysis_result, similar_analyses
                )
                analysis_result.collective_intelligence_enhanced = True
                self.stats["collective_intelligence_hits"] += 1

            # Step 4: Store analysis results in shared memory
            await self._store_semantic_analysis(analysis_result, document_id, text)

            # Step 5: Update statistics
            self._update_statistics(analysis_result)

            processing_time = (datetime.now() - start_time).total_seconds()

            logger.info(f"Semantic analysis completed for {document_id}")
            logger.info(
                f"Generated summary, {len(analysis_result.key_topics)} topics, {len(analysis_result.legal_concepts)} concepts in {processing_time:.2f}s"
            )

            return {
                "success": True,
                "semantic_analysis": {
                    "document_summary": analysis_result.document_summary,
                    "key_topics": [
                        topic.__dict__ for topic in analysis_result.key_topics
                    ],
                    "legal_concepts": [
                        concept.__dict__ for concept in analysis_result.legal_concepts
                    ],
                    "document_classification": analysis_result.document_classification.__dict__,
                    "semantic_relationships": analysis_result.semantic_relationships,
                    "content_structure": analysis_result.content_structure,
                    "confidence_score": analysis_result.confidence_score,
                    "collective_intelligence_enhanced": analysis_result.collective_intelligence_enhanced,
                },
                "collective_intelligence": {
                    "similar_analyses_found": len(similar_analyses),
                    "knowledge_enhanced": analysis_result.collective_intelligence_enhanced,
                },
                "metadata": {
                    "document_id": document_id,
                    "document_type": analysis_result.document_classification.document_type,
                    "legal_domain": analysis_result.document_classification.legal_domain,
                    "processing_time": processing_time,
                    "confidence_score": analysis_result.confidence_score,
                    "processed_at": datetime.now().isoformat(),
                    "agent_name": self.agent_name,
                },
            }

        except Exception as e:
            self.stats["errors_encountered"] += 1
            logger.error(
                f"Semantic analysis failed for {metadata.get('document_id', 'unknown')}: {e}"
            )
            raise

    async def _find_similar_semantic_analyses(
        self, text: str, document_id: str
    ) -> List[Any]:
        """Find similar semantic analyses from shared memory"""

        if not self._is_memory_available():
            return []

        try:
            # Extract key semantic terms for search
            key_terms = self._extract_semantic_keywords(text)
            search_query = " ".join(key_terms[:15])  # Use top 15 semantic terms

            # Search for similar semantic analyses
            similar_results = await self.search_memory(
                query=search_query,
                memory_types=[MemoryType.ANALYSIS, MemoryType.DOCUMENT],
                namespaces=["semantic_analyses", "legal_analysis"],
                limit=5,
                min_similarity=0.3,
            )

            return similar_results

        except Exception as e:
            logger.warning(f"Failed to find similar semantic analyses: {e}")
            return []

    def _extract_semantic_keywords(self, text: str) -> List[str]:
        """Extract semantic keywords for similarity search"""

        keywords = []

        # Extract legal domain keywords
        for domain, indicators in self.legal_domain_indicators.items():
            for indicator in indicators:
                if indicator.lower() in text.lower():
                    keywords.append(domain)
                    keywords.append(indicator)

        # Extract document type keywords
        for doc_type, indicators in self.document_type_indicators.items():
            for indicator in indicators:
                if indicator.lower() in text.lower():
                    keywords.append(doc_type)
                    keywords.append(indicator)

        # Extract high-frequency legal terms
        legal_terms = [
            "court",
            "law",
            "legal",
            "statute",
            "regulation",
            "contract",
            "plainti",
            "defendant",
            "liability",
            "damages",
            "breach",
            "jurisdiction",
            "motion",
            "brie",
            "judgment",
            "precedent",
        ]

        for term in legal_terms:
            if term in text.lower():
                keywords.append(term)

        return list(set(keywords))  # Remove duplicates

    async def _analyze_document_semantics(
        self, text: str, document_id: str
    ) -> SemanticAnalysisResult:
        """Perform comprehensive semantic analysis of the document"""

        start_time = time.time()

        # Initialize result components
        summary = ""
        topics = []
        concepts = []
        classification = DocumentClassification("unknown", "unknown")
        relationships = []
        content_structure = {}

        # Step 1: Document summarization
        if self.config.enable_summarization:
            summary = await self._generate_summary(text)
            self.stats["summaries_generated"] += 1

        # Step 2: Topic identification
        if self.config.enable_topic_modeling:
            topics = await self._identify_legal_topics(text)
            self.stats["topics_identified"] += len(topics)

        # Step 3: Concept extraction
        if self.config.enable_concept_extraction:
            concepts = await self._extract_legal_concepts(text)
            self.stats["concepts_extracted"] += len(concepts)

        # Step 4: Document classification
        if self.config.enable_classification:
            classification = await self._classify_document(text)

        # Step 5: Relationship extraction
        if self.config.enable_relationship_extraction:
            relationships = await self._extract_semantic_relationships(text)

        # Step 6: Content structure analysis
        content_structure = await self._analyze_content_structure(text)

        # Calculate overall confidence
        confidence_score = self._calculate_semantic_confidence(
            summary, topics, concepts, classification, relationships
        )

        processing_time = time.time() - start_time

        return SemanticAnalysisResult(
            document_summary=summary,
            key_topics=topics,
            legal_concepts=concepts,
            document_classification=classification,
            semantic_relationships=relationships,
            content_structure=content_structure,
            processing_time=processing_time,
            confidence_score=confidence_score,
            model_used=self.config.summarization_model,
        )

    async def _generate_summary(self, text: str) -> str:
        """Generate document summary using transformer models"""

        if "summarizer" not in self.models:
            # Fallback to extractive summarization
            return self._extractive_summary(text)

        try:
            # Split text into chunks if too long
            max_chunk_length = 1024
            if len(text) <= max_chunk_length:
                summary_result = self.models["summarizer"](
                    text,
                    max_length=self.config.summary_max_length,
                    min_length=self.config.summary_min_length,
                    do_sample=False,
                )
                return summary_result[0]["summary_text"]
            else:
                # Process in chunks and combine
                chunks = [
                    text[i : i + max_chunk_length]
                    for i in range(0, len(text), max_chunk_length)
                ]
                summaries = []

                for chunk in chunks:
                    if len(chunk.strip()) > 100:  # Only summarize substantial chunks
                        chunk_summary = self.models["summarizer"](
                            chunk,
                            max_length=min(150, len(chunk) // 3),
                            min_length=50,
                            do_sample=False,
                        )
                        summaries.append(chunk_summary[0]["summary_text"])

                # Combine chunk summaries
                combined_summary = " ".join(summaries)
                if len(combined_summary) > self.config.summary_max_length:
                    # Summarize the combined summary
                    final_summary = self.models["summarizer"](
                        combined_summary,
                        max_length=self.config.summary_max_length,
                        min_length=self.config.summary_min_length,
                        do_sample=False,
                    )
                    return final_summary[0]["summary_text"]

                return combined_summary

        except Exception as e:
            logger.warning(
                f"Transformer summarization failed, using extractive method: {e}"
            )
            return self._extractive_summary(text)

    def _extractive_summary(self, text: str) -> str:
        """Fallback extractive summarization"""

        if NLTK_AVAILABLE and sent_tokenize is not None:
            sentences = sent_tokenize(text)
        else:
            # Simple sentence splitting
            sentences = [s.strip() for s in text.split(".") if s.strip()]

        # Score sentences by legal keyword frequency
        legal_keywords = [
            "court",
            "plainti",
            "defendant",
            "law",
            "statute",
            "contract",
            "liability",
            "damages",
            "jurisdiction",
            "motion",
            "brie",
        ]

        sentence_scores = []
        for sentence in sentences:
            score = sum(
                1 for keyword in legal_keywords if keyword.lower() in sentence.lower()
            )
            sentence_scores.append((sentence, score))

        # Sort by score and take top sentences
        sentence_scores.sort(key=lambda x: x[1], reverse=True)
        top_sentences = [sent for sent, score in sentence_scores[:5] if score > 0]

        return " ".join(top_sentences)

    async def _identify_legal_topics(self, text: str) -> List[LegalTopic]:
        """Identify legal topics using topic modeling and pattern matching"""

        topics = []

        # Pattern-based topic identification
        pattern_topics = self._identify_topics_by_patterns(text)
        topics.extend(pattern_topics)

        # Machine learning-based topic modeling
        if "tfidf_vectorizer" in self.models and "lda_model" in self.models:
            ml_topics = await self._identify_topics_by_ml(text)
            topics.extend(ml_topics)

        # Remove duplicates and rank by relevance
        unique_topics = self._deduplicate_topics(topics)
        ranked_topics = sorted(
            unique_topics, key=lambda t: t.relevance_score, reverse=True
        )

        return ranked_topics[: self.config.num_topics]

    def _identify_topics_by_patterns(self, text: str) -> List[LegalTopic]:
        """Identify topics using legal domain patterns"""

        topics = []
        text_lower = text.lower()

        # Check each legal domain
        for domain, indicators in self.legal_domain_indicators.items():
            keyword_matches = []
            confidence = 0.0

            for indicator in indicators:
                if indicator in text_lower:
                    keyword_matches.append(indicator)
                    confidence += 0.1

            if keyword_matches:
                topic = LegalTopic(
                    topic_name=domain.replace("_", " ").title(),
                    topic_category=domain,
                    keywords=keyword_matches,
                    confidence=min(1.0, confidence),
                    relevance_score=len(keyword_matches) / len(indicators),
                )
                topics.append(topic)

        return topics

    async def _identify_topics_by_ml(self, text: str) -> List[LegalTopic]:
        """Identify topics using machine learning topic modeling"""

        try:
            # Vectorize text
            vectorizer = self.models["tfidf_vectorizer"]
            lda_model = self.models["lda_model"]

            # For single document, we need to fit the vectorizer
            text_vector = vectorizer.fit_transform([text])

            # Get topics
            topic_probs = lda_model.fit_transform(text_vector)[0]

            # Get feature names
            feature_names = vectorizer.get_feature_names_out()

            topics = []
            for topic_idx, prob in enumerate(topic_probs):
                if prob > self.config.topic_coherence_threshold:
                    # Get top words for this topic
                    topic_words = lda_model.components_[topic_idx]
                    top_words_idx = topic_words.argsort()[-10:][::-1]
                    top_words = [feature_names[i] for i in top_words_idx]

                    topic = LegalTopic(
                        topic_name=f"Topic {topic_idx + 1}",
                        topic_category="ml_generated",
                        keywords=top_words,
                        confidence=prob,
                        relevance_score=prob,
                    )
                    topics.append(topic)

            return topics

        except Exception as e:
            logger.warning(f"ML topic modeling failed: {e}")
            return []

    def _deduplicate_topics(self, topics: List[LegalTopic]) -> List[LegalTopic]:
        """Remove duplicate topics and merge similar ones"""

        unique_topics = []

        for topic in topics:
            # Check for similar existing topics
            similar_found = False

            for existing in unique_topics:
                # Check keyword overlap
                keyword_overlap = len(set(topic.keywords) & set(existing.keywords))
                if (
                    keyword_overlap > 0
                    or topic.topic_category == existing.topic_category
                ):
                    # Merge topics
                    existing.confidence = max(existing.confidence, topic.confidence)
                    existing.relevance_score = max(
                        existing.relevance_score, topic.relevance_score
                    )
                    existing.keywords = list(set(existing.keywords + topic.keywords))
                    similar_found = True
                    break

            if not similar_found:
                unique_topics.append(topic)

        return unique_topics

    async def _extract_legal_concepts(self, text: str) -> List[SemanticConcept]:
        """Extract legal concepts using NLP and pattern matching"""

        concepts = []

        # Pattern-based concept extraction
        if "spacy" in self.models and "matcher" in self.legal_patterns:
            nlp = self.models["spacy"]
            matcher = self.legal_patterns["matcher"]
            doc = nlp(text)

            matches = matcher(doc)
            for match_id, start, end in matches:
                span = doc[start:end]
                label = nlp.vocab.strings[match_id]

                concept = SemanticConcept(
                    concept=span.text,
                    concept_type=label.lower(),
                    confidence=0.8,
                    context=doc[max(0, start - 10) : min(len(doc), end + 10)].text,
                    legal_domain=self._determine_legal_domain(span.text),
                )
                concepts.append(concept)

        # Entity-based concept extraction
        if "spacy" in self.models:
            nlp = self.models["spacy"]
            doc = nlp(text)

            for ent in doc.ents:
                if ent.label_ in ["PERSON", "ORG", "GPE", "LAW", "MONEY", "DATE"]:
                    concept = SemanticConcept(
                        concept=ent.text,
                        concept_type=f"entity_{ent.label_.lower()}",
                        confidence=0.7,
                        context=doc[
                            max(0, ent.start - 10) : min(len(doc), ent.end + 10)
                        ].text,
                        legal_domain=self._determine_legal_domain(ent.text),
                    )
                    concepts.append(concept)

        # Filter and rank concepts
        filtered_concepts = [
            c for c in concepts if c.confidence >= self.config.min_concept_confidence
        ]
        ranked_concepts = sorted(
            filtered_concepts, key=lambda c: c.confidence, reverse=True
        )

        return ranked_concepts[
            : self.config.max_concepts_per_category * 4
        ]  # 4 categories

    def _determine_legal_domain(self, text: str) -> Optional[str]:
        """Determine legal domain for a concept"""

        text_lower = text.lower()

        for domain, indicators in self.legal_domain_indicators.items():
            for indicator in indicators:
                if indicator in text_lower:
                    return domain

        return None

    async def _classify_document(self, text: str) -> DocumentClassification:
        """Classify document type and legal domain"""

        # Determine document type
        document_type = "unknown"
        doc_type_confidence = 0.0
        doc_features = []

        text_lower = text.lower()

        for doc_type, indicators in self.document_type_indicators.items():
            matches = sum(1 for indicator in indicators if indicator in text_lower)
            if matches > 0:
                confidence = matches / len(indicators)
                if confidence > doc_type_confidence:
                    doc_type_confidence = confidence
                    document_type = doc_type
                    doc_features = [
                        indicator for indicator in indicators if indicator in text_lower
                    ]

        # Determine legal domain
        legal_domain = "unknown"
        domain_confidence = 0.0

        for domain, indicators in self.legal_domain_indicators.items():
            matches = sum(1 for indicator in indicators if indicator in text_lower)
            if matches > 0:
                confidence = matches / len(indicators)
                if confidence > domain_confidence:
                    domain_confidence = confidence
                    legal_domain = domain

        overall_confidence = (doc_type_confidence + domain_confidence) / 2.0

        return DocumentClassification(
            document_type=document_type,
            legal_domain=legal_domain,
            confidence=overall_confidence,
            classification_features=doc_features,
        )

    async def _extract_semantic_relationships(self, text: str) -> List[Dict[str, Any]]:
        """Extract semantic relationships between concepts"""

        relationships = []

        if "spacy" not in self.models:
            return relationships

        nlp = self.models["spacy"]
        doc = nlp(text)

        # Extract dependency-based relationships
        for sent in doc.sents:
            for token in sent:
                if token.dep_ in ["nsubj", "dobj", "pobj"]:
                    relationship = {
                        "subject": token.head.text,
                        "relation": token.dep_,
                        "object": token.text,
                        "context": sent.text,
                        "confidence": 0.6,
                    }
                    relationships.append(relationship)

        # Filter relationships by legal relevance
        legal_relationships = []
        for rel in relationships:
            if any(
                term in rel["context"].lower()
                for term in ["court", "law", "legal", "contract", "statute"]
            ):
                legal_relationships.append(rel)

        return legal_relationships[:20]  # Limit results

    async def _analyze_content_structure(self, text: str) -> Dict[str, Any]:
        """Analyze document content structure"""

        structure = {
            "total_length": len(text),
            "paragraph_count": len([p for p in text.split("\n\n") if p.strip()]),
            "sentence_count": 0,
            "avg_sentence_length": 0.0,
            "legal_sections": [],
        }

        # Count sentences
        if NLTK_AVAILABLE and sent_tokenize is not None:
            sentences = sent_tokenize(text)
            structure["sentence_count"] = len(sentences)
            if sentences:
                structure["avg_sentence_length"] = sum(
                    len(s.split()) for s in sentences
                ) / len(sentences)

        # Identify legal document sections
        section_patterns = [
            r"I\.\s+INTRODUCTION",
            r"II\.\s+STATEMENT OF FACTS",
            r"III\.\s+LEGAL STANDARD",
            r"IV\.\s+ARGUMENT",
            r"V\.\s+CONCLUSION",
            r"WHEREFORE",
            r"BACKGROUND",
            r"DISCUSSION",
            r"ANALYSIS",
        ]

        for pattern in section_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                structure["legal_sections"].append(
                    {
                        "section": match.group(),
                        "position": match.start(),
                        "type": "legal_section",
                    }
                )

        return structure

    def _calculate_semantic_confidence(
        self,
        summary: str,
        topics: List[LegalTopic],
        concepts: List[SemanticConcept],
        classification: DocumentClassification,
        relationships: List[Dict[str, Any]],
    ) -> float:
        """Calculate overall semantic analysis confidence"""

        confidence_components = []

        # Summary confidence
        if summary:
            summary_confidence = min(
                1.0, len(summary.split()) / 50.0
            )  # Based on summary length
            confidence_components.append(summary_confidence)

        # Topic confidence
        if topics:
            topic_confidence = sum(t.confidence for t in topics) / len(topics)
            confidence_components.append(topic_confidence)

        # Concept confidence
        if concepts:
            concept_confidence = sum(c.confidence for c in concepts) / len(concepts)
            confidence_components.append(concept_confidence)

        # Classification confidence
        confidence_components.append(classification.confidence)

        # Relationship confidence
        if relationships:
            rel_confidence = sum(r["confidence"] for r in relationships) / len(
                relationships
            )
            confidence_components.append(rel_confidence)

        return (
            sum(confidence_components) / len(confidence_components)
            if confidence_components
            else 0.0
        )

    async def _enhance_with_collective_intelligence(  # noqa: C901
        self, analysis_result: SemanticAnalysisResult, similar_analyses: List[Any]
    ) -> SemanticAnalysisResult:
        """Enhance analysis with collective intelligence"""

        try:
            enhancement_boost = 0.0

            for similar in similar_analyses:
                try:
                    if hasattr(similar.record, "metadata") and similar.record.metadata:
                        metadata = similar.record.metadata

                        # Boost confidence for similar document types
                        if "document_type" in metadata:
                            if (
                                metadata["document_type"]
                                == analysis_result.document_classification.document_type
                            ):
                                enhancement_boost += 0.1

                        # Boost confidence for similar legal domains
                        if "legal_domain" in metadata:
                            if (
                                metadata["legal_domain"]
                                == analysis_result.document_classification.legal_domain
                            ):
                                enhancement_boost += 0.1

                except Exception as e:
                    logger.warning(f"Failed to process similar analysis: {e}")

            # Update confidence with collective intelligence
            if enhancement_boost > 0:
                analysis_result.confidence_score = min(
                    1.0, analysis_result.confidence_score + enhancement_boost
                )
                analysis_result.metadata["collective_enhancement"] = enhancement_boost

        except Exception as e:
            logger.warning(f"Failed to enhance with collective intelligence: {e}")

        return analysis_result

    async def _store_semantic_analysis(
        self, analysis_result: SemanticAnalysisResult, document_id: str, text: str
    ):
        """Store semantic analysis results in shared memory"""

        # Store analysis results
        analysis_data = {
            "document_summary": analysis_result.document_summary,
            "key_topics": [topic.__dict__ for topic in analysis_result.key_topics],
            "legal_concepts": [
                concept.__dict__ for concept in analysis_result.legal_concepts
            ],
            "document_classification": analysis_result.document_classification.__dict__,
            "semantic_relationships": analysis_result.semantic_relationships,
            "confidence_score": analysis_result.confidence_score,
            "processing_time": analysis_result.processing_time,
        }

        await self.store_memory(
            namespace="semantic_analyses",
            key=f"semantic_analysis_{document_id}",
            content=json.dumps(analysis_data),
            memory_type=MemoryType.ANALYSIS,
            metadata={
                "document_id": document_id,
                "document_type": analysis_result.document_classification.document_type,
                "legal_domain": analysis_result.document_classification.legal_domain,
                "topic_count": len(analysis_result.key_topics),
                "concept_count": len(analysis_result.legal_concepts),
                "confidence_score": analysis_result.confidence_score,
                "collective_intelligence_enhanced": analysis_result.collective_intelligence_enhanced,
                "agent_type": "semantic_analyzer",
            },
            importance_score=analysis_result.confidence_score,
            confidence_score=analysis_result.confidence_score,
        )

    def _update_statistics(self, analysis_result: SemanticAnalysisResult):
        """Update processing statistics"""

        self.stats["documents_analyzed"] += 1
        self.stats["total_processing_time"] += analysis_result.processing_time

        # Update average processing time
        count = self.stats["documents_analyzed"]
        self.stats["avg_processing_time"] = self.stats["total_processing_time"] / count

        # Update document type counts
        doc_type = analysis_result.document_classification.document_type
        if doc_type not in self.stats["document_type_counts"]:
            self.stats["document_type_counts"][doc_type] = 0
        self.stats["document_type_counts"][doc_type] += 1

        # Update legal domain counts
        legal_domain = analysis_result.document_classification.legal_domain
        if legal_domain not in self.stats["legal_domain_counts"]:
            self.stats["legal_domain_counts"][legal_domain] = 0
        self.stats["legal_domain_counts"][legal_domain] += 1

    async def health_check(self) -> Dict[str, Any]:
        """Extended health check for semantic analyzer"""

        base_health = await super().health_check()

        # Add semantic analysis specific health information
        semantic_health = {
            "analysis_config": {
                "summarization_enabled": self.config.enable_summarization,
                "topic_modeling_enabled": self.config.enable_topic_modeling,
                "concept_extraction_enabled": self.config.enable_concept_extraction,
                "classification_enabled": self.config.enable_classification,
                "num_topics": self.config.num_topics,
            },
            "available_models": {
                "transformers": TRANSFORMERS_AVAILABLE and "summarizer" in self.models,
                "legal_bert": TRANSFORMERS_AVAILABLE
                and "legal_bert_model" in self.models,
                "spacy": SPACY_AVAILABLE and "spacy" in self.models,
                "sklearn": SKLEARN_AVAILABLE and "tfidf_vectorizer" in self.models,
                "nltk": NLTK_AVAILABLE,
            },
            "performance_stats": self.stats,
            "legal_patterns_loaded": len(self.document_type_indicators)
            + len(self.legal_domain_indicators),
        }

        base_health.update(semantic_health)
        return base_health


# Factory function for easy instantiation
async def create_legal_semantic_analyzer(
    services: ProductionServiceContainer,
    config: Optional[SemanticAnalysisConfig] = None,
) -> LegalSemanticAnalyzer:
    """
    Create and initialize a Legal Semantic Analyzer Agent

    Args:
        services: Service container with dependencies
        config: Optional semantic analysis configuration

    Returns:
        Initialized Legal Semantic Analyzer Agent
    """
    agent = LegalSemanticAnalyzer(services, config)

    logger.info(
        "Created Legal Semantic Analyzer Agent with collective intelligence capabilities"
    )

    return agent
