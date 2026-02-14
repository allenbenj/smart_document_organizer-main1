# AGENTS_MAP.md

Overview
- This document provides a consolidated mapping of all agent types implemented under backend/src/agents, including the concrete classes, their primary public methods, and the data contracts they expect or return. It serves as a single source of truth for how the GUI and orchestration layer interact with production, fallback, and simple agents.

Production agents (core orchestration)
- Role: Bridge between the GUI dashboard and production-ready agents. Created and wired via EnhancedAgentFactory and ProductionServiceContainer.
- Core references:
  - ProductionAgentManager: [`backend/src/agents/production_agent_manager.py`](backend/src/agents/production_agent_manager.py:1)
  - Enhanced factory and wiring: [`backend/src/agents/base/enhanced_agent_factory.py`](backend/src/agents/base/enhanced_agent_factory.py:1)
  - Production service container: [`backend/src/core/container/service_container_impl.py`](backend/src/core/container/service_container_impl.py:1)
  - Core production agents:
    - Document Processor: [`backend/src/agents/processors/document_processor.py`](backend/src/agents/processors/document_processor.py:1)
    - Entity Extractor: [`backend/src/agents/extractors/entity_extractor.py`](backend/src/agents/extractors/entity_extractor.py:1)
    - Legal Reasoning Engine: [`backend/src/agents/legal/legal_reasoning_engine.py`](backend/src/agents/legal/legal_reasoning_engine.py:1)
    - IRAC Analyzer: [`backend/src/agents/legal/irac_analyzer.py`](backend/src/agents/legal/irac_analyzer.py:1)
    - Toulmin Analyzer: [`backend/src/agents/legal/toulmin_analyzer.py`](backend/src/agents/legal/toulmin_analyzer.py:1)

- Concrete classes and key public methods
  - Document Processor
    - Class: DocumentProcessor
    - Public method (execution): _process_task(task_data, metadata) -> Dict[str, Any]
    - Typical contract: input task_data may be a file path or document payload; metadata carries extra context. Returns a dict with keys like success, data (processing results), and agent_type.
    - Reference: [`backend/src/agents/processors/document_processor.py`](backend/src/agents/processors/document_processor.py:1)
  - Entity Extractor
    - Class: LegalEntityExtractor
    - Public method (execution): _process_task(task_data, metadata) -> Dict[str, Any]
    - Contract: input text or document payload; outputs entities with labels and confidences.
    - Reference: [`backend/src/agents/extractors/entity_extractor.py`](backend/src/agents/extractors/entity_extractor.py:1)
  - IRAC Analyzer
    - Class: IracAnalyzerAgent
    - Public method (execution): _process_task(task_data, metadata) -> Dict[str, Any]
    - Contract: input document text; outputs IRAC components (issue, rule, application, conclusion) with confidences.
    - Reference: [`backend/src/agents/legal/irac_analyzer.py`](backend/src/agents/legal/irac_analyzer.py:1)
  - Toulmin Analyzer
    - Class: ToulminAnalyzer
    - Public method (execution): analyze_async(document_content, context) -> Dict[str, Any]
    - Contract: input document content; returns Toulmin components (claims, data, warrants, etc.) with confidences.
    - Reference: [`backend/src/agents/legal/toulmin_analyzer.py`](backend/src/agents/legal/toulmin_analyzer.py:1)
  - Legal Reasoning Engine
    - Class: LegalReasoningEngine
    - Public method (execution): analyze_legal_document(document_content, document_id, analysis_type)
    - Contract: input content and identifiers; outputs structured reasoning results. 
    - Reference: [`backend/src/agents/legal/legal_reasoning_engine.py`](backend/src/agents/legal/legal_reasoning_engine.py:1)
  - EnhancedAgentFactory
    - Class: EnhancedAgentFactory
    - Public methods (factory):
      - create_document_processor(service_container)
      - create_legal_entity_extractor(service_container)
      - create_irac_analyzer(service_container)
    - Contracts rely on ProductionServiceContainer for wiring.
    - Reference: [`backend/src/agents/base/enhanced_agent_factory.py`](backend/src/agents/base/enhanced_agent_factory.py:1)
  - ProductionServiceContainer
    - Class: ProductionServiceContainer
    - Public responsibilities: provide dependencies to core production agents; lifecycle management.
    - Reference: [`backend/src/core/container/service_container_impl.py`](backend/src/core/container/service_container_impl.py:1)
  - Global analytics hook
    - get_analytics_manager() returns a singleton analytics interface for production components.
    - Reference: [`backend/src/agents/analytics_manager.py`](backend/src/agents/analytics_manager.py:1) and its singleton getter at bottom: get_analytics_manager

Fallback agents (GUI-optional / mock)
- Role: Lightweight mock/backstop when production agents are unavailable. Presents consistent interfaces so GUI can operate in offline/demo mode.
- Core references:
  - FallbackAgentManager: [`backend/src/agents/fallback_agent_manager.py`](backend/src/agents/fallback_agent_manager.py:1)

- Concrete classes and key public methods
  - FallbackAgentManager
    - get_agent_status(agent_type: AgentType) -> Dict[str, Any]
    - process_document(file_path, **kwargs) -> AgentResult
    - extract_entities(text, **kwargs) -> AgentResult
    - analyze_legal_reasoning(document_content, **kwargs) -> AgentResult
    - analyze_irac(document_text, **kwargs) -> AgentResult
    - analyze_toulmin(document_content, **kwargs) -> AgentResult
    - get_system_health() -> Dict[str, Any]
    - get_available_agents() -> List[str]
    - shutdown()
  - AgentType enum and AgentResult dataclass are defined within this module for typed results.
  - Reference: [`backend/src/agents/fallback_agent_manager.py`](backend/src/agents/fallback_agent_manager.py:1)

Simple GUI-facing agent manager
- Role: Lightweight client-side manager that routes tasks to the REST API backend (FastAPI).
- Core references:
  - SimpleAgentManager: [`backend/src/agents/simple_agent_manager.py`](backend/src/agents/simple_agent_manager.py:1)

- Concrete classes and key public methods
  - SimpleAgentManager
    - initialize_session()
    - check_backend_health()
    - initialize_agent(agent_type)
    - initialize_all_agents()
    - execute_agent_task(agent_type, task_data, metadata)
    - _handle_document_task(task_data, metadata)
    - _handle_search_task(task_data, metadata)
    - _handle_tag_task(task_data, metadata)
    - _handle_analysis_task(task_data, metadata)
    - get_agent_info(agent_type)
    - get_all_agents_info()
    - get_available_agents()
    - get_ready_agents()
    - get_manager_statistics()
    - shutdown()
  - Convenience helpers
    - initialize_all_agents()
    - search_documents(query, category=None, tags=None)
    - get_documents()
    - create_document(document_data)
    - analyze_content(text)
  - References:
    - [SimpleAgentManager](backend/src/agents/simple_agent_manager.py:1)

Cross-cutting integration points and contracts
- Agents are wired via a service container to enable lifecycle management and dependency injection:
  - EnhancedAgentFactory (production) depends on ProductionServiceContainer
  - Production GUI uses the produced agents via ProductionAgentManager
  - Simple GUI uses REST API endpoints implemented by the backend
- Core references to open-source or internal utilities:
  - Enhanced factory: [`backend/src/agents/base/enhanced_agent_factory.py`](backend/src/agents/base/enhanced_agent_factory.py:1)
  - Production container: [`backend/src/core/container/service_container_impl.py`](backend/src/core/container/service_container_impl.py:1)
  - Analytics singleton: [`backend/src/agents/analytics_manager.py`](backend/src/agents/analytics_manager.py:1) get_analytics_manager

Agent resources chat-agent profiles (prompt/persona layer)
- Role: Prompt-first persona profiles used as seed material for runtime persona/skill configuration.
- Location:
  - [`agent_resources/chatAgents/AIAgentExpert.agent.md`](../agent_resources/chatAgents/AIAgentExpert.agent.md)
  - [`agent_resources/chatAgents/DataAnalysisExpert.agent.md`](../agent_resources/chatAgents/DataAnalysisExpert.agent.md)
- Notes:
  - These are not direct Python runtime classes under `backend/src/agents`; they are declarative persona profiles that map into DB-backed `manager_personas` + `manager_skills`.
  - `AIAgentExpert` specializes in lifecycle work (create, debug, evaluate, deploy).
  - `DataAnalysisExpert` specializes in schema/row/cell/table analysis workflows.

Notes and next steps
- This AGENTS_MAP.md should be kept as a living document; as new agents are added or existing ones evolve, update public methods and contracts accordingly.
- Keep runtime class contracts (`backend/src/agents`) and declarative profile contracts (`agent_resources/chatAgents`) distinct but linked.