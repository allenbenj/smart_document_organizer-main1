import json
import sqlite3  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

# Import the new centralized DatabaseConfig
from core.database_config import DatabaseConfig  # noqa: E402


class DatabaseAnalyzer:
    """
    Advanced analyzer for the file tracking database.
    This class now uses the centralized DatabaseConfig for database connections.
    """

    def __init__(self, db_config: DatabaseConfig):
        """
        Initializes the DatabaseAnalyzer with a DatabaseConfig instance.

        Args:
            db_config (DatabaseConfig): Centralized database configuration.
        """
        self.db_config = db_config
        self.db_path = self.db_config.get_db_path(
            "file_tracker"
        )  # Assuming analysis is primarily for file_tracker_new.db

        if not self.db_path:
            raise ValueError(
                "File tracker database path is not configured in DatabaseConfig."
            )

        # Ensure the parent directory exists (handled by DatabaseConfig, but good to double check)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"DatabaseAnalyzer initialized for DB: {self.db_path}")

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""

        conn = self.db_config.get_connection("file_tracker", read_only=True)
        if not conn:
            print("Failed to connect to file_tracker database for comprehensive stats.")
            return {"error": "Database not accessible"}

        cursor = conn.cursor()
        stats = {}

        try:
            # Basic counts
            cursor.execute("SELECT COUNT(*) FROM files")
            stats["total_files"] = cursor.fetchone()[0]

            # Check if 'agents' table exists before querying
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='agents'"
            )
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM agents")
                stats["total_agents"] = cursor.fetchone()[0]
            else:
                stats["total_agents"] = 0  # Default if table doesn't exist

            # Check if 'file_operations' table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='file_operations'"
            )
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM file_operations")
                stats["total_operations"] = cursor.fetchone()[0]
            else:
                stats["total_operations"] = 0

            cursor.execute("SELECT COUNT(*) FROM file_analysis")
            stats["analyzed_files"] = cursor.fetchone()[0]

            # Check if 'agent_runability' table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_runability'"
            )
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM agent_runability")
                stats["tested_agents"] = cursor.fetchone()[0]
            else:
                stats["tested_agents"] = 0

            # File size analytics
            cursor.execute(
                "SELECT SUM(file_size), AVG(file_size), MAX(file_size) FROM files WHERE file_size > 0"
            )
            total_size, avg_size, max_size = cursor.fetchone()
            stats["file_sizes"] = {
                "total_bytes": total_size or 0,
                "total_mb": (total_size or 0) / (1024 * 1024),
                "average_bytes": avg_size or 0,
                "largest_file_bytes": max_size or 0,
            }

            # File type distribution
            cursor.execute(
                "SELECT file_extension, COUNT(*) FROM files GROUP BY file_extension ORDER BY COUNT(*) DESC"
            )
            stats["file_types"] = dict(cursor.fetchall())

            # Agent runability summary (only if agent_runability table exists)
            if stats["tested_agents"] > 0:
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN overall_runability_score >= 8 THEN 1 ELSE 0 END) as fully_runnable,
                        SUM(CASE WHEN overall_runability_score BETWEEN 5 AND 7 THEN 1 ELSE 0 END) as partially_runnable,
                        SUM(CASE WHEN overall_runability_score < 5 THEN 1 ELSE 0 END) as needs_work
                    FROM agent_runability
                """)
                runability = cursor.fetchone()
                stats["agent_runability"] = {
                    "fully_runnable": runability[0] or 0,
                    "partially_runnable": runability[1] or 0,
                    "needs_work": runability[2] or 0,
                }
            else:
                stats["agent_runability"] = {
                    "fully_runnable": 0,
                    "partially_runnable": 0,
                    "needs_work": 0,
                }

            # Recent operations (only if file_operations table exists)
            if stats["total_operations"] > 0:
                cursor.execute("""
                    SELECT operation_type, COUNT(*)
                    FROM file_operations
                    GROUP BY operation_type
                    ORDER BY COUNT(*) DESC
                """)
                stats["operations_by_type"] = dict(cursor.fetchall())
            else:
                stats["operations_by_type"] = {}

            # Project health indicators
            cursor.execute("SELECT COUNT(*) FROM files WHERE status = 'completed'")
            completed_files = cursor.fetchone()[0]
            stats["project_health"] = {
                "completion_rate": completed_files / max(1, stats["total_files"]),
                "analysis_coverage": stats["analyzed_files"]
                / max(1, stats["total_files"]),
                "agent_test_coverage": stats["tested_agents"]
                / max(1, stats["total_agents"]),
            }

        except sqlite3.Error as e:
            print(f"Error getting comprehensive stats: {e}")
            stats["error"] = str(e)
        finally:
            conn.close()
        return stats

    def get_operation_timeline(self) -> List[Dict[str, Any]]:
        """Get chronological timeline of all operations."""

        conn = self.db_config.get_connection("file_tracker", read_only=True)
        if not conn:
            print("Failed to connect to file_tracker database for operation timeline.")
            return []

        cursor = conn.cursor()
        timeline = []
        try:
            # Check if 'file_operations' table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='file_operations'"
            )
            if not cursor.fetchone():
                return []  # Table does not exist

            cursor.execute("""
                SELECT timestamp, operation_type, file_path, notes
                FROM file_operations
                ORDER BY timestamp DESC
                LIMIT 50
            """)

            for row in cursor.fetchall():
                # new_size column was not consistently present in file_operations
                # Removed it from query and added explicit check for notes length
                timeline.append(
                    {
                        "timestamp": row[0],
                        "operation": row[1],
                        "file_path": row[2],
                        "notes": (
                            row[3][:100] + "..."
                            if row[3] and len(row[3]) > 100
                            else row[3]
                        ),
                    }
                )
        except sqlite3.Error as e:
            print(f"Error getting operation timeline: {e}")
        finally:
            conn.close()
        return timeline

    def get_agent_insights(self) -> Dict[str, Any]:
        """Get detailed insights about agents."""

        conn = self.db_config.get_connection("file_tracker", read_only=True)
        if not conn:
            print("Failed to connect to file_tracker database for agent insights.")
            return {"error": "Database not accessible"}

        cursor = conn.cursor()
        agents = []
        insights = {
            "agents": [],
            "summary": {
                "total_lines_of_code": 0,
                "total_functions": 0,
                "average_runability_score": 0.0,
                "top_agent_by_size": None,
                "most_runnable_agent": None,
            },
        }

        try:
            # Check if 'agents' and 'agent_runability' tables exist
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='agents'"
            )
            agents_table_exists = cursor.fetchone()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_runability'"
            )
            runability_table_exists = cursor.fetchone()

            if not agents_table_exists:
                return insights  # No agents table, return empty insights

            query = """
                SELECT
                    a.agent_name,
                    a.agent_type,
                    a.lines_of_code,
                    a.functions_count,
                    r.overall_runability_score,
                    r.syntax_valid,
                    r.imports_resolvable,
                    r.dependencies_available
                FROM agents a
            """
            if runability_table_exists:
                query += "LEFT JOIN agent_runability r ON a.agent_name = r.agent_name"
            query += " ORDER BY a.agent_name ASC"  # Order by name for consistency

            cursor.execute(query)

            for row in cursor.fetchall():
                agent_info = {
                    "name": row[0],
                    "type": row[1],
                    "lines_of_code": row[2] or 0,
                    "functions_count": row[3] or 0,
                    "runability_score": row[4] or 0,
                    "syntax_valid": bool(row[5]) if row[5] is not None else None,
                    "imports_resolvable": bool(row[6]) if row[6] is not None else None,
                    "dependencies_available": (
                        bool(row[7]) if row[7] is not None else None
                    ),
                }
                agents.append(agent_info)

            # Calculate insights
            if agents:
                total_lines = sum(a["lines_of_code"] for a in agents)
                total_functions = sum(a["functions_count"] for a in agents)
                runnable_agents = [
                    a
                    for a in agents
                    if a["runability_score"] is not None and a["runability_score"] > 0
                ]
                avg_runability = sum(
                    a["runability_score"] for a in runnable_agents
                ) / max(1, len(runnable_agents))

                insights["agents"] = agents
                insights["summary"] = {
                    "total_lines_of_code": total_lines,
                    "total_functions": total_functions,
                    "average_runability_score": avg_runability,
                    "top_agent_by_size": (
                        max(agents, key=lambda x: x["lines_of_code"])["name"]
                        if agents
                        else None
                    ),
                    "most_runnable_agent": (
                        max(agents, key=lambda x: x["runability_score"])["name"]
                        if runnable_agents
                        else None
                    ),
                }

        except sqlite3.Error as e:
            print(f"Error getting agent insights: {e}")
            insights["error"] = str(e)
        finally:
            conn.close()
        return insights

    def get_file_hotspots(self) -> Dict[str, Any]:
        """Identify file hotspots and patterns."""

        conn = self.db_config.get_connection("file_tracker", read_only=True)
        if not conn:
            print("Failed to connect to file_tracker database for file hotspots.")
            return {"error": "Database not accessible"}

        cursor = conn.cursor()
        hotspot_files = []
        largest_files = []
        directory_stats = []

        try:
            # Most operated-on files (only if file_operations table exists)
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='file_operations'"
            )
            if cursor.fetchone():
                cursor.execute("""
                    SELECT file_path, COUNT(*) as operation_count
                    FROM file_operations
                    GROUP BY file_path
                    ORDER BY COUNT(*) DESC
                    LIMIT 10
                """)
                hotspot_files = [
                    {"path": row[0], "operations": row[1]} for row in cursor.fetchall()
                ]

            # Largest files
            cursor.execute("""
                SELECT file_path, file_size, file_extension
                FROM files
                WHERE file_size > 0
                ORDER BY file_size DESC
                LIMIT 10
            """)
            largest_files = [
                {"path": row[0], "size": row[1], "extension": row[2]}
                for row in cursor.fetchall()
            ]

            # Directory analysis (assuming parent_directory column exists or can be derived)
            # If parent_directory is not a column, we need to parse file_path
            # For now, let's assume it might not exist and derive it
            cursor.execute("""
                SELECT file_path, file_size
                FROM files
                WHERE file_path IS NOT NULL
            """)
            all_files_for_dir_analysis = cursor.fetchall()

            dir_agg_stats: Dict[str, Dict[str, Any]] = {}
            for file_path_str, file_size in all_files_for_dir_analysis:
                file_path_obj = Path(file_path_str)
                # Ensure we get a parent directory, not just the root drive on Windows
                if file_path_obj.parent == file_path_obj.anchor:  # e.g., C:\
                    parent_dir = str(file_path_obj.parent)
                else:
                    parent_dir = str(file_path_obj.parent)

                if parent_dir not in dir_agg_stats:
                    dir_agg_stats[parent_dir] = {
                        "directory": parent_dir,
                        "files": 0,
                        "total_size": 0,
                    }
                dir_agg_stats[parent_dir]["files"] += 1
                dir_agg_stats[parent_dir]["total_size"] += file_size or 0

            # Convert to list and sort
            directory_stats = sorted(
                list(dir_agg_stats.values()), key=lambda x: x["files"], reverse=True
            )[:10]

        except sqlite3.Error as e:
            print(f"Error getting file hotspots: {e}")
        finally:
            conn.close()

        return {
            "hotspot_files": hotspot_files,
            "largest_files": largest_files,
            "directory_stats": directory_stats,
        }

    def generate_health_report(self) -> str:
        """Generate a comprehensive health report."""

        stats = self.get_comprehensive_stats()
        agent_insights = self.get_agent_insights()  # noqa: F841
        hotspots = self.get_file_hotspots()

        if "error" in stats:
            return f"Error generating health report: {stats['error']}"

        report = """
FILE TRACKER DATABASE HEALTH REPORT
{'=' * 50}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERVIEW STATISTICS
• Total Files Tracked: {stats['total_files']:,}
• Total Agents: {stats['total_agents']}
• Total Operations: {stats['total_operations']}
• Files Analyzed: {stats['analyzed_files']} ({stats['analyzed_files']/max(1,stats['total_files'])*100:.1f}%)
• Agents Tested: {stats['tested_agents']} ({stats['tested_agents']/max(1,stats['total_agents'])*100:.1f}%)

STORAGE METRICS
• Total Project Size: {stats['file_sizes']['total_mb']:.1f} MB
• Average File Size: {stats['file_sizes']['average_bytes']:,.0f} bytes
• Largest File: {stats['file_sizes']['largest_file_bytes']:,.0f} bytes

FILE TYPE DISTRIBUTION
"""

        for ext, count in list(stats["file_types"].items())[:10]:
            percentage = count / stats["total_files"] * 100
            report += (
                f"• {ext or 'no extension'}: {count:,} files ({percentage:.1f}%)\n"
            )

        report += """
AGENT HEALTH STATUS
• Fully Runnable: {stats['agent_runability']['fully_runnable']} agents
• Partially Runnable: {stats['agent_runability']['partially_runnable']} agents
• Need Work: {stats['agent_runability']['needs_work']} agents
• Average Runability Score: {agent_insights['summary']['average_runability_score']:.1f}/10

PROJECT HEALTH INDICATORS
• File Completion Rate: {stats['project_health']['completion_rate']*100:.1f}%
• Analysis Coverage: {stats['project_health']['analysis_coverage']*100:.1f}%
• Agent Test Coverage: {stats['project_health']['agent_test_coverage']*100:.1f}%

TOP ACTIVITY HOTSPOTS
"""

        if hotspots["hotspot_files"]:
            for i, hotspot in enumerate(hotspots["hotspot_files"][:5], 1):
                report += f"{i}. {Path(hotspot['path']).name}: {hotspot['operations']} operations\n"
        else:
            report += "No file operations recorded.\n"

        report += """
TOP PERFORMERS
• Largest Agent: {agent_insights['summary']['top_agent_by_size'] if agent_insights['summary']['top_agent_by_size'] else 'N/A'} ({agent_insights['summary']['total_lines_of_code']:,} LOC total)
• Most Runnable: {agent_insights['summary']['most_runnable_agent'] if agent_insights['summary']['most_runnable_agent'] else 'N/A'}
• Total Functions: {agent_insights['summary']['total_functions']:,}

RECENT OPERATIONS
"""
        if stats["operations_by_type"]:
            for op_type, count in list(stats["operations_by_type"].items())[:5]:
                report += f"• {op_type}: {count} operations\n"
        else:
            report += "No recent operations recorded.\n"

        return report

    def export_insights_json(
        self, output_file: str = "database_insights.json"
    ) -> Optional[str]:
        """Export all insights to JSON file."""

        insights = {
            "generated_at": datetime.now().isoformat(),
            "stats": self.get_comprehensive_stats(),
            "agent_insights": self.get_agent_insights(),
            "hotspots": self.get_file_hotspots(),
            "timeline": self.get_operation_timeline(),
        }

        # Ensure output directory exists (e.g., in a 'reports' folder within project root)
        output_dir = self.db_config.project_root / "reports"
        output_dir.mkdir(exist_ok=True)
        full_output_path = output_dir / output_file

        try:
            with open(full_output_path, "w", encoding="utf-8") as f:
                json.dump(insights, f, indent=2, default=str)
            print(f"Insights exported to {full_output_path}")
            return str(full_output_path)
        except Exception as e:
            print(f"Failed to export insights to {full_output_path}: {e}")
            return None


def main():
    """Main function for command-line usage."""
    # Initialize DatabaseConfig
    db_config = DatabaseConfig()
    # Pass the db_config instance to the analyzer
    analyzer = DatabaseAnalyzer(db_config)

    print("Analyzing file_tracker.db...")

    # Generate and display health report
    report = analyzer.generate_health_report()
    print(report)

    # Export detailed insights
    json_file = analyzer.export_insights_json()

    print("\nThe file_tracker.db is incredibly comprehensive!")
    if json_file:
        print(f"Detailed insights saved to: {json_file}")
    print("Use this data to guide development priorities")


if __name__ == "__main__":
    main()
