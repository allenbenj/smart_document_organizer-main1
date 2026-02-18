"""
Core Integration Layer - Enhanced Agent Framework with Utils/Core Components
===========================================================================

This module integrates the enhanced agent framework with the production-ready
utils/core components, creating a unified enterprise-grade Legal AI system.

Key integrations:
- BaseAgent with EnhancedVectorStore and UnifiedMemoryManager
- Agent Registry with ConnectionPool and EnhancedPersistence
- Knowledge-driven agents with ConfigurationManager
- Service container integration with all core utilities

Author: Legal AI System
Version: 2.0.0
"""

import asyncio
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional, cast  # noqa: E402

from config.configuration_manager import (  # noqa: E402
    ConfigurationManager,
    create_configuration_manager,
)
from utils.logging import (  # noqa: E402
    LogCategory,
    detailed_log_function,
    get_detailed_logger,
)
from mem_db.memory.unified_memory_manager import (  # noqa: E402
    UnifiedMemoryManager,
    create_unified_memory_manager,
)
from mem_db.vector_store.unified_vector_store import UnifiedVectorStore  # noqa: E402
from core.container.service_container_impl import ProductionServiceContainer  # noqa: E402
from .agent_registry import AgentRegistry  # noqa: E402

# Import production components from actual locations
# Import enhanced agent framework
from .base_agent import BaseAgent as CoreBaseAgent  # noqa: E402
from .enhanced_agent_factory import EnhancedAgentFactory  # noqa: E402
from .knowledge_driven_agent_system import KnowledgeDrivenAgentSystem  # noqa: E402


# Placeholder for AgentTask (not defined in base_agent.py)
class AgentTask:
    """Placeholder - AgentTask representation."""

    def __init__(
        self,
        task_id: str,
        task_type: str,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.data = data
        self.metadata = metadata or {}


# Placeholder imports for modules that don't exist yet
# TODO: Implement or find actual implementations for these
class EnhancedVectorStore:
    """Compatibility alias to UnifiedVectorStore."""


class EnhancedPersistenceManager:
    """Persistence manager contract required by integration layer."""

    connection_pool: Optional["ConnectionPool"] = None

    async def initialize(self) -> None:
        raise RuntimeError("EnhancedPersistenceManager.initialize is not implemented")

    async def health_check(self) -> Dict[str, Any]:
        raise RuntimeError("EnhancedPersistenceManager.health_check is not implemented")

    async def close(self) -> None:
        raise RuntimeError("EnhancedPersistenceManager.close is not implemented")


class ConnectionPool:
    """ConnectionPool contract required by integration layer."""


class VectorStoreManager:
    """VectorStoreManager contract required by integration layer."""


class LegalAISettings:
    """Placeholder - LegalAISettings implementation needed."""

    def __init__(self) -> None:
        self.database_url = "sqlite:///databases/legal_ai.db"
        self.redis_url_cache = "redis://localhost:6379/0"
        self.data_dir = Path("databases")
        self.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
        self.document_index_path = self.data_dir / "vectors" / "documents"
        self.entity_index_path = self.data_dir / "vectors" / "entities"


settings = LegalAISettings()


def create_enhanced_vector_store(*args, **kwargs):
    """Factory function for EnhancedVectorStore."""
    return UnifiedVectorStore(*args, **kwargs)


def create_enhanced_persistence_manager(*args, **kwargs):
    """Factory function for EnhancedPersistenceManager."""
    raise RuntimeError("EnhancedPersistenceManager implementation is required")


def create_vector_store_manager(*args, **kwargs):
    """Factory function for VectorStoreManager."""
    raise RuntimeError("VectorStoreManager implementation is required")


class IntegrationServiceContainer:
    """Small compatibility container for this integration module."""

    def __init__(self) -> None:
        self._services: Dict[str, Any] = {}

    async def register_service(self, name: str, instance: Any = None, **kwargs) -> None:
        self._services[name] = instance

    async def get_service(self, name: str) -> Any:
        return self._services.get(name)

    async def shutdown_all_services(self) -> None:
        self._services.clear()


def get_service_container(*args, **kwargs) -> IntegrationServiceContainer:
    """Factory function for service container."""
    return IntegrationServiceContainer()


def register_core_services(*args, **kwargs):
    """Register core services."""
    raise RuntimeError("register_core_services implementation is required")


# Initialize logger
class _CompatLogger:
    """Accept structured kwargs even when underlying logger is stdlib."""

    def __init__(self, base):
        self._base = base

    def _call(self, level: str, message: str, **kwargs: Any) -> None:
        fn = getattr(self._base, level)
        try:
            if kwargs:
                fn(message, **kwargs)
            else:
                fn(message)
        except TypeError:
            if kwargs:
                fn(f"{message} | {kwargs}")
            else:
                fn(message)

    def info(self, message: str, **kwargs: Any) -> None:
        self._call("info", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._call("warning", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._call("error", message, **kwargs)


integration_logger = _CompatLogger(
    get_detailed_logger("CoreIntegration", LogCategory.AGENT)
)


class EnhancedCoreAgent(CoreBaseAgent):
    """
    Enhanced agent that combines the best of both agent frameworks.

    Inherits from utils/core BaseAgent for production stability while
    integrating enhanced agent framework capabilities.
    """

    @detailed_log_function(LogCategory.AGENT)
    def __init__(
        self,
        service_container=None,
        name: Optional[str] = None,
        agent_type: str = "enhanced_core",
        knowledge_base_path: Optional[Path] = None,
        behavior_profile: Optional[str] = None,
        reasoning_framework: Optional[str] = None,
    ):
        """Initialize enhanced core agent with full integration."""
        safe_name = name or self.__class__.__name__
        safe_services = service_container or ProductionServiceContainer()
        super().__init__(cast(Any, safe_services), safe_name, agent_type)
        # Alias names expected by this integration layer.
        self.service_container = safe_services
        self.name = self.agent_name

        # Enhanced capabilities
        self.knowledge_base_path = knowledge_base_path
        self.behavior_profile = behavior_profile or "Legal Analyst"
        self.reasoning_framework = reasoning_framework or "IRAC"

        # Core service integrations
        self.vector_store: Optional[EnhancedVectorStore] = None
        self.memory_manager: Optional[UnifiedMemoryManager] = None
        self.persistence_manager: Optional[EnhancedPersistenceManager] = None
        self.config_manager: Optional[ConfigurationManager] = None

        # Initialize core services if an event loop is available.
        asyncio.create_task(self._initialize_core_services())

        integration_logger.info(
            "Enhanced core agent initialized",
            parameters={
                "name": self.name,
                "type": agent_type,
                "behavior_profile": self.behavior_profile,
                "reasoning_framework": self.reasoning_framework,
            },
        )

    @detailed_log_function(LogCategory.AGENT)
    async def _initialize_core_services(self):
        """Initialize core service integrations."""
        if not self.service_container:
            raise RuntimeError("No service container provided for enhanced core agent")
        self.config_manager = await self._get_service_async(ConfigurationManager)
        self.vector_store = await self._get_service_async(UnifiedVectorStore)
        self.memory_manager = await self._get_service_async(UnifiedMemoryManager)
        self.persistence_manager = await self._get_service_async(
            EnhancedPersistenceManager
        )

        integration_logger.info(
            "Core services initialized for agent",
            parameters={"agent_name": self.name},
        )

    async def _get_service_async(self, service_key: Any) -> Any:
        """Resolve a required service by key."""
        if not self.service_container or not hasattr(self.service_container, "get_service"):
            raise RuntimeError("Service container is unavailable")
        try:
            getter = self.service_container.get_service
            if asyncio.iscoroutinefunction(getter):
                service = await getter(service_key)
            else:
                service = getter(service_key)
            if service is None:
                raise RuntimeError(f"Required service unavailable: {service_key}")
            return service
        except Exception as e:
            raise RuntimeError(f"Failed to resolve required service {service_key}: {e}") from e

    async def _process_task(self, task_data: Any, metadata: Dict[str, Any]) -> Any:
        """
        Enhanced task processing with core service integration.

        This method combines:
        - Knowledge-driven processing from enhanced framework
        - Vector similarity search from EnhancedVectorStore
        - Memory persistence via UnifiedMemoryManager
        - Configuration-driven behavior
        """
        integration_logger.info(
            "Processing task with enhanced core integration",
            parameters={
                "agent_name": self.name,
                "task_type": type(task_data).__name__,
                "behavior_profile": self.behavior_profile,
            },
        )

        try:
            # Step 1: Load relevant knowledge from vector store
            relevant_context = await self._get_relevant_context(task_data, metadata)

            # Step 2: Apply reasoning framework
            reasoning_result = await self._apply_reasoning_framework(
                task_data, relevant_context, metadata
            )

            # Step 3: Store results in memory for future reference
            await self._store_processing_results(reasoning_result, metadata)

            # Step 4: Return enhanced result
            return {
                "result": reasoning_result,
                "context_used": relevant_context,
                "reasoning_framework": self.reasoning_framework,
                "behavior_profile": self.behavior_profile,
                "agent_name": self.name,
                "processing_metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "vector_search_performed": bool(relevant_context),
                    "memory_stored": True,
                },
            }

        except Exception as e:
            integration_logger.error(
                "Task processing failed in enhanced core agent",
                parameters={"agent_name": self.name},
                exception=e,
            )
            raise

    @detailed_log_function(LogCategory.AGENT)
    async def _get_relevant_context(
        self, task_data: Any, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get relevant context from vector store."""
        if not self.vector_store:
            raise RuntimeError("Vector store is required but not initialized")

        # Convert task data to search query
        query = self._extract_search_query(task_data)
        if not query:
            raise ValueError("Could not extract search query from task data")

        # Perform vector similarity search
        search_results = await self.vector_store.search_similar(
            query=query, k=5, search_type="document", min_similarity=0.7
        )

        # Convert search results to context format
        context = []
        for result in search_results:
            context.append(
                {
                    "content": result.content_preview,
                    "similarity_score": result.similarity_score,
                    "document_id": result.document_id,
                    "metadata": (
                        result.metadata.__dict__
                        if hasattr(result.metadata, "__dict__")
                        else {}
                    ),
                }
            )

        integration_logger.info(
            "Retrieved relevant context from vector store",
            parameters={
                "agent_name": self.name,
                "context_items": len(context),
                "query": query[:100],
            },
        )

        return context

    def _extract_search_query(self, task_data: Any) -> Optional[str]:
        """Extract search query from task data."""
        if isinstance(task_data, str):
            return task_data
        elif isinstance(task_data, dict):
            # Look for common query fields
            for field in ["query", "question", "text", "content", "input"]:
                if field in task_data:
                    return str(task_data[field])
            # Convert task data to a string representation
            return str(task_data)
        else:
            return str(task_data)

    @detailed_log_function(LogCategory.AGENT)
    async def _apply_reasoning_framework(
        self, task_data: Any, context: List[Dict[str, Any]], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply the configured reasoning framework."""

        if self.reasoning_framework == "IRAC":
            return await self._apply_irac_framework(task_data, context, metadata)
        elif self.reasoning_framework == "Toulmin":
            return await self._apply_toulmin_framework(task_data, context, metadata)
        elif self.reasoning_framework == "Critical Thinking":
            return await self._apply_critical_thinking_framework(
                task_data, context, metadata
            )
        else:
            raise ValueError(f"Unsupported reasoning framework: {self.reasoning_framework}")

    async def _apply_irac_framework(
        self, task_data: Any, context: List[Dict[str, Any]], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply IRAC (Issue, Rule, Application, Conclusion) framework."""

        # Issue identification
        issue = await self._identify_legal_issue(task_data, context)

        # Rule extraction
        relevant_rules = await self._extract_relevant_rules(issue, context)

        # Application of rules to facts
        application = await self._apply_rules_to_facts(
            task_data, relevant_rules, context
        )

        # Conclusion
        conclusion = await self._draw_conclusion(issue, relevant_rules, application)

        return {
            "framework": "IRAC",
            "issue": issue,
            "rules": relevant_rules,
            "application": application,
            "conclusion": conclusion,
            "confidence": self._calculate_confidence(
                issue, relevant_rules, application
            ),
        }

    async def _apply_toulmin_framework(
        self, task_data: Any, context: List[Dict[str, Any]], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply Toulmin argument framework."""

        # Claim identification
        claim = await self._identify_claim(task_data)

        # Evidence gathering
        evidence = await self._gather_evidence(claim, context)

        # Warrant establishment
        warrant = await self._establish_warrant(claim, evidence, context)

        # Backing for warrant
        backing = await self._find_backing(warrant, context)

        # Qualifiers and rebuttals
        qualifiers = await self._identify_qualifiers(claim, evidence)
        rebuttals = await self._identify_rebuttals(claim, evidence, context)

        return {
            "framework": "Toulmin",
            "claim": claim,
            "evidence": evidence,
            "warrant": warrant,
            "backing": backing,
            "qualifiers": qualifiers,
            "rebuttals": rebuttals,
            "confidence": self._calculate_toulmin_confidence(
                claim, evidence, warrant, backing
            ),
        }

    async def _apply_critical_thinking_framework(
        self, task_data: Any, context: List[Dict[str, Any]], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply critical thinking framework."""

        # Assumption identification
        assumptions = await self._identify_assumptions(task_data, context)

        # Evidence evaluation
        evidence_evaluation = await self._evaluate_evidence(context)

        # Alternative perspectives
        alternatives = await self._consider_alternatives(task_data, context)

        # Logical consistency check
        consistency = await self._check_logical_consistency(task_data, context)

        return {
            "framework": "Critical Thinking",
            "assumptions": assumptions,
            "evidence_evaluation": evidence_evaluation,
            "alternatives": alternatives,
            "logical_consistency": consistency,
            "confidence": self._calculate_critical_thinking_confidence(
                assumptions, evidence_evaluation, alternatives, consistency
            ),
        }

    @detailed_log_function(LogCategory.AGENT)
    async def _store_processing_results(
        self, result: Dict[str, Any], metadata: Dict[str, Any]
    ):
        """Store processing results in unified memory manager."""
        if not self.memory_manager:
            raise RuntimeError("Memory manager is required but not initialized")

        session_id = metadata.get("session_id", "default_session")

        # Store agent decision
        await cast(Any, self.memory_manager).log_agent_decision(
            agent_name=self.name,
            session_id=session_id,
            input_summary=f"Processed task with {result.get('framework', 'unknown')} framework",
            decision_details=result,
            context_used=result.get("context_used"),
            confidence=result.get("confidence", 0.5),
            tags=[self.behavior_profile, result.get("framework", "unknown")],
        )

        # Add to context window for future reference
        await cast(Any, self.memory_manager).add_context_window_entry(
            session_id=session_id,
            entry_type="agent_result",
            content=result,
            importance=result.get("confidence", 0.5),
            metadata={
                "agent_name": self.name,
                "behavior_profile": self.behavior_profile,
                "reasoning_framework": self.reasoning_framework,
            },
        )

        integration_logger.info(
            "Processing results stored in memory",
            parameters={"agent_name": self.name, "session_id": session_id},
        )

    # Placeholder methods for reasoning framework implementations
    # These would be implemented with actual legal reasoning logic

    async def _identify_legal_issue(
        self, task_data: Any, context: List[Dict[str, Any]]
    ) -> str:
        """Identify the legal issue from task data and context."""
        return f"Legal issue identified from {type(task_data).__name__}"

    async def _extract_relevant_rules(
        self, issue: str, context: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract relevant legal rules from context."""
        return [
            f"Rule extracted from context item {i}" for i in range(min(3, len(context)))
        ]

    async def _apply_rules_to_facts(
        self, task_data: Any, rules: List[str], context: List[Dict[str, Any]]
    ) -> str:
        """Apply legal rules to the facts of the case."""
        return f"Applied {len(rules)} rules to facts"

    async def _draw_conclusion(
        self, issue: str, rules: List[str], application: str
    ) -> str:
        """Draw legal conclusion based on IRAC analysis."""
        return f"Conclusion drawn from issue: {issue[:50]}..."

    async def _identify_claim(self, task_data: Any) -> str:
        """Identify the main claim in Toulmin framework."""
        return f"Claim identified from {type(task_data).__name__}"

    async def _gather_evidence(
        self, claim: str, context: List[Dict[str, Any]]
    ) -> List[str]:
        """Gather evidence supporting the claim."""
        return [f"Evidence {i+1}" for i in range(min(3, len(context)))]

    async def _establish_warrant(
        self, claim: str, evidence: List[str], context: List[Dict[str, Any]]
    ) -> str:
        """Establish warrant connecting evidence to claim."""
        return f"Warrant established for claim with {len(evidence)} pieces of evidence"

    async def _find_backing(self, warrant: str, context: List[Dict[str, Any]]) -> str:
        """Find backing for the warrant."""
        return f"Backing found for warrant in {len(context)} context items"

    async def _identify_qualifiers(self, claim: str, evidence: List[str]) -> List[str]:
        """Identify qualifiers for the claim."""
        return ["unless", "probably", "generally"]

    async def _identify_rebuttals(
        self, claim: str, evidence: List[str], context: List[Dict[str, Any]]
    ) -> List[str]:
        """Identify potential rebuttals."""
        return [f"Rebuttal {i+1}" for i in range(2)]

    async def _identify_assumptions(
        self, task_data: Any, context: List[Dict[str, Any]]
    ) -> List[str]:
        """Identify underlying assumptions."""
        return [f"Assumption {i+1}" for i in range(3)]

    async def _evaluate_evidence(self, context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate the quality and reliability of evidence."""
        return {
            "total_items": len(context),
            "average_confidence": sum(
                item.get("similarity_score", 0.5) for item in context
            )
            / max(len(context), 1),
            "quality_assessment": "moderate",
        }

    async def _consider_alternatives(
        self, task_data: Any, context: List[Dict[str, Any]]
    ) -> List[str]:
        """Consider alternative perspectives or interpretations."""
        return [f"Alternative perspective {i+1}" for i in range(2)]

    async def _check_logical_consistency(
        self, task_data: Any, context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Check for logical consistency in reasoning."""
        return {"consistent": True, "potential_contradictions": [], "confidence": 0.8}

    def _calculate_confidence(
        self, issue: str, rules: List[str], application: str
    ) -> float:
        """Calculate confidence score for IRAC analysis."""
        base_confidence = 0.7
        rule_bonus = min(0.2, len(rules) * 0.05)
        return min(1.0, base_confidence + rule_bonus)

    def _calculate_toulmin_confidence(
        self, claim: str, evidence: List[str], warrant: str, backing: str
    ) -> float:
        """Calculate confidence score for Toulmin analysis."""
        base_confidence = 0.6
        evidence_bonus = min(0.3, len(evidence) * 0.1)
        return min(1.0, base_confidence + evidence_bonus)

    def _calculate_critical_thinking_confidence(
        self,
        assumptions: List[str],
        evidence_eval: Dict[str, Any],
        alternatives: List[str],
        consistency: Dict[str, Any],
    ) -> float:
        """Calculate confidence score for critical thinking analysis."""
        base_confidence = 0.5
        consistency_bonus = 0.3 if consistency.get("consistent", False) else 0.0
        evidence_bonus = evidence_eval.get("average_confidence", 0.0) * 0.2
        return min(1.0, base_confidence + consistency_bonus + evidence_bonus)


class CoreIntegrationManager:
    """
    Manager for integrating enhanced agent framework with utils/core components.

    Provides unified access to all core services and manages their lifecycle.
    """

    @detailed_log_function(LogCategory.AGENT)
    def __init__(self, settings_instance: Optional[LegalAISettings] = None):
        """Initialize core integration manager."""
        self.settings = settings_instance or settings
        self.service_container = get_service_container()

        # Core managers
        self.config_manager: Optional[ConfigurationManager] = None
        self.persistence_manager: Optional[EnhancedPersistenceManager] = None
        self.vector_store: Optional[EnhancedVectorStore] = None
        self.memory_manager: Optional[UnifiedMemoryManager] = None
        self.vector_store_manager: Optional[VectorStoreManager] = None

        # Agent framework components
        self.agent_registry: Optional[AgentRegistry] = None
        self.agent_factory: Optional[EnhancedAgentFactory] = None
        self.knowledge_system: Optional[KnowledgeDrivenAgentSystem] = None

        self.initialized = False

        integration_logger.info("Core integration manager created")

    @detailed_log_function(LogCategory.AGENT)
    async def initialize(self):
        """Initialize all core services and agent framework components."""
        if self.initialized:
            integration_logger.warning("Core integration manager already initialized")
            return

        integration_logger.info("Initializing core integration manager")

        try:
            # Step 1: Initialize core services
            await self._initialize_core_services()

            # Step 2: Register services in container
            await self._register_services()

            # Step 3: Initialize agent framework components
            await self._initialize_agent_framework()

            # Step 4: Create integration bridges
            await self._create_integration_bridges()

            self.initialized = True
            integration_logger.info("Core integration manager initialized successfully")

        except Exception as e:
            integration_logger.error(
                "Failed to initialize core integration manager", exception=e
            )
            raise

    async def _initialize_core_services(self):
        """Initialize core utility services."""
        integration_logger.info("Initializing core utility services")

        # Configuration Manager
        self.config_manager = create_configuration_manager(vars(self.settings))
        if hasattr(self.config_manager, "initialize"):
            await cast(Any, self.config_manager).initialize()

        # Enhanced Persistence Manager
        persistence_config = {
            "database_url": self.settings.database_url,
            "redis_url": self.settings.redis_url_cache,
            "min_pg_connections": 5,
            "max_pg_connections": 20,
            "max_redis_connections": 10,
        }
        self.persistence_manager = create_enhanced_persistence_manager(
            config=persistence_config
        )
        await cast(Any, self.persistence_manager).initialize()

        # Enhanced Vector Store
        vector_config = {
            "STORAGE_PATH": str(self.settings.data_dir / "vectors"),
            "embedding_model_name": self.settings.embedding_model,
            "DEFAULT_INDEX_TYPE": "HNSW",
            "ENABLE_GPU_FAISS": False,
            "DOCUMENT_INDEX_PATH": str(self.settings.document_index_path),
            "ENTITY_INDEX_PATH": str(self.settings.entity_index_path),
        }

        connection_pool = self.persistence_manager.connection_pool
        self.vector_store = create_enhanced_vector_store(
            self.service_container,
            connection_pool=connection_pool,
            config=vector_config,
        )
        await cast(Any, self.vector_store).initialize()

        # Unified Memory Manager
        self.memory_manager = await create_unified_memory_manager()
        await self.memory_manager.initialize()

        # Vector Store Manager
        self.vector_store_manager = create_vector_store_manager(self.service_container)

        integration_logger.info("Core utility services initialized")

    async def _register_services(self):
        """Register all services in the service container."""
        integration_logger.info("Registering services in container")

        # Register core services
        await self.service_container.register_service(
            "config_manager", instance=self.config_manager
        )
        await self.service_container.register_service(
            "enhanced_persistence_manager", instance=self.persistence_manager
        )
        await self.service_container.register_service(
            "enhanced_vector_store", instance=self.vector_store
        )
        await self.service_container.register_service(
            "unified_memory_manager", instance=self.memory_manager
        )
        await self.service_container.register_service(
            "vector_store_manager", instance=self.vector_store_manager
        )

        # Register additional core services
        register_core_services()

        integration_logger.info("Services registered in container")

    async def _initialize_agent_framework(self):
        """Initialize enhanced agent framework components."""
        integration_logger.info("Initializing enhanced agent framework")

        # Agent Registry with core service integration
        self.agent_registry = AgentRegistry(service_container=self.service_container)

        # Enhanced Agent Factory
        self.agent_factory = EnhancedAgentFactory(
            service_container=self.service_container, agent_registry=self.agent_registry
        )

        # Knowledge-Driven Agent System
        knowledge_base_path = (
            self.settings.data_dir / "memory" / "chroma_memory" / "seed_documents"
        )
        self.knowledge_system = KnowledgeDrivenAgentSystem(
            service_container=self.service_container,
            knowledge_base_path=knowledge_base_path,
        )

        integration_logger.info("Enhanced agent framework initialized")

    async def _create_integration_bridges(self):
        """Create bridges between different system components."""
        integration_logger.info("Creating integration bridges")

        # Register enhanced core agent type
        if not self.agent_registry:
            raise RuntimeError("Agent registry is not initialized")

        await self.agent_registry.register_agent_type(
            "enhanced_core",
            EnhancedCoreAgent,
            "Enhanced agent with full core service integration",
        )

        # Register production agents with core integration
        await self._register_production_agents()

        integration_logger.info("Integration bridges created")

    async def _register_production_agents(self):
        """Register existing production agents with core integration."""
        try:
            # Import and register existing production agents
            from ...agents.analysis.semantic_analyzer import LegalSemanticAnalyzer  # noqa: E402
            from ...agents.embedding.unified_embedding_agent import (  # noqa: E402
                UnifiedEmbeddingAgent,
            )
            from ...agents.extractors.entity_extractor import LegalEntityExtractor  # noqa: E402
            from ...agents.legal.precedent_analyzer import LegalPrecedentAnalyzer  # noqa: E402

            # Register with enhanced capabilities
            if not self.agent_registry:
                return

            await self.agent_registry.register_agent_type(
                "semantic_analyzer",
                LegalSemanticAnalyzer,
                "Legal semantic analysis with core integration",
            )

            await self.agent_registry.register_agent_type(
                "precedent_analyzer",
                LegalPrecedentAnalyzer,
                "Legal precedent analysis with core integration",
            )

            await self.agent_registry.register_agent_type(
                "entity_extractor",
                LegalEntityExtractor,
                "Legal entity extraction with core integration",
            )

            await self.agent_registry.register_agent_type(
                "embedding_agent",
                UnifiedEmbeddingAgent,
                "Unified embedding generation with core integration",
            )

            integration_logger.info(
                "Production agents registered with core integration"
            )

        except ImportError as e:
            raise RuntimeError(
                "Required production agents are not available for registration"
            ) from e

    async def create_enhanced_agent(
        self,
        agent_type: str,
        name: Optional[str] = None,
        behavior_profile: Optional[str] = None,
        reasoning_framework: Optional[str] = None,
        **kwargs,
    ) -> EnhancedCoreAgent:
        """Create an enhanced agent with full core integration."""
        if not self.initialized:
            await self.initialize()

        if agent_type == "enhanced_core":
            return EnhancedCoreAgent(
                service_container=self.service_container,
                name=name,
                agent_type=agent_type,
                behavior_profile=behavior_profile,
                reasoning_framework=reasoning_framework,
                **kwargs,
            )
        else:
            # Use agent factory for other types
            if not self.agent_factory:
                raise RuntimeError("Agent factory is not initialized")
            return await cast(Any, self.agent_factory).create_production_agent(
                agent_type=agent_type, name=name, **kwargs
            )

    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        if not self.initialized:
            return {"status": "not_initialized"}

        status = {
            "integration_manager": "healthy",
            "initialized": self.initialized,
            "timestamp": datetime.now().isoformat(),
        }

        # Core service statuses
        if self.config_manager and hasattr(self.config_manager, "health_check"):
            status["config_manager"] = cast(Any, self.config_manager).health_check()

        if self.persistence_manager and hasattr(self.persistence_manager, "health_check"):
            status["persistence_manager"] = await cast(
                Any, self.persistence_manager
            ).health_check()

        if self.vector_store and hasattr(self.vector_store, "get_system_status"):
            status["vector_store"] = cast(Any, self.vector_store).get_system_status()

        if self.memory_manager and hasattr(self.memory_manager, "get_service_status"):
            status["memory_manager"] = await cast(
                Any, self.memory_manager
            ).get_service_status()

        # Agent framework status
        if self.agent_registry:
            status["agent_registry"] = {
                "registered_types": len(self.agent_registry.agent_types),
                "active_agents": len(self.agent_registry.active_agents),
            }

        return status

    async def shutdown(self):
        """Gracefully shutdown all services."""
        integration_logger.info("Shutting down core integration manager")

        try:
            # Shutdown agent framework components
            if self.agent_registry:
                await self.agent_registry.shutdown_all_agents()

            # Shutdown core services
            if self.memory_manager and hasattr(self.memory_manager, "close"):
                await cast(Any, self.memory_manager).close()

            if self.vector_store and hasattr(self.vector_store, "close"):
                await cast(Any, self.vector_store).close()

            if self.persistence_manager and hasattr(self.persistence_manager, "close"):
                await cast(Any, self.persistence_manager).close()

            # Shutdown service container
            await self.service_container.shutdown_all_services()

            self.initialized = False
            integration_logger.info("Core integration manager shutdown complete")

        except Exception as e:
            integration_logger.error("Error during shutdown", exception=e)


# Global integration manager instance
_integration_manager: Optional[CoreIntegrationManager] = None


def get_integration_manager() -> CoreIntegrationManager:
    """Get the global core integration manager instance."""
    global _integration_manager
    if _integration_manager is None:
        _integration_manager = CoreIntegrationManager()
    return _integration_manager


async def initialize_core_integration() -> CoreIntegrationManager:
    """Initialize and return the core integration manager."""
    manager = get_integration_manager()
    if not manager.initialized:
        await manager.initialize()
    return manager


# Export key classes and functions
__all__ = [
    "EnhancedCoreAgent",
    "CoreIntegrationManager",
    "get_integration_manager",
    "initialize_core_integration",
]
