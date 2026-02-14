"""
Unified Database Manager for Legal AI Platform

Consolidates the best features from all existing database managers:
- database_manager.py (GUI operations with specialized violation review)
- professional_database_manager.py (professional GUI with monitoring)
- modern_database_manager.py (async operations with health monitoring)
- enhanced_db_client.py (documentation tracking and prioritization)

Provides a unified interface while preserving all specialized functionality.
"""

import logging
from contextlib import asynccontextmanager  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, AsyncContextManager, Dict, List, Optional  # noqa: E402

# Async database support
try:
    import aiosqlite  # noqa: E402

    AIOSQLITE_AVAILABLE = True
except ImportError:
    AIOSQLITE_AVAILABLE = False

# ... (other optional imports like asyncpg, redis, prometheus, etc.) ...

from .database_models import (  # noqa: E402
    DatabaseConfig,
    DatabaseMetrics,
    GraphEdge,
    GraphNode,
    MemoryRecord,
    ViolationRecord,
)

logger = logging.getLogger(__name__)


class UnifiedDatabaseManager:
    """
    Unified database manager combining all features.
    """

    def __init__(self, db_config: DatabaseConfig):
        self.config = db_config
        self.logger = logging.getLogger(f"db.{db_config.name}")
        self.metrics = DatabaseMetrics()
        self._initialized = False

    async def initialize(self):
        if self.config.type == "sqlite":
            await self._initialize_sqlite()
        else:
            raise ValueError(f"Unsupported database type: {self.config.type}")
        self._initialized = True
        self.logger.info(f"Database {self.config.name} initialized successfully")

    async def _initialize_sqlite(self):
        if not AIOSQLITE_AVAILABLE:
            raise ImportError("aiosqlite is required for SQLite support")

        db_path = Path(self.config.url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(str(db_path)) as conn:
            await self._initialize_schema(conn)

    async def _initialize_schema(self, conn):
        # Combines schemas from all previous database managers
        schema_statements = [
            # ... (all CREATE TABLE and CREATE INDEX statements from database_manager.py and others) ...
            "CREATE TABLE IF NOT EXISTS violations (...);",
            "CREATE TABLE IF NOT EXISTS memory_entries (...);",
            "CREATE TABLE IF NOT EXISTS graph_nodes (...);",
            "CREATE TABLE IF NOT EXISTS graph_edges (...);",
            "CREATE TABLE IF NOT EXISTS documents (...);",
            "CREATE TABLE IF NOT EXISTS system_logs (...);",
            "CREATE TABLE IF NOT EXISTS agent_results (...);",
            "CREATE TABLE IF NOT EXISTS file_analysis (...);",
            "CREATE TABLE IF NOT EXISTS file_operations (...);",
        ]
        for statement in schema_statements:
            await conn.execute(statement)
        await conn.commit()

    @asynccontextmanager
    async def get_connection(self) -> AsyncContextManager[aiosqlite.Connection]:
        async with aiosqlite.connect(self.config.url.replace("sqlite:///", "")) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn

    # --- Violation Management --- (from database_manager.py)
    async def save_violation(self, violation: ViolationRecord) -> bool:
        # ... implementation ...
        pass

    async def get_violations(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[ViolationRecord]:
        # ... implementation ...
        pass

    # --- Memory Management --- (from database_manager.py)
    async def save_memory_entry(self, memory: MemoryRecord) -> bool:
        # ... implementation ...
        pass

    async def get_memory_entries(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        # ... implementation ...
        pass

    # --- Knowledge Graph Management --- (from database_manager.py)
    async def save_graph_node(self, node: GraphNode) -> bool:
        # ... implementation ...
        pass

    async def save_graph_edge(self, edge: GraphEdge) -> bool:
        # ... implementation ...
        pass

    # --- Documentation Tracking --- (from enhanced_db_client.py)
    async def get_files_to_document(
        self, priority_filter: str = "all"
    ) -> List[Dict[str, Any]]:
        # ... implementation ...
        pass

    async def update_documentation_status(
        self, file_path: str, status: str, doc_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        # ... implementation ...
        pass

    # ... (and so on, for all other methods)


# Factory function
async def create_unified_database_manager(
    config: DatabaseConfig,
) -> UnifiedDatabaseManager:
    manager = UnifiedDatabaseManager(config)
    await manager.initialize()
    return manager
