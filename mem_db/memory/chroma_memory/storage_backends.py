"""
Storage Backends for Unified Memory Manager
===========================================

Contains all storage backend implementations and compatibility wrappers.
"""

import asyncio
import json
import sqlite3
import threading
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .unified_memory_manager_canonical import UnifiedMemoryManager


class SQLiteBackend:
    """SQLite implementation of MemoryBackend."""

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    async def store(
        self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a value in SQLite."""
        with self._lock:
            serialized_value = (
                json.dumps(value) if not isinstance(value, str) else value
            )
            serialized_metadata = json.dumps(metadata or {})

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO memory_store (key, value, metadata, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (key, serialized_value, serialized_metadata),
                )
                conn.commit()
        return key

    async def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve a value from SQLite."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT value, metadata FROM memory_store WHERE key = ?", (key,)
                )
                row = cursor.fetchone()

                if row:
                    try:
                        return json.loads(row[0])
                    except json.JSONDecodeError:
                        return row[0]
        return None

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for values in SQLite."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT key, value, metadata FROM memory_store
                    WHERE value LIKE ? OR metadata LIKE ?
                    LIMIT ?
                """,
                    (f"%{query}%", f"%{query}%", limit),
                )

                results = []
                for row in cursor.fetchall():
                    try:
                        value = json.loads(row[1])
                    except json.JSONDecodeError:
                        value = row[1]

                    try:
                        metadata = json.loads(row[2] or "{}")
                    except json.JSONDecodeError:
                        metadata = {}

                    results.append(
                        {"key": row[0], "value": value, "metadata": metadata}
                    )

                return results

    async def delete(self, key: str) -> bool:
        """Delete a value from SQLite."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM memory_store WHERE key = ?", (key,))
                conn.commit()
                return cursor.rowcount > 0

    async def health_check(self) -> Dict[str, Any]:
        """Check SQLite backend health."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM memory_store")
                count = cursor.fetchone()[0]

            return {
                "healthy": True,
                "backend": "sqlite",
                "record_count": count,
                "db_path": str(self.db_path),
            }
        except Exception as e:
            return {"healthy": False, "backend": "sqlite", "error": str(e)}


class InMemoryBackend:
    """In-memory implementation of MemoryBackend."""

    def __init__(self):
        self._storage: Dict[str, Tuple[Any, Dict[str, Any]]] = {}
        self._lock = threading.RLock()

    async def store(
        self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a value in memory."""
        with self._lock:
            self._storage[key] = (value, metadata or {})
        return key

    async def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve a value from memory."""
        with self._lock:
            if key in self._storage:
                return self._storage[key][0]
        return None

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for values in memory."""
        results = []
        query_lower = query.lower()

        with self._lock:
            for key, (value, metadata) in self._storage.items():
                value_str = str(value).lower()
                metadata_str = str(metadata).lower()

                if query_lower in value_str or query_lower in metadata_str:
                    results.append({"key": key, "value": value, "metadata": metadata})

                if len(results) >= limit:
                    break

        return results

    async def delete(self, key: str) -> bool:
        """Delete a value from memory."""
        with self._lock:
            if key in self._storage:
                del self._storage[key]
                return True
        return False

    async def health_check(self) -> Dict[str, Any]:
        """Check in-memory backend health."""
        with self._lock:
            return {
                "healthy": True,
                "backend": "memory",
                "record_count": len(self._storage),
            }


class LegacyMemoryAdapter:
    """Adapter for legacy memory interfaces."""

    def __init__(self, unified_manager: "UnifiedMemoryManager"):
        self._manager = unified_manager
        self._deprecation_warnings: Set[str] = set()

    def _warn_deprecated(self, method_name: str, replacement: str):
        """Emit deprecation warning once per method."""
        if method_name not in self._deprecation_warnings:
            warnings.warn(
                f"{method_name} is deprecated. Use {replacement} instead.",
                DeprecationWarning,
                stacklevel=3,
            )
            self._deprecation_warnings.add(method_name)

    # Agent Memory compatibility
    def log_decision(
        self,
        agent_name: str,
        input_summary: str,
        decision: str,
        context: Dict[str, Any],
        tag: str = "decision",
    ):
        """Legacy decision logging compatibility."""
        self._warn_deprecated("log_decision", "unified_manager.log_decision")
        asyncio.create_task(
            self._manager.log_decision(
                agent_name, input_summary, decision, context, tag
            )
        )

    def log_misconduct(
        self, actor_name: str, violation_type: str, case_id: str, reference_id: str
    ):
        """Legacy misconduct logging compatibility."""
        self._warn_deprecated("log_misconduct", "unified_manager.log_misconduct")
        asyncio.create_task(
            self._manager.log_misconduct(
                actor_name, violation_type, case_id, reference_id
            )
        )

    def decisions(self) -> List[Dict[str, Any]]:
        """Legacy decisions retrieval compatibility."""
        self._warn_deprecated("decisions", "unified_manager.get_decisions")
        return asyncio.run(self._manager.get_decisions())

    def misconduct_patterns(
        self, actor_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Legacy misconduct patterns retrieval compatibility."""
        self._warn_deprecated(
            "misconduct_patterns", "unified_manager.get_misconduct_patterns"
        )
        return asyncio.run(self._manager.get_misconduct_patterns(actor_name))

    # Claude Memory Store compatibility
    def store_entity(
        self, name: str, entity_type: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Legacy entity storage compatibility."""
        self._warn_deprecated("store_entity", "unified_manager.store_claude_entity")
        return self._manager.store_claude_entity(name, entity_type, metadata)

    def add_observation(
        self,
        entity_name: str,
        content: str,
        importance_score: float = 0.5,
        source: str = "claude",
    ) -> bool:
        """Legacy observation addition compatibility."""
        self._warn_deprecated(
            "add_observation", "unified_manager.add_claude_observation"
        )
        return self._manager.add_claude_observation(entity_name, content)

    # Shared Memory compatibility
    def store(self, namespace: str, key: str, content: str, **kwargs) -> str:
        """Legacy shared memory storage compatibility."""
        self._warn_deprecated("store", "unified_manager.store_with_semantic_search")
        return asyncio.run(
            self._manager.store_with_semantic_search(namespace, key, content, **kwargs)
        )

    def search_similar(self, query_text: str, **kwargs) -> List[Any]:
        """Legacy semantic search compatibility."""
        self._warn_deprecated(
            "search_similar", "unified_manager.search_similar_content"
        )
        return asyncio.run(self._manager.search_similar_content(query_text, **kwargs))