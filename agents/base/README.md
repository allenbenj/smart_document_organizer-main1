# Enhanced Agent Framework for Legal AI Platform

## Overview

The Enhanced Agent Framework provides a sophisticated, knowledge-driven agent system specifically designed for legal AI applications. It integrates seamlessly with existing orchestrators and leverages the rich knowledge base stored in the chroma_memory seed documents.

## Key Features

### 🧠 Knowledge-Driven Architecture
- **Seed Document Integration**: Automatically loads and applies legal reasoning frameworks (IRAC, Toulmin, Causal Chain, etc.) from pre-loaded seed documents
- **Behavior Profiles**: Creates agents with specialized legal analysis behaviors (Document Parser, Fact Extractor, Issue Mapper, etc.)
- **Reasoning Framework Application**: Applies appropriate legal reasoning frameworks to analysis tasks

### 🔧 Core Components

#### 1. Agent Registry (`agent_registry.py`)
Central registry for all Legal AI agents with:
- **Capability-based Discovery**: Find agents by legal capabilities (document processing, legal analysis, precedent matching, etc.)
- **Performance Tracking**: Monitor success rates, processing times, and health status
- **Integration with Existing Orchestrators**: Seamlessly works with UltimateWorkflowOrchestrator, SmartDocumentationOrchestrator, and KnowledgeSystemsCoordinator
- **Shared Memory Coordination**: Integrates with chroma_memory for persistent agent knowledge

#### 2. Enhanced Agent Factory (`enhanced_agent_factory.py`)
Dynamic agent creation system with:
- **Pre-defined Templates**: Ready-to-use templates for common legal tasks
- **Blueprint System**: Create custom agents from detailed specifications
- **Knowledge Context Injection**: Automatically injects relevant knowledge from seed documents
- **Resource Management**: Handles LLM, vector store, and knowledge graph dependencies

#### 3. Knowledge-Driven Agent System (`knowledge_driven_agent_system.py`)
Main orchestration system that:
- **Loads Seed Knowledge**: Parses legal reasoning frameworks and agent behaviors from seed documents
- **Creates Knowledge Agents**: Generates specialized agents with embedded legal expertise
- **Executes Legal Analysis**: Runs complete legal analysis pipelines using appropriate reasoning frameworks
- **Integrates with Existing Systems**: Works with current orchestrators and shared memory

## Architecture Integration

### Existing Orchestrators Integration
The framework integrates with existing orchestrators:

```python
# UltimateWorkflowOrchestrator integration
orchestrator = service_container.get_service('ultimate_workflow_orchestrator')
result = await orchestrator.execute_workflow(document_path)

# KnowledgeSystemsCoordinator integration  
coordinator = service_container.get_service('knowledge_systems_coordinator')
search_results = await coordinator.hybrid_search(query)

# SmartDocumentationOrchestrator integration
doc_orchestrator = service_container.get_service('smart_doc_orchestrator')
doc_results = await doc_orchestrator.run_smart_documentation_workflow()
```

### Shared Memory Integration
All agents connect to the shared chroma_memory system:

```python
# Automatic connection to shared memory
agent_system = create_knowledge_driven_agent_system(service_container)
await agent_system.initialize()  # Connects to chroma_memory automatically
```

## Usage Examples

### Basic Usage

```python
from legal_ai_modular.agents.base import create_enhanced_agent_framework

# Initialize the complete framework
agent_system = create_enhanced_agent_framework(service_container)
await agent_system.initialize()

# Execute a legal analysis task
task = LegalAnalysisTask(
    task_id="analysis_001",
    document_content="Legal document content...",
    analysis_type="fact_extraction",
    reasoning_framework=LegalReasoningFramework.IRAC,
    expected_output_format="structured"
)

result = await agent_system.execute_legal_analysis_task(task)
```

### Complete Legal Analysis Pipeline

```python
# Run a complete legal analysis pipeline
pipeline_result = await agent_system.create_legal_analysis_pipeline(
    document_content="Complex legal document...",
    pipeline_steps=[
        'document_parsing',
        'fact_extraction', 
        'issue_mapping',
        'timeline_construction',
        'legal_argument_mapping',
        'legal_summarization'
    ]
)
```

### Agent Registry Usage

```python
# Find agents by capability
legal_analyzers = await agent_system.agent_registry.find_agents_by_capability(
    capability=AgentCapability.LEGAL_ANALYSIS,
    practice_area="criminal_law",
    jurisdiction="federal"
)

# Execute with best available agent
result = await agent_system.agent_registry.execute_with_best_agent(
    capability=AgentCapability.PRECEDENT_MATCHING,
    task_data={"legal_query": "Fourth Amendment search and seizure"},
    priority=TaskPriority.HIGH
)
```

## Legal Reasoning Frameworks

The system automatically applies appropriate legal reasoning frameworks based on the analysis type:

### IRAC (Issue, Rule, Application, Conclusion)
- **Used for**: Legal summarization, issue analysis
- **Knowledge Source**: `IRAC.txt`, `agent.system.reasoning.irac.md`

### Toulmin Model of Argument
- **Used for**: Legal argument mapping, argument analysis
- **Knowledge Source**: `Toulmin_Model.txt`, `agent.system.reasoning.toulmin.model.md`

### Causal Chain Reasoning
- **Used for**: Timeline construction, causation analysis
- **Knowledge Source**: `causal_chain_reasoning.txt`, `agent.system.reasoning.causal.chain.md`

### Issue Trees
- **Used for**: Issue mapping, problem structuring
- **Knowledge Source**: `issue_trees.txt`, `agent.system.reasoning.issuetrees.md`

### MECE Principle
- **Used for**: Fact extraction, categorization
- **Knowledge Source**: `mece_principle.txt`, `agent.system.reasoning.mece.principle.md`

### Critical Thinking Framework
- **Used for**: Document parsing, validation
- **Knowledge Source**: `critical_thinking_framework.txt`, `agent.system.reasoning.critical.thinking.md`

### SWOT Analysis
- **Used for**: Strategic case assessment
- **Knowledge Source**: `swot_analysis_framework.txt`, `agent.system.reasoning.swot.md`

## Agent Behavior Profiles

The system creates agents with specialized behaviors based on seed document knowledge:

### Document Parser Agent
- **Purpose**: Extract and structure legal document content
- **Knowledge Source**: `agent_knowledge.txt` (Document Parser section)
- **Capabilities**: Document processing, text analysis, structural analysis

### Fact Extraction Agent
- **Purpose**: Identify and extract factual elements using IRAC and legal taxonomies
- **Knowledge Source**: `agent_knowledge.txt` (Fact Extraction section)
- **Capabilities**: Entity extraction, text analysis, legal analysis

### Issue Mapping Agent
- **Purpose**: Classify facts into legal issue domains using MECE structuring
- **Knowledge Source**: `agent_knowledge.txt` (Issue Mapping section)
- **Capabilities**: Legal analysis, reasoning, text analysis

### Timeline Constructor Agent
- **Purpose**: Assemble chronological facts with causal relationships
- **Knowledge Source**: `agent_knowledge.txt` (Timeline Constructor section)
- **Capabilities**: Semantic analysis, causal reasoning

### Legal Argument Mapper Agent
- **Purpose**: Align facts with legal elements using Toulmin Model
- **Knowledge Source**: `agent_knowledge.txt` (Legal Argument Mapper section)
- **Capabilities**: Legal analysis, reasoning, precedent matching

### Legal Summarizer Agent
- **Purpose**: Synthesize analysis into executive summaries
- **Knowledge Source**: `agent_knowledge.txt` (Legal Summarizer section)
- **Capabilities**: Semantic analysis, document generation

## Configuration

### Service Container Integration

```python
# Register with service container
service_container.register_service('enhanced_agent_framework', agent_system)

# Access from other services
agent_system = service_container.get_service('enhanced_agent_framework')
```

### Configuration Options

```python
# Custom configuration
config = ServiceIntegrationConfig(
    enable_auto_discovery=True,
    enable_orchestrator_integration=True,
    enable_shared_memory=True,
    chroma_memory_path="legal_ai_modular/memory/chroma_memory",
    max_concurrent_agents=10,
    agent_timeout_seconds=300
)

agent_system = create_enhanced_agent_framework(
    service_container=service_container,
    config_manager=config_manager,
    integration_config=config
)
```

## Performance Monitoring

The framework provides comprehensive performance monitoring:

```python
# Get system status
status = await agent_system.get_system_status()
print(f"Knowledge agents created: {status['knowledge_stats']['knowledge_agents_created']}")
print(f"Tasks processed: {status['knowledge_stats']['tasks_processed_with_knowledge']}")

# Get agent registry statistics
registry_stats = await agent_system.agent_registry.get_registry_statistics()
print(f"Registered agents: {registry_stats['registered_agents']}")
print(f"Active instances: {registry_stats['active_instances']}")
```

## Error Handling

The framework includes comprehensive error handling:

```python
try:
    result = await agent_system.execute_legal_analysis_task(task)
    if result.success:
        print("Analysis completed successfully")
        print(f"Knowledge enhanced: {result.metadata.get('knowledge_enhanced', False)}")
    else:
        print(f"Analysis failed: {result.error_message}")
except Exception as e:
    print(f"System error: {e}")
```

## Integration with Existing Systems

### Chroma Memory Integration
- Automatic connection to shared chroma_memory
- Persistent storage of agent metadata and task results
- Knowledge retrieval from seed documents

### Orchestrator Integration
- **UltimateWorkflowOrchestrator**: Document processing workflows
- **SmartDocumentationOrchestrator**: Documentation generation
- **KnowledgeSystemsCoordinator**: Hybrid search and knowledge operations

### Service Container Integration
- Automatic service registration
- Dependency injection
- Health monitoring integration

## Development and Extension

### Adding New Agent Templates

```python
# Define new template in enhanced_agent_factory.py
AgentTemplate.CUSTOM_ANALYZER = "custom_analyzer"

# Add template configuration
self.agent_templates[AgentTemplate.CUSTOM_ANALYZER] = {
    'base_class': 'CustomAnalyzerAgent',
    'capabilities': [AgentCapability.CUSTOM_ANALYSIS],
    'practice_areas': ['specialized_law'],
    'requires_llm': True,
    'concurrent_capacity': 2
}
```

### Adding New Reasoning Frameworks

```python
# Add to LegalReasoningFramework enum
class LegalReasoningFramework(Enum):
    CUSTOM_FRAMEWORK = "custom_framework"

# Add framework knowledge file to seed_documents/
# Update _load_seed_documents_knowledge() method
```

### Custom Agent Behaviors

```python
# Create custom blueprint
blueprint = AgentBlueprint(
    name="Custom Legal Agent",
    description="Specialized agent for custom legal analysis",
    template=AgentTemplate.LEGAL_ANALYZER,
    capabilities=[AgentCapability.LEGAL_ANALYSIS, AgentCapability.CUSTOM_ANALYSIS],
    practice_areas=["custom_law"],
    jurisdictions=["federal"],
    custom_config={"custom_setting": "value"}
)

# Register and create agent
blueprint_id = agent_factory.register_blueprint(blueprint)
agent_id = await agent_factory.create_agent_from_blueprint(blueprint)
```

## Troubleshooting

### Common Issues

1. **Seed Documents Not Loading**
   - Verify `legal_ai_modular/memory/chroma_memory/seed_documents` path exists
   - Check file permissions and encoding (UTF-8)

2. **Chroma Memory Connection Failed**
   - Ensure chroma_memory service is available in service container
   - Check ChromaMemoryManager import path

3. **Agent Creation Failed**
   - Verify all required dependencies are available
   - Check service container configuration

4. **Orchestrator Integration Issues**
   - Ensure orchestrator services are registered in service container
   - Verify orchestrator method signatures match expected interface

### Debug Mode

```python
# Enable detailed logging
import logging
logging.getLogger("KnowledgeDrivenAgentSystem").setLevel(logging.DEBUG)
logging.getLogger("AgentRegistry").setLevel(logging.DEBUG)
logging.getLogger("EnhancedAgentFactory").setLevel(logging.DEBUG)
```

## License

This enhanced agent framework is part of the Legal AI Modular system and follows the same licensing terms as the parent project.