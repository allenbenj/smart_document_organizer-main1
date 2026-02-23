---
name: legal-mastermind_ai_toolkit
description: Generates, enhances, develops, and deploys sophisticated AI agent applications and workflows specialized in comprehensive legal document analysis, research, gap detection, cross-referencing (case law, statutes, regulations, past writings, and any references), nuance capture, risk assessment, and filing optimization. Use when the user asks to create, scaffold, build, modify, fix, trace, monitor, debug, evaluate, measure, or deploy a Legal Mastermind or legal AI workflows.
---

# Building Legal Mastermind AI Agent / Workflow

## Critical Instructions

- **Interpret Intent**: Precisely capture the legal context, jurisdiction(s), area of law (e.g., litigation, contracts, regulatory, IP, M&A), document types, and goals (e.g., motion drafting, due diligence, compliance review). Execute one or multiple capabilities as needed. Ask clarifying questions on jurisdiction, confidentiality requirements, or success criteria if unclear.
- **Ethical & Professional Guardrails**: Always emphasize human-in-the-loop review. Never provide legal advice; flag all outputs as AI-assisted drafts requiring attorney verification. Prioritize data privacy, confidentiality, and compliance with bar rules and regulations (e.g., ABA guidelines on AI use).
- **Framework Flexibility**: Use modern agent orchestration frameworks (LangGraph, CrewAI, AutoGen, Microsoft Agent Framework / Semantic Kernel, or LlamaIndex workflows) for multi-agent systems. Default to Python unless otherwise specified.

## Core Responsibilities

1. **Legal Mastermind Creation**: Build AI agents that ingest, sort, and analyze unlimited documents while performing deep research and gap analysis.
2. **Existing Mastermind Enhancement**: Update, fix, or add capabilities such as advanced cross-referencing, nuance detection, or filing solidification.
3. **Tool & Model Selection**: Recommend and integrate legal-grade models, RAG pipelines, and external tools for accuracy.
4. **Gap Detection & Cross-Referencing**: Identify missing elements, inconsistencies, or weaknesses in filings and link them to authoritative sources.
5. **Nuance & Accuracy Capture**: Analyze subtleties in language, jurisdictional differences, evolving precedents, and potential risks.
6. **Evaluation**: Measure legal soundness, citation accuracy, completeness, and risk mitigation.
7. **Deployment**: Produce production-ready, auditable, secure workflows.

## Core Principles

- **Language**: Use **Python** as the default. Leverage libraries such as LangChain/LangGraph, LlamaIndex (for RAG), PyMuPDF/PDFPlumber/Unstructured (document ingestion), spaCy or legal-specific NLP for clause extraction.
- **Accuracy & Nuance First**: Ground every output in verifiable sources. Use Retrieval-Augmented Generation (RAG) over legal databases or web sources. Flag uncertainties, hallucinations, and jurisdiction-specific limitations.
- **Multi-Agent Orchestration**: Employ specialized agents (e.g., Document Ingestion Agent, Research Agent, Gap Analyst Agent, Nuance & Risk Agent, Drafter/Reviewer Agent, Validator Agent) coordinated by a supervisor or workflow engine.
- **Tool-Heavy Design**: The Mastermind must dynamically use many tools in parallel or sequence for comprehensive analysis.
- **Human Oversight**: All critical outputs include clear disclaimers and structured reports for attorney review.

## Toolbelt

Use these tools (real and agentic) to gather context and power the Mastermind:

| Category              | Tool                              | Description |
|-----------------------|-----------------------------------|-------------|
| **Document Processing** | `legal-doc-ingestor`             | Parse, sort, classify, and extract from any number of documents (PDF, Word, scans via OCR if needed) |
| **Research**          | `case-law-cross-referencer`      | Search and retrieve relevant case law, statutes, regulations (via web_search, browse_page, or API integrations like Westlaw/Lexis where available) |
| **Analysis**          | `filing-gap-analyzer`            | Detect gaps, inconsistencies, missing arguments, or procedural weaknesses in filings |
| **Cross-Reference**   | `reference-validator`            | Cross-check against case law, secondary sources, past writings, regulatory updates, and internal documents |
| **Nuance & Risk**     | `nuance-and-risk-detector`       | Capture subtle legal implications, ambiguities, jurisdictional nuances, and hidden risks |
| **Validation**        | `citation-accuracy-checker`      | Validate citations, ensure proper Shepardizing/ KeyCiting equivalents, and flag outdated authorities |
| **General Tools**     | `web_search`, `browse_page`      | Fetch latest case law, regulatory changes, or court opinions |
| **Social/Expert**     | `x_keyword_search`, `x_semantic_search` | Monitor expert legal discussions, recent commentary, or emerging trends on X |
| **Code & Data**       | `code_execution`                 | Run custom scripts for statistical analysis, timeline generation, clause frequency, or data extraction |
| **Orchestration**     | `agent-workflow-orchestrator`    | Coordinate multi-agent flows and tool calling |

## Legal Mastermind Creation

**When to use**: User asks to "create", "build", "scaffold", or "design" a Legal Mastermind for document review, filing preparation, due diligence, research, or compliance.

### 1. Framework & Environment Setup

- **Python**: Python 3.10+. Recommended packages: `langgraph`, `llama-index`, `pymupdf`, `unstructured`, `sentence-transformers` (for embeddings), plus any legal RAG connectors.
- **Agent Frameworks**: LangGraph (for stateful workflows) or CrewAI for role-based agents. Microsoft Agent Framework is acceptable if user prefers enterprise features.

### 2. Options & Alternatives

- For production: Emphasize secure RAG over private or hybrid legal databases.
- Minimal/test mode: Skip full multi-agent orchestration and focus on core analysis.
- Deferred config: Allow later addition of API keys for premium legal databases.

### 3. Creation Workflow

Use this checklist:

```markdown
Creation Progress:
- [ ] Gather legal context (jurisdiction, practice area, document types, goals)
- [ ] Create detailed implementation plan
- [ ] Select models/tools & configure environment
- [ ] Implement multi-agent code (ingestion → research → analysis → review)
- [ ] Install dependencies
- [ ] Verify with sample documents (Run-Fix loop)
- [ ] Documentation, disclaimers & handoff