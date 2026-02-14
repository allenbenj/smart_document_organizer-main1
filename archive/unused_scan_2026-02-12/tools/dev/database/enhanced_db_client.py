import json
import sqlite3  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional, Tuple  # noqa: E402

# Import the new centralized DatabaseConfig
from core.database_config import DatabaseConfig  # noqa: E402


class EnhancedDocumentationClient:
    """
    Enhanced client for database-driven documentation with intelligent prioritization,
    progress tracking, and comprehensive analytics.
    This class now uses the centralized DatabaseConfig for database connections.
    """

    def __init__(self, db_config: DatabaseConfig):
        """
        Initializes the EnhancedDocumentationClient with a DatabaseConfig instance.

        Args:
            db_config (DatabaseConfig): Centralized database configuration.
        """
        self.db_config = db_config
        self.db_path = self.db_config.get_db_path("file_tracker")

        if not self.db_path:
            raise ValueError(
                "File tracker database path is not configured in DatabaseConfig."
            )

        # Ensure the parent directory exists (handled by DatabaseConfig, but good to double check)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"EnhancedDocumentationClient initialized for DB: {self.db_path}")

    def get_files_to_document(  # noqa: C901
        self, priority_filter: str = "all"
    ) -> List[Dict[str, Any]]:
        """
        Get files that need documentation with intelligent prioritization.

        Args:
            priority_filter: "high", "medium", "low", "all", "agents_only", "new_files"

        Returns:
            List of file information dictionaries with priority scoring
        """
        conn = self.db_config.get_connection("file_tracker", read_only=True)
        if not conn:
            print("Failed to connect to file_tracker database for documentation files.")
            return []

        cursor = conn.cursor()

        # Base query with comprehensive file information
        # Note: Some columns like 'modified_time', 'file_type', 'analysis_date',
        # 'lines_of_code', 'classes_found', 'functions_found' might not exist in
        # the current file_tracker_new.db schema or are derived.
        # We will adjust the query to use available columns and add checks.
        base_query = """
            SELECT
                f.file_path,
                f.file_size,
                f.file_extension,
                f.content_hash,
                f.modified_time, -- Assuming this exists from file_scanner
                f.status,
                fa.complexity_score,
                -- Add more columns from file_analysis if they exist and are relevant
                fa.primary_purpose,
                fa.key_functionality
            FROM files f
            LEFT JOIN file_analysis fa ON f.file_path = fa.file_path
            -- LEFT JOIN agents a ON f.file_path = a.file_path -- 'agents' table might not directly link by file_path
            -- LEFT JOIN agent_runability ar ON a.agent_name = ar.agent_name
        """

        # Check for existence of 'agents' and 'agent_runability' tables for joins
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agents'"
        )
        agents_table_exists = cursor.fetchone()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_runability'"
        )
        agent_runability_table_exists = cursor.fetchone()

        if agents_table_exists:
            base_query += " LEFT JOIN agents a ON f.file_path = a.file_path "
        if agent_runability_table_exists:
            base_query += (
                " LEFT JOIN agent_runability ar ON a.agent_name = ar.agent_name "
            )

        # Apply filters based on priority
        where_clause = (
            "WHERE 1=1"  # Start with a true condition to easily append AND clauses
        )

        # Default to Python files for documentation, can be expanded
        where_clause += " AND f.file_extension = '.py'"

        if priority_filter == "agents_only":
            if agents_table_exists:
                where_clause += " AND a.agent_name IS NOT NULL AND (f.status = 'pending' OR f.status IS NULL OR f.status = 'cataloged')"
            else:
                return []  # No agents table, no agents to document
        elif priority_filter == "new_files":
            where_clause += " AND fa.analysis_timestamp IS NULL"
        elif priority_filter == "high":
            where_clause += """
                AND (f.status = 'pending' OR f.status IS NULL OR f.status = 'cataloged')
                AND (fa.complexity_score > 7
                     OR f.file_size > 10000)
            """
            if agents_table_exists:
                where_clause += " OR a.agent_name IS NOT NULL"
        elif priority_filter == "medium":
            where_clause += """
                AND (f.status = 'pending' OR f.status IS NULL OR f.status = 'cataloged')
                AND (fa.complexity_score BETWEEN 4 AND 7
                     OR f.file_size BETWEEN 1000 AND 10000)
            """
        elif priority_filter == "low":
            where_clause += """
                AND (f.status = 'pending' OR f.status IS NULL OR f.status = 'cataloged')
                AND (fa.complexity_score < 4
                     OR f.file_size < 1000)
            """
        else:  # "all"
            where_clause += " AND (f.status = 'pending' OR f.status IS NULL OR f.status = 'cataloged' OR f.status = 'modified')"

        # Order by complexity and size, agent status
        order_by_clause = " ORDER BY fa.complexity_score DESC, f.file_size DESC"
        if agents_table_exists and agent_runability_table_exists:
            order_by_clause = " ORDER BY (CASE WHEN a.agent_name IS NOT NULL THEN 1 ELSE 0 END) DESC, fa.complexity_score DESC, f.file_size DESC, ar.overall_runability_score DESC"

        query = f"{base_query} {where_clause} {order_by_clause}"

        try:
            cursor.execute(query)
            results = cursor.fetchall()

            files_to_document = []
            for row in results:
                # Map row data to dictionary, handling potential None values and column indices
                file_info = {
                    "file_path": row[0],
                    "file_size": row[1] or 0,
                    "file_extension": row[2],
                    "content_hash": row[3],
                    "modified_time": row[4],
                    "status": row[5],
                    "complexity_score": row[6] or 0,
                    "primary_purpose": row[7],  # From file_analysis
                    "key_functionality": row[8],  # From file_analysis
                    "agent_name": None,
                    "agent_type": None,
                    "runability_score": 0,
                }

                # Dynamically get agent and runability info if tables were joined
                if agents_table_exists and agent_runability_table_exists:
                    # These indices depend on the order of columns in the SELECT statement
                    # and the joins. Adjust if the base_query changes.
                    # Assuming a.agent_name is at index 9, a.agent_type at 10, ar.overall_runability_score at 11
                    # This requires careful alignment with the SQL query.
                    # For simplicity, let's re-fetch agent info if needed, or ensure query returns it.
                    # For now, let's assume the base_query SELECTs them if joined.
                    # A safer approach is to select specific columns by name if using row_factory = sqlite3.Row
                    # Or explicitly list all columns in SELECT and know their indices.
                    # Given the current base_query, we need to adjust indices if agents/runability are joined.
                    # Let's adjust the base_query to include these only if joined.
                    # For now, assuming they are NOT directly in the initial row[0-8]
                    # and will be fetched separately or added to the SELECT if tables exist.

                    # To avoid complex index management, let's just add them if they were part of the SELECT
                    # This requires the SELECT part of the query to be dynamic based on table existence.
                    # For simplicity, I'll assume `file_analysis` is the main join and `agents`/`agent_runability`
                    # would be handled by a more complex query or separate lookup if needed.
                    # Let's stick to the selected code's original intent where agent info was directly available.
                    # The original code implies these columns are always present if agent tables exist.
                    # To make it robust, we'd need to dynamically build the SELECT statement.

                    # For now, let's keep the _calculate_priority_score expecting a tuple
                    # and ensure the tuple passed to it matches the expected structure.
                    # The current select statement only has 9 columns (0-8).
                    # The original _calculate_priority_score expects 14 columns.
                    # This is a mismatch.

                    # Let's modify the base_query to explicitly select agent/runability columns if tables exist.
                    # This means the row indices will change.

                    # Re-evaluating the original `get_files_to_document` in `enhanced_db_client.py`:
                    # It selected: f.file_path, f.file_size, f.file_extension, f.content_hash, f.modified_time, f.file_type, f.status, fa.complexity_score, fa.lines_of_code, fa.classes_found, fa.functions_found, a.agent_name, a.agent_type, ar.overall_runability_score
                    # This means the tuple passed to _calculate_priority_score had 14 elements.
                    # My current SELECT statement only has 9 elements. This needs correction.

                    # Let's rebuild the SELECT statement dynamically to match the original structure.
                    select_columns = [
                        "f.file_path",
                        "f.file_size",
                        "f.file_extension",
                        "f.content_hash",
                        "f.modified_time",
                        "f.status",
                        "fa.complexity_score",
                        "fa.lines_of_code",
                        "fa.classes_found",
                        "fa.functions_found",  # These need to be added to file_analysis schema if not there
                    ]
                    join_clauses = [
                        "LEFT JOIN file_analysis fa ON f.file_path = fa.file_path"
                    ]
                    agent_columns = [
                        "NULL",
                        "NULL",
                        "NULL",
                    ]  # Default NULLs for agent, agent_type, runability_score

                    if agents_table_exists:
                        agent_columns[0] = "a.agent_name"
                        agent_columns[1] = "a.agent_type"
                        join_clauses.append(
                            "LEFT JOIN agents a ON f.file_path = a.file_path"
                        )
                    if agent_runability_table_exists:
                        agent_columns[2] = "ar.overall_runability_score"
                        # This join assumes 'a' is already joined for 'agent_name'
                        if (
                            agents_table_exists
                        ):  # Only add if agents table is also joined
                            join_clauses.append(
                                "LEFT JOIN agent_runability ar ON a.agent_name = ar.agent_name"
                            )
                        else:  # If agents table doesn't exist but runability does, this path is unlikely or needs different join
                            pass  # Handle this edge case if necessary, for now, assume agents table is prerequisite

                    # Add agent columns to select_columns, ensuring they are at the end as per original structure
                    select_columns.extend(agent_columns)

                    # Reconstruct base_query
                    base_query = f"SELECT {', '.join(select_columns)} FROM files f {' '.join(join_clauses)}"

                    # Rerun cursor.execute with the new query
                    cursor.execute(f"{base_query} {where_clause} {order_by_clause}")
                    results = cursor.fetchall()
                    # Re-process results with new column indices
                    files_to_document = []
                    for row in results:
                        file_info = {
                            "file_path": row[0],
                            "file_size": row[1] or 0,
                            "file_extension": row[2],
                            "content_hash": row[3],
                            "modified_time": row[4],
                            "status": row[5],
                            "complexity_score": row[6] or 0,
                            "lines_of_code": row[7] or 0,  # Assuming fa.lines_of_code
                            "classes_found": row[8],  # Assuming fa.classes_found
                            "functions_found": row[9],  # Assuming fa.functions_found
                            "agent_name": row[10],  # a.agent_name
                            "agent_type": row[11],  # a.agent_type
                            "runability_score": row[12]
                            or 0,  # ar.overall_runability_score
                            "priority_score": self._calculate_priority_score(
                                row
                            ),  # Pass the full row
                        }
                        files_to_document.append(file_info)

        except sqlite3.Error as e:
            print(f"Error executing query in get_files_to_document: {e}")
            return []
        finally:
            conn.close()

        # Sort by priority score
        files_to_document.sort(key=lambda x: x["priority_score"], reverse=True)

        return files_to_document

    def _calculate_priority_score(self, row: tuple) -> float:
        """
        Calculate priority score based on multiple factors.
        This function expects the row tuple to have 13 elements, matching the
        dynamic SELECT statement in get_files_to_document.
        Indices:
        0: file_path
        1: file_size
        2: file_extension
        3: content_hash
        4: modified_time
        5: status
        6: complexity_score
        7: lines_of_code
        8: classes_found
        9: functions_found
        10: agent_name
        11: agent_type
        12: runability_score
        """
        # Ensure row has enough elements to prevent IndexError
        if len(row) < 13:
            # Fallback for incomplete row data, or log an error
            return 0.0

        complexity = row[6] or 0
        size = row[1] or 0
        is_agent = 1 if row[10] else 0  # Check agent_name (index 10)
        runability = row[12] or 0  # Check runability_score (index 12)

        # Priority scoring algorithm
        priority_score = (
            complexity * 2.0  # Complexity is important
            + (size / 1000) * 0.5  # Size factor (scaled)
            + is_agent * 5.0  # Agents get priority
            + runability * 0.5  # Runnable agents get bonus
        )

        return min(priority_score, 10.0)  # Cap at 10

    def get_documentation_progress(self) -> Dict[str, Any]:
        """Get comprehensive documentation progress statistics."""
        conn = self.db_config.get_connection("file_tracker", read_only=True)
        if not conn:
            print(
                "Failed to connect to file_tracker database for documentation progress."
            )
            return {"error": "Database not accessible"}

        cursor = conn.cursor()
        progress_stats = {}

        try:
            # Overall progress for Python files
            cursor.execute("SELECT COUNT(*) FROM files WHERE file_extension = '.py'")
            total_python_files = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM files WHERE file_extension = '.py' AND status = 'documented'"
            )
            documented_files = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM files WHERE file_extension = '.py' AND (status = 'pending' OR status IS NULL OR status = 'cataloged')"
            )
            pending_files = cursor.fetchone()[0]

            progress_stats["overall_progress"] = {
                "total_python_files": total_python_files,
                "documented_files": documented_files,
                "pending_files": pending_files,
                "completion_percentage": (documented_files / max(1, total_python_files))
                * 100,
            }

            # Agent-specific progress (if 'agents' table exists)
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='agents'"
            )
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM agents")
                total_agents = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT COUNT(*) FROM agents a
                    JOIN files f ON a.file_path = f.file_path
                    WHERE f.status = 'documented'
                """)
                documented_agents = cursor.fetchone()[0]

                progress_stats["agent_progress"] = {
                    "total_agents": total_agents,
                    "documented_agents": documented_agents,
                    "agent_completion_percentage": (
                        documented_agents / max(1, total_agents)
                    )
                    * 100,
                }
            else:
                progress_stats["agent_progress"] = {
                    "total_agents": 0,
                    "documented_agents": 0,
                    "agent_completion_percentage": 0.0,
                }

            # Complexity distribution (from file_analysis table)
            cursor.execute("""
                SELECT
                    COUNT(CASE WHEN fa.complexity_score >= 8 THEN 1 END) as high_complexity,
                    COUNT(CASE WHEN fa.complexity_score BETWEEN 4 AND 7 THEN 1 END) as medium_complexity,
                    COUNT(CASE WHEN fa.complexity_score < 4 THEN 1 END) as low_complexity
                FROM file_analysis fa
                JOIN files f ON fa.file_path = f.file_path
                WHERE f.file_extension = '.py'
            """)
            complexity_stats = cursor.fetchone()
            progress_stats["complexity_distribution"] = {
                "high_complexity": complexity_stats[0] or 0,
                "medium_complexity": complexity_stats[1] or 0,
                "low_complexity": complexity_stats[2] or 0,
            }

            # Recent documentation activity (from file_operations table)
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='file_operations'"
            )
            if cursor.fetchone():
                cursor.execute("""
                    SELECT COUNT(*) FROM file_operations
                    WHERE operation_type LIKE '%DOC%' OR operation_type = 'documented'
                """)
                recent_doc_operations = cursor.fetchone()[0]
                progress_stats["recent_activity"] = {
                    "documentation_operations": recent_doc_operations
                }
            else:
                progress_stats["recent_activity"] = {"documentation_operations": 0}

        except sqlite3.Error as e:
            print(f"Error getting documentation progress: {e}")
            progress_stats["error"] = str(e)
        finally:
            conn.close()
        return progress_stats

    def update_documentation_status(
        self, file_path: str, status: str, doc_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update documentation status with comprehensive tracking.
        Logs the operation to file_operations table.

        Args:
            file_path: File being documented
            status: New status (documented, in_progress, error, etc.)
            doc_metadata: Additional documentation metadata (will be JSON dumped)
        """
        conn = self.db_config.get_connection("file_tracker", read_only=False)
        if not conn:
            print(
                "Failed to connect to file_tracker database to update documentation status."
            )
            return

        cursor = conn.cursor()
        try:
            # Update file status in 'files' table
            cursor.execute(
                """
                UPDATE files
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
            """,
                (status, file_path),
            )

            # Log the documentation operation in 'file_operations' table
            # Ensure file_operations table exists (handled by DatabaseConfig.enhance_database_schema)
            notes = (
                json.dumps(doc_metadata)
                if doc_metadata
                else "Documentation status updated"
            )
            cursor.execute(
                """
                INSERT INTO file_operations
                (file_path, operation_type, notes, timestamp)
                VALUES (?, ?, ?, julianday('now'))
            """,
                (file_path, f"DOCUMENTATION_{status.upper()}", notes),
            )

            conn.commit()
            print(
                f"Updated documentation status for {Path(file_path).name} to '{status}'"
            )
        except sqlite3.Error as e:
            print(f"Error updating documentation status for {file_path}: {e}")
            conn.rollback()
        finally:
            conn.close()

    def store_documentation_results(
        self, file_path: str, doc_results: Dict[str, Any]
    ) -> None:
        """
        Store comprehensive documentation results in the file_analysis table.
        This is a more detailed update after documentation generation.

        Args:
            file_path: File that was documented
            doc_results: Results including docstrings, rst files, etc.
                         (will be JSON dumped into analysis_notes)
        """
        conn = self.db_config.get_connection("file_tracker", read_only=False)
        if not conn:
            print(
                "Failed to connect to file_tracker database to store documentation results."
            )
            return

        cursor = conn.cursor()
        try:
            # Update or insert file analysis with documentation info
            # This assumes file_analysis table has 'analysis_notes' for storing JSON
            cursor.execute(
                """
                INSERT OR REPLACE INTO file_analysis (
                    file_path, file_name, file_type, analysis_timestamp,
                    analysis_notes, primary_purpose -- Add primary_purpose if available in doc_results
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    file_path,
                    Path(file_path).name,
                    doc_results.get("file_type", "python_documented"),  # Default type
                    datetime.now().timestamp(),
                    json.dumps(doc_results),
                    doc_results.get(
                        "primary_purpose", "Documentation Generated"
                    ),  # Example
                ),
            )

            # Log successful documentation completion
            cursor.execute(
                """
                INSERT INTO file_operations
                (file_path, operation_type, notes, timestamp)
                VALUES (?, ?, ?, julianday('now'))
            """,
                (
                    file_path,
                    "DOCUMENTATION_COMPLETED",
                    f"Generated documentation for {doc_results.get('functions_documented', 0)} functions",
                ),
            )

            conn.commit()
            print(f"Stored documentation results for {Path(file_path).name}")
        except sqlite3.Error as e:
            print(f"Error storing documentation results for {file_path}: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_documentation_recommendations(self) -> List[Dict[str, Any]]:
        """
        Get intelligent recommendations for what to document next.
        Leverages get_files_to_document to get prioritized list.

        Returns:
            List[Dict[str, Any]]: A list of recommended files with reasons and estimated effort.
        """
        # Get all files that need documentation, prioritized
        files = self.get_files_to_document("all")

        recommendations = []

        # Generate recommendations based on the prioritized files
        for file_info in files[:10]:  # Consider top N files for recommendations
            reasons = []

            if file_info.get("agent_name"):
                reasons.append(f"Agent file: {file_info['agent_name']}")

            if file_info.get("complexity_score", 0) > 7:
                reasons.append(f"High complexity: {file_info['complexity_score']}/10")

            if file_info.get("file_size", 0) > 20000:
                reasons.append(f"Large file: {file_info['file_size']:,} bytes")

            if file_info.get("runability_score", 0) > 8:
                reasons.append(f"Highly runnable: {file_info['runability_score']}/10")

            if not reasons:
                reasons.append("Standard documentation candidate")

            recommendations.append(
                {
                    "file_path": file_info["file_path"],
                    "file_name": Path(file_info["file_path"]).name,
                    "priority_score": file_info["priority_score"],
                    "reasons": reasons,
                    "estimated_effort": self._estimate_documentation_effort(file_info),
                }
            )

        return recommendations

    def _estimate_documentation_effort(self, file_info: Dict[str, Any]) -> str:
        """Estimate documentation effort based on file characteristics."""
        size = file_info.get("file_size", 0)
        complexity = file_info.get("complexity_score", 0)

        if size > 50000 or complexity > 8:
            return "High (2-3 hours)"
        elif size > 10000 or complexity > 5:
            return "Medium (1-2 hours)"
        else:
            return "Low (30-60 minutes)"

    def generate_documentation_report(self) -> str:
        """Generate a comprehensive documentation status report."""
        progress = self.get_documentation_progress()  # noqa: F841
        recommendations = self.get_documentation_recommendations()

        report = """
DOCUMENTATION STATUS REPORT
{'=' * 40}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERALL PROGRESS
• Python Files: {progress['overall_progress']['total_python_files']:,}
• Documented: {progress['overall_progress']['documented_files']:,}
• Pending: {progress['overall_progress']['pending_files']:,}
• Completion: {progress['overall_progress']['completion_percentage']:.1f}%

AGENT DOCUMENTATION
• Total Agents: {progress['agent_progress']['total_agents']}
• Documented: {progress['agent_progress']['documented_agents']}
• Agent Completion: {progress['agent_progress']['agent_completion_percentage']:.1f}%

COMPLEXITY BREAKDOWN
• High Complexity: {progress['complexity_distribution']['high_complexity']} files
• Medium Complexity: {progress['complexity_distribution']['medium_complexity']} files
• Low Complexity: {progress['complexity_distribution']['low_complexity']} files

TOP RECOMMENDATIONS
"""

        for i, rec in enumerate(recommendations[:5], 1):
            reasons_str = ", ".join(rec["reasons"])
            report += (
                f"{i}. {rec['file_name']} (Priority: {rec['priority_score']:.1f})\n"
            )
            report += f"   Reasons: {reasons_str}\n"
            report += f"   Effort: {rec['estimated_effort']}\n\n"

        return report


# Legacy compatibility functions (can be removed if no longer needed by external callers)
# These would typically be removed in a fully refactored system.
def get_files_to_document_legacy() -> List[Tuple[str, str]]:
    """Legacy compatibility function."""
    # This requires an instance of DatabaseConfig to be created here,
    # or passed globally, which is less ideal.
    # For a clean refactor, these legacy functions should be removed.
    # For now, we'll create a dummy db_config.
    print("WARNING: Using legacy get_files_to_document_legacy. Please update callers.")
    db_config = DatabaseConfig()  # This might re-initialize paths, etc.
    client = EnhancedDocumentationClient(db_config)
    files = client.get_files_to_document("all")
    return [(f["file_path"], f["content_hash"]) for f in files]


def update_doc_status_legacy(file_path: str, new_status: str):
    """Legacy compatibility function."""
    print("WARNING: Using legacy update_doc_status_legacy. Please update callers.")
    db_config = DatabaseConfig()
    client = EnhancedDocumentationClient(db_config)
    client.update_documentation_status(file_path, new_status)


def store_analysis_results_legacy(file_path: str, analysis_data: dict):
    """Legacy compatibility function."""
    print("WARNING: Using legacy store_analysis_results_legacy. Please update callers.")
    db_config = DatabaseConfig()
    client = EnhancedDocumentationClient(db_config)
    client.store_documentation_results(file_path, analysis_data)


if __name__ == "__main__":
    print("--- Testing EnhancedDocumentationClient ---")

    # Initialize core components
    db_config = DatabaseConfig()
    # No AIClient or AIAnalyzer directly needed for this client's core functions
    # but they are used by other modules that populate the DB this client reads.

    client = EnhancedDocumentationClient(db_config)

    print("\n--- Documentation Progress ---")
    progress = client.get_documentation_progress()
    print(" Documentation Progress:")
    print(
        f"   • {progress['overall_progress']['completion_percentage']:.1f}% of Python files documented"
    )
    print(
        f"   • {progress['agent_progress']['agent_completion_percentage']:.1f}% of agents documented"
    )

    print("\n--- High Priority Files ---")
    high_priority = client.get_files_to_document("high")
    print(f" High Priority Files: {len(high_priority)}")
    for i, file_info in enumerate(high_priority[:5], 1):
        name = Path(file_info["file_path"]).name
        print(f"   {i}. {name} (Priority: {file_info['priority_score']:.1f})")

    print("\n--- Top Recommendation ---")
    recommendations = client.get_documentation_recommendations()
    if recommendations:
        rec = recommendations[0]
        print(f"    {rec['file_name']}")
        print(f"    Priority Score: {rec['priority_score']:.1f}")
        print(f"    Reasons: {', '.join(rec['reasons'])}")
        print(f"    Estimated Effort: {rec['estimated_effort']}")
    else:
        print("No documentation recommendations found.")

    # Generate full report
    report_file_name = "documentation_status_report.txt"
    report_output_path = db_config.project_root / "reports" / report_file_name
    report_output_path.parent.mkdir(exist_ok=True)  # Ensure directory exists

    try:
        with open(report_output_path, "w", encoding="utf-8") as f:
            f.write(client.generate_documentation_report())
        print(f"\nFull report saved to: {report_output_path}")
    except Exception as e:
        print(f"Error saving documentation report: {e}")
