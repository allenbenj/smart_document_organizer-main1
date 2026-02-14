"""
Analytics Manager for Smart Document Organizer
==============================================

Provides comprehensive analytics and reporting capabilities for document management,
including document statistics, processing metrics, and system health monitoring.

Features:
- Document processing analytics
- Tag usage statistics
- Search pattern analysis
- System performance metrics
- User activity tracking
- Comprehensive reporting
"""

import json
import logging  # noqa: E402
import sqlite3  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

logger = logging.getLogger(__name__)


@dataclass
class DocumentRecord:
    """Document record structure for analytics"""

    id: str
    filename: str
    file_type: str
    file_size: int
    upload_time: datetime
    processing_status: str
    processing_options: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None


@dataclass
class SystemEvent:
    """System event record structure"""

    id: int
    timestamp: datetime
    level: str
    component: str
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ProcessingResult:
    """Processing result record structure"""

    id: int
    component_name: str
    session_id: Optional[str]
    result: Dict[str, Any]
    created_at: datetime


class DocumentAnalyticsManager:
    """Manages analytics and reporting for the document organizer"""

    def __init__(self, db_path: str = "document_analytics.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database with required tables"""
        with self._get_connection() as conn:
            # Documents table for tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    upload_time TIMESTAMP NOT NULL,
                    processing_status TEXT NOT NULL,
                    processing_options TEXT,
                    results TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # System logs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    level TEXT NOT NULL,
                    component TEXT NOT NULL,
                    message TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Processing results table for storing component outputs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processing_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component_name TEXT NOT NULL,
                    session_id TEXT,
                    result_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

            # User activity tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    session_id TEXT,
                    activity_type TEXT NOT NULL,
                    activity_data TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

            # Search analytics
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    results_count INTEGER NOT NULL,
                    response_time_ms INTEGER,
                    user_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

            # Create indexes for better performance
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(file_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_logs_level ON system_logs(level)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_logs_component ON system_logs(component)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_processing_component ON processing_results(component_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_processing_session ON processing_results(session_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_user ON user_activity(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_search_timestamp ON search_analytics(timestamp)"
            )

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            conn.close()

    # Document tracking methods
    def save_document(
        self,
        doc_id: str,
        filename: str,
        file_type: str,
        file_size: int,
        processing_options: Dict[str, Any],
    ) -> bool:
        """Save document information"""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO documents (
                        id, filename, file_type, file_size, upload_time,
                        processing_status, processing_options
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        doc_id,
                        filename,
                        file_type,
                        file_size,
                        datetime.now(),
                        "UPLOADED",
                        json.dumps(processing_options),
                    ),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            return False

    def update_document_status(
        self, doc_id: str, status: str, results: Optional[Dict] = None
    ) -> bool:
        """Update document processing status"""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE documents
                    SET processing_status = ?, results = ?
                    WHERE id = ?
                """,
                    (status, json.dumps(results) if results else None, doc_id),
                )
                conn.commit()
                return conn.total_changes > 0
        except Exception as e:
            logger.error(f"Failed to update document status: {e}")
            return False

    def get_documents(self, limit: int = 50) -> List[DocumentRecord]:
        """Retrieve document records"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT * FROM documents
                    ORDER BY upload_time DESC
                    LIMIT ?
                """,
                    (limit,),
                )
                rows = cursor.fetchall()

                documents = []
                for row in rows:
                    docrecord = DocumentRecord(  # noqa: F841
                        id=row["id"],
                        filename=row["filename"],
                        file_type=row["file_type"],
                        file_size=row["file_size"],
                        upload_time=(
                            datetime.fromisoformat(row["upload_time"])
                            if isinstance(row["upload_time"], str)
                            else row["upload_time"]
                        ),
                        processing_status=row["processing_status"],
                        processing_options=(
                            json.loads(row["processing_options"])
                            if row["processing_options"]
                            else None
                        ),
                        results=json.loads(row["results"]) if row["results"] else None,
                    )
                    documents.append(doc_record)  # noqa: F821

                return documents
        except Exception as e:
            logger.error(f"Failed to retrieve documents: {e}")
            return []

    # Processing result storage
    def save_processing_result(
        self,
        component_name: str,
        result: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> bool:
        """Persist a serialized processing result."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO processing_results (component_name, session_id, result_json)
                    VALUES (?, ?, ?)
                """,
                    (component_name, session_id, json.dumps(result)),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to save processing result: {e}")
            return False

    def get_processing_results(
        self,
        component_name: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ProcessingResult]:
        """Retrieve stored processing results with optional filtering."""
        try:
            query = "SELECT * FROM processing_results WHERE 1=1"
            params = []

            if component_name:
                query += " AND component_name = ?"
                params.append(component_name)

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            with self._get_connection() as conn:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                results = []
                for row in rows:
                    result = ProcessingResult(
                        id=row["id"],
                        component_name=row["component_name"],
                        session_id=row["session_id"],
                        result=json.loads(row["result_json"]),
                        created_at=(
                            datetime.fromisoformat(row["created_at"])
                            if isinstance(row["created_at"], str)
                            else row["created_at"]
                        ),
                    )
                    results.append(result)

                return results
        except Exception as e:
            logger.error(f"Failed to retrieve processing results: {e}")
            return []

    # Logging methods
    def log_system_event(
        self,
        level: str,
        component: str,
        message: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Log system events"""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO system_logs (
                        timestamp, level, component, message, user_id, session_id, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        datetime.now(),
                        level,
                        component,
                        message,
                        user_id,
                        session_id,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to log system event: {e}")
            return False

    def get_system_logs(
        self, filters: Optional[Dict[str, Any]] = None, limit: int = 100
    ) -> List[SystemEvent]:
        """Retrieve system logs with optional filters"""
        try:
            query = "SELECT * FROM system_logs WHERE 1=1"
            params = []

            if filters:
                if "level" in filters and filters["level"] != "ALL":
                    query += " AND level = ?"
                    params.append(filters["level"])

                if "component" in filters and filters["component"] != "ALL":
                    query += " AND component = ?"
                    params.append(filters["component"])

                if "start_time" in filters:
                    query += " AND timestamp >= ?"
                    params.append(filters["start_time"])

                if "end_time" in filters:
                    query += " AND timestamp <= ?"
                    params.append(filters["end_time"])

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            with self._get_connection() as conn:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                logs = []
                for row in rows:
                    log_event = SystemEvent(
                        id=row["id"],
                        timestamp=(
                            datetime.fromisoformat(row["timestamp"])
                            if isinstance(row["timestamp"], str)
                            else row["timestamp"]
                        ),
                        level=row["level"],
                        component=row["component"],
                        message=row["message"],
                        user_id=row["user_id"],
                        session_id=row["session_id"],
                        metadata=(
                            json.loads(row["metadata"]) if row["metadata"] else None
                        ),
                    )
                    logs.append(log_event)

                return logs
        except Exception as e:
            logger.error(f"Failed to retrieve system logs: {e}")
            return []

    # User activity tracking
    def log_user_activity(
        self,
        activity_type: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        activity_data: Optional[Dict] = None,
    ) -> bool:
        """Log user activity"""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO user_activity (user_id, session_id, activity_type, activity_data)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        user_id,
                        session_id,
                        activity_type,
                        json.dumps(activity_data) if activity_data else None,
                    ),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to log user activity: {e}")
            return False

    # Search analytics
    def log_search_query(
        self,
        query: str,
        results_count: int,
        response_time_ms: int,
        user_id: Optional[str] = None,
    ) -> bool:
        """Log search query analytics"""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO search_analytics (query, results_count, response_time_ms, user_id)
                    VALUES (?, ?, ?, ?)
                """,
                    (query, results_count, response_time_ms, user_id),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to log search query: {e}")
            return False

    # Analytics methods
    def get_analytics_data(self) -> Dict[str, Any]:
        """Get comprehensive analytics data for dashboard"""
        try:
            with self._get_connection() as conn:
                # Document stats
                cursor = conn.execute("SELECT COUNT(*) as total FROM documents")
                total_docs = cursor.fetchone()["total"]

                cursor = conn.execute(
                    "SELECT COUNT(*) as processed FROM documents WHERE processing_status = 'COMPLETED'"
                )
                processed_docs = cursor.fetchone()["processed"]

                cursor = conn.execute(
                    "SELECT COUNT(*) as failed FROM documents WHERE processing_status = 'FAILED'"
                )
                failed_docs = cursor.fetchone()["failed"]

                # File type distribution
                cursor = conn.execute(
                    "SELECT file_type, COUNT(*) as count FROM documents GROUP BY file_type"
                )
                file_types = {
                    row["file_type"]: row["count"] for row in cursor.fetchall()
                }

                # Processing time trends (last 30 days)
                thirty_days_ago = datetime.now() - timedelta(days=30)
                cursor = conn.execute(
                    """
                    SELECT DATE(upload_time) as date, COUNT(*) as count
                    FROM documents
                    WHERE upload_time >= ?
                    GROUP BY DATE(upload_time)
                    ORDER BY date
                """,
                    (thirty_days_ago,),
                )
                daily_uploads = {row["date"]: row["count"] for row in cursor.fetchall()}

                # Search analytics
                cursor = conn.execute(
                    "SELECT COUNT(*) as total_searches FROM search_analytics"
                )
                total_searches = cursor.fetchone()["total_searches"]

                cursor = conn.execute(
                    "SELECT AVG(response_time_ms) as avg_response_time FROM search_analytics"
                )
                avg_response_time = cursor.fetchone()["avg_response_time"] or 0

                # Top search queries
                cursor = conn.execute("""
                    SELECT query, COUNT(*) as frequency
                    FROM search_analytics
                    GROUP BY query
                    ORDER BY frequency DESC
                    LIMIT 10
                """)
                top_queries = [
                    {"query": row["query"], "frequency": row["frequency"]}
                    for row in cursor.fetchall()
                ]

                # System health metrics
                cursor = conn.execute(
                    "SELECT level, COUNT(*) as count FROM system_logs GROUP BY level"
                )
                log_levels = {row["level"]: row["count"] for row in cursor.fetchall()}

                return {
                    "documents": {
                        "total": total_docs,
                        "processed": processed_docs,
                        "failed": failed_docs,
                        "success_rate": (processed_docs / max(1, total_docs)) * 100,
                        "file_types": file_types,
                        "daily_uploads": daily_uploads,
                    },
                    "search": {
                        "total_searches": total_searches,
                        "avg_response_time_ms": avg_response_time,
                        "top_queries": top_queries,
                    },
                    "system": {
                        "log_levels": log_levels,
                    },
                }
        except Exception as e:
            logger.error(f"Failed to retrieve analytics data: {e}")
            return {}

    def get_document_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get detailed document processing statistics"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            with self._get_connection() as conn:
                # Processing status breakdown
                cursor = conn.execute(
                    """
                    SELECT processing_status, COUNT(*) as count
                    FROM documents
                    WHERE upload_time >= ?
                    GROUP BY processing_status
                """,
                    (cutoff_date,),
                )
                status_breakdown = {
                    row["processing_status"]: row["count"] for row in cursor.fetchall()
                }

                # Average file sizes by type
                cursor = conn.execute(
                    """
                    SELECT file_type, AVG(file_size) as avg_size, COUNT(*) as count
                    FROM documents
                    WHERE upload_time >= ?
                    GROUP BY file_type
                """,
                    (cutoff_date,),
                )
                file_type_stats = {
                    row["file_type"]: {
                        "avg_size": row["avg_size"],
                        "count": row["count"],
                    }
                    for row in cursor.fetchall()
                }

                return {
                    "period_days": days,
                    "status_breakdown": status_breakdown,
                    "file_type_stats": file_type_stats,
                }
        except Exception as e:
            logger.error(f"Failed to retrieve document statistics: {e}")
            return {}

    def cleanup_old_data(self, days: int = 90) -> bool:
        """Clean up old data based on retention policy"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            with self._get_connection() as conn:
                # Clean old logs
                conn.execute(
                    "DELETE FROM system_logs WHERE timestamp < ?", (cutoff_date,)
                )

                # Clean old user activity
                conn.execute(
                    "DELETE FROM user_activity WHERE timestamp < ?", (cutoff_date,)
                )

                # Clean old search analytics
                conn.execute(
                    "DELETE FROM search_analytics WHERE timestamp < ?", (cutoff_date,)
                )

                # Clean old completed documents (keep metadata, remove detailed results)
                conn.execute(
                    """
                    UPDATE documents
                    SET results = NULL
                    WHERE upload_time < ? AND processing_status = 'COMPLETED'
                """,
                    (cutoff_date,),
                )

                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return False


# Global analytics manager instance
_analytics_manager_instance = None


def get_analytics_manager() -> DocumentAnalyticsManager:
    """Get global analytics manager instance."""
    global _analytics_manager_instance
    if _analytics_manager_instance is None:
        _analytics_manager_instance = DocumentAnalyticsManager()
    return _analytics_manager_instance
