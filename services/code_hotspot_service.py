from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodeHotspotService:
    """Compute ranked code hotspots from change, issue, and complexity signals."""

    def __init__(self, file_index_db_path: Path | None = None) -> None:
        self.file_index_db_path = file_index_db_path or Path("databases") / "file_index.db"

    def get_hotspots(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.file_index_db_path.exists():
            return []

        sql = """
        WITH change_counts AS (
            SELECT file_path, COUNT(*) AS change_events
            FROM file_change_history
            GROUP BY file_path
        ),
        issue_weights AS (
            SELECT
                f.file_path AS file_path,
                COALESCE(
                    SUM(
                        CASE LOWER(COALESCE(i.severity, 'low'))
                            WHEN 'critical' THEN 5
                            WHEN 'high' THEN 3
                            WHEN 'medium' THEN 2
                            ELSE 1
                        END
                    ),
                    0
                ) AS issue_weight
            FROM files f
            LEFT JOIN file_issues i ON i.file_id = f.id
            AND LOWER(COALESCE(i.status, 'open')) NOT IN ('resolved', 'wont_fix')
            GROUP BY f.file_path
        ),
        latest_analysis AS (
            SELECT file_path, complexity_score
            FROM file_analysis
            WHERE id IN (
                SELECT MAX(id)
                FROM file_analysis
                GROUP BY file_path
            )
        )
        SELECT
            f.file_path,
            COALESCE(cc.change_events, 0) AS change_events,
            COALESCE(iw.issue_weight, 0) AS issue_weight,
            COALESCE(la.complexity_score, 0.0) AS complexity_score
        FROM files f
        LEFT JOIN change_counts cc ON cc.file_path = f.file_path
        LEFT JOIN issue_weights iw ON iw.file_path = f.file_path
        LEFT JOIN latest_analysis la ON la.file_path = f.file_path
        """
        try:
            with sqlite3.connect(str(self.file_index_db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(sql).fetchall()
        except sqlite3.Error as exc:
            logger.error("Failed to compute hotspots: %s", exc)
            return []

        scored: list[dict[str, Any]] = []
        for row in rows:
            change_events = int(row["change_events"] or 0)
            issue_weight = int(row["issue_weight"] or 0)
            complexity_score = float(row["complexity_score"] or 0.0)

            normalized_change = min(change_events / 10.0, 1.0)
            normalized_issues = min(issue_weight / 10.0, 1.0)
            normalized_complexity = min(max(complexity_score, 0.0) / 10.0, 1.0)

            hotspot_score = (
                normalized_change * 40.0
                + normalized_issues * 35.0
                + normalized_complexity * 25.0
            )
            risk_level = self._risk_level(hotspot_score)

            scored.append(
                {
                    "file_path": row["file_path"],
                    "change_events": change_events,
                    "issue_weight": issue_weight,
                    "complexity_score": round(complexity_score, 3),
                    "hotspot_score": round(hotspot_score, 3),
                    "risk_level": risk_level,
                    "recommended_action": self._recommendation(
                        change_events,
                        issue_weight,
                        complexity_score,
                        risk_level,
                    ),
                }
            )

        scored.sort(key=lambda item: item["hotspot_score"], reverse=True)
        return scored[:limit]

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 75:
            return "critical"
        if score >= 50:
            return "high"
        if score >= 25:
            return "medium"
        return "low"

    @staticmethod
    def _recommendation(
        change_events: int,
        issue_weight: int,
        complexity_score: float,
        risk_level: str,
    ) -> str:
        recommendations: list[str] = []
        if issue_weight >= 6:
            recommendations.append("prioritize issue triage and fix open high-severity defects")
        if complexity_score >= 7:
            recommendations.append("schedule refactor to reduce complexity")
        if change_events >= 8:
            recommendations.append("stabilize churn with tighter review and test gates")
        if not recommendations:
            if risk_level in {"critical", "high"}:
                recommendations.append("perform focused architecture review for risk reduction")
            else:
                recommendations.append("monitor trend and re-evaluate after next scan")
        return "; ".join(recommendations)


code_hotspot_service = CodeHotspotService()
