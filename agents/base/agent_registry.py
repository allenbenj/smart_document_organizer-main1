"""
Agent Registry and Coordination System
Integrates with existing orchestrators and shared chroma_memory system.
"""

import asyncio
import importlib  # noqa: E402
import inspect  # noqa: E402
import json  # noqa: E402
import uuid  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime  # noqa: E402
from enum import Enum  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional, Set, Type, TypedDict, cast  # noqa: E402

from config.configuration_manager import ConfigurationManager  # noqa: E402

# Use enhanced detailed logging
from utils.logging import (  # noqa: E402
    LogCategory,
    detailed_log_function,
    get_detailed_logger,
)

# Import base agent and canonical result contract
from agents.core.models import AgentResult  # noqa: E402
from .base_agent import AgentStatus, BaseAgent, TaskPriority  # noqa: E402

# Initialize logger for this module
registry_logger = get_detailed_logger("AgentRegistry", LogCategory.AGENT)


class AgentCapability(Enum):
    """Standard agent capabilities for the Legal AI Platform."""

    DOCUMENT_PROCESSING = "document_processing"
    TEXT_ANALYSIS = "text_analysis"
    ENTITY_EXTRACTION = "entity_extraction"
    LEGAL_ANALYSIS = "legal_analysis"
    SEMANTIC_ANALYSIS = "semantic_analysis"
    STRUCTURAL_ANALYSIS = "structural_analysis"
    CITATION_ANALYSIS = "citation_analysis"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    VECTOR_SEARCH = "vector_search"
    MEMORY_MANAGEMENT = "memory_management"
    WORKFLOW_ORCHESTRATION = "workflow_orchestration"
    PRECEDENT_MATCHING = "precedent_matching"
    COMPLIANCE_CHECKING = "compliance_checking"
    DOCUMENT_GENERATION = "document_generation"
    REASONING = "reasoning"
    VALIDATION = "validation"


@dataclass
class AgentMetadata:
    """Comprehensive metadata for registered agents."""

    agent_id: str
    name: str
    description: str
    version: str
    capabilities: Set[AgentCapability]

    # Technical details
    agent_class: Type[BaseAgent]
    module_path: str
    dependencies: List[str] = field(default_factory=list)

    # Legal domain specifics
    practice_areas: List[str] = field(default_factory=list)
    jurisdictions: List[str] = field(default_factory=list)
    document_types: List[str] = field(default_factory=list)

    # Performance characteristics
    avg_processing_time: float = 0.0
    success_rate: float = 1.0
    task_count: int = 0
    memory_usage_mb: float = 0.0
    concurrent_capacity: int = 1

    # Status and health
    status: AgentStatus = AgentStatus.IDLE
    last_health_check: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None

    # Integration details
    requires_chroma_memory: bool = True
    requires_llm: bool = True
    requires_vector_store: bool = False
    requires_knowledge_graph: bool = False

    # Registration details
    registered_at: datetime = field(default_factory=datetime.now)
    registered_by: str = "system"
    tags: List[str] = field(default_factory=list)


@dataclass
class AgentInstance:
    """Runtime instance of an agent."""

    instance_id: str
    agent_id: str
    agent_instance: BaseAgent
    metadata: AgentMetadata

    # Runtime state
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    task_count: int = 0
    active_tasks: Set[str] = field(default_factory=set)

    # Shared memory integration
    chroma_memory_connected: bool = False
    memory_namespace: Optional[str] = None


class OrchestratorClassInfo(TypedDict):
    """Metadata for lazily-instantiated orchestrators discovered by import."""

    class_: type
    module: str
    capabilities: List[AgentCapability]
    available: bool


class AgentRegistry:
    """
    Central registry for all Legal AI agents with integration to existing orchestrators
    and shared chroma_memory system.

    Features:
    - Agent discovery and registration
    - Capability-based agent selection
    - Integration with existing orchestrators
    - Shared memory coordination via chroma_memory
    - Health monitoring and performance tracking
    - Dynamic agent loading and lifecycle management
    """

    def __init__(
        self,
        service_container: Any,
        config_manager: Optional[ConfigurationManager] = None,
    ):
        self.service_container = service_container
        self.config_manager = config_manager
        self.logger = get_detailed_logger("AgentRegistry", LogCategory.AGENT)

        # Agent storage
        self.registered_agents: Dict[str, AgentMetadata] = {}
        self.active_instances: Dict[str, AgentInstance] = {}
        self.agent_classes: Dict[str, Type[BaseAgent]] = {}

        # Capability mapping
        self.capability_index: Dict[AgentCapability, Set[str]] = {}
        self.practice_area_index: Dict[str, Set[str]] = {}
        self.jurisdiction_index: Dict[str, Set[str]] = {}

        # Integration with existing orchestrators
        self.orchestrator_integrations: Dict[str, Any | OrchestratorClassInfo] = {}

        # Shared memory integration
        self.chroma_memory_path = "legal_ai_modular/memory/chroma_memory"
        self.shared_memory_manager = None

        # Performance tracking
        self.registry_stats = {
            "total_registered": 0,
            "active_instances": 0,
            "total_tasks_processed": 0,
            "avg_response_time": 0.0,
            "health_check_failures": 0,
        }

        # Auto-discovery settings
        self.auto_discovery_paths = [
            "legal_ai_modular.agents.analysis",
            "legal_ai_modular.agents.document",
            "legal_ai_modular.agents.extraction",
            "legal_ai_modular.agents.legal",
            "legal_ai_modular.agents.memory",
            "legal_ai_modular.agents.embedding",
        ]

        # Production agents registry
        self.production_agents_registered = False

        self.logger.info(
            "Agent Registry initialized",
            parameters={"chroma_memory_path": self.chroma_memory_path},
        )

    @detailed_log_function(LogCategory.AGENT)
    async def initialize(self) -> None:
        """Initialize the agent registry with auto-discovery and orchestrator integration."""
        try:
            # Initialize shared memory connection
            await self._initialize_shared_memory()

            # Discover and register existing orchestrators
            await self._discover_orchestrators()

            # Auto-discover agents
            await self._auto_discover_agents()

            # Load persisted agent metadata
            await self._load_agent_metadata()

            # Start health monitoring
            asyncio.create_task(self._health_monitor_loop())

            self.logger.info(
                "Agent Registry initialization complete",
                parameters={
                    "registered_agents": len(self.registered_agents),
                    "orchestrator_integrations": len(self.orchestrator_integrations),
                },
            )

        except Exception as e:
            self.logger.error("Failed to initialize Agent Registry", exception=e)
            raise

    async def _initialize_shared_memory(self) -> None:
        """Initialize connection to shared chroma memory."""
        try:
            # Try to get shared memory manager from service container
            if hasattr(self.service_container, "get_service"):
                try:
                    maybe_memory = self.service_container.get_service(
                        "chroma_memory_manager"
                    )
                    self.shared_memory_manager = (
                        await maybe_memory
                        if inspect.isawaitable(maybe_memory)
                        else maybe_memory
                    )
                    if self.shared_memory_manager:
                        self.logger.info(
                            "Connected to shared chroma memory via service container"
                        )
                        return
                except Exception as e:
                    self.logger.debug(
                        "Could not get chroma memory from service container",
                        exception=e,
                    )

            # Fallback: Try to import and initialize directly
            try:
                module = importlib.import_module("mem_db.memory.chroma_memory.chroma_db")
                chroma_cls = getattr(module, "ChromaMemoryManager")

                self.shared_memory_manager = chroma_cls(
                    persist_directory=self.chroma_memory_path,
                    collection_name="legal_ai_agent_registry",
                )
                await self.shared_memory_manager.initialize()
                self.logger.info("Initialized direct connection to chroma memory")
            except (ImportError, AttributeError) as e:
                self.logger.warning("Could not import ChromaMemoryManager", exception=e)
                self.shared_memory_manager = None

        except Exception as e:
            self.logger.error("Failed to initialize shared memory", exception=e)
            self.shared_memory_manager = None

    def _orchestrator_configs(self) -> List[Dict[str, Any]]:
        """Return built-in orchestrator discovery configs."""
        return [
            {
                "name": "ultimate_workflow_orchestrator",
                "module": "legal_ai_modular.utils.code_reference.ultimate_orchestrator_1",
                "class": "UltimateWorkflowOrchestrator",
                "capabilities": [
                    AgentCapability.WORKFLOW_ORCHESTRATION,
                    AgentCapability.DOCUMENT_PROCESSING,
                ],
            },
            {
                "name": "smart_doc_orchestrator",
                "module": "legal_ai_modular.services.tools.agents.smart_doc_orchestrator",
                "class": "SmartDocumentationOrchestrator",
                "capabilities": [
                    AgentCapability.DOCUMENT_GENERATION,
                    AgentCapability.WORKFLOW_ORCHESTRATION,
                ],
            },
            {
                "name": "knowledge_systems_coordinator",
                "module": "legal_ai_modular.storage.archived_memory.knowledge_graphs.knowledge_systems_coordinator",
                "class": "KnowledgeSystemsCoordinator",
                "capabilities": [
                    AgentCapability.KNOWLEDGE_GRAPH,
                    AgentCapability.VECTOR_SEARCH,
                ],
            },
        ]

    async def _get_orchestrator_from_container(self, name: str) -> Any:
        """Resolve orchestrator from service container if available."""
        if not hasattr(self.service_container, "get_service"):
            return None

        orchestrator = self.service_container.get_service(name)
        if inspect.isawaitable(orchestrator):
            orchestrator = await orchestrator
        return orchestrator

    def _discover_orchestrator_class(self, config: Dict[str, Any]) -> Optional[type]:
        """Import and return orchestrator class from config."""
        try:
            module = importlib.import_module(config["module"])
            return cast(type, getattr(module, config["class"]))
        except (ImportError, AttributeError) as e:
            self.logger.debug(
                f"Orchestrator not available: {config['name']}",
                exception=e,
            )
            return None

    async def _discover_orchestrators(self) -> None:
        """Discover and integrate with existing orchestrators."""
        try:
            for config in self._orchestrator_configs():
                try:
                    orchestrator = await self._get_orchestrator_from_container(
                        config["name"]
                    )
                    if orchestrator:
                        self.orchestrator_integrations[config["name"]] = orchestrator
                        self.logger.info(
                            f"Integrated with orchestrator: {config['name']}"
                        )
                        continue

                    orchestrator_class = self._discover_orchestrator_class(config)
                    if orchestrator_class is None:
                        continue

                    self.orchestrator_integrations[config["name"]] = {
                        "class_": orchestrator_class,
                        "module": config["module"],
                        "capabilities": config["capabilities"],
                        "available": True,
                    }
                    self.logger.info(f"Discovered orchestrator: {config['name']}")

                except Exception as e:
                    self.logger.warning(
                        f"Failed to discover orchestrator {config['name']}",
                        exception=e,
                    )

        except Exception as e:
            self.logger.error("Failed to discover orchestrators", exception=e)

    async def _register_production_agents(self) -> None:  # noqa: C901
        """Register existing production agents with enhanced capabilities."""
        if self.production_agents_registered:
            return

        try:
            # Import and register Legal Semantic Analyzer
            try:
                from ..analysis.semantic_analyzer import LegalSemanticAnalyzer  # noqa: E402

                await self.register_agent(
                    agent_class=LegalSemanticAnalyzer,
                    name="LegalSemanticAnalyzer",
                    description="Advanced legal document semantic analysis with collective intelligence",
                    capabilities={
                        AgentCapability.SEMANTIC_ANALYSIS,
                        AgentCapability.LEGAL_ANALYSIS,
                        AgentCapability.TEXT_ANALYSIS,
                        AgentCapability.DOCUMENT_PROCESSING,
                        AgentCapability.REASONING,
                    },
                    practice_areas=[
                        "litigation",
                        "contracts",
                        "criminal",
                        "corporate",
                        "regulatory",
                    ],
                    document_types=[
                        "brie",
                        "motion",
                        "complaint",
                        "contract",
                        "statute",
                        "regulation",
                    ],
                    requires_chroma_memory=True,
                    requires_llm=True,
                    registered_by="production_system",
                )
                self.logger.info("Registered LegalSemanticAnalyzer")
            except Exception as e:
                self.logger.warning(
                    "Failed to register LegalSemanticAnalyzer", exception=e
                )

            # Import and register Legal Precedent Analyzer
            try:
                from ..legal.precedent_analyzer import LegalPrecedentAnalyzer  # noqa: E402

                await self.register_agent(
                    agent_class=LegalPrecedentAnalyzer,
                    name="LegalPrecedentAnalyzer",
                    description="Comprehensive legal precedent analysis and citation extraction",
                    capabilities={
                        AgentCapability.PRECEDENT_MATCHING,
                        AgentCapability.CITATION_ANALYSIS,
                        AgentCapability.LEGAL_ANALYSIS,
                        AgentCapability.TEXT_ANALYSIS,
                        AgentCapability.REASONING,
                    },
                    practice_areas=[
                        "litigation",
                        "appellate",
                        "constitutional",
                        "statutory",
                    ],
                    document_types=["case_law", "brie", "motion", "opinion"],
                    requires_chroma_memory=True,
                    requires_vector_store=True,
                    registered_by="production_system",
                )
                self.logger.info("Registered LegalPrecedentAnalyzer")
            except Exception as e:
                self.logger.warning(
                    "Failed to register LegalPrecedentAnalyzer", exception=e
                )

            # Import and register Legal Entity Extractor
            try:
                from ..extractors.entity_extractor import LegalEntityExtractor  # noqa: E402

                await self.register_agent(
                    agent_class=LegalEntityExtractor,
                    name="LegalEntityExtractor",
                    description="Multi-model legal entity extraction with ontology validation",
                    capabilities={
                        AgentCapability.ENTITY_EXTRACTION,
                        AgentCapability.TEXT_ANALYSIS,
                        AgentCapability.DOCUMENT_PROCESSING,
                        AgentCapability.VALIDATION,
                    },
                    practice_areas=["litigation", "contracts", "corporate", "criminal"],
                    document_types=[
                        "complaint",
                        "contract",
                        "brie",
                        "motion",
                        "judgment",
                    ],
                    requires_chroma_memory=True,
                    requires_llm=False,
                    registered_by="production_system",
                )
                self.logger.info("Registered LegalEntityExtractor")
            except Exception as e:
                self.logger.warning(
                    "Failed to register LegalEntityExtractor", exception=e
                )

            # Import and register Unified Embedding Agent
            try:
                from ..embedding.unified_embedding_agent import UnifiedEmbeddingAgent  # noqa: E402

                await self.register_agent(
                    agent_class=UnifiedEmbeddingAgent,
                    name="UnifiedEmbeddingAgent",
                    description="Unified embedding generation with graph database integration",
                    capabilities={
                        AgentCapability.VECTOR_SEARCH,
                        AgentCapability.KNOWLEDGE_GRAPH,
                        AgentCapability.MEMORY_MANAGEMENT,
                        AgentCapability.TEXT_ANALYSIS,
                    },
                    practice_areas=["all"],
                    document_types=["all"],
                    requires_chroma_memory=False,
                    requires_vector_store=True,
                    requires_knowledge_graph=True,
                    registered_by="production_system",
                )
                self.logger.info("Registered UnifiedEmbeddingAgent")
            except Exception as e:
                self.logger.warning(
                    "Failed to register UnifiedEmbeddingAgent", exception=e
                )

            self.production_agents_registered = True
            self.logger.info("Production agents registration completed")

        except Exception as e:
            self.logger.error("Failed to register production agents", exception=e)

    @detailed_log_function(LogCategory.AGENT)
    async def register_agent(
        self,
        agent_class: Type[BaseAgent],
        name: Optional[str] = None,
        description: Optional[str] = None,
        capabilities: Optional[Set[AgentCapability]] = None,
        **metadata_kwargs,
    ) -> str:
        """Register an agent class with the registry."""
        try:
            # Generate agent ID
            agent_id = str(uuid.uuid4())

            # Extract metadata from class if not provided
            if not name:
                name = agent_class.__name__

            if not description:
                description = (
                    getattr(agent_class, "__doc__", f"Agent: {name}")
                    or f"Agent: {name}"
                )

            if not capabilities:
                capabilities = self._infer_capabilities(agent_class)

            safe_description = description or f"Agent: {name}"

            # Create metadata
            metadata = AgentMetadata(
                agent_id=agent_id,
                name=name,
                description=safe_description,
                version=getattr(agent_class, "__version__", "1.0.0"),
                capabilities=capabilities,
                agent_class=agent_class,
                module_path=f"{agent_class.__module__}.{agent_class.__name__}",
                **metadata_kwargs,
            )

            # Store agent
            self.registered_agents[agent_id] = metadata
            self.agent_classes[agent_id] = agent_class

            # Update indices
            self._update_indices(agent_id, metadata)

            # Update stats
            self.registry_stats["total_registered"] += 1

            # Store in shared memory if available
            if self.shared_memory_manager:
                await self._store_agent_metadata_in_memory(agent_id, metadata)

            self.logger.info(
                f"Registered agent: {name}",
                parameters={
                    "agent_id": agent_id,
                    "capabilities": [c.value for c in capabilities],
                },
            )

            return agent_id

        except Exception as e:
            self.logger.error(f"Failed to register agent: {name}", exception=e)
            raise

    @detailed_log_function(LogCategory.AGENT)
    async def create_agent_instance(self, agent_id: str, **init_kwargs) -> str:
        """Create a runtime instance of a registered agent."""
        if agent_id not in self.registered_agents:
            raise ValueError(f"Agent not registered: {agent_id}")

        try:
            metadata = self.registered_agents[agent_id]
            agent_class = self.agent_classes[agent_id]

            # Create instance
            agent_instance = agent_class(self.service_container, **init_kwargs)

            # Connect to shared memory if required
            chroma_connected = False
            memory_namespace = None
            if metadata.requires_chroma_memory and self.shared_memory_manager:
                try:
                    if hasattr(agent_instance, "set_shared_memory"):
                        agent_instance.set_shared_memory(self.shared_memory_manager)
                        chroma_connected = True
                        memory_namespace = f"agent_{metadata.name.lower()}"
                        self.logger.debug(
                            f"Connected agent to shared memory: {memory_namespace}"
                        )
                except Exception as e:
                    self.logger.warning(
                        "Failed to connect agent to shared memory", exception=e
                    )

            # Create instance record
            instance_id = str(uuid.uuid4())
            instance = AgentInstance(
                instance_id=instance_id,
                agent_id=agent_id,
                agent_instance=agent_instance,
                metadata=metadata,
                chroma_memory_connected=chroma_connected,
                memory_namespace=memory_namespace,
            )

            self.active_instances[instance_id] = instance
            self.registry_stats["active_instances"] += 1

            # Update agent status
            metadata.status = AgentStatus.IDLE

            self.logger.info(
                f"Created agent instance: {metadata.name}",
                parameters={
                    "instance_id": instance_id,
                    "chroma_connected": chroma_connected,
                },
            )

            return instance_id

        except Exception as e:
            self.logger.error(
                f"Failed to create agent instance: {agent_id}", exception=e
            )
            raise

    @detailed_log_function(LogCategory.AGENT)
    async def find_agents_by_capability(
        self,
        capability: AgentCapability,
        practice_area: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        max_results: int = 10,
    ) -> List[AgentMetadata]:
        """Find agents by capability with optional legal domain filters."""
        try:
            # Get agents with the capability
            candidate_ids = self.capability_index.get(capability, set())

            # Apply practice area filter
            if practice_area and practice_area in self.practice_area_index:
                candidate_ids = candidate_ids.intersection(
                    self.practice_area_index[practice_area]
                )

            # Apply jurisdiction filter
            if jurisdiction and jurisdiction in self.jurisdiction_index:
                candidate_ids = candidate_ids.intersection(
                    self.jurisdiction_index[jurisdiction]
                )

            # Get metadata and sort by success rate and performance
            candidates = []
            for agent_id in candidate_ids:
                if agent_id in self.registered_agents:
                    metadata = self.registered_agents[agent_id]
                    candidates.append(metadata)

            # Sort by success rate and performance
            candidates.sort(
                key=lambda x: (x.success_rate, -x.avg_processing_time), reverse=True
            )

            results = candidates[:max_results]

            self.logger.info(
                f"Found {len(results)} agents for capability: {capability.value}",
                parameters={
                    "practice_area": practice_area,
                    "jurisdiction": jurisdiction,
                },
            )

            return results

        except Exception as e:
            self.logger.error(
                f"Failed to find agents by capability: {capability.value}", exception=e
            )
            return []

    @detailed_log_function(LogCategory.AGENT)
    async def execute_with_best_agent(
        self,
        capability: AgentCapability,
        task_data: Any,
        priority: TaskPriority = TaskPriority.MEDIUM,
        **filters,
    ) -> AgentResult:
        """Execute a task with the best available agent for the capability."""
        try:
            # Find suitable agents
            agents = await self.find_agents_by_capability(capability, **filters)

            if not agents:
                raise RuntimeError(
                    f"No agents available for capability: {capability.value}"
                )

            # Try agents in order of preference
            for metadata in agents:
                try:
                    # Get or create instance
                    instance = await self._get_or_create_instance(metadata.agent_id)

                    # Execute task
                    result = await instance.agent_instance.execute(
                        task_data=task_data,
                        priority=priority,
                        metadata={
                            "capability": capability.value,
                            "registry_execution": True,
                        },
                    )

                    # Update performance metrics
                    await self._update_performance_metrics(metadata.agent_id, result)

                    # Update instance usage
                    instance.last_used = datetime.now()
                    instance.task_count += 1

                    self.logger.info(
                        f"Task executed successfully with agent: {metadata.name}",
                        parameters={
                            "capability": capability.value,
                            "success": result.success,
                        },
                    )

                    return result

                except Exception as e:
                    self.logger.warning(
                        f"Agent execution failed: {metadata.name}", exception=e
                    )
                    metadata.error_count += 1
                    metadata.last_error = str(e)
                    continue

            # If we get here, all agents failed
            raise RuntimeError(f"All agents failed for capability: {capability.value}")

        except Exception as e:
            self.logger.error(
                f"Failed to execute with best agent: {capability.value}", exception=e
            )
            raise

    @detailed_log_function(LogCategory.AGENT)
    async def coordinate_with_orchestrator(
        self, orchestrator_name: str, workflow_data: Dict[str, Any]
    ) -> Any:
        """Coordinate with existing orchestrators for complex workflows."""
        if orchestrator_name not in self.orchestrator_integrations:
            raise ValueError(f"Orchestrator not available: {orchestrator_name}")

        try:
            orchestrator = self.orchestrator_integrations[orchestrator_name]

            # Handle different orchestrator types
            if orchestrator_name == "ultimate_workflow_orchestrator":
                if isinstance(orchestrator, dict) and "class_" in orchestrator:
                    # Create instance if needed
                    orchestrator_instance = cast(Any, orchestrator["class_"])(
                        self.service_container
                    )
                    result = await cast(Any, orchestrator_instance).execute_workflow(
                        **workflow_data
                    )
                else:
                    # Use existing instance
                    result = await cast(Any, orchestrator).execute_workflow(
                        **workflow_data
                    )

            elif orchestrator_name == "knowledge_systems_coordinator":
                if isinstance(orchestrator, dict) and "class_" in orchestrator:
                    orchestrator_instance = cast(Any, orchestrator["class_"])(
                        service_config=workflow_data.get("config")
                    )
                    await cast(Any, orchestrator_instance).initialize()
                    result = await cast(Any, orchestrator_instance).hybrid_search(
                        **workflow_data.get("search_params", {})
                    )
                else:
                    result = await cast(Any, orchestrator).hybrid_search(
                        **workflow_data.get("search_params", {})
                    )

            else:
                # Generic orchestrator execution
                if hasattr(orchestrator, "execute"):
                    result = await cast(Any, orchestrator).execute(**workflow_data)
                elif hasattr(orchestrator, "process"):
                    result = await cast(Any, orchestrator).process(**workflow_data)
                else:
                    raise RuntimeError(
                        f"Orchestrator {orchestrator_name} has no execute or process method"
                    )

            self.logger.info(f"Coordinated with orchestrator: {orchestrator_name}")
            return result

        except Exception as e:
            self.logger.error(
                f"Failed to coordinate with orchestrator: {orchestrator_name}",
                exception=e,
            )
            raise

    async def _auto_discover_agents(self) -> None:
        """Auto-discover agents from configured paths."""
        try:
            for module_path in self.auto_discovery_paths:
                try:
                    await self._discover_agents_in_module(module_path)
                except Exception as e:
                    self.logger.debug(
                        f"Could not discover agents in {module_path}", exception=e
                    )

        except Exception as e:
            self.logger.error("Auto-discovery failed", exception=e)

    async def _discover_agents_in_module(self, module_path: str) -> None:
        """Discover agents in a specific module path."""
        try:
            # Try to import the module
            try:
                module = importlib.import_module(module_path)
            except ImportError:
                return

            # Look for BaseAgent subclasses
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BaseAgent)
                    and obj != BaseAgent
                    and obj.__module__ == module_path
                ):

                    try:
                        await self.register_agent(
                            agent_class=obj,
                            name=name,
                            description=getattr(
                                obj, "__doc__", f"Auto-discovered agent: {name}"
                            ),
                            registered_by="auto_discovery",
                        )
                    except Exception as e:
                        self.logger.debug(
                            f"Failed to register auto-discovered agent: {name}",
                            exception=e,
                        )

        except Exception as e:
            self.logger.debug(
                f"Failed to discover agents in module: {module_path}", exception=e
            )

    def _infer_capabilities(self, agent_class: Type[BaseAgent]) -> Set[AgentCapability]:
        """Infer agent capabilities from class name and methods."""
        capabilities = set()

        class_name = agent_class.__name__.lower()

        # Capability inference based on naming patterns
        capability_patterns = {
            AgentCapability.DOCUMENT_PROCESSING: ["document", "processor", "doc"],
            AgentCapability.TEXT_ANALYSIS: ["text", "analysis", "analyzer"],
            AgentCapability.ENTITY_EXTRACTION: [
                "entity",
                "extraction",
                "extractor",
                "ner",
            ],
            AgentCapability.LEGAL_ANALYSIS: ["legal", "law", "precedent"],
            AgentCapability.SEMANTIC_ANALYSIS: ["semantic", "meaning"],
            AgentCapability.STRUCTURAL_ANALYSIS: ["structural", "structure"],
            AgentCapability.CITATION_ANALYSIS: ["citation", "cite"],
            AgentCapability.KNOWLEDGE_GRAPH: ["knowledge", "graph", "kg"],
            AgentCapability.VECTOR_SEARCH: ["vector", "embedding", "search"],
            AgentCapability.MEMORY_MANAGEMENT: ["memory", "mem"],
            AgentCapability.REASONING: ["reasoning", "inference", "logic"],
            AgentCapability.VALIDATION: ["validation", "validator", "verify"],
        }

        for capability, patterns in capability_patterns.items():
            if any(pattern in class_name for pattern in patterns):
                capabilities.add(capability)

        # Check methods for additional capabilities
        methods = [method for method in dir(agent_class) if not method.startswith("_")]

        if any(method in ["process_document", "extract_text"] for method in methods):
            capabilities.add(AgentCapability.DOCUMENT_PROCESSING)

        if any(method in ["analyze", "analyze_text"] for method in methods):
            capabilities.add(AgentCapability.TEXT_ANALYSIS)

        # Default capability if none inferred
        if not capabilities:
            capabilities.add(AgentCapability.TEXT_ANALYSIS)

        return capabilities

    def _update_indices(self, agent_id: str, metadata: AgentMetadata) -> None:
        """Update capability and domain indices."""
        # Update capability index
        for capability in metadata.capabilities:
            if capability not in self.capability_index:
                self.capability_index[capability] = set()
            self.capability_index[capability].add(agent_id)

        # Update practice area index
        for practice_area in metadata.practice_areas:
            if practice_area not in self.practice_area_index:
                self.practice_area_index[practice_area] = set()
            self.practice_area_index[practice_area].add(agent_id)

        # Update jurisdiction index
        for jurisdiction in metadata.jurisdictions:
            if jurisdiction not in self.jurisdiction_index:
                self.jurisdiction_index[jurisdiction] = set()
            self.jurisdiction_index[jurisdiction].add(agent_id)

    async def _get_or_create_instance(self, agent_id: str) -> AgentInstance:
        """Get existing instance or create new one."""
        # Look for existing instance
        for instance in self.active_instances.values():
            if instance.agent_id == agent_id and instance.metadata.status in [
                AgentStatus.IDLE,
                AgentStatus.COMPLETED,
            ]:
                return instance

        # Create new instance
        instance_id = await self.create_agent_instance(agent_id)
        return self.active_instances[instance_id]

    async def _update_performance_metrics(
        self, agent_id: str, result: AgentResult
    ) -> None:
        """Update performance metrics for an agent."""
        if agent_id not in self.registered_agents:
            return

        metadata = self.registered_agents[agent_id]

        # Update success rate
        total_tasks = metadata.task_count
        if result.success:
            success_count = int(metadata.success_rate * total_tasks) + 1
        else:
            success_count = int(metadata.success_rate * total_tasks)

        metadata.success_rate = success_count / (total_tasks + 1)

        # Update average processing time
        if result.processing_time > 0:
            if metadata.avg_processing_time == 0:
                metadata.avg_processing_time = result.processing_time
            else:
                metadata.avg_processing_time = (
                    metadata.avg_processing_time * total_tasks + result.processing_time
                ) / (total_tasks + 1)

        # Update task count
        metadata.task_count += 1

    async def _store_agent_metadata_in_memory(
        self, agent_id: str, metadata: AgentMetadata
    ) -> None:
        """Store agent metadata in shared memory."""
        try:
            if not self.shared_memory_manager:
                return

            metadata_dict = {
                "agent_id": agent_id,
                "name": metadata.name,
                "description": metadata.description,
                "capabilities": [c.value for c in metadata.capabilities],
                "practice_areas": metadata.practice_areas,
                "jurisdictions": metadata.jurisdictions,
                "success_rate": metadata.success_rate,
                "avg_processing_time": metadata.avg_processing_time,
                "registered_at": metadata.registered_at.isoformat(),
            }

            await self.shared_memory_manager.store_document(
                doc_id=f"agent_metadata_{agent_id}",
                content=json.dumps(metadata_dict),
                metadata={
                    "type": "agent_metadata",
                    "agent_name": metadata.name,
                    "capabilities": [c.value for c in metadata.capabilities],
                },
            )

        except Exception as e:
            self.logger.warning(
                "Failed to store agent metadata in shared memory", exception=e
            )

    async def _health_monitor_loop(self) -> None:
        """Background health monitoring loop."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                await self._perform_health_checks()
            except Exception as e:
                self.logger.error("Health monitor loop error", exception=e)

    async def _perform_health_checks(self) -> None:
        """Perform health checks on all active instances."""
        try:
            for instance in self.active_instances.values():
                try:
                    if hasattr(instance.agent_instance, "health_check"):
                        health_status = await instance.agent_instance.health_check()

                        if health_status.get("healthy", True):
                            instance.metadata.status = AgentStatus.IDLE
                            instance.metadata.last_health_check = datetime.now()
                        else:
                            instance.metadata.status = AgentStatus.FAILED
                            instance.metadata.error_count += 1
                            instance.metadata.last_error = health_status.get(
                                "error", "Health check failed"
                            )

                except Exception as e:
                    instance.metadata.status = AgentStatus.FAILED
                    instance.metadata.error_count += 1
                    instance.metadata.last_error = str(e)
                    self.registry_stats["health_check_failures"] += 1

        except Exception as e:
            self.logger.error("Health check failed", exception=e)

    async def _load_agent_metadata(self) -> None:
        """Load persisted agent metadata."""
        try:
            metadata_file = Path("storage/agent_registry_metadata.json")
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    data = json.load(f)

                # Load performance metrics for registered agents
                for agent_id, stored_data in data.items():
                    if agent_id in self.registered_agents:
                        metadata = self.registered_agents[agent_id]
                        metadata.success_rate = stored_data.get("success_rate", 1.0)
                        metadata.avg_processing_time = stored_data.get(
                            "avg_processing_time", 0.0
                        )
                        metadata.error_count = stored_data.get("error_count", 0)

                self.logger.info("Loaded persisted agent metadata")

        except Exception as e:
            self.logger.warning("Failed to load agent metadata", exception=e)

    async def get_registry_statistics(self) -> Dict[str, Any]:
        """Get comprehensive registry statistics."""
        return {
            "registry_stats": self.registry_stats.copy(),
            "registered_agents": len(self.registered_agents),
            "active_instances": len(self.active_instances),
            "capability_distribution": {
                cap.value: len(agents) for cap, agents in self.capability_index.items()
            },
            "orchestrator_integrations": list(self.orchestrator_integrations.keys()),
            "shared_memory_connected": self.shared_memory_manager is not None,
            "health_status": {
                agent_id: metadata.status.value
                for agent_id, metadata in self.registered_agents.items()
            },
        }

    async def save_metadata(self) -> None:
        """Save agent metadata to persistent storage."""
        try:
            storage_dir = Path("storage")
            storage_dir.mkdir(exist_ok=True)

            metadata_to_save = {}
            for agent_id, metadata in self.registered_agents.items():
                metadata_to_save[agent_id] = {
                    "success_rate": metadata.success_rate,
                    "avg_processing_time": metadata.avg_processing_time,
                    "error_count": metadata.error_count,
                    "task_count": getattr(metadata, "task_count", 0),
                    "last_health_check": (
                        metadata.last_health_check.isoformat()
                        if metadata.last_health_check
                        else None
                    ),
                }

            metadata_file = storage_dir / "agent_registry_metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata_to_save, f, indent=2)

            self.logger.info("Agent metadata saved successfully")

        except Exception as e:
            self.logger.error("Failed to save agent metadata", exception=e)

    @property
    def agent_types(self) -> Dict[str, Type[BaseAgent]]:
        """Compatibility view of agent types keyed by agent name."""
        return {
            metadata.name: metadata.agent_class
            for metadata in self.registered_agents.values()
        }

    @property
    def active_agents(self) -> Dict[str, AgentInstance]:
        """Compatibility alias for active runtime instances."""
        return self.active_instances

    async def register_agent_type(
        self,
        agent_type: str,
        agent_class: Type[BaseAgent],
        description: Optional[str] = None,
    ) -> str:
        """Compatibility wrapper for legacy integrations."""
        return await self.register_agent(
            agent_class=agent_class,
            name=agent_type,
            description=description,
        )

    async def shutdown_all_agents(self) -> None:
        """Compatibility wrapper for legacy integrations."""
        await self.shutdown()

    async def shutdown(self) -> None:
        """Shutdown the agent registry gracefully."""
        try:
            # Save metadata
            await self.save_metadata()

            # Shutdown active instances
            for instance in self.active_instances.values():
                try:
                    if hasattr(instance.agent_instance, "shutdown"):
                        await instance.agent_instance.shutdown()
                except Exception as e:
                    self.logger.warning(
                        f"Failed to shutdown agent instance: {instance.instance_id}",
                        exception=e,
                    )

            # Clear collections
            self.active_instances.clear()
            self.orchestrator_integrations.clear()

            self.logger.info("Agent Registry shutdown complete")

        except Exception as e:
            self.logger.error("Error during Agent Registry shutdown", exception=e)


# Factory function for service container integration
def create_agent_registry(
    service_container: Any, config_manager: Optional[ConfigurationManager] = None
) -> AgentRegistry:
    """Create Agent Registry with dependency injection."""
    return AgentRegistry(
        service_container=service_container, config_manager=config_manager
    )
