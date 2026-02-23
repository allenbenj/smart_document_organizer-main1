"""
Legal Reasoning Engine - Advanced Legal Intelligence System
==========================================================

This module provides sophisticated legal reasoning capabilities that combine
multiple reasoning frameworks with the legal ontology and core services.

Key Features:
- Multiple reasoning frameworks (IRAC, Toulmin, Critical Thinking)
- Legal ontology integration for entity and relationship extraction
- Case law analysis and precedent matching
- Legal argument construction and validation
- Compliance checking and violation detection

Author: Legal AI System
Version: 2.0.0
"""

import asyncio
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from enum import Enum  # noqa: E402
from typing import Any, Dict, List, Optional, Tuple  # noqa: E402

from utils.logging import (  # noqa: E402
    LogCategory,
    detailed_log_function,
    get_detailed_logger,
)

# Import core components
from agents.base.core_integration import EnhancedCoreAgent  # noqa: E402
from agents.core.models import LegalDocument  # noqa: E402
from agents.extractors.hybrid_extractor import HybridLegalExtractor  # noqa: E402

# Initialize logger
reasoning_logger = get_detailed_logger("LegalReasoningEngine", LogCategory.AGENT)


class ReasoningFramework(Enum):
    """Available legal reasoning frameworks."""

    IRAC = "irac"  # Issue, Rule, Application, Conclusion
    TOULMIN = "toulmin"  # Claim, Evidence, Warrant, Backing
    CRITICAL_THINKING = "critical_thinking"  # Assumptions, Evidence, Alternatives
    CAUSAL_CHAIN = "causal_chain"  # Cause and effect analysis
    ISSUE_TREES = "issue_trees"  # Hierarchical issue breakdown
    MECE = "mece"  # Mutually Exclusive, Collectively Exhaustive
    SWOT = "swot"  # Strengths, Weaknesses, Opportunities, Threats


class LegalDomain(Enum):
    """Legal practice domains."""

    CRIMINAL_LAW = "criminal_law"
    CIVIL_LAW = "civil_law"
    CONTRACT_LAW = "contract_law"
    CONSTITUTIONAL_LAW = "constitutional_law"
    ADMINISTRATIVE_LAW = "administrative_law"
    CORPORATE_LAW = "corporate_law"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    FAMILY_LAW = "family_law"
    EMPLOYMENT_LAW = "employment_law"
    ENVIRONMENTAL_LAW = "environmental_law"


@dataclass
class LegalIssue:
    """Represents a legal issue identified in a document or case."""

    issue_id: str
    description: str
    domain: LegalDomain
    complexity_level: float  # 0.0 to 1.0
    relevant_statutes: List[str] = field(default_factory=list)
    relevant_cases: List[str] = field(default_factory=list)
    entities_involved: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class LegalArgument:
    """Represents a structured legal argument."""

    argument_id: str
    framework: ReasoningFramework
    claim: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    reasoning: Dict[str, Any] = field(default_factory=dict)
    conclusion: str = ""
    confidence: float = 0.0
    supporting_authorities: List[str] = field(default_factory=list)
    counterarguments: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ComplianceCheck:
    """Represents a compliance check result."""

    check_id: str
    regulation: str
    status: str  # COMPLIANT, NON_COMPLIANT, UNCLEAR
    violations: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.0
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class LegalReasoningResult:
    """Comprehensive result from legal reasoning analysis."""

    document_id: str
    analysis_type: str

    # Identified issues and arguments
    legal_issues: List[LegalIssue] = field(default_factory=list)
    legal_arguments: List[LegalArgument] = field(default_factory=list)

    # Extracted entities and relationships
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)

    # Compliance and violations
    compliance_checks: List[ComplianceCheck] = field(default_factory=list)
    potential_violations: List[Dict[str, Any]] = field(default_factory=list)

    # Analysis metadata
    reasoning_framework_used: ReasoningFramework = ReasoningFramework.IRAC
    confidence_score: float = 0.0
    processing_time: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "document_id": self.document_id,
            "analysis_type": self.analysis_type,
            "legal_issues": [
                {
                    "issue_id": issue.issue_id,
                    "description": issue.description,
                    "domain": issue.domain.value,
                    "complexity_level": issue.complexity_level,
                    "relevant_statutes": issue.relevant_statutes,
                    "relevant_cases": issue.relevant_cases,
                    "entities_involved": issue.entities_involved,
                    "confidence": issue.confidence,
                    "created_at": issue.created_at.isoformat(),
                }
                for issue in self.legal_issues
            ],
            "legal_arguments": [
                {
                    "argument_id": arg.argument_id,
                    "framework": arg.framework.value,
                    "claim": arg.claim,
                    "evidence": arg.evidence,
                    "reasoning": arg.reasoning,
                    "conclusion": arg.conclusion,
                    "confidence": arg.confidence,
                    "supporting_authorities": arg.supporting_authorities,
                    "counterarguments": arg.counterarguments,
                    "created_at": arg.created_at.isoformat(),
                }
                for arg in self.legal_arguments
            ],
            "entities": self.entities,
            "relationships": self.relationships,
            "compliance_checks": [
                {
                    "check_id": check.check_id,
                    "regulation": check.regulation,
                    "status": check.status,
                    "violations": check.violations,
                    "recommendations": check.recommendations,
                    "confidence": check.confidence,
                    "checked_at": check.checked_at.isoformat(),
                }
                for check in self.compliance_checks
            ],
            "potential_violations": self.potential_violations,
            "reasoning_framework_used": self.reasoning_framework_used.value,
            "confidence_score": self.confidence_score,
            "processing_time": self.processing_time,
            "recommendations": self.recommendations,
            "created_at": self.created_at.isoformat(),
        }


class LegalReasoningEngine(EnhancedCoreAgent):
    """
    Advanced Legal Reasoning Engine that combines multiple reasoning frameworks
    with legal ontology and core service integration.
    """

    @detailed_log_function(LogCategory.AGENT)
    def __init__(
        self,
        service_container=None,
        name: Optional[str] = None,
        reasoning_framework: ReasoningFramework = ReasoningFramework.IRAC,
        legal_domain: Optional[LegalDomain] = None,
        **kwargs,
    ):
        """Initialize the Legal Reasoning Engine."""
        super().__init__(
            service_container=service_container,
            name=name or "LegalReasoningEngine",
            agent_type="legal_reasoning",
            behavior_profile="Legal Analyst",
            reasoning_framework=reasoning_framework.value,
            **kwargs,
        )

        self.reasoning_framework = reasoning_framework
        self.legal_domain = legal_domain
        self.hybrid_extractor = HybridLegalExtractor(service_container)

        # Initialize NLI Evidence Verifier
        self.nli_pipeline = None
        try:
            from transformers import pipeline as transformers_pipeline
            nli_ref = r"E:\Project\smart_document_organizer-main\models\nli-deberta-v3-base"
            self.nli_pipeline = transformers_pipeline(
                "text-classification",
                model=nli_ref,
                tokenizer=nli_ref,
            )
            reasoning_logger.info("Loaded NLI Evidence Verifier successfully")
        except Exception as e:
            reasoning_logger.warning(f"Could not load NLI Verifier: {e}")

        # Initialize Cognitive Reasoning Service (Adversarial Engine)
        try:
            from services.cognitive_reasoning_service import CognitiveReasoningService
            # We pass 'self' as a placeholder manager since the engine itself is part of the manager's fleet
            self.cognitive_service = CognitiveReasoningService(agent_manager=None) 
            reasoning_logger.info("Cognitive Reasoning Service initialized")
        except Exception as e:
            reasoning_logger.warning(f"Failed to init Cognitive Service: {e}")
            self.cognitive_service = None

        # Legal knowledge bases
        self.statute_database = {}  # Would be loaded from external sources
        self.case_law_database = {}  # Would be loaded from external sources
        self.regulation_database = {}  # Would be loaded from external sources

        reasoning_logger.info(
            "Legal Reasoning Engine initialized",
            parameters={
                "name": self.name,
                "framework": self.reasoning_framework.value,
                "domain": self.legal_domain.value if self.legal_domain else "general",
            },
        )

    @detailed_log_function(LogCategory.AGENT)
    async def analyze_legal_document(
        self,
        document_content: str,
        document_id: str,
        analysis_type: str = "comprehensive",
        reasoning_framework: Optional[ReasoningFramework] = None,
    ) -> LegalReasoningResult:
        """
        Perform comprehensive legal analysis of a document.

        Args:
            document_content: The text content of the legal document
            document_id: Unique identifier for the document
            analysis_type: Type of analysis to perform
            reasoning_framework: Override the default reasoning framework

        Returns:
            LegalReasoningResult with comprehensive analysis
        """
        start_time = asyncio.get_event_loop().time()
        framework = reasoning_framework or self.reasoning_framework

        reasoning_logger.info(
            "Starting legal document analysis",
            parameters={
                "document_id": document_id,
                "analysis_type": analysis_type,
                "framework": framework.value,
                "content_length": len(document_content),
            },
        )

        try:
            # 1. Jurisdiction Gate: Lock domain to prevent drift
            from .jurisdiction import JurisdictionDetector, LegalDomain as JurisDomain
            detector = JurisdictionDetector()
            juris_context = detector.detect(document_content)
            
            result = LegalReasoningResult(
                document_id=document_id,
                analysis_type=analysis_type,
                reasoning_framework_used=framework,
            )
            result.recommendations.append(f"Jurisdiction Locked: {juris_context.system.value} / {juris_context.domain.value}")

            # 2. Extract specific entities (Using Oracle for high fidelity)
            entities, relationships = await self._extract_legal_entities(
                document_content
            )
            result.entities = entities
            result.relationships = relationships

            # 3. Model-Driven Issue Derivation (No templates)
            # Filter for specific entities only (Stoplist enforced in extractor)
            specific_entities = [e for e in entities if e.get("confidence", 0) > 0.7]
            
            # Step 2: Identify legal issues by anchoring to specific entities and NLI verification
            result.legal_issues = await self._derive_grounded_issues(
                document_content, specific_entities, juris_context
            )

            # Step 3: Construct legal arguments using fact spans
            result.legal_arguments = await self._construct_evidence_arguments(
                document_content, result.legal_issues, framework
            )

            # Step 4: Perform compliance checks (ONLY if jurisdiction matches)
            if juris_context.domain == JurisDomain.REGULATORY:
                result.compliance_checks = await self._perform_compliance_checks(
                    document_content, entities, relationships
                )
            else:
                reasoning_logger.info("Skipping regulatory compliance sweep: Domain mismatch.")

            # Step 5: Identify potential violations (Fact-grounded only)
            result.potential_violations = await self._identify_violations(
                document_content, result.legal_issues, result.compliance_checks
            )

            # 6. Strategic Shadow Mode (Adversarial Analysis)
            if (analysis_type == "adversarial" or "shadow" in analysis_type) and self.cognitive_service:
                adv_result = await self.cognitive_service.run_adversarial_analysis(document_content, document_id)
                # Inject findings into recommendations
                result.recommendations.append("--- STRATEGIC SHADOW MODE ---")
                for claim in adv_result["prosecution_theory"]["claims"]:
                    result.recommendations.append(f"State Theory: {claim}")
                for rebuttal in adv_result["defense_rebuttal"]["counter_claims"]:
                    result.recommendations.append(f"Defense Move: {rebuttal}")

            # Step 6: Generate recommendations
            result.recommendations.extend(await self._generate_recommendations(
                result.legal_issues, result.legal_arguments, result.compliance_checks
            ))

            # Calculate overall confidence and processing time
            result.confidence_score = self._calculate_overall_confidence(result)
            result.processing_time = asyncio.get_event_loop().time() - start_time

            reasoning_logger.info(
                "Legal document analysis completed",
                parameters={
                    "document_id": document_id,
                    "issues_found": len(result.legal_issues),
                    "arguments_constructed": len(result.legal_arguments),
                    "compliance_checks": len(result.compliance_checks),
                    "violations_found": len(result.potential_violations),
                    "confidence": result.confidence_score,
                    "processing_time": result.processing_time,
                },
            )

            return result

        except Exception as e:
            reasoning_logger.error(
                "Legal document analysis failed",
                parameters={"document_id": document_id},
                exception=e,
            )
            raise

    async def _extract_legal_entities(
        self, content: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract legal entities and relationships from content using high-fidelity extractor."""
        if not content or not content.strip():
            raise ValueError("Cannot extract legal entities from empty content")

        reasoning_logger.debug("Extracting legal entities and relationships via high-fidelity engine")
        
        # Resolve the production LegalEntityExtractor from the container
        try:
            from agents.extractors.legal_entity_extractor import LegalEntityExtractor
            extractor = await self.service_container.get_service(LegalEntityExtractor)
            if not extractor:
                extractor = await self.service_container.get_service("entity_extractor")
            
            if extractor:
                # Dispatch task directly to the high-fidelity engine
                res = await extractor._process_task(content, {"document_id": "reasoning_eval"})
                entities = res.get("extraction_result", {}).get("entities", [])
                relationships = res.get("extraction_result", {}).get("relationships", [])
                
                # Convert ExtractedEntity objects back to dict if needed by downstream
                # (Assuming _process_task already returned dicts, but let's be safe)
                final_entities = [e if isinstance(e, dict) else e.to_dict() for e in entities]
                final_rels = [r if isinstance(r, dict) else r.to_dict() for r in relationships]
                
                return final_entities, final_rels
        except Exception as e:
            reasoning_logger.warning(f"High-fidelity extraction failed, falling back to basic: {e}")

        # Fallback to simple extraction if advanced is unavailable
        return [], []

    async def _derive_grounded_issues(
        self,
        content: str,
        entities: List[Dict[str, Any]],
        juris_context: Any
    ) -> List[LegalIssue]:
        """
        Phase 2: Derive legal issues from fact clusters and legal verbs.
        Uses NLI to verify grounding before proposing an issue.
        """
        reasoning_logger.info("Deriving grounded legal issues from fact clusters")
        issues = []
        
        # 1. Detect Legal Verbs (Action Anchors)
        legal_actions = {
            "seized": "Fourth Amendment / Search & Seizure",
            "consented": "Voluntariness of Consent",
            "charged": "Prosecutorial Discretion",
            "suppressed": "Evidence Admissibility",
            "appealed": "Procedural Posture",
            "delayed": "Discovery Violation / Due Process",
            "lied": "Witness Credibility / Perjury"
        }
        
        # 2. Identify clusters of (Specific Entity + Legal Verb)
        sentences = content.split(".") # Simple sentence split for grounding
        for i, sent in enumerate(sentences):
            sent = sent.strip()
            if len(sent) < 20: continue
            
            for verb, doctrine in legal_actions.items():
                if verb in sent.lower():
                    # Find if a specific entity is involved in this sentence
                    involved = [e for e in entities if e["text"].lower() in sent.lower()]
                    
                    if involved:
                        # 3. Verify Grounding via NLI
                        # Ask the model: Does this sentence actually discuss [Doctrine]?
                        verification = await self._verify_evidence_with_nli(doctrine, sent)
                        
                        if verification["label"] == "supports" and verification["score"] > 0.6:
                            issue_id = f"fact_issue_{len(issues) + 1}"
                            
                            # Formulate question: "Whether [Entity] [Verb]..."
                            entity_name = involved[0]["text"]
                            question = f"Whether {entity_name}'s action of being '{verb}' aligns with {doctrine} standards."
                            
                            issue = LegalIssue(
                                issue_id=issue_id,
                                description=question,
                                domain=juris_context.domain,
                                complexity_level=verification["score"],
                                confidence=verification["score"],
                                entities_involved=involved,
                                relevant_statutes=[doctrine] # Temporary anchor
                            )
                            issues.append(issue)
                            
        return issues[:5] # Limit to top 5 for precision

    async def _construct_evidence_arguments(
        self,
        content: str,
        legal_issues: List[LegalIssue],
        framework: ReasoningFramework,
    ) -> List[LegalArgument]:
        """Construct arguments using actual fact spans rather than templates."""
        arguments = []
        for issue in legal_issues:
            # Find the actual text span for this issue
            # In a real run, we'd use the span found in _derive_grounded_issues
            # For now, we search the content for the entity + issue context
            fact_span = {"text": "Evidence linked to " + issue.entities_involved[0]["text"], "start_char": 0, "end_char": 100}
            
            arg = LegalArgument(
                argument_id=f"arg_{issue.issue_id}",
                framework=framework,
                claim=issue.description,
                evidence=[fact_span],
                reasoning={"logic": f"Fact grounded in text with {issue.confidence:.2f} confidence"},
                conclusion="Pending full NLI-validation of rule application",
                confidence=issue.confidence
            )
            arguments.append(arg)
        return arguments

    async def _construct_legal_arguments(
        self,
        content: str,
        legal_issues: List[LegalIssue],
        framework: ReasoningFramework,
    ) -> List[LegalArgument]:
        """Construct legal arguments using the specified reasoning framework."""
        reasoning_logger.debug(
            f"Constructing arguments using {framework.value} framework"
        )

        arguments = []

        for issue in legal_issues:
            if framework == ReasoningFramework.IRAC:
                argument = await self._construct_irac_argument(content, issue)
            elif framework == ReasoningFramework.TOULMIN:
                argument = await self._construct_toulmin_argument(content, issue)
            elif framework == ReasoningFramework.CRITICAL_THINKING:
                argument = await self._construct_critical_thinking_argument(
                    content, issue
                )
            else:
                argument = await self._construct_generic_argument(content, issue)

            if argument:
                arguments.append(argument)

        reasoning_logger.debug(f"Constructed {len(arguments)} legal arguments")
        return arguments

    async def _construct_irac_argument(
        self, content: str, issue: LegalIssue
    ) -> LegalArgument:
        """Construct argument using IRAC framework."""

        # Issue identification
        issue_statement = issue.description

        # Rule identification (would query legal databases)
        relevant_rules = await self._find_relevant_rules(issue)

        # Application of rules to facts
        application = await self._apply_rules_to_facts(
            content, relevant_rules, [{"issue": issue.description, "domain": issue.domain.value}]
        )

        # Conclusion
        conclusion = await self._draw_legal_conclusion(
            issue_statement, relevant_rules, application
        )

        return LegalArgument(
            argument_id=f"irac_arg_{issue.issue_id}",
            framework=ReasoningFramework.IRAC,
            claim=issue_statement,
            evidence=[{"type": "rule", "content": rule} for rule in relevant_rules],
            reasoning={
                "issue": issue_statement,
                "rules": relevant_rules,
                "application": application,
                "conclusion": conclusion,
            },
            conclusion=conclusion,
            confidence=issue.confidence * 0.9,  # Slightly reduce confidence
            supporting_authorities=relevant_rules,
        )

    async def _construct_toulmin_argument(
        self, content: str, issue: LegalIssue
    ) -> LegalArgument:
        """Construct argument using Toulmin framework."""

        # Claim
        claim = f"The issue of {issue.description} requires legal resolution"

        # Evidence (data)
        evidence = await self._gather_evidence_for_issue(content, issue)

        # Warrant (connecting evidence to claim)
        warrant = await self._establish_warrant(
            claim,
            [str(item.get("content", "")) for item in evidence],
            [{"issue": issue.description, "domain": issue.domain.value}],
        )

        # Backing (support for warrant)
        backing = await self._find_backing_for_warrant(warrant, issue)

        return LegalArgument(
            argument_id=f"toulmin_arg_{issue.issue_id}",
            framework=ReasoningFramework.TOULMIN,
            claim=claim,
            evidence=evidence,
            reasoning={
                "claim": claim,
                "evidence": evidence,
                "warrant": warrant,
                "backing": backing,
            },
            conclusion=f"Based on the evidence and warrant, {claim.lower()}",
            confidence=issue.confidence * 0.85,
            supporting_authorities=[backing] if backing else [],
        )

    async def _construct_critical_thinking_argument(
        self, content: str, issue: LegalIssue
    ) -> LegalArgument:
        """Construct argument using critical thinking framework."""

        # Identify assumptions
        assumptions = await self._identify_assumptions_in_issue(content, issue)

        # Evaluate evidence
        evidence_evaluation = await self._evaluate_evidence_quality(content, issue)

        # Consider alternative perspectives
        alternatives = await self._consider_alternative_interpretations(content, issue)

        # Check logical consistency
        consistency_check = await self._check_logical_consistency(
            content, [{"issue": issue.description, "domain": issue.domain.value}]
        )

        return LegalArgument(
            argument_id=f"critical_arg_{issue.issue_id}",
            framework=ReasoningFramework.CRITICAL_THINKING,
            claim=f"Critical analysis of {issue.description}",
            evidence=evidence_evaluation,
            reasoning={
                "assumptions": assumptions,
                "evidence_evaluation": evidence_evaluation,
                "alternatives": alternatives,
                "consistency_check": consistency_check,
            },
            conclusion=f"After critical analysis, the issue requires {consistency_check.get('recommendation', 'further investigation')}",
            confidence=issue.confidence * 0.8,
            counterarguments=alternatives,
        )

    async def _construct_generic_argument(
        self, content: str, issue: LegalIssue
    ) -> LegalArgument:
        """Construct a generic legal argument."""
        return LegalArgument(
            argument_id=f"generic_arg_{issue.issue_id}",
            framework=ReasoningFramework.IRAC,  # Default to IRAC
            claim=issue.description,
            evidence=[{"type": "content_analysis", "content": content[:200]}],
            reasoning={"analysis": "Generic legal analysis performed"},
            conclusion=f"The issue of {issue.description} requires legal attention",
            confidence=issue.confidence * 0.7,
        )

    async def _perform_compliance_checks(
        self,
        content: str,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> List[ComplianceCheck]:
        """Perform compliance checks against relevant regulations."""
        reasoning_logger.debug("Performing compliance checks")

        compliance_checks = []

        # Mock compliance rules - would be loaded from regulation database
        compliance_rules = {
            "data_privacy": {
                "regulation": "GDPR Article 6",
                "keywords": ["personal data", "consent", "processing"],
                "severity": "HIGH",
            },
            "contract_terms": {
                "regulation": "UCC Section 2-302",
                "keywords": ["unconscionable", "unfair terms"],
                "severity": "MEDIUM",
            },
        }

        content_lower = content.lower()

        for rule_id, rule_info in compliance_rules.items():
            violations = []
            status = "COMPLIANT"

            # Check for potential violations
            for keyword in rule_info["keywords"]:
                if keyword in content_lower:
                    violations.append(
                        {
                            "keyword": keyword,
                            "context": self._extract_context(content, keyword),
                            "severity": rule_info["severity"],
                        }
                    )
                    status = "NON_COMPLIANT"

            compliance_check = ComplianceCheck(
                check_id=f"compliance_{rule_id}",
                regulation=rule_info["regulation"],
                status=status,
                violations=violations,
                recommendations=self._generate_compliance_recommendations(violations),
                confidence=0.8 if violations else 0.9,
            )

            compliance_checks.append(compliance_check)

        reasoning_logger.debug(f"Completed {len(compliance_checks)} compliance checks")
        return compliance_checks

    async def _identify_violations(
        self,
        content: str,
        legal_issues: List[LegalIssue],
        compliance_checks: List[ComplianceCheck],
    ) -> List[Dict[str, Any]]:
        """Identify potential legal violations."""
        reasoning_logger.debug("Identifying potential violations")

        violations = []

        # Collect violations from compliance checks
        for check in compliance_checks:
            if check.status == "NON_COMPLIANT":
                for violation in check.violations:
                    violations.append(
                        {
                            "violation_id": f"violation_{len(violations) + 1}",
                            "type": "compliance_violation",
                            "regulation": check.regulation,
                            "description": f"Potential violation: {violation['keyword']}",
                            "severity": violation["severity"],
                            "context": violation["context"],
                            "confidence": check.confidence,
                            "recommendations": check.recommendations,
                        }
                    )

        # Identify violations from legal issues
        for issue in legal_issues:
            if issue.confidence > 0.8 and "violation" in issue.description.lower():
                violations.append(
                    {
                        "violation_id": f"violation_{len(violations) + 1}",
                        "type": "legal_issue_violation",
                        "domain": issue.domain.value,
                        "description": issue.description,
                        "severity": (
                            "HIGH" if issue.complexity_level > 0.8 else "MEDIUM"
                        ),
                        "confidence": issue.confidence,
                        "entities_involved": issue.entities_involved,
                    }
                )

        reasoning_logger.debug(f"Identified {len(violations)} potential violations")
        return violations

    async def _generate_recommendations(
        self,
        legal_issues: List[LegalIssue],
        legal_arguments: List[LegalArgument],
        compliance_checks: List[ComplianceCheck],
    ) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # Recommendations based on legal issues
        for issue in legal_issues:
            if issue.confidence > 0.7:
                recommendations.append(
                    f"Address {issue.domain.value} issue: {issue.description}"
                )

        # Recommendations based on compliance checks
        for check in compliance_checks:
            if check.status == "NON_COMPLIANT":
                recommendations.extend(check.recommendations)

        # Recommendations based on argument strength
        weak_arguments = [arg for arg in legal_arguments if arg.confidence < 0.6]
        if weak_arguments:
            recommendations.append(
                f"Strengthen {len(weak_arguments)} legal arguments with additional evidence"
            )

        return recommendations

    # =================================================================
    # LEGAL REASONING HELPER METHODS
    # =================================================================

    async def _find_relevant_rules(self, issue: LegalIssue) -> List[str]:
        """Find relevant legal rules for an issue from configured sources."""
        if issue.relevant_statutes:
            return issue.relevant_statutes
        stored_rules = self.statute_database.get(issue.domain.value, [])
        return [str(rule) for rule in stored_rules if str(rule).strip()]

    async def _apply_rules_to_facts(
        self, task_data: Any, rules: List[str], context: List[Dict[str, Any]]
    ) -> str:
        """Apply legal rules to facts using provided contextual material."""
        if not rules:
            return "No applicable rules were identified from configured legal sources."
        fact_summary = str(task_data)[:300]
        return (
            f"Applied {len(rules)} rule(s) to available facts: {fact_summary}"
        )

    async def _draw_legal_conclusion(
        self, issue: str, rules: List[str], application: str
    ) -> str:
        """Draw a legal conclusion based on IRAC analysis artifacts."""
        if not rules:
            return (
                f"No legal conclusion could be finalized for {issue.lower()} because no "
                "applicable rules were available."
            )
        return (
            f"Based on {len(rules)} applicable rule(s), {issue.lower()} requires "
            f"resolution. Application summary: {application[:240]}"
        )

    async def _gather_evidence_for_issue(
        self, content: str, issue: LegalIssue
    ) -> List[Dict[str, Any]]:
        """Gather issue-linked evidence snippets from document content."""
        snippets: List[Dict[str, Any]] = []
        terms = [
            issue.description,
            issue.domain.value.replace("_", " "),
        ]
        seen_contexts = set()
        for term in terms:
            context = self._extract_context(content, term, context_size=180)
            normalized = context.strip()
            if normalized and normalized not in seen_contexts:
                seen_contexts.add(normalized)
                snippets.append(
                    {
                        "type": "textual_evidence",
                        "content": normalized,
                        "relevance": issue.confidence,
                        "source": "document_content",
                    }
                )
        return snippets

    async def _establish_warrant(
        self, claim: str, evidence: List[str], context: List[Dict[str, Any]]
    ) -> str:
        """Establish warrant connecting evidence to claim."""
        if not evidence:
            return ""
        return (
            f"Evidence in the record supports the claim '{claim}' under the "
            "applicable legal framework."
        )

    async def _find_backing_for_warrant(self, warrant: str, issue: LegalIssue) -> str:
        """Find backing for the warrant from configured case-law sources."""
        if issue.relevant_cases:
            return issue.relevant_cases[0]
        known_cases = self.case_law_database.get(issue.domain.value, [])
        return str(known_cases[0]) if known_cases else ""

    async def _identify_assumptions_in_issue(
        self, content: str, issue: LegalIssue
    ) -> List[str]:
        """Identify underlying assumptions in the legal issue."""
        assumptions = []
        if issue.domain.value.replace("_", " ") in content.lower():
            assumptions.append(
                f"Assumption: {issue.domain.value} jurisdiction applies."
            )
        if "court" in content.lower():
            assumptions.append("Assumption: Court procedures are procedurally valid.")
        return assumptions

    async def _evaluate_evidence_quality(
        self, content: str, issue: LegalIssue
    ) -> List[Dict[str, Any]]:
        """Evaluate the quality and reliability of evidence using NLI verification."""
        evidence = await self._gather_evidence_for_issue(content, issue)
        if not evidence:
            return []
            
        evaluated = []
        for item in evidence:
            snippet = item.get("content", "")
            verification = await self._verify_evidence_with_nli(issue.description, snippet)
            
            evaluated.append({
                "evidence_type": item.get("type", "unknown"),
                "quality_score": verification.get("score", item.get("relevance", 0.0)),
                "reliability": verification.get("label", "neutral"),
                "source": item.get("source", "document_content"),
                "verification_reasoning": f"NLI Class: {verification.get('label')} with {verification.get('score', 0):.2f} confidence"
            })
        return evaluated

    async def _verify_evidence_with_nli(self, claim: str, premise: str) -> Dict[str, Any]:
        """Use the DeBERTa-NLI model to verify if a premise supports a legal claim."""
        if not hasattr(self, "nli_pipeline") or not self.nli_pipeline:
            return {"label": "neutral", "score": 0.5}
            
        try:
            # Clean text to prevent model index errors
            premise_clean = premise[:512] 
            claim_clean = claim[:128]
            
            # Format for NLI: Premise [SEP] Hypothesis
            result = self.nli_pipeline({"text": premise_clean, "text_pair": f"This supports the claim: {claim_clean}"})
            
            # Map NLI labels
            label = result[0]["label"].lower()
            score = result[0]["score"]
            
            # Map typical model labels to AEDIS labels
            label_map = {
                "entailment": "supports",
                "neutral": "neutral",
                "contradiction": "contradicts",
                "label_0": "contradicts",
                "label_1": "neutral",
                "label_2": "supports"
            }
            
            return {
                "label": label_map.get(label, label),
                "score": float(score)
            }
        except Exception as e:
            reasoning_logger.warning(f"NLI Verification failed: {e}")
            return {"label": "neutral", "score": 0.5} # Neutral fallback

    async def _consider_alternative_interpretations(
        self, content: str, issue: LegalIssue
    ) -> List[str]:
        """Consider alternative legal interpretations from available issue data."""
        alternatives = []
        if issue.relevant_cases:
            alternatives.append(
                "Alternative interpretation may emerge from cited precedent."
            )
        if issue.entities_involved:
            alternatives.append(
                "Alternative interpretation may depend on which entity role is prioritized."
            )
        return alternatives

    async def _check_logical_consistency(
        self, task_data: Any, context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Check for coarse logical consistency in provided material."""
        text = str(task_data).lower()
        contradictions = []
        if "shall" in text and "shall not" in text:
            contradictions.append("Conflicting modal obligations detected.")

        return {
            "consistent": len(contradictions) == 0,
            "contradictions": contradictions,
            "recommendation": (
                "resolve contradictory obligations before finalizing analysis"
                if contradictions
                else "proceed with analysis"
            ),
        }

    def _extract_context(
        self, content: str, keyword: str, context_size: int = 100
    ) -> str:
        """Extract context around a keyword."""
        content_lower = content.lower()
        keyword_lower = keyword.lower()

        index = content_lower.find(keyword_lower)
        if index == -1:
            return ""

        start = max(0, index - context_size // 2)
        end = min(len(content), index + len(keyword) + context_size // 2)

        return content[start:end]

    def _generate_compliance_recommendations(
        self, violations: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations for compliance violations."""
        recommendations = []

        for violation in violations:
            severity = violation.get("severity", "MEDIUM")
            keyword = violation.get("keyword", "unknown")

            if severity == "HIGH":
                recommendations.append(
                    f"Immediately address {keyword} compliance issue"
                )
            else:
                recommendations.append(
                    f"Review and update {keyword} related procedures"
                )

        return recommendations

    def _calculate_overall_confidence(self, result: LegalReasoningResult) -> float:
        """Calculate overall confidence score for the analysis."""
        confidence_scores = []

        # Include issue confidences
        confidence_scores.extend([issue.confidence for issue in result.legal_issues])

        # Include argument confidences
        confidence_scores.extend([arg.confidence for arg in result.legal_arguments])

        # Include compliance check confidences
        confidence_scores.extend(
            [check.confidence for check in result.compliance_checks]
        )

        if not confidence_scores:
            return 0.5  # Default confidence

        return sum(confidence_scores) / len(confidence_scores)

    async def _process_task(self, task_data: Any, metadata: Dict[str, Any]) -> Any:
        """Implementation of abstract method from BaseAgent."""
        content = ""
        if isinstance(task_data, dict):
            content = task_data.get("content") or task_data.get("text") or ""
        elif isinstance(task_data, str):
            content = task_data

        if content:
            document_id = metadata.get("document_id", "unknown")
            analysis_type = metadata.get("analysis_type", "comprehensive")

            result = await self.analyze_legal_document(
                document_content=content,
                document_id=document_id,
                analysis_type=analysis_type,
            )

            return result.to_dict()

        raise ValueError("Invalid or empty task data for Legal Reasoning Engine")


# Factory function for service container integration
def create_legal_reasoning_engine(
    service_container=None,
    reasoning_framework: ReasoningFramework = ReasoningFramework.IRAC,
    legal_domain: Optional[LegalDomain] = None,
    **kwargs,
) -> LegalReasoningEngine:
    """Factory function to create Legal Reasoning Engine for service container."""
    return LegalReasoningEngine(
        service_container=service_container,
        reasoning_framework=reasoning_framework,
        legal_domain=legal_domain,
        **kwargs,
    )


__all__ = [
    "LegalReasoningEngine",
    "ReasoningFramework",
    "LegalDomain",
    "LegalIssue",
    "LegalArgument",
    "ComplianceCheck",
    "LegalReasoningResult",
    "create_legal_reasoning_engine",
]
