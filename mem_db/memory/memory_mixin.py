"""Memory mixin shim.

Use `MemoryMixin` for the generic storage behavior.
Use `LegalMemoryMixin` from `agents.base.agent_mixins` for legal-domain helpers.
"""

import inspect
import json
import logging  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

from .memory_interfaces import MemoryRecord, MemoryType, SearchResult  # noqa: E402
from .unified_memory_manager import UnifiedMemoryManager  # noqa: E402

logger = logging.getLogger(__name__)


class MemoryMixin:
    """
    Mixin class to provide memory capabilities to agents.

    This mixin enables agents to:
    - Store their findings in shared memory
    - Search for relevant knowledge from other agents
    - Access case law and precedent knowledge
    - Contribute to the collective intelligence of the platform
    """

    def __init__(self, *args, **kwargs):
        """Initialize the MemoryMixin."""
        super().__init__(*args, **kwargs)

        self._memory_manager: Optional[UnifiedMemoryManager] = None
        self._agent_id: str = getattr(self, "agent_name", self.__class__.__name__)
        self._session_id: Optional[str] = None

        # Try to get memory manager from service container (sync/async-safe)
        if hasattr(self, "services") and self.services:
            try:
                get_service_fn = getattr(self.services, "get_service", None)
                if callable(get_service_fn) and inspect.iscoroutinefunction(get_service_fn):
                    # Async service container: resolve lazily in async methods.
                    self._memory_manager = None
                else:
                    maybe_mgr = self.services.get_service(UnifiedMemoryManager)
                    if maybe_mgr is None:
                        maybe_mgr = self.services.get_service("memory_manager")
                    self._memory_manager = maybe_mgr if not inspect.isawaitable(maybe_mgr) else None
                    if self._memory_manager:
                        logger.info(
                            f"Agent {self._agent_id} connected to shared memory system"
                        )
            except Exception as e:
                logger.error(f"Failed to connect to memory manager: {e}")

    async def _ensure_memory_manager(self) -> bool:
        """Resolve memory manager lazily, supporting async service containers."""
        if self._memory_manager:
            return True
        if not (hasattr(self, "services") and self.services):
            return False
        try:
            maybe_mgr = self.services.get_service(UnifiedMemoryManager)
            if maybe_mgr is None:
                maybe_mgr = self.services.get_service("memory_manager")
            self._memory_manager = await maybe_mgr if inspect.isawaitable(maybe_mgr) else maybe_mgr
            if self._memory_manager:
                logger.info(f"Agent {self._agent_id} connected to shared memory system")
                return True
        except Exception as e:
            logger.warning(f"Memory manager not available for agent {self._agent_id}: {e}")
        return False

    def set_session_id(self, session_id: str) -> None:
        """Set the current session ID for this agent."""
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("Session ID must be a non-empty string")
        self._session_id = session_id
        logger.debug(f"Session ID set to {session_id} for agent {self._agent_id}")

    async def store_memory(
        self,
        namespace: str,
        key: str,
        content: str,
        memory_type: MemoryType = MemoryType.AGENT,
        metadata: Optional[Dict[str, Any]] = None,
        importance_score: float = 1.0,
        confidence_score: float = 1.0,
        document_id: Optional[str] = None,
    ) -> str:
        """
        Store content in shared memory.

        Args:
            namespace: Logical grouping (e.g., 'legal_analysis', 'entities', 'case_law')
            key: Unique key within namespace
            content: Text content to store
            memory_type: Type of memory record
            metadata: Additional metadata
            importance_score: Importance for ranking (0.0-1.0)
            confidence_score: Confidence in the information (0.0-1.0)
            document_id: Associated document ID if applicable

        Returns:
            str: Unique record ID
        """
        if not await self._ensure_memory_manager():
            logger.warning(f"Memory manager not available for agent {self._agent_id}")
            return ""

        if not namespace or not key or not content:
            raise ValueError("Namespace, key, and content must be provided")

        try:
            # Enhance metadata with agent context
            enhanced_metadata = metadata or {}
            enhanced_metadata.update(
                {
                    "stored_by": self._agent_id,
                    "stored_at": datetime.now().isoformat(),
                    "session_id": self._session_id,
                }
            )

            record = MemoryRecord(
                record_id="",  # Will be generated
                namespace=namespace,
                key=key,
                content=content,
                memory_type=memory_type,
                agent_id=self._agent_id,
                document_id=document_id,
                metadata=enhanced_metadata,
                importance_score=importance_score,
                confidence_score=confidence_score,
            )

            record_id = await self._memory_manager.store(record)
            logger.debug(f"Agent {self._agent_id} stored memory record {record_id}")
            return record_id

        except Exception as e:
            logger.error(f"Failed to store memory for agent {self._agent_id}: {e}")
            return ""

    async def search_memory(
        self,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        namespaces: Optional[List[str]] = None,
        include_own_memories: bool = True,
        limit: int = 10,
        min_similarity: float = 0.6,
    ) -> List[SearchResult]:
        """
        Search for relevant content in shared memory.

        Args:
            query: Search query text
            memory_types: Filter by memory types
            namespaces: Filter by namespaces
            include_own_memories: Whether to include this agent's own memories
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold

        Returns:
            List of search results
        """
        if not await self._ensure_memory_manager():
            logger.warning(f"Memory manager not available for agent {self._agent_id}")
            return []

        try:
            results = []

            # Search across specified memory types or all types
            search_types = memory_types or list(MemoryType)

            for memory_type in search_types:
                # Search across specified namespaces or all namespaces
                search_namespaces = namespaces or [None]

                for namespace in search_namespaces:
                    type_results = await self._memory_manager.search(
                        query=query,
                        memory_type=memory_type,
                        namespace=namespace,
                        agent_id=(
                            None if include_own_memories else f"NOT_{self._agent_id}"
                        ),
                        limit=limit,
                        min_similarity=min_similarity,
                    )
                    results.extend(type_results)

            # Sort by combined score and remove duplicates
            unique_results = {}
            for result in results:
                record_id = result.record.record_id
                if (
                    record_id not in unique_results
                    or result.combined_score > unique_results[record_id].combined_score
                ):
                    unique_results[record_id] = result

            final_results = list(unique_results.values())
            final_results.sort(key=lambda x: x.combined_score, reverse=True)

            logger.debug(
                f"Agent {self._agent_id} found {len(final_results)} memory results for query: {query}"
            )
            return final_results[:limit]

        except Exception as e:
            logger.error(f"Failed to search memory for agent {self._agent_id}: {e}")
            return []

    async def get_shared_knowledge(self, limit: int = 20) -> List[MemoryRecord]:
        """
        Get knowledge shared with this agent from other agents.

        This is a key feature that enables collective intelligence:
        agents can learn from discoveries made by other agents.

        Args:
            limit: Maximum number of shared knowledge records

        Returns:
            List of memory records shared by other agents
        """
        if not await self._ensure_memory_manager():
            logger.warning(f"Memory manager not available for agent {self._agent_id}")
            return []

        try:
            shared_records = await self._memory_manager.get_shared_knowledge(
                agent_id=self._agent_id, limit=limit
            )

            logger.debug(
                f"Agent {self._agent_id} retrieved {len(shared_records)} shared knowledge records"
            )
            return shared_records

        except Exception as e:
            logger.error(
                f"Failed to get shared knowledge for agent {self._agent_id}: {e}"
            )
            return []

    async def store_document_analysis(
        self,
        document_id: str,
        analysis_type: str,
        analysis_result: Dict[str, Any],
        summary: Optional[str] = None,
        entities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Store document analysis results in memory.

        Args:
            document_id: Unique document identifier
            analysis_type: Type of analysis (e.g., 'entity_extraction', 'legal_analysis')
            analysis_result: The analysis result data
            summary: Optional summary of the analysis
            entities: Extracted entities from the document
            metadata: Additional metadata

        Returns:
            List of record IDs stored
        """
        record_ids = []

        # Store main analysis result
        analysis_content = summary or json.dumps(analysis_result, default=str)
        analysis_metadata = metadata or {}
        analysis_metadata.update(
            {
                "analysis_type": analysis_type,
                "document_id": document_id,
                "full_result": analysis_result,
            }
        )

        analysis_record_id = await self.store_memory(
            namespace="document_analysis",
            key=f"{document_id}_{analysis_type}",
            content=analysis_content,
            memory_type=MemoryType.ANALYSIS,
            metadata=analysis_metadata,
            importance_score=0.8,
            document_id=document_id,
        )

        if analysis_record_id:
            record_ids.append(analysis_record_id)

        # Store extracted entities if provided
        if entities:
            for i, entity in enumerate(entities):
                entity_record_id = await self.store_memory(
                    namespace="extracted_entities",
                    key=f"{document_id}_entity_{i}",
                    content=entity,
                    memory_type=MemoryType.ENTITY,
                    metadata={
                        "document_id": document_id,
                        "entity_index": i,
                        "extraction_method": analysis_type,
                    },
                    importance_score=0.6,
                    document_id=document_id,
                )

                if entity_record_id:
                    record_ids.append(entity_record_id)

        logger.info(
            f"Agent {self._agent_id} stored {len(record_ids)} records for document {document_id}"
        )
        return record_ids

    async def store_case_law_analysis(
        self,
        case_citation: str,
        case_summary: str,
        legal_principles: List[str],
        precedent_value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store case law analysis in memory.

        This is critical for building the legal knowledge base that
        makes the platform collectively smarter about legal precedents.

        Args:
            case_citation: Legal citation for the case
            case_summary: Summary of the case
            legal_principles: List of legal principles from the case
            precedent_value: Importance of this case as precedent (0.0-1.0)
            metadata: Additional case metadata

        Returns:
            Record ID of the stored case analysis
        """
        case_metadata = metadata or {}
        case_metadata.update(
            {
                "case_citation": case_citation,
                "legal_principles": legal_principles,
                "precedent_value": precedent_value,
                "case_type": "precedent_analysis",
            }
        )

        record_id = await self.store_memory(
            namespace="case_law",
            key=case_citation,
            content=case_summary,
            memory_type=MemoryType.CASE_LAW,
            metadata=case_metadata,
            importance_score=precedent_value,
            confidence_score=0.9,
        )

        logger.info(
            f"Agent {self._agent_id} stored case law analysis for {case_citation}"
        )
        return record_id

    async def find_similar_cases(
        self, legal_issue: str, jurisdiction: Optional[str] = None, limit: int = 5
    ) -> List[SearchResult]:
        """
        Find similar cases based on legal issues.

        Args:
            legal_issue: Description of the legal issue
            jurisdiction: Optional jurisdiction filter
            limit: Maximum number of cases to return

        Returns:
            List of similar case law records
        """
        search_query = legal_issue
        if jurisdiction:
            search_query += f" jurisdiction:{jurisdiction}"

        results = await self.search_memory(
            query=search_query,
            memory_types=[MemoryType.CASE_LAW],
            namespaces=["case_law"],
            limit=limit,
            min_similarity=0.5,
        )

        logger.debug(
            f"Agent {self._agent_id} found {len(results)} similar cases for issue: {legal_issue}"
        )
        return results

    async def get_memory_statistics(self) -> Dict[str, Any]:
        """
        Get memory usage statistics for this agent.

        Returns:
            Dictionary containing memory statistics
        """
        if not self._memory_manager:
            return {"status": "memory_not_available"}

        try:
            # Get global statistics
            global_stats = await self._memory_manager.get_statistics()

            # Get agent-specific statistics
            agent_records_count = global_stats.get("top_agents", {}).get(
                self._agent_id, 0
            )

            return {
                "agent_id": self._agent_id,
                "agent_records": agent_records_count,
                "global_statistics": global_stats,
                "memory_manager_available": True,
            }

        except Exception as e:
            logger.error(
                f"Failed to get memory statistics for agent {self._agent_id}: {e}"
            )
            return {"status": "error", "message": str(e)}

    def _is_memory_available(self) -> bool:
        """Check if memory manager is available."""
        return self._memory_manager is not None

    async def link_memory_to_file(
        self,
        memory_record_id: str,
        file_path: str,
        relation_type: str = "references",
        confidence: float = 1.0,
        source: str = "system",
    ) -> bool:
        """Link a memory record to a file path."""
        if not await self._ensure_memory_manager():
            logger.warning(f"Memory manager not available for agent {self._agent_id}")
            return False
        
        if not memory_record_id or not file_path:
            logger.warning("Cannot link memory to file with empty identifiers")
            return False
        
        return await self._memory_manager.link_memory_to_file(
            memory_record_id=memory_record_id,
            file_path=file_path,
            relation_type=relation_type,
            confidence=confidence,
            source=source,
        )
    
    async def get_linked_memories_for_file(
        self, file_path: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve memory records linked to a file path."""
        if not await self._ensure_memory_manager():
            logger.warning(f"Memory manager not available for agent {self._agent_id}")
            return []
        if not file_path:
            return []
        return await self._memory_manager.get_memories_for_file(file_path, limit)

    async def get_linked_files_for_memory(
        self, memory_record_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve file paths linked to a memory record."""
        if not await self._ensure_memory_manager():
            logger.warning(f"Memory manager not available for agent {self._agent_id}")
            return []
        if not memory_record_id:
            return []
        return await self._memory_manager.get_files_for_memory(memory_record_id, limit)
