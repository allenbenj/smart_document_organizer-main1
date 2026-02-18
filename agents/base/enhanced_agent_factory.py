"""
Enhanced Agent Factory for Legal AI Platform
Integrates with Agent Registry and existing orchestrators.
"""

import inspect
import os
from dataclasses import dataclass
from enum import Enum  # noqa: E402
from typing import Any, Dict, List, Optional, Type  # noqa: E402

from config.configuration_manager import ConfigurationManager  # noqa: E402

# Use enhanced detailed logging
from utils.logging import (  # noqa: E402
    LogCategory,
    detailed_log_function,
    get_detailed_logger,
)
from .agent_registry import AgentCapability, AgentRegistry  # noqa: E402

# Import base components
from .base_agent import AgentStatus, BaseAgent, TaskPriority  # noqa: E402

# Import existing production agents for integration.
# To keep startup fast and robust, eager heavy imports are disabled by default.
_EAGER_AGENT_IMPORTS = os.getenv("EAGER_AGENT_IMPORTS", "0").strip().lower() in {"1", "true", "yes", "on"}

LegalSemanticAnalyzer = None
create_legal_semantic_analyzer = None
SEMANTIC_ANALYZER_AVAILABLE = False

LegalPrecedentAnalyzer = None
create_legal_precedent_analyzer = None
PRECEDENT_ANALYZER_AVAILABLE = False

LegalEntityExtractor = None
create_legal_entity_extractor = None
ENTITY_EXTRACTOR_AVAILABLE = False

UnifiedEmbeddingAgent = None
EMBEDDING_AGENT_AVAILABLE = False

CITATION_ANALYZER_AVAILABLE = False
COMPLIANCE_CHECKER_AVAILABLE = False
CONTRACT_ANALYZER_AVAILABLE = False

if _EAGER_AGENT_IMPORTS:
    try:
        from agents.analysis.semantic_analyzer import (  # noqa: E402
            LegalSemanticAnalyzer,
            create_legal_semantic_analyzer,
        )

        SEMANTIC_ANALYZER_AVAILABLE = True
    except Exception:
        LegalSemanticAnalyzer = None
        create_legal_semantic_analyzer = None
        SEMANTIC_ANALYZER_AVAILABLE = False

    try:
        from agents.legal.precedent_analyzer import (  # noqa: E402
            LegalPrecedentAnalyzer,
            create_legal_precedent_analyzer,
        )

        PRECEDENT_ANALYZER_AVAILABLE = True
    except Exception:
        LegalPrecedentAnalyzer = None
        create_legal_precedent_analyzer = None
        PRECEDENT_ANALYZER_AVAILABLE = False

    try:
        from agents.extractors.entity_extractor import (  # noqa: E402
            LegalEntityExtractor,
            create_legal_entity_extractor,
        )

        ENTITY_EXTRACTOR_AVAILABLE = True
    except Exception:
        LegalEntityExtractor = None
        create_legal_entity_extractor = None
        ENTITY_EXTRACTOR_AVAILABLE = False

    try:
        from agents.embedding.unified_embedding_agent import UnifiedEmbeddingAgent  # noqa: E402

        EMBEDDING_AGENT_AVAILABLE = True
    except Exception:
        UnifiedEmbeddingAgent = None
        EMBEDDING_AGENT_AVAILABLE = False

    # Optional analyzers (stubs available)
    try:
        from agents.legal.citation_analyzer import (  # type: ignore  # noqa: E402, F401
            CitationAnalyzer,
            create_citation_analyzer,
        )

        CITATION_ANALYZER_AVAILABLE = True
    except Exception:
        CITATION_ANALYZER_AVAILABLE = False

    try:
        from agents.legal.compliance_checker import (  # type: ignore  # noqa: E402, F401
            ComplianceChecker,
            create_compliance_checker,
        )

        COMPLIANCE_CHECKER_AVAILABLE = True
    except Exception:
        COMPLIANCE_CHECKER_AVAILABLE = False

    try:
        from agents.legal.contract_analyzer import (  # type: ignore  # noqa: E402, F401
            ContractAnalyzer,
            create_contract_analyzer,
        )

        CONTRACT_ANALYZER_AVAILABLE = True
    except Exception:
        CONTRACT_ANALYZER_AVAILABLE = False

# Initialize logger
factory_logger = get_detailed_logger("EnhancedAgentFactory", LogCategory.AGENT)


class AgentTemplate(Enum):
    """Pre-defined agent templates for common legal AI tasks."""

    DOCUMENT_PROCESSOR = "document_processor"
    LEGAL_ANALYZER = "legal_analyzer"
    ENTITY_EXTRACTOR = "entity_extractor"
    CITATION_ANALYZER = "citation_analyzer"
    PRECEDENT_MATCHER = "precedent_matcher"
    COMPLIANCE_CHECKER = "compliance_checker"
    SEMANTIC_ANALYZER = "semantic_analyzer"
    MEMORY_MANAGER = "memory_manager"
    WORKFLOW_COORDINATOR = "workflow_coordinator"
    PRODUCTION_SEMANTIC_ANALYZER = "production_semantic_analyzer"
    PRODUCTION_PRECEDENT_ANALYZER = "production_precedent_analyzer"
    PRODUCTION_ENTITY_EXTRACTOR = "production_entity_extractor"
    PRODUCTION_EMBEDDING_AGENT = "production_embedding_agent"


@dataclass
class AgentBlueprint:
    """Blueprint for creating specialized legal AI agents."""

    name: str
    description: str
    template: AgentTemplate
    capabilities: List[AgentCapability]

    # Legal domain specifics
    practice_areas: List[str]
    jurisdictions: List[str]
    document_types: List[str]

    # Technical requirements
    requires_llm: bool = True
    requires_vector_store: bool = False
    requires_knowledge_graph: bool = False
    requires_chroma_memory: bool = True

    # Performance characteristics
    concurrent_capacity: int = 1
    memory_usage_mb: float = 100.0
    expected_processing_time: float = 5.0

    # Custom configuration
    custom_config: Optional[Dict[str, Any]] = None


class EnhancedAgentFactory:
    """
    Enhanced factory for creating and managing Legal AI agents.

    Features:
    - Integration with Agent Registry
    - Pre-defined templates for common legal tasks
    - Dynamic agent creation from blueprints
    - Integration with existing orchestrators
    - Shared memory coordination via chroma_memory
    - Performance optimization and resource management
    """

    def __init__(
        self,
        service_container: Any,
        agent_registry: Optional[AgentRegistry] = None,
        config_manager: Optional[ConfigurationManager] = None,
    ):
        self.service_container = service_container
        self.agent_registry = agent_registry
        self.config_manager = config_manager
        self.logger = get_detailed_logger("EnhancedAgentFactory", LogCategory.AGENT)

        # Template definitions
        self.agent_templates = self._initialize_templates()

        # Agent blueprints
        self.blueprints: Dict[str, AgentBlueprint] = {}

        # Factory statistics
        self.factory_stats = {
            "agents_created": 0,
            "templates_used": {},
            "blueprints_registered": 0,
            "creation_failures": 0,
        }

        self.logger.info("Enhanced Agent Factory initialized")

    @detailed_log_function(LogCategory.AGENT)
    def _initialize_templates(self) -> Dict[AgentTemplate, Dict[str, Any]]:
        """Initialize pre-defined agent templates."""
        templates = {
            AgentTemplate.DOCUMENT_PROCESSOR: {
                "base_class": "DocumentProcessorAgent",
                "capabilities": [
                    AgentCapability.DOCUMENT_PROCESSING,
                    AgentCapability.TEXT_ANALYSIS,
                    AgentCapability.STRUCTURAL_ANALYSIS,
                ],
                "practice_areas": ["general"],
                "document_types": ["pdf", "docx", "txt", "html"],
                "requires_llm": True,
                "requires_chroma_memory": True,
                "concurrent_capacity": 3,
            },
            AgentTemplate.LEGAL_ANALYZER: {
                "base_class": "LegalAnalysisAgent",
                "capabilities": [
                    AgentCapability.LEGAL_ANALYSIS,
                    AgentCapability.PRECEDENT_MATCHING,
                    AgentCapability.REASONING,
                ],
                "practice_areas": ["litigation", "contracts", "constitutional"],
                "document_types": ["case_law", "statutes", "regulations"],
                "requires_llm": True,
                "requires_knowledge_graph": True,
                "requires_chroma_memory": True,
                "concurrent_capacity": 2,
            },
            AgentTemplate.ENTITY_EXTRACTOR: {
                "base_class": "EntityExtractionAgent",
                "capabilities": [
                    AgentCapability.ENTITY_EXTRACTION,
                    AgentCapability.TEXT_ANALYSIS,
                ],
                "practice_areas": ["general"],
                "document_types": ["legal_documents"],
                "requires_llm": True,
                "requires_chroma_memory": True,
                "concurrent_capacity": 5,
            },
            AgentTemplate.CITATION_ANALYZER: {
                "base_class": "CitationAnalysisAgent",
                "capabilities": [
                    AgentCapability.CITATION_ANALYSIS,
                    AgentCapability.VALIDATION,
                ],
                "practice_areas": ["research", "litigation"],
                "document_types": ["case_law", "briefs"],
                "requires_llm": False,
                "requires_knowledge_graph": True,
                "requires_chroma_memory": True,
                "concurrent_capacity": 4,
            },
            AgentTemplate.PRECEDENT_MATCHER: {
                "base_class": "PrecedentMatchingAgent",
                "capabilities": [
                    AgentCapability.PRECEDENT_MATCHING,
                    AgentCapability.LEGAL_ANALYSIS,
                    AgentCapability.VECTOR_SEARCH,
                ],
                "practice_areas": ["litigation", "research"],
                "document_types": ["case_law"],
                "requires_llm": True,
                "requires_vector_store": True,
                "requires_knowledge_graph": True,
                "requires_chroma_memory": True,
                "concurrent_capacity": 2,
            },
            AgentTemplate.COMPLIANCE_CHECKER: {
                "base_class": "ComplianceCheckingAgent",
                "capabilities": [
                    AgentCapability.COMPLIANCE_CHECKING,
                    AgentCapability.VALIDATION,
                    AgentCapability.LEGAL_ANALYSIS,
                ],
                "practice_areas": ["regulatory", "corporate"],
                "document_types": ["regulations", "policies", "contracts"],
                "requires_llm": True,
                "requires_knowledge_graph": True,
                "requires_chroma_memory": True,
                "concurrent_capacity": 2,
            },
            AgentTemplate.SEMANTIC_ANALYZER: {
                "base_class": "SemanticAnalysisAgent",
                "capabilities": [
                    AgentCapability.SEMANTIC_ANALYSIS,
                    AgentCapability.TEXT_ANALYSIS,
                    AgentCapability.VECTOR_SEARCH,
                ],
                "practice_areas": ["general"],
                "document_types": ["legal_documents"],
                "requires_llm": True,
                "requires_vector_store": True,
                "requires_chroma_memory": True,
                "concurrent_capacity": 3,
            },
            AgentTemplate.MEMORY_MANAGER: {
                "base_class": "MemoryManagementAgent",
                "capabilities": [
                    AgentCapability.MEMORY_MANAGEMENT,
                    AgentCapability.VECTOR_SEARCH,
                ],
                "practice_areas": ["general"],
                "document_types": ["all"],
                "requires_llm": False,
                "requires_vector_store": True,
                "requires_chroma_memory": True,
                "concurrent_capacity": 10,
            },
            AgentTemplate.WORKFLOW_COORDINATOR: {
                "base_class": "WorkflowCoordinatorAgent",
                "capabilities": [
                    AgentCapability.WORKFLOW_ORCHESTRATION,
                    AgentCapability.MEMORY_MANAGEMENT,
                ],
                "practice_areas": ["general"],
                "document_types": ["all"],
                "requires_llm": False,
                "requires_chroma_memory": True,
                "concurrent_capacity": 1,
            },
        }

        # Add production agent templates if available
        if SEMANTIC_ANALYZER_AVAILABLE:
            templates[AgentTemplate.PRODUCTION_SEMANTIC_ANALYZER] = {
                "base_class": "LegalSemanticAnalyzer",
                "production_class": LegalSemanticAnalyzer,
                "factory_function": create_legal_semantic_analyzer,
                "capabilities": [
                    AgentCapability.SEMANTIC_ANALYSIS,
                    AgentCapability.LEGAL_ANALYSIS,
                    AgentCapability.TEXT_ANALYSIS,
                    AgentCapability.DOCUMENT_PROCESSING,
                    AgentCapability.REASONING,
                ],
                "practice_areas": [
                    "litigation",
                    "contracts",
                    "criminal",
                    "corporate",
                    "regulatory",
                ],
                "document_types": [
                    "brief",
                    "motion",
                    "complaint",
                    "contract",
                    "statute",
                    "regulation",
                ],
                "requires_llm": True,
                "requires_chroma_memory": True,
                "concurrent_capacity": 2,
            }

        if PRECEDENT_ANALYZER_AVAILABLE:
            templates[AgentTemplate.PRODUCTION_PRECEDENT_ANALYZER] = {
                "base_class": "LegalPrecedentAnalyzer",
                "production_class": LegalPrecedentAnalyzer,
                "factory_function": create_legal_precedent_analyzer,
                "capabilities": [
                    AgentCapability.PRECEDENT_MATCHING,
                    AgentCapability.CITATION_ANALYSIS,
                    AgentCapability.LEGAL_ANALYSIS,
                    AgentCapability.TEXT_ANALYSIS,
                    AgentCapability.REASONING,
                ],
                "practice_areas": [
                    "litigation",
                    "appellate",
                    "constitutional",
                    "statutory",
                ],
                "document_types": ["case_law", "brief", "motion", "opinion"],
                "requires_llm": True,
                "requires_vector_store": True,
                "requires_chroma_memory": True,
                "concurrent_capacity": 2,
            }

        if ENTITY_EXTRACTOR_AVAILABLE:
            templates[AgentTemplate.PRODUCTION_ENTITY_EXTRACTOR] = {
                "base_class": "LegalEntityExtractor",
                "production_class": LegalEntityExtractor,
                "factory_function": create_legal_entity_extractor,
                "capabilities": [
                    AgentCapability.ENTITY_EXTRACTION,
                    AgentCapability.TEXT_ANALYSIS,
                    AgentCapability.DOCUMENT_PROCESSING,
                    AgentCapability.VALIDATION,
                ],
                "practice_areas": ["litigation", "contracts", "corporate", "criminal"],
                "document_types": [
                    "complaint",
                    "contract",
                    "brief",
                    "motion",
                    "judgment",
                ],
                "requires_llm": False,
                "requires_chroma_memory": True,
                "concurrent_capacity": 3,
            }

        if EMBEDDING_AGENT_AVAILABLE:
            templates[AgentTemplate.PRODUCTION_EMBEDDING_AGENT] = {
                "base_class": "UnifiedEmbeddingAgent",
                "production_class": UnifiedEmbeddingAgent,
                "capabilities": [
                    AgentCapability.VECTOR_SEARCH,
                    AgentCapability.KNOWLEDGE_GRAPH,
                    AgentCapability.MEMORY_MANAGEMENT,
                    AgentCapability.TEXT_ANALYSIS,
                ],
                "practice_areas": ["all"],
                "document_types": ["all"],
                "requires_llm": False,
                "requires_vector_store": True,
                "requires_knowledge_graph": True,
                "concurrent_capacity": 5,
            }

        self.logger.info(
            f"Initialized {len(templates)} agent templates (including {sum(1 for t in templates.values() if 'production_class' in t)} production agents)"
        )
        return templates

    @detailed_log_function(LogCategory.AGENT)
    def register_blueprint(self, blueprint: AgentBlueprint) -> str:
        """Register a custom agent blueprint."""
        try:
            blueprint_id = (
                f"{blueprint.template.value}_{blueprint.name.lower().replace(' ', '_')}"
            )
            self.blueprints[blueprint_id] = blueprint
            self.factory_stats["blueprints_registered"] += 1

            self.logger.info(
                f"Registered agent blueprint: {blueprint.name}",
                parameters={
                    "blueprint_id": blueprint_id,
                    "template": blueprint.template.value,
                },
            )

            return blueprint_id

        except Exception as e:
            self.logger.error(
                f"Failed to register blueprint: {blueprint.name}", exception=e
            )
            raise

    @detailed_log_function(LogCategory.AGENT)
    async def create_agent_from_template(
        self,
        template: AgentTemplate,
        name: Optional[str] = None,
        custom_config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Create an agent from a pre-defined template."""
        try:
            if template not in self.agent_templates:
                raise ValueError(f"Unknown template: {template}")

            template_config = self.agent_templates[template]

            # Create blueprint from template
            blueprint = AgentBlueprint(
                name=name or f"{template.value}_agent",
                description=f"Agent created from {template.value} template",
                template=template,
                capabilities=[
                    AgentCapability(cap) for cap in template_config["capabilities"]
                ],
                practice_areas=template_config.get("practice_areas", ["general"]),
                jurisdictions=kwargs.get("jurisdictions", ["general"]),
                document_types=template_config.get("document_types", ["general"]),
                requires_llm=template_config.get("requires_llm", True),
                requires_vector_store=template_config.get(
                    "requires_vector_store", False
                ),
                requires_knowledge_graph=template_config.get(
                    "requires_knowledge_graph", False
                ),
                requires_chroma_memory=template_config.get(
                    "requires_chroma_memory", True
                ),
                concurrent_capacity=template_config.get("concurrent_capacity", 1),
                custom_config=custom_config or {},
            )

            # Create agent from blueprint
            agent_id = await self.create_agent_from_blueprint(blueprint)

            # Update statistics
            self.factory_stats["agents_created"] += 1
            template_name = template.value
            self.factory_stats["templates_used"][template_name] = (
                self.factory_stats["templates_used"].get(template_name, 0) + 1
            )

            self.logger.info(
                f"Created agent from template: {template.value}",
                parameters={"agent_id": agent_id, "name": blueprint.name},
            )

            return agent_id

        except Exception as e:
            self.factory_stats["creation_failures"] += 1
            self.logger.error(
                f"Failed to create agent from template: {template.value}", exception=e
            )
            raise

    @detailed_log_function(LogCategory.AGENT)
    async def create_agent_from_blueprint(self, blueprint: AgentBlueprint) -> str:
        """Create an agent from a blueprint."""
        try:
            # Generate dynamic agent class
            agent_class = await self._generate_agent_class(blueprint)

            # Register with agent registry if available
            if self.agent_registry:
                agent_id = await self.agent_registry.register_agent(
                    agent_class=agent_class,
                    name=blueprint.name,
                    description=blueprint.description,
                    capabilities=set(blueprint.capabilities),
                    practice_areas=blueprint.practice_areas,
                    jurisdictions=blueprint.jurisdictions,
                    document_types=blueprint.document_types,
                    requires_llm=blueprint.requires_llm,
                    requires_vector_store=blueprint.requires_vector_store,
                    requires_knowledge_graph=blueprint.requires_knowledge_graph,
                    requires_chroma_memory=blueprint.requires_chroma_memory,
                    concurrent_capacity=blueprint.concurrent_capacity,
                    memory_usage_mb=blueprint.memory_usage_mb,
                    registered_by="enhanced_agent_factory",
                )

                self.logger.info(
                    f"Agent registered with registry: {blueprint.name}",
                    parameters={"agent_id": agent_id},
                )
                return agent_id
            else:
                # Create instance directly if no registry
                agent_instance = agent_class(  # noqa: F841
                    self.service_container,
                    agent_name=blueprint.name,
                    agent_type=blueprint.template.value,
                )
                instance_id = f"direct_{blueprint.name.lower().replace(' ', '_')}"

                self.logger.info(
                    f"Agent created directly: {blueprint.name}",
                    parameters={"instance_id": instance_id},
                )
                return instance_id

        except Exception as e:
            self.factory_stats["creation_failures"] += 1
            self.logger.error(
                f"Failed to create agent from blueprint: {blueprint.name}", exception=e
            )
            raise

    async def _generate_agent_class(self, blueprint: AgentBlueprint) -> Type[BaseAgent]:
        """Generate a dynamic agent class based on blueprint."""
        try:
            # Get template configuration
            template_config = self.agent_templates.get(blueprint.template, {})

            # Create dynamic class
            class_name = f"Generated{blueprint.name.replace(' ', '')}Agent"

            # Define agent methods based on capabilities
            class_methods = self._generate_agent_methods(blueprint)

            # Create class attributes
            class_attrs = {
                "__module__": "legal_ai_modular.agents.base.enhanced_agent_factory",
                "__doc__": blueprint.description,
                "__version__": "1.0.0",
                "blueprint": blueprint,
                "template_config": template_config,
                **class_methods,
            }

            # Create the dynamic class
            agent_class = type(class_name, (BaseAgent,), class_attrs)

            self.logger.debug(f"Generated dynamic agent class: {class_name}")
            return agent_class

        except Exception as e:
            self.logger.error(
                f"Failed to generate agent class for: {blueprint.name}", exception=e
            )
            raise

    def _generate_agent_methods(self, blueprint: AgentBlueprint) -> Dict[str, Any]:  # noqa: C901
        """Generate agent methods based on capabilities."""
        methods = {}

        # Initialize method
        def __init__(self, service_container, **kwargs):
            super(self.__class__, self).__init__(service_container, **kwargs)
            self.blueprint = blueprint
            self.capabilities = blueprint.capabilities
            self.practice_areas = blueprint.practice_areas
            self.jurisdictions = blueprint.jurisdictions

            # Set up shared memory if required
            if blueprint.requires_chroma_memory:
                self._setup_shared_memory()

            # Set up other services based on requirements
            if blueprint.requires_vector_store:
                self._setup_vector_store()

            if blueprint.requires_knowledge_graph:
                self._setup_knowledge_graph()

        methods["__init__"] = __init__

        # Execute method based on template
        if blueprint.template == AgentTemplate.DOCUMENT_PROCESSOR:
            methods["execute"] = self._create_document_processor_execute()
        elif blueprint.template == AgentTemplate.LEGAL_ANALYZER:
            methods["execute"] = self._create_legal_analyzer_execute()
        else:
            raise ValueError(
                f"No execute generator implemented for template {blueprint.template.value}"
            )

        # Add helper methods
        methods["_setup_shared_memory"] = self._create_setup_shared_memory()
        methods["_setup_vector_store"] = self._create_setup_vector_store()
        methods["_setup_knowledge_graph"] = self._create_setup_knowledge_graph()
        methods["health_check"] = self._create_health_check()

        return methods

    def _create_document_processor_execute(self):
        """Create execute method for document processor agents."""

        async def execute(self, task_data, priority=TaskPriority.MEDIUM, metadata=None):
            try:
                self.status = AgentStatus.PROCESSING

                # Extract document content
                if isinstance(task_data, dict) and "document_path" in task_data:
                    document_path = task_data["document_path"]

                    # Use existing orchestrator if available
                    if hasattr(self.service_container, "get_service"):
                        orchestrator = self.service_container.get_service(
                            "ultimate_workflow_orchestrator"
                        )
                        if inspect.isawaitable(orchestrator):
                            orchestrator = await orchestrator
                        if orchestrator:
                            result = await orchestrator.execute_workflow(document_path)
                            return self._create_success_result(
                                result, "Document processed via orchestrator"
                            )

                    raise RuntimeError(
                        "ultimate_workflow_orchestrator is required but unavailable"
                    )
                else:
                    return self._create_error_result(
                        "Invalid task data for document processing"
                    )

            except Exception as e:
                self.status = AgentStatus.FAILED
                return self._create_error_result(str(e))
            finally:
                self.status = AgentStatus.IDLE

        return execute

    def _create_legal_analyzer_execute(self):
        """Create execute method for legal analyzer agents."""

        async def execute(self, task_data, priority=TaskPriority.MEDIUM, metadata=None):
            try:
                self.status = AgentStatus.PROCESSING

                if isinstance(task_data, dict) and "legal_text" in task_data:
                    legal_text = task_data["legal_text"]
                    analysis_type = task_data.get("analysis_type", "general")

                    # Use knowledge systems coordinator if available
                    if hasattr(self.service_container, "get_service"):
                        coordinator = self.service_container.get_service(
                            "knowledge_systems_coordinator"
                        )
                        if inspect.isawaitable(coordinator):
                            coordinator = await coordinator
                        if coordinator:
                            if analysis_type == "precedent":
                                result = await coordinator.precedent_analysis(
                                    legal_text
                                )
                            else:
                                result = await coordinator.legal_concept_search(
                                    legal_text
                                )
                            return self._create_success_result(
                                result, "Legal analysis completed via coordinator"
                            )

                    raise RuntimeError(
                        "knowledge_systems_coordinator is required but unavailable"
                    )
                else:
                    return self._create_error_result(
                        "Invalid task data for legal analysis"
                    )

            except Exception as e:
                self.status = AgentStatus.FAILED
                return self._create_error_result(str(e))
            finally:
                self.status = AgentStatus.IDLE

        return execute

    def _create_generic_execute(self):
        """Create generic execute method."""

        async def execute(self, task_data, priority=TaskPriority.MEDIUM, metadata=None):
            try:
                self.status = AgentStatus.PROCESSING

                # Generic processing based on capabilities
                result = {
                    "agent_name": self.blueprint.name,
                    "capabilities": [cap.value for cap in self.capabilities],
                    "task_data_received": bool(task_data),
                    "processing_timestamp": self._get_current_timestamp(),
                }

                return self._create_success_result(
                    result, "Generic processing completed"
                )

            except Exception as e:
                self.status = AgentStatus.FAILED
                return self._create_error_result(str(e))
            finally:
                self.status = AgentStatus.IDLE

        return execute

    def _create_setup_shared_memory(self):
        """Create shared memory setup method."""

        def _setup_shared_memory(self):
            try:
                if not hasattr(self.service_container, "get_service") or inspect.iscoroutinefunction(
                    self.service_container.get_service
                ):
                    raise RuntimeError("Service container get_service sync accessor is required")
                self.shared_memory = self.service_container.get_service(
                    "chroma_memory_manager"
                )
                if not self.shared_memory:
                    raise RuntimeError("Shared chroma memory service is required but unavailable")
                self.logger.info("Connected to shared chroma memory")
            except Exception as e:
                self.logger.error("Failed to setup shared memory", exception=e)
                raise

        return _setup_shared_memory

    def _create_setup_vector_store(self):
        """Create vector store setup method."""

        def _setup_vector_store(self):
            try:
                if not hasattr(self.service_container, "get_service") or inspect.iscoroutinefunction(
                    self.service_container.get_service
                ):
                    raise RuntimeError("Service container get_service sync accessor is required")
                self.vector_store = self.service_container.get_service("vector_store")
                if not self.vector_store:
                    raise RuntimeError("Vector store service is required but unavailable")
                self.logger.info("Connected to vector store")
            except Exception as e:
                self.logger.error("Failed to setup vector store", exception=e)
                raise

        return _setup_vector_store

    def _create_setup_knowledge_graph(self):
        """Create knowledge graph setup method."""

        def _setup_knowledge_graph(self):
            try:
                if not hasattr(self.service_container, "get_service") or inspect.iscoroutinefunction(
                    self.service_container.get_service
                ):
                    raise RuntimeError("Service container get_service sync accessor is required")
                self.knowledge_graph = self.service_container.get_service(
                    "knowledge_graph"
                )
                if not self.knowledge_graph:
                    raise RuntimeError(
                        "Knowledge graph service is required but unavailable"
                    )
                self.logger.info("Connected to knowledge graph")
            except Exception as e:
                self.logger.error("Failed to setup knowledge graph", exception=e)
                raise

        return _setup_knowledge_graph

    def _create_health_check(self):
        """Create health check method."""

        async def health_check(self):
            try:
                health_status = {
                    "healthy": True,
                    "agent_name": self.blueprint.name,
                    "status": self.status.value,
                    "capabilities": [cap.value for cap in self.capabilities],
                    "shared_memory_connected": hasattr(self, "shared_memory")
                    and self.shared_memory is not None,
                    "vector_store_connected": hasattr(self, "vector_store")
                    and self.vector_store is not None,
                    "knowledge_graph_connected": hasattr(self, "knowledge_graph")
                    and self.knowledge_graph is not None,
                    "last_check": self._get_current_timestamp(),
                }

                # Check service connections
                if (
                    self.blueprint.requires_chroma_memory
                    and not health_status["shared_memory_connected"]
                ):
                    health_status["healthy"] = False
                    health_status["error"] = (
                        "Shared memory connection required but not available"
                    )

                if (
                    self.blueprint.requires_vector_store
                    and not health_status["vector_store_connected"]
                ):
                    health_status["healthy"] = False
                    health_status["error"] = (
                        "Vector store connection required but not available"
                    )

                if (
                    self.blueprint.requires_knowledge_graph
                    and not health_status["knowledge_graph_connected"]
                ):
                    health_status["healthy"] = False
                    health_status["error"] = (
                        "Knowledge graph connection required but not available"
                    )

                return health_status

            except Exception as e:
                return {
                    "healthy": False,
                    "error": str(e),
                    "agent_name": getattr(self, "blueprint", {}).get("name", "unknown"),
                    "last_check": self._get_current_timestamp(),
                }

        return health_check

    @detailed_log_function(LogCategory.AGENT)
    async def create_production_agent(
        self,
        template: AgentTemplate,
        name: Optional[str] = None,
        custom_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a production agent using the existing sophisticated implementations."""
        try:
            if template not in self.agent_templates:
                raise ValueError(f"Unknown template: {template}")

            template_config = self.agent_templates[template]

            # Check if this is a production agent template
            if "production_class" not in template_config:
                raise ValueError(
                    f"Template {template} is not a production agent template"
                )

            production_class = template_config["production_class"]
            agent_name = name or f"{template.value}_production"

            # Create production agent instance
            if "factory_function" in template_config:
                # Use factory function if available
                factory_function = template_config["factory_function"]
                agent_instance = await factory_function(
                    self.service_container, custom_config
                )
            else:
                # Create directly
                agent_instance = production_class(self.service_container, custom_config)  # noqa: F841

            # Register with agent registry if available
            if self.agent_registry:
                agent_id = await self.agent_registry.register_agent(
                    agent_class=production_class,
                    name=agent_name,
                    description=f"Production {template.value} with advanced capabilities",
                    capabilities=set(
                        [
                            AgentCapability(cap)
                            for cap in template_config["capabilities"]
                        ]
                    ),
                    practice_areas=template_config.get("practice_areas", ["general"]),
                    document_types=template_config.get("document_types", ["general"]),
                    requires_llm=template_config.get("requires_llm", True),
                    requires_vector_store=template_config.get(
                        "requires_vector_store", False
                    ),
                    requires_knowledge_graph=template_config.get(
                        "requires_knowledge_graph", False
                    ),
                    requires_chroma_memory=template_config.get(
                        "requires_chroma_memory", True
                    ),
                    concurrent_capacity=template_config.get("concurrent_capacity", 1),
                    registered_by="production_agent_factory",
                )

                self.logger.info(
                    f"Created production agent: {agent_name}",
                    parameters={"agent_id": agent_id, "template": template.value},
                )
                return agent_id
            else:
                # Return instance ID if no registry
                instance_id = f"production_{agent_name.lower().replace(' ', '_')}"
                self.logger.info(
                    f"Created production agent directly: {agent_name}",
                    parameters={"instance_id": instance_id},
                )
                return instance_id

        except Exception as e:
            self.factory_stats["creation_failures"] += 1
            self.logger.error(
                f"Failed to create production agent: {template.value}", exception=e
            )
            raise

    @detailed_log_function(LogCategory.AGENT)
    async def create_complete_legal_ai_suite(self) -> Dict[str, str]:
        """Create a complete suite of legal AI agents including production agents."""
        try:
            agent_suite = {}

            # Create production agents if available
            if SEMANTIC_ANALYZER_AVAILABLE:
                semantic_id = await self.create_production_agent(
                    AgentTemplate.PRODUCTION_SEMANTIC_ANALYZER,
                    name="Production Legal Semantic Analyzer",
                )
                agent_suite["semantic_analyzer"] = semantic_id

            if PRECEDENT_ANALYZER_AVAILABLE:
                precedent_id = await self.create_production_agent(
                    AgentTemplate.PRODUCTION_PRECEDENT_ANALYZER,
                    name="Production Legal Precedent Analyzer",
                )
                agent_suite["precedent_analyzer"] = precedent_id

            if ENTITY_EXTRACTOR_AVAILABLE:
                entity_id = await self.create_production_agent(
                    AgentTemplate.PRODUCTION_ENTITY_EXTRACTOR,
                    name="Production Legal Entity Extractor",
                )
                agent_suite["entity_extractor"] = entity_id

            if EMBEDDING_AGENT_AVAILABLE:
                embedding_id = await self.create_production_agent(
                    AgentTemplate.PRODUCTION_EMBEDDING_AGENT,
                    name="Production Unified Embedding Agent",
                )
                agent_suite["embedding_agent"] = embedding_id

            # Create additional template-based agents for comprehensive coverage
            workflow_id = await self.create_agent_from_template(
                AgentTemplate.WORKFLOW_COORDINATOR, name="Legal Workflow Coordinator"
            )
            agent_suite["workflow_coordinator"] = workflow_id

            memory_id = await self.create_agent_from_template(
                AgentTemplate.MEMORY_MANAGER, name="Legal Memory Manager"
            )
            agent_suite["memory_manager"] = memory_id

            self.logger.info(
                f"Created complete legal AI suite with {len(agent_suite)} agents",
                parameters={"agents": list(agent_suite.keys())},
            )

            return agent_suite

        except Exception as e:
            self.logger.error("Failed to create complete legal AI suite", exception=e)
            raise

    @detailed_log_function(LogCategory.AGENT)
    async def create_specialized_legal_agents(self) -> Dict[str, str]:
        """Create a set of specialized legal agents for common tasks."""
        try:
            specialized_agents = {}

            # Document processing agent
            doc_agent_id = await self.create_agent_from_template(
                AgentTemplate.DOCUMENT_PROCESSOR,
                name="Legal Document Processor",
                jurisdictions=["federal", "state"],
                custom_config={"max_document_size_mb": 50},
            )
            specialized_agents["document_processor"] = doc_agent_id

            # Legal analysis agent
            legal_agent_id = await self.create_agent_from_template(
                AgentTemplate.LEGAL_ANALYZER,
                name="Legal Analysis Specialist",
                jurisdictions=["federal", "state"],
                custom_config={"analysis_depth": "comprehensive"},
            )
            specialized_agents["legal_analyzer"] = legal_agent_id

            # Entity extraction agent
            entity_agent_id = await self.create_agent_from_template(
                AgentTemplate.ENTITY_EXTRACTOR,
                name="Legal Entity Extractor",
                custom_config={
                    "entity_types": ["person", "organization", "case", "statute"]
                },
            )
            specialized_agents["entity_extractor"] = entity_agent_id

            # Citation analysis agent
            citation_agent_id = await self.create_agent_from_template(
                AgentTemplate.CITATION_ANALYZER,
                name="Citation Analysis Specialist",
                custom_config={"citation_formats": ["bluebook", "alwd"]},
            )
            specialized_agents["citation_analyzer"] = citation_agent_id

            # Precedent matching agent
            precedent_agent_id = await self.create_agent_from_template(
                AgentTemplate.PRECEDENT_MATCHER,
                name="Precedent Matching Engine",
                jurisdictions=["federal", "state"],
                custom_config={"similarity_threshold": 0.7},
            )
            specialized_agents["precedent_matcher"] = precedent_agent_id

            self.logger.info(
                f"Created {len(specialized_agents)} specialized legal agents",
                parameters={"agents": list(specialized_agents.keys())},
            )

            return specialized_agents

        except Exception as e:
            self.logger.error("Failed to create specialized legal agents", exception=e)
            raise

    def get_factory_statistics(self) -> Dict[str, Any]:
        """Get factory statistics."""
        return {
            "factory_stats": self.factory_stats.copy(),
            "available_templates": [template.value for template in AgentTemplate],
            "registered_blueprints": len(self.blueprints),
            "blueprint_names": list(self.blueprints.keys()),
            "agent_registry_connected": self.agent_registry is not None,
        }

    async def shutdown(self) -> None:
        """Shutdown the factory gracefully."""
        try:
            self.logger.info("Enhanced Agent Factory shutting down")

            # Clear blueprints
            self.blueprints.clear()

            self.logger.info("Enhanced Agent Factory shutdown complete")

        except Exception as e:
            self.logger.error("Error during factory shutdown", exception=e)


# Factory function for service container integration
def create_enhanced_agent_factory(
    service_container: Any,
    agent_registry: Optional[AgentRegistry] = None,
    config_manager: Optional[ConfigurationManager] = None,
) -> EnhancedAgentFactory:
    """Create Enhanced Agent Factory with dependency injection."""
    return EnhancedAgentFactory(
        service_container=service_container,
        agent_registry=agent_registry,
        config_manager=config_manager,
    )
