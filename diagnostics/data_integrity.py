"""
Data integrity checks for the Smart Document Organizer.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def _get_db_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

def check_orphaned_memory_links(unified_memory_db_path: Path, file_index_db_path: Path) -> Dict[str, Any]:
    """
    Checks for memory_code_links entries where the memory_record_id or file_path
    does not exist in their respective source tables.
    """
    orphaned_links: List[Dict[str, Any]] = []
    
    um_conn = None
    fi_conn = None
    
    try:
        um_conn = _get_db_connection(unified_memory_db_path)
        fi_conn = _get_db_connection(file_index_db_path)

        # Check for links with non-existent memory_record_id
        cursor = um_conn.execute("""
            SELECT l.memory_record_id, l.file_path, l.relation_type
            FROM memory_code_links l
            LEFT JOIN memory_records m ON l.memory_record_id = m.record_id
            WHERE m.record_id IS NULL;
        """)
        for row in cursor.fetchall():
            orphaned_links.append({
                "type": "orphaned_memory_record",
                "memory_record_id": row["memory_record_id"],
                "file_path": row["file_path"],
                "relation_type": row["relation_type"],
                "issue": "memory_record_id does not exist in memory_records"
            })
        
        # Check for links with non-existent file_path (case-insensitive due to OS variations)
        # Note: This check relies on the file_path in file_index.db being accurate.
        cursor = um_conn.execute("""
            SELECT l.memory_record_id, l.file_path, l.relation_type
            FROM memory_code_links l;
        """)
        all_links = cursor.fetchall()

        for link in all_links:
            # Check if file_path exists in file_index.db
            file_path_lower = link["file_path"].lower()
            fi_cursor = fi_conn.execute("""
                SELECT id FROM files WHERE LOWER(file_path) = ? OR LOWER(absolute_path) = ?;
            """, (file_path_lower, file_path_lower))
            if fi_cursor.fetchone() is None:
                orphaned_links.append({
                    "type": "orphaned_file_path",
                    "memory_record_id": link["memory_record_id"],
                    "file_path": link["file_path"],
                    "relation_type": link["relation_type"],
                    "issue": "file_path does not exist in file_index.db (case-insensitive check)"
                })

    except Exception as e:
        logger.error(f"Error during orphaned memory links check: {e}")
        return {"status": "error", "error_message": str(e), "details": orphaned_links}
    finally:
        if um_conn:
            um_conn.close()
        if fi_conn:
            fi_conn.close()

    status = "healthy" if not orphaned_links else "unhealthy"
    return {"status": status, "count": len(orphaned_links), "details": orphaned_links}

# Additional data integrity checks can be added here.
