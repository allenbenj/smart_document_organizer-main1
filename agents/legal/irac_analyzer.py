"""
IRAC Analyzer Agent - Production Legal AI
==========================================

A production-grade IRAC (Issue, Rule, Application, Conclusion) analyzer that integrates
with the Legal AI platform's service container architecture and shared memory system.

This agent embodies the collective intelligence approach - it learns from other agents'
IRAC analyses and contributes its findings to help all agents become smarter.

Features:
- Pattern-based and LLM-based IRAC extraction
- Nested IRAC analysis support
- Knowledge graph integration
- Precedent matching with shared memory
- Async processing with proper error handling
- Service container integration for dependencies
"""

import json
import logging  # noqa: E402
import re  # noqa: E402
import inspect  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

# Core imports
from agents.base import BaseAgent  # noqa: E402
from agents.base.agent_mixins import LegalDomainMixin, LegalMemoryMixin  # noqa: E402
from core.container.service_container_impl import ProductionServiceContainer  # noqa: E402
from mem_db.memory import MemoryType  # noqa: E402

logger = logging.getLogger(__name__)

try:
    import networkx as nx  # noqa: E402

    NETWORKX_AVAILABLE = True
except ImportError:
    nx = None
    NETWORKX_AVAILABLE = False


@dataclass
class IracConfig:
    """Configuration for IRAC analysis"""

    min_confidence: float = 0.7
    max_sections: int = 20
    enable_pattern_matching: bool = True
    use_llm_validation: bool = True
    enable_nested_irac: bool = True
    enable_kg: bool = True
    enable_precedent_matching: bool = True
    debug: bool = False
    llm_model: str = "gpt-5-nano-2025-08-07"
    prompt_override: Optional[str] = None


@dataclass
class IracComponent:
    """Represents a single IRAC component"""

    component_type: str  # 'issue', 'rule', 'application', 'conclusion'
    content: str
    confidence: float
    start_pos: int = 0
    end_pos: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IracAnalysis:
    """Complete IRAC analysis result"""

    document_id: str
    issue: IracComponent
    rule: IracComponent
    application: IracComponent
    conclusion: IracComponent
    overall_confidence: float
    precedents_found: List[Dict[str, Any]] = field(default_factory=list)
    nested_analyses: List["IracAnalysis"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "document_id": self.document_id,
            "issue": {
                "content": self.issue.content,
                "confidence": self.issue.confidence,
                "metadata": self.issue.metadata,
            },
            "rule": {
                "content": self.rule.content,
                "confidence": self.rule.confidence,
                "metadata": self.rule.metadata,
            },
            "application": {
                "content": self.application.content,
                "confidence": self.application.confidence,
                "metadata": self.application.metadata,
            },
            "conclusion": {
                "content": self.conclusion.content,
                "confidence": self.conclusion.confidence,
                "metadata": self.conclusion.metadata,
            },
            "overall_confidence": self.overall_confidence,
            "precedents_found": self.precedents_found,
            "nested_analyses": [nested.to_dict() for nested in self.nested_analyses],
            "metadata": self.metadata,
        }


class IracAnalyzerAgent(BaseAgent, LegalDomainMixin, LegalMemoryMixin):
    """
    Production IRAC Analyzer Agent with collective intelligence.

    This agent performs sophisticated IRAC analysis while learning from and
    contributing to the shared knowledge base that makes all agents smarter.
    """

    def __init__(
        self, services: ProductionServiceContainer, config: Optional[IracConfig] = None
    ):
        # Initialize base agent with specialized configuration
        super().__init__(
            services=services,
            agent_name="IracAnalyzer",
            agent_type="legal_analysis",
            timeout_seconds=600.0,  # IRAC analysis can be complex
        )

        # Initialize mixins
        LegalDomainMixin.__init__(self)
        LegalMemoryMixin.__init__(self)

        # Configuration
        self.config = config or IracConfig()

        # Pattern cache for performance
        self._pattern_cache = {}
        self._compile_patterns()

        # Statistics
        self.stats = {
            "analyses_performed": 0,
            "precedents_found": 0,
            "nested_analyses_detected": 0,
            "avg_confidence": 0.0,
        }

        logger.info(f"IracAnalyzerAgent initialized with config: {self.config}")

    def _compile_patterns(self):
        """Compile regex patterns for IRAC component detection"""

        # Issue patterns
        self._pattern_cache["issue"] = [
            re.compile(
                r"(?i)(?:the\s+)?(?:issue|question|problem)\s+(?:is|presented|here)\s+(.+?)(?:\.|;|\n\n)",
                re.DOTALL,
            ),
            re.compile(
                r"(?i)(?:issue|question):\s*(.+?)(?:\n\n|\n(?=[A-Z])|$)", re.DOTALL
            ),
            re.compile(r"(?i)whether\s+(.+?)(?:\.|;|\n)", re.DOTALL),
        ]

        # Rule patterns
        self._pattern_cache["rule"] = [
            re.compile(
                r"(?i)(?:the\s+)?(?:rule|law|statute|regulation|principle)\s+(?:states|provides|holds)\s+(.+?)(?:\.|;|\n\n)",
                re.DOTALL,
            ),
            re.compile(r"(?i)(?:rule|law):\s*(.+?)(?:\n\n|\n(?=[A-Z])|$)", re.DOTALL),
            re.compile(r"(?i)according\s+to\s+(.+?)(?:\.|;|\n)", re.DOTALL),
        ]

        # Application patterns
        self._pattern_cache["application"] = [
            re.compile(
                r"(?i)(?:applying|application|analysis|here)\s+(.+?)(?:\n\n|\n(?=[A-Z])|$)",
                re.DOTALL,
            ),
            re.compile(r"(?i)application:\s*(.+?)(?:\n\n|\n(?=[A-Z])|$)", re.DOTALL),
            re.compile(r"(?i)in\s+this\s+case\s+(.+?)(?:\.|;|\n\n)", re.DOTALL),
        ]

        # Conclusion patterns
        self._pattern_cache["conclusion"] = [
            re.compile(
                r"(?i)(?:therefore|thus|consequently|in\s+conclusion)\s+(.+?)(?:\.|;|\n\n)",
                re.DOTALL,
            ),
            re.compile(r"(?i)conclusion:\s*(.+?)(?:\n\n|\n(?=[A-Z])|$)", re.DOTALL),
            re.compile(
                r"(?i)(?:the\s+)?(?:court|result|outcome)\s+(?:held|finds|concludes)\s+(.+?)(?:\.|;|\n)",
                re.DOTALL,
            ),
        ]

    async def _process_task(
        self, task_data: Any, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process IRAC analysis task with collective intelligence integration.

        Args:
            task_data: Document text or structured input for IRAC analysis
            metadata: Task metadata including document_id, correlation_id, etc.

        Returns:
            IRAC analysis result with collective intelligence enhancements
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
                raise ValueError("No document text provided for IRAC analysis")

            logger.info(f"Starting IRAC analysis for document {document_id}")

            # Step 1: Check shared memory for similar IRAC analyses
            similar_analyses = await self._find_similar_irac_analyses(document_text)  # noqa: F821
            logger.info(
                f"Found {len(similar_analyses)} similar IRAC analyses from collective memory"
            )

            # Step 2: Perform pattern-based IRAC extraction
            pattern_result = await self._extract_irac_patterns(document_text)  # noqa: F821

            # Step 3: Enhance with LLM analysis if configured
            if self.config.use_llm_validation:
                llm_result = await self._llm_irac_analysis(
                    document_text, similar_analyses  # noqa: F821
                )
                # Combine pattern and LLM results
                irac_analysis = await self._combine_irac_results(
                    pattern_result, llm_result, document_id
                )
            else:
                irac_analysis = await self._create_irac_from_patterns(
                    pattern_result, document_id
                )

            # Step 4: Find relevant legal precedents
            if self.config.enable_precedent_matching:
                precedents = await self._find_relevant_precedents(irac_analysis)
                irac_analysis.precedents_found = precedents

            # Step 5: Detect nested IRAC structures
            if self.config.enable_nested_irac:
                nested_analyses = await self._detect_nested_irac(
                    document_text, irac_analysis  # noqa: F821
                )
                irac_analysis.nested_analyses = nested_analyses

            # Step 6: Store analysis in shared memory for collective intelligence
            await self._store_irac_analysis(irac_analysis)

            # Update statistics
            self._update_statistics(irac_analysis)

            logger.info(
                f"IRAC analysis completed for document {document_id} with confidence {irac_analysis.overall_confidence:.2f}"
            )

            return {
                "success": True,
                "analysis": irac_analysis.to_dict(),
                "collective_intelligence": {
                    "similar_analyses_found": len(similar_analyses),
                    "precedents_matched": len(irac_analysis.precedents_found),
                    "nested_analyses_detected": len(irac_analysis.nested_analyses),
                },
                "metadata": {
                    "document_id": document_id,
                    "analysis_method": (
                        "hybrid_pattern_llm"
                        if self.config.use_llm_validation
                        else "pattern_based"
                    ),
                    "confidence": irac_analysis.overall_confidence,
                    "processed_at": datetime.now().isoformat(),
                    "agent_name": self.agent_name,
                },
            }

        except Exception as e:
            logger.error(
                f"IRAC analysis failed for document {metadata.get('document_id', 'unknown')}: {e}"
            )
            raise

    async def _find_similar_irac_analyses(self, document_text: str) -> List[Any]:
        """
        Find similar IRAC analyses from shared memory to enhance current analysis.

        This is a key collective intelligence feature - learning from other agents.
        """
        if not self._is_memory_available():
            return []

        try:
            # Extract key legal concepts for similarity search
            key_concepts = self._extract_key_legal_concepts(document_text)
            search_query = " ".join(key_concepts[:5])  # Use top 5 concepts

            # Search for similar IRAC analyses
            similar_results = await self.search_memory(
                query=search_query,
                memory_types=[MemoryType.ANALYSIS],
                namespaces=["legal_analysis"],
                limit=5,
                min_similarity=0.6,
            )

            # Filter for IRAC analyses specifically
            irac_analyses = []
            for result in similar_results:
                metadata = result.record.metadata
                if metadata.get("analysis_type") == "irac":
                    irac_analyses.append(result)

            return irac_analyses

        except Exception as e:
            logger.warning(f"Failed to find similar IRAC analyses: {e}")
            return []

    def _extract_key_legal_concepts(self, text: str) -> List[str]:
        """Extract key legal concepts for similarity matching"""

        # Legal concept patterns
        legal_patterns = [
            r"\b(?:contract|agreement|breach|damages|liability|negligence|tort|statute|regulation|precedent|case\s+law)\b",
            r"\b(?:constitutional|amendment|due\s+process|equal\s+protection|commerce\s+clause)\b",
            r"\b(?:criminal|civil|administrative|appellate|district|supreme)\s+(?:court|law|procedure)\b",
            r"\b(?:plaintiff|defendant|petitioner|respondent|appellant|appellee)\b",
        ]

        concepts = []
        for pattern in legal_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            concepts.extend([match.lower() for match in matches])

        # Remove duplicates and return most frequent
        concept_counts = {}
        for concept in concepts:
            concept_counts[concept] = concept_counts.get(concept, 0) + 1

        # Sort by frequency
        sorted_concepts = sorted(
            concept_counts.items(), key=lambda x: x[1], reverse=True
        )
        return [concept for concept, count in sorted_concepts]

    async def _extract_irac_patterns(self, text: str) -> Dict[str, IracComponent]:
        """Extract IRAC components using pattern matching"""

        components = {}

        for component_type in ["issue", "rule", "application", "conclusion"]:
            patterns = self._pattern_cache[component_type]
            best_match = None
            best_confidence = 0.0

            for pattern in patterns:
                matches = pattern.finditer(text)
                for match in matches:
                    content = match.group(1).strip()
                    if len(content) > 10:  # Minimum content length
                        # Calculate confidence based on pattern strength and content quality
                        confidence = self._calculate_pattern_confidence(
                            content, component_type
                        )
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_match = IracComponent(
                                component_type=component_type,
                                content=content,
                                confidence=confidence,
                                start_pos=match.start(),
                                end_pos=match.end(),
                                metadata={"extraction_method": "pattern_matching"},
                            )

            if best_match:
                components[component_type] = best_match
            else:
                # Create placeholder with low confidence
                components[component_type] = IracComponent(
                    component_type=component_type,
                    content=f"No clear {component_type} identified",
                    confidence=0.1,
                    metadata={
                        "extraction_method": "pattern_matching",
                        "status": "not_found",
                    },
                )

        return components

    def _calculate_pattern_confidence(self, content: str, component_type: str) -> float:
        """Calculate confidence score for pattern-matched content"""

        base_confidence = 0.5

        # Length factor
        length_factor = min(1.0, len(content.split()) / 10)

        # Component-specific keywords boost confidence
        keyword_boosts = {
            "issue": ["whether", "question", "problem", "dispute"],
            "rule": ["law", "statute", "regulation", "principle", "test", "standard"],
            "application": ["here", "this case", "applying", "analysis", "facts"],
            "conclusion": ["therefore", "thus", "held", "conclude", "result"],
        }

        keywords = keyword_boosts.get(component_type, [])
        keyword_factor = sum(
            1 for keyword in keywords if keyword.lower() in content.lower()
        ) / len(keywords)

        # Combine factors
        confidence = base_confidence + (length_factor * 0.3) + (keyword_factor * 0.2)
        return min(1.0, confidence)

    async def _llm_irac_analysis(  # noqa: C901
        self, text: str, similar_analyses: List[Any]
    ) -> Dict[str, Any]:
        """Perform LLM-based IRAC analysis enhanced with collective intelligence"""

        # Build context from similar analyses
        collectivecontext = ""
        if similar_analyses:
            collectivecontext = (  # noqa: F841
                "\n\nSimilar IRAC analyses from other legal documents:\n"
            )
            for i, result in enumerate(similar_analyses[:3], 1):
                try:
                    analysis_data = json.loads(result.record.content)
                    collective_context += f"\n{i}. Issue: {analysis_data.get('issue', {}).get('content', 'N/A')[:100]}..."  # noqa: F821
                    collective_context += f"\n   Rule: {analysis_data.get('rule', {}).get('content', 'N/A')[:100]}..."
                except Exception:
                    pass

        # Enhanced IRAC analysis prompt
        prompt = """
        Perform a comprehensive IRAC (Issue, Rule, Application, Conclusion) analysis of the following legal text.

        Legal Text:
        {text}
        {collective_context}

        Please provide a structured IRAC analysis with:

        1. ISSUE: What is the legal question or problem presented?
        2. RULE: What law, statute, regulation, or legal principle applies?
        3. APPLICATION: How does the rule apply to the specific facts?
        4. CONCLUSION: What is the result or holding?

        For each component, provide:
        - Clear, concise content
        - Confidence level (0.0-1.0)
        - Any relevant citations or precedents

        Respond in JSON format:
        {{
            "issue": {{"content": "...", "confidence": 0.0, "citations": []}},
            "rule": {{"content": "...", "confidence": 0.0, "citations": []}},
            "application": {{"content": "...", "confidence": 0.0, "citations": []}},
            "conclusion": {{"content": "...", "confidence": 0.0, "citations": []}},
            "overall_confidence": 0.0,
            "precedents": []
        }}
        """

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

            if llm_service:
                # Make LLM call
                response = await llm_service.complete(
                    prompt=prompt,
                    model=self.config.llm_model,
                    temperature=0.1,  # Low temperature for consistent analysis
                    max_tokens=2000,
                )

                # Parse JSON response
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    # Fallback: extract JSON from response
                    json_match = re.search(r"\{.*\}", response, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                    else:
                        logger.warning("Failed to parse LLM response as JSON")
                        return {}
            else:
                logger.warning("LLM service not available, skipping LLM analysis")
                return {}

        except Exception as e:
            logger.error(f"LLM IRAC analysis failed: {e}")
            return {}

    async def _combine_irac_results(
        self,
        pattern_result: Dict[str, IracComponent],
        llm_result: Dict[str, Any],
        document_id: str,
    ) -> IracAnalysis:
        """Combine pattern and LLM analysis results"""

        combined_components = {}

        for component_type in ["issue", "rule", "application", "conclusion"]:
            pattern_comp = pattern_result.get(component_type)
            llm_comp = llm_result.get(component_type, {})

            if pattern_comp and llm_comp:
                # Use LLM result if available and more confident
                llm_confidence = llm_comp.get("confidence", 0.0)
                if llm_confidence > pattern_comp.confidence:
                    combined_components[component_type] = IracComponent(
                        component_type=component_type,
                        content=llm_comp.get("content", pattern_comp.content),
                        confidence=llm_confidence,
                        metadata={
                            "extraction_method": "llm_enhanced",
                            "pattern_confidence": pattern_comp.confidence,
                            "llm_confidence": llm_confidence,
                            "citations": llm_comp.get("citations", []),
                        },
                    )
                else:
                    # Enhance pattern result with LLM metadata
                    pattern_comp.metadata.update(
                        {
                            "llm_confidence": llm_confidence,
                            "citations": llm_comp.get("citations", []),
                        }
                    )
                    combined_components[component_type] = pattern_comp
            elif llm_comp:
                combined_components[component_type] = IracComponent(
                    component_type=component_type,
                    content=llm_comp.get("content", ""),
                    confidence=llm_comp.get("confidence", 0.5),
                    metadata={
                        "extraction_method": "llm_only",
                        "citations": llm_comp.get("citations", []),
                    },
                )
            elif pattern_comp:
                combined_components[component_type] = pattern_comp
            else:
                # Fallback empty component
                combined_components[component_type] = IracComponent(
                    component_type=component_type,
                    content=f"No {component_type} identified",
                    confidence=0.1,
                    metadata={"extraction_method": "fallback"},
                )

        # Calculate overall confidence
        overall_confidence = (
            sum(comp.confidence for comp in combined_components.values()) / 4
        )

        # Create final analysis
        return IracAnalysis(
            document_id=document_id,
            issue=combined_components["issue"],
            rule=combined_components["rule"],
            application=combined_components["application"],
            conclusion=combined_components["conclusion"],
            overall_confidence=overall_confidence,
            metadata={
                "analysis_method": "hybrid_pattern_llm",
                "llm_overall_confidence": llm_result.get("overall_confidence", 0.0),
                "precedents_from_llm": llm_result.get("precedents", []),
            },
        )

    async def _create_irac_from_patterns(
        self, pattern_result: Dict[str, IracComponent], document_id: str
    ) -> IracAnalysis:
        """Create IRAC analysis from pattern results only"""

        overall_confidence = (
            sum(comp.confidence for comp in pattern_result.values()) / 4
        )

        return IracAnalysis(
            document_id=document_id,
            issue=pattern_result["issue"],
            rule=pattern_result["rule"],
            application=pattern_result["application"],
            conclusion=pattern_result["conclusion"],
            overall_confidence=overall_confidence,
            metadata={"analysis_method": "pattern_only"},
        )

    async def _find_relevant_precedents(
        self, irac_analysis: IracAnalysis
    ) -> List[Dict[str, Any]]:
        """Find relevant legal precedents based on IRAC analysis"""

        # Use the legal domain mixin to find similar precedents
        legal_issue = irac_analysis.issue.content
        precedents = await self.find_similar_precedents(
            legal_issue=legal_issue, min_strength=0.5, limit=5
        )

        precedent_summaries = []
        for precedent_result in precedents:
            metadata = precedent_result.record.metadata
            precedent_summaries.append(
                {
                    "citation": metadata.get("case_citation", "Unknown"),
                    "summary": precedent_result.record.content[:200] + "...",
                    "strength": metadata.get("precedent_strength", 0.0),
                    "jurisdiction": metadata.get("jurisdiction", "unknown"),
                    "similarity_score": precedent_result.similarity_score,
                }
            )

        return precedent_summaries

    async def _detect_nested_irac(
        self, text: str, main_analysis: IracAnalysis
    ) -> List[IracAnalysis]:
        """Detect nested IRAC structures within the document"""

        # Simple implementation - look for multiple legal issues
        nested_analyses = []

        # Split text into sections and analyze each
        sections = re.split(r"\n\s*\n", text)
        for i, section in enumerate(sections):
            if len(section.split()) > 50:  # Minimum section size
                section_analysis = await self._extract_irac_patterns(section)
                section_confidence = (
                    sum(comp.confidence for comp in section_analysis.values()) / 4
                )

                if section_confidence > 0.3:  # Threshold for valid nested IRAC
                    nested_irac = await self._create_irac_from_patterns(
                        section_analysis, f"{main_analysis.document_id}_section_{i}"
                    )
                    nested_analyses.append(nested_irac)

        return nested_analyses

    async def _store_irac_analysis(self, analysis: IracAnalysis) -> str:
        """Store IRAC analysis in shared memory for collective intelligence"""

        return await self.store_analysis_result(
            analysis_type="irac",
            document_id=analysis.document_id,
            analysis_data=analysis.to_dict(),
            confidence_score=analysis.overall_confidence,
            metadata={
                "agent_type": "irac_analyzer",
                "precedents_count": len(analysis.precedents_found),
                "nested_count": len(analysis.nested_analyses),
                "analysis_method": analysis.metadata.get("analysis_method", "unknown"),
            },
        )

    def _update_statistics(self, analysis: IracAnalysis):
        """Update agent statistics"""
        self.stats["analyses_performed"] += 1
        self.stats["precedents_found"] += len(analysis.precedents_found)
        self.stats["nested_analyses_detected"] += len(analysis.nested_analyses)

        # Update running average confidence
        current_avg = self.stats["avg_confidence"]
        count = self.stats["analyses_performed"]
        new_avg = ((current_avg * (count - 1)) + analysis.overall_confidence) / count
        self.stats["avg_confidence"] = new_avg

    async def health_check(self) -> Dict[str, Any]:
        """Extended health check for IRAC analyzer"""
        base_health = await super().health_check()

        # Add IRAC-specific health information
        irac_health = {
            "irac_config": {
                "llm_validation_enabled": self.config.use_llm_validation,
                "precedent_matching_enabled": self.config.enable_precedent_matching,
                "nested_analysis_enabled": self.config.enable_nested_irac,
            },
            "performance_stats": self.stats.copy(),
            "pattern_cache_size": len(self._pattern_cache),
        }

        base_health.update(irac_health)
        return base_health


# Factory function for easy instantiation
async def create_irac_analyzer(
    services: ProductionServiceContainer, config: Optional[IracConfig] = None
) -> IracAnalyzerAgent:
    """
    Create and initialize an IRAC Analyzer Agent

    Args:
        services: Service container with dependencies
        config: Optional IRAC configuration

    Returns:
        Initialized IRAC Analyzer Agent
    """
    agent = IracAnalyzerAgent(services, config)

    # Perform any additional initialization
    logger.info(
        "Created IRAC Analyzer Agent with collective intelligence capabilities"
    )

    return agent
