"""
Agent Memory Interface
Simple interface for agents to interact with the shared ChromaDB memory system.
"""

from datetime import datetime
from typing import Any, Dict, List  # noqa: E402

try:
    from ..core.chroma_memory_manager import (  # noqa: E402
        MemoryDocument,
        MemoryQuery,
        get_chroma_memory_manager,
    )

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


class AgentMemoryInterface:
    """Simplified interface for agents to use shared memory."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.memory_manager = get_chroma_memory_manager() if CHROMA_AVAILABLE else None

        if not self.memory_manager:
            print(f"Warning: ChromaDB not available for agent {agent_id}")

    def remember(
        self,
        content: str,
        memory_type: str = "general",
        legal_framework: str = "general",
        confidence: float = 0.8,
        additional_metadata: Dict = None,
    ) -> bool:
        """
        Store a memory in the shared knowledge base.

        Args:
            content: The content to remember
            memory_type: Type of memory (analysis, insight, pattern, etc.)
            legal_framework: Legal framework used (IRAC, Toulmin, MECE, etc.)
            confidence: Confidence in the content (0.0 to 1.0)
            additional_metadata: Any additional metadata

        Returns:
            bool: True if successfully stored
        """
        if not self.memory_manager:
            return False

        metadata = {
            "type": memory_type,
            "legal_framework": legal_framework,
            "confidence": confidence,
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat(),
            **(additional_metadata or {}),
        }

        doc_id = f"{self.agent_id}_{memory_type}_{int(datetime.now().timestamp())}"
        memory_doc = MemoryDocument(
            id=doc_id, content=content, metadata=metadata, agent_source=self.agent_id
        )

        return self.memory_manager.add_memory(memory_doc, self.agent_id)

    def recall(
        self,
        query: str,
        num_results: int = 5,
        memory_type: str = None,
        legal_framework: str = None,
        min_confidence: float = 0.5,
        min_similarity: float = 0.7,
    ) -> List[Dict]:
        """
        Query the shared memory for relevant content.

        Args:
            query: What to search for
            num_results: Maximum number of results
            memory_type: Filter by memory type
            legal_framework: Filter by legal framework
            min_confidence: Minimum confidence threshold
            min_similarity: Minimum similarity threshold

        Returns:
            List of relevant memories with content and metadata
        """
        if not self.memory_manager:
            return []

        # Build metadata filter
        metadata_filter = {}
        if memory_type:
            metadata_filter["type"] = memory_type
        if legal_framework:
            metadata_filter["legal_framework"] = legal_framework
        if min_confidence > 0:
            metadata_filter["confidence"] = {"$gte": min_confidence}

        memory_query = MemoryQuery(
            query_text=query,
            agent_id=self.agent_id,
            num_results=num_results,
            metadata_filter=metadata_filter if metadata_filter else None,
            similarity_threshold=min_similarity,
        )

        return self.memory_manager.query_memory(memory_query)

    def remember_legal_analysis(
        self,
        issue: str,
        rule: str,
        application: str,
        conclusion: str,
        confidence: float = 0.8,
        case_type: str = None,
    ) -> bool:
        """
        Store an IRAC legal analysis in memory.

        Args:
            issue: The legal issue identified
            rule: The applicable legal rule
            application: How the rule applies to the facts
            conclusion: The resulting conclusion
            confidence: Confidence in the analysis
            case_type: Type of case (contract, tort, etc.)

        Returns:
            bool: True if successfully stored
        """
        irac_content = """
LEGAL ANALYSIS - IRAC Framework

ISSUE: {issue}

RULE: {rule}

APPLICATION: {application}

CONCLUSION: {conclusion}
        """.strip()

        metadata = {
            "case_type": case_type,
            "irac_components": {
                "issue": issue,
                "rule": rule,
                "application": application,
                "conclusion": conclusion,
            },
        }

        return self.remember(
            content=irac_content,
            memory_type="legal_analysis",
            legal_framework="IRAC",
            confidence=confidence,
            additional_metadata=metadata,
        )

    def remember_contract_insight(
        self,
        contract_type: str,
        clause_type: str,
        insight: str,
        precedent: str = None,
        confidence: float = 0.8,
    ) -> bool:
        """
        Store a contract-related insight.

        Args:
            contract_type: Type of contract (employment, commercial, etc.)
            clause_type: Type of clause (payment, termination, etc.)
            insight: The insight or pattern discovered
            precedent: Related legal precedent if any
            confidence: Confidence in the insight

        Returns:
            bool: True if successfully stored
        """
        content = """
CONTRACT INSIGHT

Contract Type: {contract_type}
Clause Type: {clause_type}

Insight: {insight}
"""

        if precedent:
            content += f"\nRelated Precedent: {precedent}"

        metadata = {
            "contract_type": contract_type,
            "clause_type": clause_type,
            "precedent": precedent,
        }

        return self.remember(
            content=content,
            memory_type="contract_insight",
            legal_framework="Contract_Analysis",
            confidence=confidence,
            additional_metadata=metadata,
        )

    def find_similar_cases(
        self, case_description: str, num_results: int = 3
    ) -> List[Dict]:
        """
        Find similar legal cases in memory.

        Args:
            case_description: Description of the current case
            num_results: Number of similar cases to find

        Returns:
            List of similar cases with analysis
        """
        return self.recall(
            query=case_description,
            num_results=num_results,
            memory_type="legal_analysis",
            min_similarity=0.75,
        )

    def find_contract_patterns(
        self, contract_context: str, num_results: int = 5
    ) -> List[Dict]:
        """
        Find relevant contract patterns and insights.

        Args:
            contract_context: Context or description of contract issue
            num_results: Number of patterns to find

        Returns:
            List of relevant contract insights
        """
        return self.recall(
            query=contract_context,
            num_results=num_results,
            memory_type="contract_insight",
            min_similarity=0.7,
        )

    def learn_from_framework(self, framework: str, context: str = None) -> List[Dict]:
        """
        Learn from previous uses of a specific legal framework.

        Args:
            framework: Legal framework (IRAC, Toulmin, MECE, etc.)
            context: Optional context to narrow the search

        Returns:
            List of relevant framework applications
        """
        query = f"{framework} framework"
        if context:
            query += f" {context}"

        return self.recall(
            query=query, legal_framework=framework, num_results=5, min_similarity=0.6
        )

    def get_my_contributions(self, limit: int = 20) -> List[Dict]:
        """
        Get all memories contributed by this agent.

        Args:
            limit: Maximum number of memories to return

        Returns:
            List of this agent's contributions
        """
        if not self.memory_manager:
            return []

        return self.memory_manager.get_agent_memories(self.agent_id, limit)

    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the shared memory system.

        Returns:
            Dictionary with memory system statistics
        """
        if not self.memory_manager:
            return {"error": "Memory system not available"}

        return self.memory_manager.get_memory_statistics()

    def remember_successful_strategy(
        self, problem_type: str, strategy: str, outcome: str, confidence: float = 0.9
    ) -> bool:
        """
        Remember a successful problem-solving strategy.

        Args:
            problem_type: Type of problem solved
            strategy: The strategy that worked
            outcome: The successful outcome
            confidence: Confidence in the strategy

        Returns:
            bool: True if successfully stored
        """
        content = """
SUCCESSFUL STRATEGY

Problem Type: {problem_type}

Strategy: {strategy}

Outcome: {outcome}

Agent: {self.agent_id}
Success Date: {datetime.now().strftime('%Y-%m-%d')}
        """.strip()

        metadata = {
            "problem_type": problem_type,
            "outcome_type": "success",
            "strategy_confidence": confidence,
        }

        return self.remember(
            content=content,
            memory_type="strategy",
            legal_framework="Problem_Solving",
            confidence=confidence,
            additional_metadata=metadata,
        )

    def find_successful_strategies(self, problem_type: str) -> List[Dict]:
        """
        Find successful strategies for a similar problem type.

        Args:
            problem_type: Type of problem to find strategies for

        Returns:
            List of successful strategies
        """
        return self.recall(
            query=f"{problem_type} successful strategy",
            memory_type="strategy",
            min_confidence=0.7,
            min_similarity=0.7,
        )


# Convenience functions for agents
def create_agent_memory(agent_id: str) -> AgentMemoryInterface:
    """Create an agent memory interface for the specified agent."""
    return AgentMemoryInterface(agent_id)


def quick_remember(agent_id: str, content: str, memory_type: str = "general") -> bool:
    """Quick function to store content in shared memory."""
    interface = AgentMemoryInterface(agent_id)
    return interface.remember(content, memory_type)


def quick_recall(agent_id: str, query: str, num_results: int = 3) -> List[Dict]:
    """Quick function to query shared memory."""
    interface = AgentMemoryInterface(agent_id)
    return interface.recall(query, num_results)


if __name__ == "__main__":
    # Example usage
    agent = AgentMemoryInterface("example_agent")

    print("🧠 Testing Agent Memory Interface...")

    # Test remembering an IRAC analysis
    success = agent.remember_legal_analysis(
        issue="Whether the contract clause is enforceable",
        rule="Contract clauses must be clear and unambiguous",
        application="The clause in question uses vague language that could be interpreted multiple ways",
        conclusion="The clause is likely unenforceable due to ambiguity",
        confidence=0.85,
        case_type="contract_dispute",
    )
    print(f"IRAC Analysis Stored: {success}")

    # Test remembering a contract insight
    success = agent.remember_contract_insight(
        contract_type="employment",
        clause_type="termination",
        insight="Termination clauses with 30-day notice are standard in this jurisdiction",
        confidence=0.9,
    )
    print(f"Contract Insight Stored: {success}")

    # Test recalling similar content
    results = agent.recall("contract termination clause notice period", num_results=2)
    print(f"Recall Results: {len(results)} memories found")

    # Test finding similar cases
    similar_cases = agent.find_similar_cases("contract clause enforceability ambiguity")
    print(f"Similar Cases: {len(similar_cases)} found")

    # Get memory statistics
    stats = agent.get_memory_stats()
    print(f"Memory Stats: {stats.get('total_documents', 'N/A')} total documents")

    print("✅ Agent Memory Interface testing completed!")
