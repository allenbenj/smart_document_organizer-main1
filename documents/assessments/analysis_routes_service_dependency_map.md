# Service Dependency Map - Analysis Routes Pipeline

## Overview

This document provides a visual representation of the service dependency chain and initialization order for the analysis routes pipeline.

## Service Initialization Order

```mermaid
graph TD
    Start[Start.py Application Startup] --> SC[ProductionServiceContainer Created]
    SC --> Bootstrap[bootstrap.configure Services]
    
    Bootstrap --> CM[ConfigurationManager]
    Bootstrap --> DM[DatabaseManager]
    Bootstrap --> VS[VectorStore UnifiedVectorStore]
    Bootstrap --> KM[KnowledgeManager]
    Bootstrap --> MM[UnifiedMemoryManager]
    Bootstrap --> MS[MemoryService]
    Bootstrap --> EPM[EnhancedPersistenceManager]
    Bootstrap --> LLM[LLMManager]
    
    SC --> PAM[ProductionAgentManager Created]
    PAM --> Init[manager.initialize]
    
    Init --> CheckLazy{AGENTS_LAZY_INIT?}
    CheckLazy -->|No| InitProd[_initialize_production_system]
    CheckLazy -->|Yes| Defer[Defer Initialization]
    
    InitProd --> CreateAgents[_create_core_agents]
    
    CreateAgents --> DP[Document Processor Agent]
    CreateAgents --> EE[Entity Extractor Agent]
    CreateAgents --> LR[Legal Reasoning Agent]
    CreateAgents --> IRAC[IRAC Analyzer Agent]
    CreateAgents --> TOUL[Toulmin Analyzer Agent]
    CreateAgents --> PA[Precedent Analyzer Optional]
    
    PAM --> Register[Register in Service Container]
    
    Register --> Ready[System Ready]
```

## Request Flow - Analysis Route

```mermaid
sequenceDiagram
    participant Client
    participant Route[routes/agent_routes/analysis.py]
    participant DI[get_agent_service Dependency]
    participant AS[AgentService]
    participant PAM[ProductionAgentManager]
    participant Agent[Agent Instance]
    participant Validator[Response Validator]
    participant Memory[MemoryService Optional]
    
    Client->>Route: POST /api/agents/legal
    Route->>DI: Depends(get_agent_service)
    DI->>DI: get_strict_production_manager
    DI->>DI: Check initialization
    DI->>AS: AgentService(manager)
    AS-->>Route: AgentService instance
    
    Route->>AS: dispatch_task("analyze_legal", payload)
    AS->>AS: Check manager.initialize if needed
    AS->>PAM: analyze_legal_reasoning(text, **context)
    PAM->>PAM: Check is_initialized
    PAM->>PAM: Get agent from agents dict
    PAM->>Agent: agent.analyze_legal_document()
    Agent-->>PAM: Result
    PAM-->>AS: AgentResult
    AS-->>Route: AgentResult or dict
    
    Route->>Validator: _v("legal_reasoning", result)
    Validator->>Validator: enforce_agent_response
    Validator-->>Route: Validated dict
    
    Route->>Memory: create_proposal (optional)
    Memory-->>Route: Success/Failure
    
    Route-->>Client: Validated Response
```

## Service Container Dependency Graph

```mermaid
graph LR
    SC[Service Container] --> CM[ConfigurationManager]
    SC --> DM[DatabaseManager]
    SC --> VS[VectorStore]
    SC --> KM[KnowledgeManager]
    SC --> MM[MemoryManager]
    SC --> MS[MemoryService]
    SC --> EPM[PersistenceManager]
    SC --> LLM[LLMManager]
    SC --> PAM[AgentManager]
    
    PAM --> DP[DocumentProcessor]
    PAM --> EE[EntityExtractor]
    PAM --> LR[LegalReasoning]
    PAM --> IRAC[IRACAnalyzer]
    PAM --> TOUL[ToulminAnalyzer]
    
    DP --> SC
    EE --> SC
    LR --> SC
    IRAC --> SC
    TOUL --> SC
    
    DP --> LLM
    EE --> LLM
    LR --> LLM
    IRAC --> LLM
    TOUL --> LLM
    
    DP --> VS
    EE --> VS
    LR --> KM
```

## Task Dispatch Flow

```mermaid
graph TD
    Route[Route Handler] --> AS[AgentService.dispatch_task]
    
    AS --> CheckInit{Manager Initialized?}
    CheckInit -->|No| Init[manager.initialize]
    Init --> CheckInit
    
    CheckInit -->|Yes| MapTask[Map task_type to method]
    
    MapTask --> T1[process_document]
    MapTask --> T2[extract_entities]
    MapTask --> T3[analyze_legal]
    MapTask --> T4[analyze_irac]
    MapTask --> T5[analyze_toulmin]
    MapTask --> T6[analyze_semantic]
    MapTask --> T7[analyze_contradictions]
    MapTask --> T8[analyze_violations]
    MapTask --> T9[analyze_contract]
    MapTask --> T10[check_compliance]
    MapTask --> T11[embed_texts]
    MapTask --> T12[classify_text]
    MapTask --> T13[orchestrate_task]
    MapTask --> T14[submit_feedback]
    
    T1 --> PAM[ProductionAgentManager Method]
    T2 --> PAM
    T3 --> PAM
    T4 --> PAM
    T5 --> PAM
    T6 --> PAM
    T7 --> PAM
    T8 --> PAM
    T9 --> PAM
    T10 --> PAM
    T11 --> PAM
    T12 --> PAM
    T13 --> PAM
    T14 --> PAM
    
    PAM --> Agent[Agent Instance or Fallback]
    Agent --> Result[AgentResult]
    Result --> AS
    AS --> Route
```

## Agent Creation Flow

```mermaid
graph TD
    Init[_create_core_agents] --> Always[Always Create]
    Init --> Conditional{Conditional Create}
    
    Always --> DP[Document Processor]
    
    Conditional --> CheckEE{AGENTS_ENABLE_ENTITY_EXTRACTOR?}
    CheckEE -->|Yes| EE[Entity Extractor]
    CheckEE -->|No| SkipEE[Skip]
    
    Conditional --> CheckLR{AGENTS_ENABLE_LEGAL_REASONING?}
    CheckLR -->|Yes| LR[Legal Reasoning]
    CheckLR -->|No| SkipLR[Skip]
    
    Conditional --> CheckIRAC{AGENTS_ENABLE_IRAC?}
    CheckIRAC -->|Yes| IRAC[IRAC Analyzer]
    CheckIRAC -->|No| SkipIRAC[Skip]
    
    Conditional --> CheckTOUL{AGENTS_ENABLE_TOULMIN?}
    CheckTOUL -->|Yes| TOUL[Toulmin Analyzer]
    CheckTOUL -->|No| SkipTOUL[Skip]
    
    Conditional --> CheckPA{PRECEDENT_ANALYZER_AVAILABLE?}
    CheckPA -->|Yes| PA[Precedent Analyzer]
    CheckPA -->|No| SkipPA[Skip]
    
    DP --> AgentsDict[agents Dict]
    EE --> AgentsDict
    LR --> AgentsDict
    IRAC --> AgentsDict
    TOUL --> AgentsDict
    PA --> AgentsDict
    
    AgentsDict --> Ready[System Ready]
```

## Missing Agent Implementations

The following agents are referenced in routes but NOT created in `_create_core_agents()`:

- **SEMANTIC_ANALYZER**: Implemented as method `analyze_semantic()` in OperationsMixin, checks for agent instance but has degradation notice fallback
- **CONTRADICTION_DETECTOR**: Implemented as method `analyze_contradictions()` in OperationsMixin, uses heuristic fallback
- **VIOLATION_REVIEW**: Implemented as method `analyze_violations()` in OperationsMixin, uses heuristic fallback
- **CLASSIFIER**: Implemented as method `classify_text()` in OperationsMixin, uses transformers with keyword fallback
- **EMBEDDER**: Implemented as method `embed_texts()` in OperationsMixin, uses sentence-transformers with hash fallback
- **ORCHESTRATOR**: Implemented as method `orchestrate()` in OperationsMixin, uses DAG orchestrator if available

**Note:** These are implemented as **manager methods** rather than separate agent instances, which is a valid pattern but inconsistent with the agent registry approach.
