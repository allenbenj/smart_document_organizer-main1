# ARCHITECTURE_MAP.md

AGENT MAP (LLM-READY)

# ---------------------
# 1. Production Agents (full backend)
# 2. Fallback Agents (mock/offline)
# 3. Simple GUI Manager (REST client)
# 4. Cross-cutting contracts
#
# Each entry = <agent_name>: <class> | <primary_method> | <input_contract> -> <output_contract>

## 1. PRODUCTION AGENTS
document_processor: DocumentProcessor | _process_task(task_data, metadata) | file_path or doc payload | -> {success, data, agent_type}
  - Reference: [`agents/processors/document_processor.py`](agents/processors/document_processor.py:1)

entity_extractor: LegalEntityExtractor | _process_task(task_data, metadata) | text or doc payload | -> {entities: [{label, confidence}]}
  - Reference: [`agents/extractors/entity_extractor.py`](agents/extractors/entity_extractor.py:1)

irac_analyzer: IracAnalyzerAgent | _process_task(task_data, metadata) | document text | -> {issue, rule, application, conclusion, confidences}
  - Reference: [`agents/legal/irac_analyzer.py`](agents/legal/irac_analyzer.py:1)

toulmin_analyzer: ToulminAnalyzer | analyze_async(document_content, context) | document content | -> {claims, data, warrants, backing, qualifier, rebuttal, confidences}
  - Reference: [`agents/legal/toulmin_analyzer.py`](agents/legal/toulmin_analyzer.py:1)

legal_reasoning: LegalReasoningEngine | analyze_legal_document(content, document_id, analysis_type) | content, id, type | -> structured reasoning results
  - Reference: [`agents/legal/legal_reasoning_engine.py`](agents/legal/legal_reasoning_engine.py:1)

enhanced_factory: EnhancedAgentFactory | create_document_processor(service_container) | ProductionServiceContainer | -> DocumentProcessor
  - Reference: [`agents/base/enhanced_agent_factory.py`](agents/base/enhanced_agent_factory.py:1)

production_container: ProductionServiceContainer | DI lifecycle provider | config | -> wired agents
  - Reference: [`core/container/service_container_impl.py`](core/container/service_container_impl.py:1)

# Cross-check with concrete production agents
- Document Processor: [`agents/processors/document_processor.py`](agents/processors/document_processor.py:1)
- Entity Extractor: [`agents/extractors/entity_extractor.py`](agents/extractors/entity_extractor.py:1)
- IRAC Analyzer: [`agents/legal/irac_analyzer.py`](agents/legal/irac_analyzer.py:1)
- Toulmin Analyzer: [`agents/legal/toulmin_analyzer.py`](agents/legal/toulmin_analyzer.py:1)
- Legal Reasoning Engine: [`agents/legal/legal_reasoning_engine.py`](agents/legal/legal_reasoning_engine.py:1)

## 2. FALLBACK AGENTS (mock)
fallback_manager: FallbackAgentManager | get_agent_status(agent_type) | AgentType enum | -> {status, message}
  - Reference: [`agents/fallback_agent_manager.py`](agents/fallback_agent_manager.py:1)

fallback_manager: FallbackAgentManager | process_document(file_path, **kwargs) | file_path | -> AgentResult
  - Reference: [`agents/fallback_agent_manager.py`](agents/fallback_agent_manager.py:1)

fallback_manager: FallbackAgentManager | extract_entities(text, **kwargs) | text | -> AgentResult
  - Reference: [`agents/fallback_agent_manager.py`](agents/fallback_agent_manager.py:1)

fallback_manager: FallbackAgentManager | analyze_legal_reasoning(content, **kwargs) | content | -> AgentResult
  - Reference: [`agents/fallback_agent_manager.py`](agents/fallback_agent_manager.py:1)

fallback_manager: FallbackAgentManager | analyze_irac(text, **kwargs) | text | -> AgentResult
  - Reference: [`agents/fallback_agent_manager.py`](agents/fallback_agent_manager.py:1)

fallback_manager: FallbackAgentManager | analyze_toulmin(content, **kwargs) | content | -> AgentResult
  - Reference: [`agents/fallback_agent_manager.py`](agents/fallback_agent_manager.py:1)

fallback_manager: FallbackAgentManager | get_system_health() | None | -> {overall, agents: {agent_name: status}}
  - Reference: [`agents/fallback_agent_manager.py`](agents/fallback_agent_manager.py:1)

fallback_manager: FallbackAgentManager | get_available_agents() | None | -> [agent_name strings]
  - Reference: [`agents/fallback_agent_manager.py`](agents/fallback_agent_manager.py:1)

## 3. SIMPLE GUI MANAGER (REST client)
simple_manager: SimpleAgentManager | initialize_session() | None | -> session_id
  - Reference: [`agents/simple_agent_manager.py`](agents/simple_agent_manager.py:1)

simple_manager: SimpleAgentManager | check_backend_health() | None | -> {status, latency_ms}
  - Reference: [`agents/simple_agent_manager.py`](agents/simple_agent_manager.py:1)

simple_manager: SimpleAgentManager | initialize_agent(agent_type) | agent_type string | -> {status}
  - Reference: [`agents/simple_agent_manager.py`](agents/simple_agent_manager.py:1)

simple_manager: SimpleAgentManager | initialize_all_agents() | None | -> {status}
  - Reference: [`agents/simple_agent_manager.py`](agents/simple_agent_manager.py:1)

simple_manager: SimpleAgentManager | execute_agent_task(agent_type, task_data, metadata) | agent_type, task_data, metadata | -> AgentResult
  - Reference: [`agents/simple_agent_manager.py`](agents/simple_agent_manager.py:1)

simple_manager: SimpleAgentManager | search_documents(query, category, tags) | query string | -> [doc hits]
  - Reference: [`agents/simple_agent_manager.py`](agents/simple_agent_manager.py:1)

simple_manager: SimpleAgentManager | create_document(document_data) | dict | -> {doc_id}
  - Reference: [`agents/simple_agent_manager.py`](agents/simple_agent_manager.py:1)

simple_manager: SimpleAgentManager | analyze_content(text) | text | -> analysis dict
  - Reference: [`agents/simple_agent_manager.py`](agents/simple_agent_manager.py:1)

## 4. CROSS-CUTTING CONTRACTS
factory: EnhancedAgentFactory | create_document_processor(service_container) | ProductionServiceContainer | -> DocumentProcessor
  - Reference: [`agents/base/enhanced_agent_factory.py`](agents/base/enhanced_agent_factory.py:1)

factory: EnhancedAgentFactory | create_legal_entity_extractor(service_container) | ProductionServiceContainer | -> LegalEntityExtractor
  - Reference: [`agents/base/enhanced_agent_factory.py`](agents/base/enhanced_agent_factory.py:1)

factory: EnhancedAgentFactory | create_irac_analyzer(service_container) | ProductionServiceContainer | -> IracAnalyzerAgent
  - Reference: [`agents/base/enhanced_agent_factory.py`](agents/base/enhanced_agent_factory.py:1)

container: ProductionServiceContainer | lifecycle & DI provider | config | -> wired agents
  - Reference: [`core/container/service_container_impl.py`](core/container/service_container_impl.py:1)

analytics: get_analytics_manager() | singleton | None | -> analytics interface
  - Reference: [`agents/analytics_manager.py`](agents/analytics_manager.py:1)

Usage examples (LLM-driven prompts)
- “Call the IRAC analyzer on this text” → irac_analyzer._process_task(text, {})
- “Mock fallback for entity extraction” → fallback_manager.extract_entities(text)
- “Initialize all agents via REST” → simple_manager.initialize_all_agents()
- “Create a production DocumentProcessor” → EnhancedAgentFactory().create_document_processor(service_container)

GUI integration surface (conceptual)
- gui_dashboard.py (proposed): acts as the REST client orchestrating GUI actions against the backend via SimpleAgentManager and directly via REST for advanced workflows.

CAn you use this?
