"""
Database connection and operations for the Smart Document Organizer.

This module provides database connectivity, schema management, and CRUD operations
following the architecture specifications for the document management system.
"""

import logging  # noqa: E402
import os
import sqlite3  # noqa: E402
import threading
from contextlib import contextmanager  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional, Tuple  # noqa: E402

from utils.models import (  # noqa: E402
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    SearchQuery,
    TagCreate,
    TagResponse,
)
from mem_db.db.interfaces.logging import (  # noqa: E402
    LogCategory,
    LogLevel,
    StructuredLogger,
    StandardStructuredLogger,
    generate_correlation_id,
)
from mem_db.repositories.document_repository import DocumentRepository
from mem_db.repositories.file_index_repository import FileIndexRepository
from mem_db.repositories.knowledge_repository import KnowledgeRepository
from mem_db.repositories.organization_repository import OrganizationRepository
from mem_db.repositories.persona_repository import PersonaRepository
from mem_db.repositories.taskmaster_repository import TaskMasterRepository
from mem_db.repositories.watch_repository import WatchRepository
from mem_db.repositories.analysis_version_repository import AnalysisVersionRepository
from mem_db.repositories.learning_path_repository import LearningPathRepository

# Setup logging
logger = logging.getLogger(__name__)

# Module-level singleton instance for application-wide use
_default_db_manager = None  # type: ignore[var-annotated]


def get_database_manager(db_path: Optional[str] = None) -> "DatabaseManager":
    """Return a process-wide DatabaseManager singleton.

    If ``db_path`` is provided, initializes (or re-initializes) the singleton
    with the given path. This helps ensure a consistent integration point for
    routes and background workers.
    """
    global _default_db_manager
    if _default_db_manager is None or db_path is not None:
        _default_db_manager = DatabaseManager(db_path)
    return _default_db_manager


class DatabaseManager:
    """
    Manages database connections and operations for the Smart Document Organizer.

    Provides methods for document management, tagging, search operations,
    and database schema management following the architecture specifications.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        structured_logger: Optional[StructuredLogger] = None,
    ):
        """Initialize database manager with optional custom database path."""
        if db_path:
            self.db_path = Path(db_path)
        else:
            # Default path following the existing structure
            self.db_path = (
                Path(__file__).parent.parent / "mem_db" / "data" / "documents.db"
            )

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Structured logger setup
        self.structured_logger = structured_logger or StandardStructuredLogger(
            logging.getLogger(__name__)
        )

        # SQLite concurrency settings
        self._busy_timeout_ms = 5000
        self._conn_local = threading.local()
        self._ensure_wal_mode()

        # Initialize database schema
        self._initialize_schema()

        # Domain repositories (phased extraction)
        self.organization_repo = OrganizationRepository(self.get_connection)
        self.taskmaster_repo = TaskMasterRepository(self.get_connection)
        self.knowledge_repo = KnowledgeRepository(self.get_connection)
        self.persona_repo = PersonaRepository(self.get_connection)
        self.file_index_repo = FileIndexRepository(self.get_connection)
        self.watch_repo = WatchRepository(self.get_connection)
        self.document_repo = DocumentRepository(self.get_connection)
        self.analysis_version_repo = AnalysisVersionRepository(self.get_connection)
        self.learning_path_repo = LearningPathRepository(self.get_connection)

        logger.info(f"Database initialized at: {self.db_path}")

    def _log(
        self,
        level: LogLevel,
        message: str,
        category: LogCategory = LogCategory.DATABASE,
        correlation_id: Optional[str] = None,
        **context: Any,
    ) -> str:
        cid = correlation_id or generate_correlation_id()
        if level == LogLevel.TRACE:
            self.structured_logger.trace(message, category=category, correlation_id=cid, **context)
        elif level == LogLevel.DEBUG:
            self.structured_logger.debug(message, category=category, correlation_id=cid, **context)
        elif level == LogLevel.INFO:
            self.structured_logger.info(message, category=category, correlation_id=cid, **context)
        elif level == LogLevel.WARNING:
            self.structured_logger.warning(message, category=category, correlation_id=cid, **context)
        elif level == LogLevel.ERROR:
            self.structured_logger.error(message, category=category, correlation_id=cid, **context)
        else:
            self.structured_logger.critical(message, category=category, correlation_id=cid, **context)
        return cid

    def _configure_connection(self, conn: sqlite3.Connection) -> None:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {int(self._busy_timeout_ms)}")

    def _ensure_wal_mode(self) -> None:
        conn = sqlite3.connect(str(self.db_path), timeout=max(1.0, self._busy_timeout_ms / 1000.0))
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.commit()
        finally:
            conn.close()

    def _get_thread_connection(self) -> sqlite3.Connection:
        conn = getattr(self._conn_local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=max(1.0, self._busy_timeout_ms / 1000.0),
                check_same_thread=True,
            )
            self._configure_connection(conn)
            self._conn_local.conn = conn
        return conn

    @contextmanager
    def get_connection(self):
        """Context manager for thread-local SQLite connections with retry-friendly settings."""
        conn = self._get_thread_connection()
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise

    def close(self) -> None:
        conn = getattr(self._conn_local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            finally:
                self._conn_local.conn = None

    def _initialize_schema(self):
        """Initialize database schema with all required tables."""
        with self.get_connection() as conn:
            # Create documents table (maps to file_analysis in architecture)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    file_path TEXT,
                    primary_purpose TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)

            # Create document_content table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_content (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    content_text TEXT,
                    content_type TEXT DEFAULT 'text/plain',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            """)

            # Create document_analytics table for derived text analytics
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_analytics (
                    document_id INTEGER PRIMARY KEY,
                    char_count INTEGER DEFAULT 0,
                    word_count INTEGER DEFAULT 0,
                    sentence_count INTEGER DEFAULT 0,
                    top_terms TEXT, -- JSON array of {term, count}
                    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            """)

            # Create document_tags table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    tag_name TEXT NOT NULL,
                    tag_value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                    UNIQUE(document_id, tag_name)
                )
            """)

            # Create search_indices table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_indices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    search_terms TEXT NOT NULL,
                    relevance_score REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            """)

            # File index table (canonical file registry for UI selection + prechecks)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    display_name TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    normalized_path TEXT NOT NULL,
                    path_hash TEXT NOT NULL UNIQUE,
                    file_size INTEGER,
                    mtime REAL,
                    mime_type TEXT,
                    mime_source TEXT,
                    sha256 TEXT,
                    ext TEXT,
                    status TEXT NOT NULL DEFAULT 'ready',
                    last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_error TEXT,
                    metadata_json TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_duplicate_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_file_id INTEGER NOT NULL,
                    duplicate_file_id INTEGER NOT NULL,
                    relationship_type TEXT NOT NULL DEFAULT 'exact',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    match_basis TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    UNIQUE(canonical_file_id, duplicate_file_id, relationship_type),
                    FOREIGN KEY (canonical_file_id) REFERENCES files_index(id) ON DELETE CASCADE,
                    FOREIGN KEY (duplicate_file_id) REFERENCES files_index(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS watched_directories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_path TEXT NOT NULL,
                    normalized_path TEXT NOT NULL UNIQUE,
                    recursive INTEGER NOT NULL DEFAULT 1,
                    keywords_json TEXT,
                    allowed_exts_json TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_content_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_type TEXT NOT NULL DEFAULT 'text',
                    title TEXT,
                    content TEXT NOT NULL,
                    token_estimate INTEGER DEFAULT 0,
                    char_count INTEGER DEFAULT 0,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    UNIQUE(file_id, chunk_index),
                    FOREIGN KEY (file_id) REFERENCES files_index(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_extracted_tables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    source_chunk_id INTEGER,
                    table_index INTEGER NOT NULL DEFAULT 0,
                    extraction_status TEXT NOT NULL DEFAULT 'placeholder',
                    extraction_method TEXT,
                    headers_json TEXT,
                    rows_json TEXT,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    UNIQUE(file_id, table_index),
                    FOREIGN KEY (file_id) REFERENCES files_index(id) ON DELETE CASCADE,
                    FOREIGN KEY (source_chunk_id) REFERENCES file_content_chunks(id) ON DELETE SET NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_chunk_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    chunk_id INTEGER NOT NULL,
                    embedding_model TEXT NOT NULL,
                    vector_dim INTEGER NOT NULL,
                    embedding_json TEXT NOT NULL,
                    embedding_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    UNIQUE(chunk_id, embedding_model),
                    FOREIGN KEY (file_id) REFERENCES files_index(id) ON DELETE CASCADE,
                    FOREIGN KEY (chunk_id) REFERENCES file_content_chunks(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    entity_text TEXT NOT NULL,
                    entity_type TEXT,
                    ontology_id TEXT,
                    confidence REAL DEFAULT 0.5,
                    provenance TEXT,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    UNIQUE(file_id, ontology_id, entity_text),
                    FOREIGN KEY (file_id) REFERENCES files_index(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_entity_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file_id INTEGER NOT NULL,
                    target_file_id INTEGER NOT NULL,
                    ontology_id TEXT,
                    link_basis TEXT NOT NULL DEFAULT 'shared_entity',
                    confidence REAL DEFAULT 0.6,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    UNIQUE(source_file_id, target_file_id, ontology_id, link_basis),
                    FOREIGN KEY (source_file_id) REFERENCES files_index(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_file_id) REFERENCES files_index(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS mv_timeline_summary (
                    file_id INTEGER PRIMARY KEY,
                    first_event_ts TEXT,
                    last_event_ts TEXT,
                    event_count INTEGER NOT NULL DEFAULT 0,
                    refreshed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_id) REFERENCES files_index(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS mv_keyword_entity_summary (
                    file_id INTEGER PRIMARY KEY,
                    rule_tag_count INTEGER NOT NULL DEFAULT 0,
                    entity_count INTEGER NOT NULL DEFAULT 0,
                    unresolved_candidate_count INTEGER NOT NULL DEFAULT 0,
                    refreshed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_id) REFERENCES files_index(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS mv_file_health_summary (
                    file_id INTEGER PRIMARY KEY,
                    status TEXT,
                    is_missing INTEGER NOT NULL DEFAULT 0,
                    is_damaged INTEGER NOT NULL DEFAULT 0,
                    is_stale INTEGER NOT NULL DEFAULT 0,
                    refreshed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_id) REFERENCES files_index(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS taskmaster_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT,
                    summary_json TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS taskmaster_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    task_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL DEFAULT 0,
                    payload_json TEXT,
                    result_json TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES taskmaster_runs(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS taskmaster_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    task_id INTEGER,
                    level TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT,
                    data_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES taskmaster_runs(id) ON DELETE CASCADE,
                    FOREIGN KEY (task_id) REFERENCES taskmaster_tasks(id) ON DELETE SET NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS taskmaster_job_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT NOT NULL,
                    payload_json TEXT,
                    status TEXT NOT NULL DEFAULT 'queued',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 2,
                    last_error TEXT,
                    worker_name TEXT,
                    available_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS taskmaster_dead_letters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    queue_job_id INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    payload_json TEXT,
                    error_message TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (queue_job_id) REFERENCES taskmaster_job_queue(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS manager_knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    term TEXT NOT NULL,
                    category TEXT,
                    canonical_value TEXT,
                    ontology_entity_id TEXT,
                    framework_type TEXT,
                    jurisdiction TEXT,
                    components_json TEXT,
                    legal_use_cases_json TEXT,
                    preferred_perspective TEXT,
                    is_canonical INTEGER NOT NULL DEFAULT 0,
                    issue_category TEXT,
                    severity TEXT,
                    impact_description TEXT,
                    root_cause_json TEXT,
                    fix_status TEXT,
                    resolution_evidence TEXT,
                    resolution_date TIMESTAMP,
                    next_review_date TEXT,
                    related_frameworks_json TEXT,
                    aliases_json TEXT,
                    description TEXT,
                    attributes_json TEXT,
                    relations_json TEXT,
                    sources_json TEXT,
                    notes TEXT,
                    source TEXT,
                    confidence REAL DEFAULT 0.5,
                    status TEXT NOT NULL DEFAULT 'proposed',
                    verified INTEGER NOT NULL DEFAULT 0,
                    verified_by TEXT,
                    user_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    UNIQUE(term, category)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS manager_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    context_json TEXT,
                    linked_term TEXT,
                    status TEXT NOT NULL DEFAULT 'open',
                    answer TEXT,
                    asked_by TEXT DEFAULT 'taskmaster',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    answered_at TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS manager_personas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    role TEXT,
                    system_prompt TEXT,
                    activation_rules_json TEXT,
                    settings_json TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    confidence REAL,
                    source TEXT,
                    status TEXT NOT NULL DEFAULT 'proposed',
                    review_note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS manager_skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    config_json TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS manager_persona_skills (
                    persona_id INTEGER NOT NULL,
                    skill_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (persona_id, skill_id),
                    FOREIGN KEY (persona_id) REFERENCES manager_personas(id) ON DELETE CASCADE,
                    FOREIGN KEY (skill_id) REFERENCES manager_skills(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS scan_manifest (
                    path_hash TEXT PRIMARY KEY,
                    normalized_path TEXT NOT NULL,
                    file_size INTEGER,
                    mtime REAL,
                    sha256 TEXT,
                    last_status TEXT,
                    last_error TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS taskmaster_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    mode TEXT NOT NULL,
                    payload_json TEXT,
                    every_minutes INTEGER NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    last_run_at TIMESTAMP,
                    next_run_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS manager_skill_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    persona_id INTEGER,
                    skill_name TEXT NOT NULL,
                    output_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES taskmaster_runs(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS organization_proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    file_id INTEGER NOT NULL,
                    current_path TEXT,
                    proposed_folder TEXT NOT NULL,
                    proposed_filename TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    rationale TEXT,
                    alternatives_json TEXT,
                    provider TEXT,
                    model TEXT,
                    status TEXT NOT NULL DEFAULT 'proposed',
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (file_id) REFERENCES files_index(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS organization_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id INTEGER NOT NULL,
                    file_id INTEGER,
                    action TEXT NOT NULL,
                    original_json TEXT,
                    final_json TEXT,
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (proposal_id) REFERENCES organization_proposals(id) ON DELETE CASCADE,
                    FOREIGN KEY (file_id) REFERENCES files_index(id) ON DELETE SET NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS organization_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id INTEGER,
                    file_id INTEGER,
                    action_type TEXT NOT NULL,
                    from_path TEXT,
                    to_path TEXT,
                    success INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    rollback_group TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (proposal_id) REFERENCES organization_proposals(id) ON DELETE SET NULL,
                    FOREIGN KEY (file_id) REFERENCES files_index(id) ON DELETE SET NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS aedis_analysis_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id TEXT NOT NULL UNIQUE,
                    artifact_row_id INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    parent_version INTEGER,
                    status TEXT NOT NULL DEFAULT 'draft',
                    payload_json TEXT,
                    audit_deltas_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (artifact_row_id) REFERENCES files_index(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS aedis_learning_paths (
                    path_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    objective_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    ontology_version INTEGER NOT NULL DEFAULT 1,
                    heuristic_snapshot_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS aedis_learning_path_steps (
                    path_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    instruction TEXT NOT NULL,
                    objective_id TEXT NOT NULL,
                    heuristic_ids_json TEXT,
                    evidence_spans_json TEXT,
                    difficulty INTEGER NOT NULL DEFAULT 1,
                    completed INTEGER NOT NULL DEFAULT 0,
                    step_order INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (path_id, step_id),
                    FOREIGN KEY (path_id) REFERENCES aedis_learning_paths(path_id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_jobs (
                    job_id TEXT PRIMARY KEY,
                    workflow TEXT NOT NULL DEFAULT 'memory_first_v2',
                    status TEXT NOT NULL DEFAULT 'queued',
                    current_step TEXT NOT NULL DEFAULT 'sources',
                    progress REAL NOT NULL DEFAULT 0,
                    draft_state TEXT NOT NULL DEFAULT 'clean',
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    idempotency_key TEXT,
                    webhook_enabled INTEGER NOT NULL DEFAULT 0,
                    webhook_url TEXT,
                    webhook_last_delivery_status TEXT,
                    webhook_last_delivery_at TIMESTAMP,
                    stepper_json TEXT,
                    pagination_json TEXT,
                    undo_json TEXT,
                    metadata_json TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_idempotency_keys (
                    scope TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (scope, idempotency_key)
                )
            """)

            # Schema migrations (versioned, auditable)
            from mem_db.migrations.runner import apply_migrations  # noqa: E402

            strict_migrations = (
                str(os.getenv("STRICT_DB_MIGRATIONS", "1")).strip().lower()
                not in {"0", "false", "no", "off"}
            )
            migration_results = apply_migrations(conn, strict=strict_migrations)
            if (not strict_migrations) and any(r.get("status") == "failed" for r in migration_results):
                logger.warning("Database migrations had failures in non-strict mode: %s", migration_results)

            # Create indexes for better performance
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_file_type ON documents(file_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_document_tags_name ON document_tags(tag_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_search_indices_terms ON search_indices(search_terms)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_index_status ON files_index(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_index_ext ON files_index(ext)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_index_mtime ON files_index(mtime)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_index_sha256 ON files_index(sha256)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_index_path_hash ON files_index(path_hash)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_index_mime ON files_index(mime_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_dup_rel_canonical ON file_duplicate_relationships(canonical_file_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_dup_rel_duplicate ON file_duplicate_relationships(duplicate_file_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_dup_rel_type ON file_duplicate_relationships(relationship_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_watched_directories_active ON watched_directories(active)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_content_chunks_file_id ON file_content_chunks(file_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_content_chunks_type ON file_content_chunks(chunk_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_extracted_tables_file_id ON file_extracted_tables(file_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_chunk_embeddings_file_id ON file_chunk_embeddings(file_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_chunk_embeddings_model ON file_chunk_embeddings(embedding_model)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_entities_file_id ON file_entities(file_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_entities_ontology_id ON file_entities(ontology_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_entity_links_source ON file_entity_links(source_file_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_entity_links_target ON file_entity_links(target_file_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_taskmaster_runs_status ON taskmaster_runs(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_taskmaster_tasks_run_id ON taskmaster_tasks(run_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_taskmaster_events_run_id ON taskmaster_events(run_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_taskmaster_queue_status_available ON taskmaster_job_queue(status, available_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_taskmaster_dead_letters_job_id ON taskmaster_dead_letters(queue_job_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_manager_knowledge_term ON manager_knowledge(term)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_manager_questions_status ON manager_questions(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_manager_personas_active ON manager_personas(active)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_proposals_status ON knowledge_proposals(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_manager_skills_enabled ON manager_skills(enabled)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scan_manifest_mtime ON scan_manifest(mtime)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_taskmaster_schedules_next_run ON taskmaster_schedules(next_run_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_manager_skill_results_run_id ON manager_skill_results(run_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_proposals_file_id ON organization_proposals(file_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_proposals_status ON organization_proposals(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_feedback_proposal_id ON organization_feedback(proposal_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_actions_file_id ON organization_actions(file_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_learning_path_steps_path_order ON aedis_learning_path_steps(path_id, step_order)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_learning_path_steps_path_completed ON aedis_learning_path_steps(path_id, completed)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_jobs_status_updated ON workflow_jobs(status, updated_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_jobs_idempotency_key ON workflow_jobs(idempotency_key)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_aedis_analysis_versions_analysis_id ON aedis_analysis_versions(analysis_id)"
            )

            # Full-text search baseline over chunk titles/content
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS file_content_chunks_fts USING fts5(title, content, content='file_content_chunks', content_rowid='id')"
            )
            conn.execute(
                "CREATE TRIGGER IF NOT EXISTS file_chunks_ai AFTER INSERT ON file_content_chunks BEGIN INSERT INTO file_content_chunks_fts(rowid, title, content) VALUES (new.id, new.title, new.content); END"
            )
            conn.execute(
                "CREATE TRIGGER IF NOT EXISTS file_chunks_ad AFTER DELETE ON file_content_chunks BEGIN INSERT INTO file_content_chunks_fts(file_content_chunks_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content); END"
            )
            conn.execute(
                "CREATE TRIGGER IF NOT EXISTS file_chunks_au AFTER UPDATE ON file_content_chunks BEGIN INSERT INTO file_content_chunks_fts(file_content_chunks_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content); INSERT INTO file_content_chunks_fts(rowid, title, content) VALUES (new.id, new.title, new.content); END"
            )

            conn.commit()
            logger.info("Database schema initialized successfully")

    # Organization Proposals
    def organization_add_proposal(self, proposal: Dict[str, Any]) -> int:
        return self.organization_repo.add_proposal(proposal)

    def organization_list_proposals(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return self.organization_repo.list_proposals(status=status, limit=limit, offset=offset)

    def organization_get_proposal(self, proposal_id: int) -> Optional[Dict[str, Any]]:
        return self.organization_repo.get_proposal(proposal_id)

    def organization_update_proposal(
        self,
        proposal_id: int,
        *,
        status: Optional[str] = None,
        proposed_folder: Optional[str] = None,
        proposed_filename: Optional[str] = None,
        confidence: Optional[float] = None,
        rationale: Optional[str] = None,
    ) -> bool:
        return self.organization_repo.update_proposal(
            proposal_id,
            status=status,
            proposed_folder=proposed_folder,
            proposed_filename=proposed_filename,
            confidence=confidence,
            rationale=rationale,
        )

    def organization_delete_proposal(self, proposal_id: int) -> bool:
        return self.organization_repo.delete_proposal(proposal_id)

    def organization_add_feedback(self, feedback: Dict[str, Any]) -> int:
        return self.organization_repo.add_feedback(feedback)

    def organization_add_action(self, action: Dict[str, Any]) -> int:
        return self.organization_repo.add_action(action)

    def organization_list_feedback(self, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        return self.organization_repo.list_feedback(limit=limit, offset=offset)

    def organization_list_actions(self, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        return self.organization_repo.list_actions(limit=limit, offset=offset)

    def organization_stats(self) -> Dict[str, Any]:
        return self.organization_repo.stats()

    # Analysis Version Operations
    def add_analysis_version(self, analysis_version_data: Dict[str, Any]) -> int:
        return self.analysis_version_repo.add_analysis_version(analysis_version_data)

    def get_analysis_version(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        return self.analysis_version_repo.get_analysis_version(analysis_id)

    def update_analysis_version(
        self,
        analysis_id: str,
        *,
        status: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        audit_deltas: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        return self.analysis_version_repo.update_analysis_version(
            analysis_id, status=status, payload=payload, audit_deltas=audit_deltas
        )

    def list_analysis_versions(
        self,
        *,
        artifact_row_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return self.analysis_version_repo.list_analysis_versions(
            artifact_row_id=artifact_row_id, status=status, limit=limit, offset=offset
        )

    def delete_analysis_version(self, analysis_id: str) -> bool:
        return self.analysis_version_repo.delete_analysis_version(analysis_id)

    # Learning Path Operations
    def learning_path_upsert(self, path_data: Dict[str, Any]) -> bool:
        return self.learning_path_repo.upsert_path(path_data)

    def learning_path_get(self, path_id: str) -> Optional[Dict[str, Any]]:
        return self.learning_path_repo.get_path(path_id)

    def learning_path_update_step_completion(
        self,
        *,
        path_id: str,
        step_id: str,
        completed: bool,
        updated_at: str,
    ) -> bool:
        return self.learning_path_repo.update_step_completion(
            path_id=path_id,
            step_id=step_id,
            completed=completed,
            updated_at=updated_at,
        )

    def learning_path_list_recommended_steps(self, path_id: str) -> List[Dict[str, Any]]:
        return self.learning_path_repo.list_recommended_steps(path_id)

    # Document CRUD Operations

    def create_document(
        self, document: DocumentCreate, correlation_id: Optional[str] = None
    ) -> DocumentResponse:
        return self.document_repo.create_document(document)

    def get_document(self, document_id: int) -> Optional[DocumentResponse]:
        return self.document_repo.get_document(document_id)

    def update_document(  # noqa: C901
        self,
        document_id: int,
        document: DocumentUpdate,
        correlation_id: Optional[str] = None,
    ) -> Optional[DocumentResponse]:
        return self.document_repo.update_document(document_id, document)

    def delete_document(self, document_id: int, correlation_id: Optional[str] = None) -> bool:
        return self.document_repo.delete_document(document_id)

    def list_documents(
        self,
        limit: int = 20,
        offset: int = 0,
        category: Optional[str] = None,
        file_type: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Tuple[List[DocumentResponse], int]:
        return self.document_repo.list_documents(
            limit=limit,
            offset=offset,
            category=category,
            file_type=file_type,
        )

    def get_document_analytics(self, document_id: int) -> Optional[Dict[str, Any]]:
        return self.document_repo.get_document_analytics(document_id)

    def recompute_document_analytics(self, document_id: int) -> bool:
        return self.document_repo.recompute_document_analytics(document_id)

    # Tag Operations

    def add_document_tags(
        self, document_id: int, tags: List[TagCreate]
    ) -> List[TagResponse]:
        return self.document_repo.add_document_tags(document_id, tags)

    def get_document_tags(self, document_id: int) -> List[TagResponse]:
        return self.document_repo.get_document_tags(document_id)

    def delete_document_tag(self, document_id: int, tag_name: str) -> bool:
        return self.document_repo.delete_document_tag(document_id, tag_name)

    def get_all_tags(self) -> List[str]:
        return self.document_repo.get_all_tags()

    def get_documents_by_tag(
        self, tag_name: str, limit: int = 20, offset: int = 0
    ) -> Tuple[List[DocumentResponse], int]:
        return self.document_repo.get_documents_by_tag(tag_name, limit=limit, offset=offset)

    # Search Operations

    def search_documents(
        self, query: SearchQuery, correlation_id: Optional[str] = None
    ) -> Tuple[List[DocumentResponse], int]:
        return self.document_repo.search_documents(query)

    def get_search_suggestions(self, query: str) -> Dict[str, List[str]]:
        return self.document_repo.get_search_suggestions(query)

    # Document search index updates are implemented in DocumentRepository.

    # File Index Operations

    def upsert_indexed_file(
        self,
        *,
        display_name: str,
        original_path: str,
        normalized_path: str,
        file_size: Optional[int],
        mtime: Optional[float],
        mime_type: Optional[str],
        mime_source: Optional[str],
        sha256: Optional[str],
        ext: Optional[str],
        status: str,
        last_error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        return self.file_index_repo.upsert_indexed_file(
            display_name=display_name,
            original_path=original_path,
            normalized_path=normalized_path,
            file_size=file_size,
            mtime=mtime,
            mime_type=mime_type,
            mime_source=mime_source,
            sha256=sha256,
            ext=ext,
            status=status,
            last_error=last_error,
            metadata=metadata,
        )

    def get_indexed_file(self, file_id: int) -> Optional[Dict[str, Any]]:
        return self.file_index_repo.get_indexed_file(file_id)

    def list_indexed_files(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        ext: Optional[str] = None,
        query: Optional[str] = None,
        sort_by: str = "last_checked_at",
        sort_dir: str = "desc",
        keyword: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        return self.file_index_repo.list_indexed_files(
            limit=limit,
            offset=offset,
            status=status,
            ext=ext,
            query=query,
            sort_by=sort_by,
            sort_dir=sort_dir,
            keyword=keyword,
        )

    def list_all_indexed_files(self) -> List[Dict[str, Any]]:
        return self.file_index_repo.list_all_indexed_files()

    def replace_file_chunks(
        self,
        file_id: int,
        chunks: List[Dict[str, Any]],
    ) -> List[int]:
        return self.file_index_repo.replace_file_chunks(file_id, chunks)

    def list_file_chunks(self, file_id: int) -> List[Dict[str, Any]]:
        return self.file_index_repo.list_file_chunks(file_id)

    def search_file_chunks_fulltext(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self.file_index_repo.search_file_chunks_fulltext(query, limit=limit)

    def replace_file_entities(self, file_id: int, entities: List[Dict[str, Any]]) -> int:
        return self.file_index_repo.replace_file_entities(file_id, entities)

    def list_file_entities(self, file_id: int) -> List[Dict[str, Any]]:
        return self.file_index_repo.list_file_entities(file_id)

    def refresh_file_entity_links(self) -> int:
        return self.file_index_repo.refresh_file_entity_links()

    def list_file_entity_links(self, file_id: int) -> List[Dict[str, Any]]:
        return self.file_index_repo.list_file_entity_links(file_id)

    def refresh_materialized_file_summaries(self, stale_after_hours: int = 24) -> Dict[str, int]:
        return self.file_index_repo.refresh_materialized_file_summaries(stale_after_hours=stale_after_hours)

    def replace_file_tables(self, file_id: int, tables: List[Dict[str, Any]]) -> int:
        return self.file_index_repo.replace_file_tables(file_id, tables)

    def list_file_tables(self, file_id: int) -> List[Dict[str, Any]]:
        return self.file_index_repo.list_file_tables(file_id)

    def upsert_chunk_embedding(
        self,
        *,
        file_id: int,
        chunk_id: int,
        embedding_model: str,
        embedding: List[float],
    ) -> int:
        return self.file_index_repo.upsert_chunk_embedding(
            file_id=file_id,
            chunk_id=chunk_id,
            embedding_model=embedding_model,
            embedding=embedding,
        )

    def semantic_similarity_search(
        self,
        *,
        query_embedding: List[float],
        embedding_model: str,
        limit: int = 10,
        min_similarity: float = 0.0,
        file_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        return self.file_index_repo.semantic_similarity_search(
            query_embedding=query_embedding,
            embedding_model=embedding_model,
            limit=limit,
            min_similarity=min_similarity,
            file_id=file_id,
        )

    def refresh_exact_duplicate_relationships(self) -> Dict[str, int]:
        return self.file_index_repo.refresh_exact_duplicate_relationships()

    def get_file_duplicate_relationships(self, file_id: int) -> Dict[str, Any]:
        return self.file_index_repo.get_file_duplicate_relationships(file_id)

    def upsert_watched_directory(
        self,
        *,
        original_path: str,
        normalized_path: str,
        recursive: bool = True,
        keywords: Optional[List[str]] = None,
        allowed_exts: Optional[List[str]] = None,
        active: bool = True,
    ) -> int:
        return self.watch_repo.upsert_watched_directory(
            original_path=original_path,
            normalized_path=normalized_path,
            recursive=recursive,
            keywords=keywords,
            allowed_exts=allowed_exts,
            active=active,
        )

    def list_watched_directories(self, active_only: bool = True) -> List[Dict[str, Any]]:
        return self.watch_repo.list_watched_directories(active_only=active_only)

    # TaskMaster Operations

    def taskmaster_create_run(self, run_type: str, payload: Optional[Dict[str, Any]] = None) -> int:
        return self.taskmaster_repo.create_run(run_type, payload)

    def taskmaster_complete_run(self, run_id: int, status: str, summary: Optional[Dict[str, Any]] = None) -> None:
        self.taskmaster_repo.complete_run(run_id, status, summary)

    def taskmaster_create_task(self, run_id: int, task_name: str, payload: Optional[Dict[str, Any]] = None) -> int:
        return self.taskmaster_repo.create_task(run_id, task_name, payload)

    def taskmaster_update_task(
        self,
        task_id: int,
        *,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        result: Optional[Dict[str, Any]] = None,
        done: bool = False,
    ) -> None:
        self.taskmaster_repo.update_task(task_id, status=status, progress=progress, result=result, done=done)

    def taskmaster_add_event(
        self,
        run_id: int,
        *,
        level: str,
        event_type: str,
        message: str,
        task_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> int:
        return self.taskmaster_repo.add_event(
            run_id,
            level=level,
            event_type=event_type,
            message=message,
            task_id=task_id,
            data=data,
        )

    def taskmaster_get_run_status(self, run_id: int) -> Optional[str]:
        return self.taskmaster_repo.get_run_status(run_id)

    def taskmaster_get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        return self.taskmaster_repo.get_run(run_id)

    def taskmaster_list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        run_type: Optional[str] = None,
        started_after: Optional[str] = None,
        started_before: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self.taskmaster_repo.list_runs(
            limit=limit,
            offset=offset,
            status=status,
            run_type=run_type,
            started_after=started_after,
            started_before=started_before,
        )

    def taskmaster_list_events(
        self,
        run_id: int,
        limit: int = 500,
        level: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self.taskmaster_repo.list_events(run_id, limit=limit, level=level, event_type=event_type)

    def taskmaster_cancel_run(self, run_id: int) -> bool:
        return self.taskmaster_repo.cancel_run(run_id)

    def taskmaster_queue_depth(self, *, include_running: bool = False) -> int:
        return self.taskmaster_repo.queue_depth(include_running=include_running)

    def taskmaster_queue_enqueue(self, *, mode: str, payload: Optional[Dict[str, Any]] = None, max_retries: int = 2) -> int:
        return self.taskmaster_repo.queue_enqueue(mode=mode, payload=payload, max_retries=max_retries)

    def taskmaster_queue_claim_next(self, *, worker_name: str) -> Optional[Dict[str, Any]]:
        return self.taskmaster_repo.queue_claim_next(worker_name=worker_name)

    def taskmaster_queue_mark_completed(self, queue_job_id: int) -> None:
        self.taskmaster_repo.queue_mark_completed(queue_job_id)

    def taskmaster_queue_mark_retry_or_dead_letter(self, queue_job_id: int, *, error_message: str) -> str:
        return self.taskmaster_repo.queue_mark_retry_or_dead_letter(queue_job_id, error_message=error_message)

    def taskmaster_dead_letters(self, *, limit: int = 100) -> List[Dict[str, Any]]:
        return self.taskmaster_repo.dead_letters(limit=limit)

    # Manager Knowledge Operations

    def knowledge_upsert(
        self,
        *,
        term: str,
        category: Optional[str] = None,
        canonical_value: Optional[str] = None,
        ontology_entity_id: Optional[str] = None,
        framework_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        components: Optional[Dict[str, Any]] = None,
        legal_use_cases: Optional[List[Dict[str, Any]]] = None,
        preferred_perspective: Optional[str] = None,
        is_canonical: bool = False,
        issue_category: Optional[str] = None,
        severity: Optional[str] = None,
        impact_description: Optional[str] = None,
        root_cause: Optional[List[Dict[str, Any]]] = None,
        fix_status: Optional[str] = None,
        resolution_evidence: Optional[str] = None,
        resolution_date: Optional[str] = None,
        next_review_date: Optional[str] = None,
        related_frameworks: Optional[List[Any]] = None,
        aliases: Optional[List[str]] = None,
        description: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        relations: Optional[List[Dict[str, Any]]] = None,
        sources: Optional[List[Any]] = None,
        notes: Optional[str] = None,
        source: Optional[str] = None,
        confidence: float = 0.5,
        status: str = "proposed",
        verified: bool = False,
        verified_by: Optional[str] = None,
        user_notes: Optional[str] = None,
    ) -> int:
        return self.knowledge_repo.upsert(
            term=term,
            category=category,
            canonical_value=canonical_value,
            ontology_entity_id=ontology_entity_id,
            framework_type=framework_type,
            jurisdiction=jurisdiction,
            components=components,
            legal_use_cases=legal_use_cases,
            preferred_perspective=preferred_perspective,
            is_canonical=is_canonical,
            issue_category=issue_category,
            severity=severity,
            impact_description=impact_description,
            root_cause=root_cause,
            fix_status=fix_status,
            resolution_evidence=resolution_evidence,
            resolution_date=resolution_date,
            next_review_date=next_review_date,
            related_frameworks=related_frameworks,
            aliases=aliases,
            description=description,
            attributes=attributes,
            relations=relations,
            sources=sources,
            notes=notes,
            source=source,
            confidence=confidence,
            status=status,
            verified=verified,
            verified_by=verified_by,
            user_notes=user_notes,
        )

    def knowledge_list(
        self,
        *,
        status: Optional[str] = None,
        category: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return self.knowledge_repo.list(
            status=status,
            category=category,
            query=query,
            limit=limit,
            offset=offset,
        )

    def knowledge_set_ontology_link(self, knowledge_id: int, ontology_entity_id: str) -> bool:
        return self.knowledge_repo.set_ontology_link(knowledge_id, ontology_entity_id)

    def knowledge_get_item(self, knowledge_id: int) -> Optional[Dict[str, Any]]:
        return self.knowledge_repo.get_item(knowledge_id)

    def knowledge_update_item(
        self,
        knowledge_id: int,
        *,
        term: Optional[str] = None,
        category: Optional[str] = None,
        canonical_value: Optional[str] = None,
        ontology_entity_id: Optional[str] = None,
        framework_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        components: Optional[Dict[str, Any]] = None,
        legal_use_cases: Optional[List[Dict[str, Any]]] = None,
        preferred_perspective: Optional[str] = None,
        is_canonical: Optional[bool] = None,
        issue_category: Optional[str] = None,
        severity: Optional[str] = None,
        impact_description: Optional[str] = None,
        root_cause: Optional[List[Dict[str, Any]]] = None,
        fix_status: Optional[str] = None,
        resolution_evidence: Optional[str] = None,
        resolution_date: Optional[str] = None,
        next_review_date: Optional[str] = None,
        related_frameworks: Optional[List[Any]] = None,
        aliases: Optional[List[str]] = None,
        description: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        relations: Optional[List[Dict[str, Any]]] = None,
        sources: Optional[List[Any]] = None,
        source: Optional[str] = None,
        confidence: Optional[float] = None,
        status: Optional[str] = None,
        verified: Optional[bool] = None,
        verified_by: Optional[str] = None,
        user_notes: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        return self.knowledge_repo.update_item(
            knowledge_id,
            term=term,
            category=category,
            canonical_value=canonical_value,
            ontology_entity_id=ontology_entity_id,
            framework_type=framework_type,
            jurisdiction=jurisdiction,
            components=components,
            legal_use_cases=legal_use_cases,
            preferred_perspective=preferred_perspective,
            is_canonical=is_canonical,
            issue_category=issue_category,
            severity=severity,
            impact_description=impact_description,
            root_cause=root_cause,
            fix_status=fix_status,
            resolution_evidence=resolution_evidence,
            resolution_date=resolution_date,
            next_review_date=next_review_date,
            related_frameworks=related_frameworks,
            aliases=aliases,
            description=description,
            attributes=attributes,
            relations=relations,
            sources=sources,
            source=source,
            confidence=confidence,
            status=status,
            verified=verified,
            verified_by=verified_by,
            user_notes=user_notes,
            notes=notes,
        )

    def knowledge_delete_item(self, knowledge_id: int) -> bool:
        return self.knowledge_repo.delete_item(knowledge_id)

    def knowledge_set_verification(
        self,
        knowledge_id: int,
        *,
        verified: bool,
        verified_by: Optional[str] = None,
        user_notes: Optional[str] = None,
    ) -> bool:
        return self.knowledge_repo.set_verification(
            knowledge_id,
            verified=verified,
            verified_by=verified_by,
            user_notes=user_notes,
        )

    def knowledge_has_term(self, term: str, category: Optional[str] = None) -> bool:
        return self.knowledge_repo.has_term(term, category)

    def knowledge_add_question(
        self,
        *,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        linked_term: Optional[str] = None,
        asked_by: str = "taskmaster",
    ) -> int:
        return self.knowledge_repo.add_question(
            question=question,
            context=context,
            linked_term=linked_term,
            asked_by=asked_by,
        )

    def knowledge_answer_question(self, question_id: int, answer: str) -> bool:
        return self.knowledge_repo.answer_question(question_id, answer)

    def knowledge_list_questions(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return self.knowledge_repo.list_questions(status=status, limit=limit, offset=offset)

    def knowledge_add_proposal(
        self,
        *,
        proposal_type: str,
        payload: Dict[str, Any],
        confidence: Optional[float] = None,
        source: Optional[str] = None,
        status: str = "proposed",
    ) -> int:
        return self.knowledge_repo.add_proposal(
            proposal_type=proposal_type,
            payload=payload,
            confidence=confidence,
            source=source,
            status=status,
        )

    def knowledge_list_proposals(self, *, status: Optional[str] = None, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        return self.knowledge_repo.list_proposals(status=status, limit=limit, offset=offset)

    def knowledge_get_proposal(self, proposal_id: int) -> Optional[Dict[str, Any]]:
        return self.knowledge_repo.get_proposal(proposal_id)

    def knowledge_update_proposal_status(self, proposal_id: int, *, status: str, review_note: Optional[str] = None) -> bool:
        return self.knowledge_repo.update_proposal_status(proposal_id, status=status, review_note=review_note)

    # Persona/Skills Operations

    def persona_upsert(
        self,
        *,
        name: str,
        role: Optional[str] = None,
        system_prompt: Optional[str] = None,
        activation_rules: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        active: bool = True,
    ) -> int:
        return self.persona_repo.upsert(
            name=name,
            role=role,
            system_prompt=system_prompt,
            activation_rules=activation_rules,
            settings=settings,
            active=active,
        )

    def persona_get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return self.persona_repo.get_by_name(name)

    def persona_list(self, active_only: bool = False) -> List[Dict[str, Any]]:
        return self.persona_repo.list(active_only=active_only)

    def skill_upsert(self, *, name: str, description: Optional[str] = None, config: Optional[Dict[str, Any]] = None, enabled: bool = True) -> int:
        return self.persona_repo.skill_upsert(name=name, description=description, config=config, enabled=enabled)

    def skill_list(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        return self.persona_repo.skill_list(enabled_only=enabled_only)

    def persona_attach_skill(self, persona_id: int, skill_id: int) -> bool:
        return self.persona_repo.attach_skill(persona_id, skill_id)

    def persona_skill_names(self, persona_id: int) -> List[str]:
        return [str(s.get("name")) for s in self.persona_repo.persona_skills(persona_id)]

    def persona_skills(self, persona_id: int) -> List[Dict[str, Any]]:
        return self.persona_repo.persona_skills(persona_id)

    def persona_resolve(self, *, mode: Optional[str] = None, content_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return self.persona_repo.resolve(mode=mode, content_type=content_type)

    # Scan Manifest Operations

    def scan_manifest_get(self, path_hash: str) -> Optional[Dict[str, Any]]:
        return self.watch_repo.scan_manifest_get(path_hash)

    def scan_manifest_upsert(
        self,
        *,
        path_hash: str,
        normalized_path: str,
        file_size: Optional[int],
        mtime: Optional[float],
        sha256: Optional[str],
        last_status: Optional[str],
        last_error: Optional[str],
    ) -> None:
        self.watch_repo.scan_manifest_upsert(
            path_hash=path_hash,
            normalized_path=normalized_path,
            file_size=file_size,
            mtime=mtime,
            sha256=sha256,
            last_status=last_status,
            last_error=last_error,
        )

    # TaskMaster schedule operations

    def skill_result_add(
        self,
        *,
        run_id: int,
        skill_name: str,
        output: Dict[str, Any],
        persona_id: Optional[int] = None,
    ) -> int:
        return self.persona_repo.skill_result_add(
            run_id=run_id,
            skill_name=skill_name,
            output=output,
            persona_id=persona_id,
        )

    def skill_result_list(self, run_id: int) -> List[Dict[str, Any]]:
        return self.persona_repo.skill_result_list(run_id)

    def schedule_upsert(
        self,
        *,
        name: Optional[str],
        mode: str,
        payload: Optional[Dict[str, Any]],
        every_minutes: int,
        active: bool = True,
    ) -> int:
        return self.taskmaster_repo.schedule_upsert(
            name=name,
            mode=mode,
            payload=payload,
            every_minutes=every_minutes,
            active=active,
        )

    def schedule_list(self, active_only: bool = False) -> List[Dict[str, Any]]:
        return self.taskmaster_repo.schedule_list(active_only=active_only)

    def schedule_due(self) -> List[Dict[str, Any]]:
        return self.taskmaster_repo.schedule_due()

    def schedule_mark_ran(self, schedule_id: int, every_minutes: int) -> None:
        self.taskmaster_repo.schedule_mark_ran(schedule_id, every_minutes)

    def schema_migration_status(self) -> List[Dict[str, Any]]:
        from mem_db.migrations.runner import migration_status  # noqa: E402

        with self.get_connection() as conn:
            return migration_status(conn)

    # Health and Statistics

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for health monitoring."""
        return self.document_repo.get_database_stats()


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_database_manager(db_path: Optional[str] = None) -> DatabaseManager:  # noqa: F811
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager


def init_database(db_path: Optional[str] = None) -> DatabaseManager:
    """Initialize the database with optional custom path."""
    global _db_manager
    _db_manager = DatabaseManager(db_path)
    return _db_manager
