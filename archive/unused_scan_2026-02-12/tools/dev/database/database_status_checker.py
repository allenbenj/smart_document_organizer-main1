#!/usr/bin/env python3
"""
Database Status Verification Script
===================================

Comprehensive checker for all databases across the Coding_Project ecosystem:
- Project tools databases (code_database.db, file_tracker_new.db)
- Legal AI databases (project_status.db, comprehensive_project_status.db)
- Database maintenance tools status
- Integration and synchronization verification

Author: AI Assistant (External API Coordination)
Date: 2024
"""

import json
import os  # noqa: E402
import sqlite3  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict  # noqa: E402


class DatabaseStatusChecker:
    """Comprehensive database status and maintenance verification."""

    def __init__(self):
        """Initialize the database status checker."""
        self.project_root = Path("/mnt/e/Coding_Project")

        # Database locations
        self.databases = {
            "project_tools": {
                "code_database": str(
                    self.project_root / "project_tools/data/code_database.db"
                ),
                "file_tracker": str(
                    self.project_root / "project_tools/data/file_tracker_new.db"
                ),
            },
            "legal_ai": {
                "project_status": str(
                    self.project_root / "legal_ai/storage/databases/project_status.db"
                ),
                "comprehensive_status": str(
                    self.project_root
                    / "legal_ai/storage/databases/comprehensive_project_status.db"
                ),
            },
        }

        # Database maintenance tools
        self.maintenance_tools = {
            "code_database_manager": str(
                self.project_root
                / "project_tools/database_tools/core/code_database_manager.py"
            ),
            "enhanced_db_analyzer": str(
                self.project_root
                / "project_tools/database_tools/core/enhanced_db_analyzer.py"
            ),
            "ai_database_updater": str(
                self.project_root
                / "project_tools/database_tools/utilities/ai_database_updater.py"
            ),
            "realtime_monitor": str(
                self.project_root
                / "project_tools/database_tools/monitoring/realtime_db_monitor_gui.py"
            ),
            "database_api_server": str(
                self.project_root
                / "project_tools/database_tools/viewers/database_api_server.py"
            ),
        }

    def check_database_health(self, db_path: str) -> Dict[str, Any]:
        """
        Check the health status of a specific database.

        Args:
            db_path: Path to the database file

        Returns:
            Dictionary with health status information
        """
        result = {
            "path": db_path,
            "exists": False,
            "accessible": False,
            "tables": [],
            "table_count": 0,
            "record_counts": {},
            "file_size_mb": 0,
            "last_modified": None,
            "age_hours": 0,
            "errors": [],
        }

        try:
            # Check if file exists
            if not os.path.exists(db_path):
                result["errors"].append(f"Database file does not exist: {db_path}")
                return result

            result["exists"] = True

            # Get file info
            stat = os.stat(db_path)
            result["file_size_mb"] = stat.st_size / (1024 * 1024)
            result["last_modified"] = datetime.fromtimestamp(stat.st_mtime)
            result["age_hours"] = (
                datetime.now() - result["last_modified"]
            ).total_seconds() / 3600

            # Try to connect and get table info
            conn = sqlite3.connect(db_path, timeout=5.0)
            cursor = conn.cursor()

            # Get table list
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            result["tables"] = [table[0] for table in tables]
            result["table_count"] = len(result["tables"])
            result["accessible"] = True

            # Get record counts for each table
            for table_name in result["tables"]:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                    count = cursor.fetchone()[0]
                    result["record_counts"][table_name] = count
                except Exception as e:
                    result["record_counts"][table_name] = f"Error: {str(e)}"

            conn.close()

        except sqlite3.Error as e:
            result["errors"].append(f"SQLite error: {str(e)}")
        except Exception as e:
            result["errors"].append(f"General error: {str(e)}")

        return result

    def check_maintenance_tools(self) -> Dict[str, Any]:
        """
        Check the status of database maintenance tools.

        Returns:
            Dictionary with maintenance tools status
        """
        tools_status = {}

        for tool_name, tool_path in self.maintenance_tools.items():
            status = {
                "path": tool_path,
                "exists": os.path.exists(tool_path),
                "file_size": 0,
                "last_modified": None,
                "is_executable": False,
            }

            if status["exists"]:
                stat = os.stat(tool_path)
                status["file_size"] = stat.st_size
                status["last_modified"] = datetime.fromtimestamp(stat.st_mtime)
                status["is_executable"] = os.access(tool_path, os.X_OK)

            tools_status[tool_name] = status

        return tools_status

    def analyze_database_integration(self) -> Dict[str, Any]:
        """
        Analyze integration between different database systems.

        Returns:
            Dictionary with integration analysis
        """
        integration_analysis = {
            "project_tools_health": {},
            "legal_ai_health": {},
            "sync_issues": [],
            "recommendations": [],
        }

        # Check project tools databases
        for db_name, db_path in self.databases["project_tools"].items():
            integration_analysis["project_tools_health"][db_name] = (
                self.check_database_health(db_path)
            )

        # Check legal AI databases
        for db_name, db_path in self.databases["legal_ai"].items():
            integration_analysis["legal_ai_health"][db_name] = (
                self.check_database_health(db_path)
            )

        # Analyze for sync issues
        all_dbs = {**self.databases["project_tools"], **self.databases["legal_ai"]}

        # Check for stale databases (not updated in 24 hours)
        for db_name, db_path in all_dbs.items():
            health = self.check_database_health(db_path)
            if health["exists"] and health["age_hours"] > 24:
                integration_analysis["sync_issues"].append(
                    f"{db_name}: Not updated in {health['age_hours']:.1f} hours"
                )

        # Generate recommendations
        if integration_analysis["sync_issues"]:
            integration_analysis["recommendations"].append(
                "Some databases appear stale - consider running maintenance tools"
            )

        # Check if both project_tools and legal_ai databases exist
        pt_exists = any(
            health["exists"]
            for health in integration_analysis["project_tools_health"].values()
        )
        la_exists = any(
            health["exists"]
            for health in integration_analysis["legal_ai_health"].values()
        )

        if pt_exists and la_exists:
            integration_analysis["recommendations"].append(
                "Consider implementing cross-database synchronization"
            )

        return integration_analysis

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive database status report.

        Returns:
            Complete status report
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "databases": {},
            "maintenance_tools": self.check_maintenance_tools(),
            "integration_analysis": self.analyze_database_integration(),
            "summary": {
                "total_databases": 0,
                "healthy_databases": 0,
                "accessible_databases": 0,
                "stale_databases": 0,
                "total_records": 0,
            },
        }

        # Check all databases
        all_dbs = {**self.databases["project_tools"], **self.databases["legal_ai"]}

        for db_name, db_path in all_dbs.items():
            health = self.check_database_health(db_path)
            report["databases"][db_name] = health

            # Update summary
            report["summary"]["total_databases"] += 1

            if health["exists"] and health["accessible"] and not health["errors"]:
                report["summary"]["healthy_databases"] += 1

            if health["accessible"]:
                report["summary"]["accessible_databases"] += 1

            if health["exists"] and health["age_hours"] > 24:
                report["summary"]["stale_databases"] += 1

            # Count total records
            for count in health["record_counts"].values():
                if isinstance(count, int):
                    report["summary"]["total_records"] += count

        return report

    def print_status_summary(self, report: Dict[str, Any]):  # noqa: C901
        """Print a human-readable status summary."""
        print("=" * 60)
        print("DATABASE STATUS VERIFICATION REPORT")
        print("=" * 60)
        print(f"Generated: {report['generated_at']}")
        print()

        # Summary
        summary = report["summary"]
        print("SUMMARY:")
        print(f"  Total Databases: {summary['total_databases']}")
        print(f"  Healthy: {summary['healthy_databases']}")
        print(f"  Accessible: {summary['accessible_databases']}")
        print(f"  Stale (>24h): {summary['stale_databases']}")
        print(f"  Total Records: {summary['total_records']:,}")
        print()

        # Database details
        print("DATABASE STATUS:")
        for db_name, health in report["databases"].items():
            status_icon = (
                "✅"
                if health["exists"] and health["accessible"] and not health["errors"]
                else "❌"
            )
            print(f"  {status_icon} {db_name}")

            if health["exists"]:
                print(f"    Size: {health['file_size_mb']:.2f} MB")
                print(f"    Tables: {health['table_count']}")
                print(f"    Last Modified: {health['last_modified']}")
                print(f"    Age: {health['age_hours']:.1f} hours")

                if health["record_counts"]:
                    print(f"    Records: {dict(health['record_counts'])}")
            else:
                print("    Status: Missing")

            if health["errors"]:
                for error in health["errors"]:
                    print(f"    Error: {error}")
            print()

        # Maintenance tools
        print("MAINTENANCE TOOLS:")
        for tool_name, status in report["maintenance_tools"].items():
            icon = "✅" if status["exists"] else "❌"
            print(f"  {icon} {tool_name}")
            if status["exists"]:
                print(f"    Size: {status['file_size']:,} bytes")
                print(f"    Modified: {status['last_modified']}")
            else:
                print("    Status: Missing")
        print()

        # Integration analysis
        if report["integration_analysis"]["sync_issues"]:
            print("SYNC ISSUES:")
            for issue in report["integration_analysis"]["sync_issues"]:
                print(f"  ⚠️  {issue}")
            print()

        if report["integration_analysis"]["recommendations"]:
            print("RECOMMENDATIONS:")
            for rec in report["integration_analysis"]["recommendations"]:
                print(f"  💡 {rec}")
            print()

    def export_report(self, report: Dict[str, Any], output_path: str = None) -> str:
        """Export report to JSON file."""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = (
                f"/mnt/e/Coding_Project/database_status_report_{timestamp}.json"
            )

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        return output_path


def main():
    """Run comprehensive database status check."""
    checker = DatabaseStatusChecker()

    print("Performing comprehensive database status check...")
    print()

    # Generate report
    report = checker.generate_comprehensive_report()

    # Print summary
    checker.print_status_summary(report)

    # Export report
    report_path = checker.export_report(report)
    print(f"Full report exported to: {report_path}")


if __name__ == "__main__":
    main()
