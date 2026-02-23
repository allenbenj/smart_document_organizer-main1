from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DataIntegrityService:
    """Run data integrity checks across file index and unified memory stores."""

    def __init__(
        self,
        file_index_db_path: Path | None = None,
        unified_memory_db_path: Path | None = None,
    ) -> None:
        self.file_index_db_path = file_index_db_path or Path("databases") / "file_index.db"
        self.unified_memory_db_path = (
            unified_memory_db_path or Path("databases") / "unified_memory.db"
        )

    def generate_report(self) -> dict[str, Any]:
        """Generate a single integrity report with actionable recommendations."""
        issues: list[dict[str, Any]] = []

        issues.extend(self._check_file_index_integrity())
        issues.extend(self._check_unified_memory_integrity())

        total_issues = sum(int(item.get("issue_count", 0)) for item in issues)
        severity_rank = {"critical": 3, "warning": 2, "info": 1}
        highest = "info"
        for item in issues:
            sev = str(item.get("severity", "info")).lower()
            if severity_rank.get(sev, 0) > severity_rank.get(highest, 0):
                highest = sev

        return {
            "status": "ok" if total_issues == 0 else "issues_detected",
            "total_checks": len(issues),
            "total_issues": total_issues,
            "highest_severity": highest if total_issues > 0 else "none",
            "issues": issues,
            "actions": [item["recommended_action"] for item in issues if item["issue_count"] > 0],
        }

    def _check_file_index_integrity(self) -> list[dict[str, Any]]:
        if not self.file_index_db_path.exists():
            return [
                self._issue(
                    check_name="file_index_db_missing",
                    issue_count=1,
                    severity="warning",
                    details=f"Database not found: {self.file_index_db_path}",
                    recommended_action=(
                        "Initialize or restore file_index.db and run file scan/indexing "
                        "before using analytics views."
                    ),
                )
            ]

        issues: list[dict[str, Any]] = []
        try:
            with sqlite3.connect(str(self.file_index_db_path)) as conn:
                orphan_analysis_count = self._scalar(
                    conn,
                    """
                    SELECT COUNT(*)
                    FROM file_analysis fa
                    LEFT JOIN files f ON f.file_path = fa.file_path
                    WHERE f.file_path IS NULL
                    """,
                )
                missing_analysis_count = self._scalar(
                    conn,
                    """
                    SELECT COUNT(*)
                    FROM files f
                    LEFT JOIN file_analysis fa ON fa.file_path = f.file_path
                    WHERE fa.file_path IS NULL
                    """,
                )
        except sqlite3.Error as exc:
            logger.error("Failed file index integrity check: %s", exc)
            return [
                self._issue(
                    check_name="file_index_query_error",
                    issue_count=1,
                    severity="critical",
                    details=f"SQLite error while checking file index: {exc}",
                    recommended_action=(
                        "Repair file_index.db (integrity check/restore) and rerun indexing."
                    ),
                )
            ]

        issues.append(
            self._issue(
                check_name="file_analysis_orphans",
                issue_count=orphan_analysis_count,
                severity="warning" if orphan_analysis_count else "info",
                details=(
                    "Rows in file_analysis reference file_path values missing from files table."
                ),
                recommended_action=(
                    "Delete orphan analysis rows or rescan files to repopulate files table."
                ),
            )
        )
        issues.append(
            self._issue(
                check_name="files_without_analysis",
                issue_count=missing_analysis_count,
                severity="warning" if missing_analysis_count else "info",
                details="Files present without analysis rows.",
                recommended_action=(
                    "Run analysis pipeline for unprocessed files to populate file_analysis."
                ),
            )
        )
        return issues

    def _check_unified_memory_integrity(self) -> list[dict[str, Any]]:
        if not self.unified_memory_db_path.exists():
            return [
                self._issue(
                    check_name="unified_memory_db_missing",
                    issue_count=1,
                    severity="warning",
                    details=f"Database not found: {self.unified_memory_db_path}",
                    recommended_action=(
                        "Initialize unified_memory.db before memory-linked workflows."
                    ),
                )
            ]

        issues: list[dict[str, Any]] = []
        try:
            with sqlite3.connect(str(self.unified_memory_db_path)) as conn:
                orphan_links_count = self._safe_scalar(
                    conn,
                    """
                    SELECT COUNT(*)
                    FROM memory_code_links l
                    LEFT JOIN memory_records m ON m.record_id = l.memory_record_id
                    WHERE m.record_id IS NULL
                    """,
                )
                empty_content_count = self._scalar(
                    conn,
                    """
                    SELECT COUNT(*)
                    FROM memory_records
                    WHERE TRIM(COALESCE(content, '')) = ''
                    """,
                )
                invalid_confidence_count = self._scalar(
                    conn,
                    """
                    SELECT COUNT(*)
                    FROM memory_records
                    WHERE confidence_score < 0 OR confidence_score > 1
                    """,
                )
        except sqlite3.Error as exc:
            logger.error("Failed unified memory integrity check: %s", exc)
            return [
                self._issue(
                    check_name="unified_memory_query_error",
                    issue_count=1,
                    severity="critical",
                    details=f"SQLite error while checking unified memory: {exc}",
                    recommended_action=(
                        "Repair unified_memory.db and re-run memory ingestion."
                    ),
                )
            ]

        issues.append(
            self._issue(
                check_name="memory_code_orphan_links",
                issue_count=orphan_links_count,
                severity="warning" if orphan_links_count else "info",
                details=(
                    "Rows in memory_code_links reference memory_record_id values missing "
                    "from memory_records."
                ),
                recommended_action=(
                    "Remove orphan links and rebuild links from valid memory records."
                ),
            )
        )
        issues.append(
            self._issue(
                check_name="empty_memory_content",
                issue_count=empty_content_count,
                severity="warning" if empty_content_count else "info",
                details="Memory records contain empty content.",
                recommended_action=(
                    "Backfill content from source artifacts or purge invalid records."
                ),
            )
        )
        issues.append(
            self._issue(
                check_name="invalid_memory_confidence",
                issue_count=invalid_confidence_count,
                severity="warning" if invalid_confidence_count else "info",
                details="Memory confidence_score is outside expected range [0, 1].",
                recommended_action=(
                    "Normalize confidence_score values to [0,1] in ingestion/update paths."
                ),
            )
        )
        return issues

    @staticmethod
    def _scalar(conn: sqlite3.Connection, query: str) -> int:
        cursor = conn.execute(query)
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _safe_scalar(conn: sqlite3.Connection, query: str) -> int:
        try:
            return DataIntegrityService._scalar(conn, query)
        except sqlite3.Error:
            # Table may not exist yet; treat as zero for transitional migrations.
            return 0

    @staticmethod
    def _issue(
        *,
        check_name: str,
        issue_count: int,
        severity: str,
        details: str,
        recommended_action: str,
    ) -> dict[str, Any]:
        return {
            "check_name": check_name,
            "issue_count": int(issue_count),
            "severity": severity,
            "details": details,
            "recommended_action": recommended_action,
        }


data_integrity_service = DataIntegrityService()
