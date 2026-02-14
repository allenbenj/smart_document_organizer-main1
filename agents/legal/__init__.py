"""
Legal Analysis Agents Module for Legal AI Platform
==================================================

Contains specialized legal analysis agents for legal reasoning and precedent analysis.

Key Features:
- IRAC legal reasoning framework implementation
- Comprehensive precedent analysis and citation extraction
- Legal authority assessment and ranking
- Integration with shared memory for collective intelligence
- Production-grade error handling and performance optimization

All legal analysis agents integrate with the shared memory system to enable
collective intelligence across legal analysis tasks.
"""

from .irac_analyzer import IracAnalyzerAgent, create_irac_analyzer
from .precedent_analyzer import (  # noqa: E402
    LegalPrecedentAnalyzer,
    PrecedentAnalysisConfig,
    create_legal_precedent_analyzer,
)

__all__ = [
    "IracAnalyzerAgent",
    "create_irac_analyzer",
    "LegalPrecedentAnalyzer",
    "PrecedentAnalysisConfig",
    "create_legal_precedent_analyzer",
]
