"""
Legal Analysis Agents Module for Legal AI Platform
==================================================

Contains advanced legal analysis agents for semantic understanding and document analysis.

Key Features:
- Comprehensive semantic analysis and document summarization
- Legal topic identification and classification
- Content structure analysis and legal concept extraction
- Integration with shared memory for collective intelligence
- Production-grade error handling and performance optimization

All analysis agents integrate with the ChromaDB shared memory system to enable
collective intelligence across legal analysis tasks.
"""

from .semantic_analyzer import (
    LegalSemanticAnalyzer,
    SemanticAnalysisConfig,
    create_legal_semantic_analyzer,
)

__all__ = [
    "LegalSemanticAnalyzer",
    "SemanticAnalysisConfig",
    "create_legal_semantic_analyzer",
]
