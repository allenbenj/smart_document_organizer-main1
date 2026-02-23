from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from services.contracts.aedis_models import ProvenanceRecord, EvidenceSpan
from mem_db.database import get_database_manager

logger = logging.getLogger(__name__)


class ProvenanceGateError(RuntimeError):
    """Raised when a provenance write-gate validation fails."""


class ProvenanceService:
    """
    Mandatory service for creating and retrieving evidence-backed provenance chains.
    Enforces the AEDIS Phase 3 'Global Provenance Contract'.
    """

    def __init__(self, db_manager=None):
        self.db = db_manager or get_database_manager()
        self._ensure_schema_ready()

    def _ensure_schema_ready(self) -> None:
        """
        Ensure provenance tables/indexes exist in the currently active database.
        This prevents write-gate failures when migrations were not applied
        to the runtime DB file used by desktop workflows.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS aedis_provenance_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_artifact_row_id INTEGER NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    extractor_id TEXT NOT NULL,
                    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS aedis_evidence_spans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provenance_id INTEGER NOT NULL,
                    start_char INTEGER NOT NULL,
                    end_char INTEGER NOT NULL,
                    quote TEXT,
                    FOREIGN KEY (provenance_id) REFERENCES aedis_provenance_records(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS aedis_artifact_provenance_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provenance_id INTEGER NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    FOREIGN KEY (provenance_id) REFERENCES aedis_provenance_records(id)
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_provenance_source ON aedis_provenance_records(source_artifact_row_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_offsets ON aedis_evidence_spans(start_char, end_char)"
            )
            conn.commit()

    def validate_write_gate(
        self,
        record: ProvenanceRecord,
        target_type: str,
        target_id: str,
    ) -> None:
        """Validate provenance contract before persistence."""
        if not isinstance(target_type, str) or not target_type.strip():
            raise ProvenanceGateError(
                "Provenance Write-Gate Failure: target_type is required"
            )
        if not isinstance(target_id, str) or not target_id.strip():
            raise ProvenanceGateError(
                "Provenance Write-Gate Failure: target_id is required"
            )
        if not record.spans:
            raise ProvenanceGateError(
                "Provenance Write-Gate Failure: at least one EvidenceSpan is required"
            )

    def record_provenance(self, record: ProvenanceRecord, target_type: str, target_id: str) -> int:
        """
        Validate and persist a provenance record, linking it to a target artifact.
        
        This is the primary 'Write-Gate' for Phase 3.
        """
        self.validate_write_gate(record, target_type, target_id)
        self._ensure_schema_ready()

        # 1. Contract Validation (performed by Pydantic in the DTO itself)
        # 2. Persist to Database
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Insert main record
                cursor.execute(
                    """
                    INSERT INTO aedis_provenance_records
                    (source_artifact_row_id, source_sha256, extractor_id, captured_at, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record.source_artifact_row_id,
                        record.source_sha256,
                        record.extractor,
                        record.captured_at.isoformat(),
                        record.notes,
                    ),
                )
                provenance_id = int(cursor.lastrowid)

                # Insert character-level spans
                for span in record.spans:
                    cursor.execute(
                        """
                        INSERT INTO aedis_evidence_spans
                        (provenance_id, start_char, end_char, quote)
                        VALUES (?, ?, ?, ?)
                        """,
                        (provenance_id, span.start_char, span.end_char, span.quote),
                    )

                # Create the link to the target (e.g. analysis version or proposal)
                cursor.execute(
                    """
                    INSERT INTO aedis_artifact_provenance_links
                    (provenance_id, target_type, target_id)
                    VALUES (?, ?, ?)
                    """,
                    (provenance_id, target_type, target_id),
                )

            logger.info(f"Provenance record {provenance_id} linked to {target_type}:{target_id}")
            return provenance_id
        except Exception as e:
            logger.error(f"Failed to record provenance: {e}")
            raise ProvenanceGateError(f"Provenance Write-Gate Failure: {e}")

    def get_provenance_for_artifact(self, target_type: str, target_id: str) -> Optional[ProvenanceRecord]:
        """Reconstruct a provenance record from the database."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Join link to record
            cursor.execute(
                """
                SELECT r.id, r.source_artifact_row_id, r.source_sha256, r.extractor_id, r.captured_at, r.notes
                FROM aedis_provenance_records r
                JOIN aedis_artifact_provenance_links l ON r.id = l.provenance_id
                WHERE l.target_type = ? AND l.target_id = ?
                """,
                (target_type, target_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            prov_id, art_id, sha, ext, captured, notes = row

            # Get spans
            cursor.execute(
                "SELECT start_char, end_char, quote FROM aedis_evidence_spans WHERE provenance_id = ?",
                (prov_id,),
            )
            spans = [
                EvidenceSpan(
                    artifact_row_id=art_id,
                    start_char=s[0],
                    end_char=s[1],
                    quote=s[2],
                )
                for s in cursor.fetchall()
            ]

        return ProvenanceRecord(
            source_artifact_row_id=art_id,
            source_sha256=sha,
            captured_at=datetime.fromisoformat(captured),
            extractor=ext,
            spans=spans,
            notes=notes,
        )

    def delete_provenance_links_for_target(self, target_type: str, target_id: str) -> int:
        """
        Deletes provenance links associated with a specific target artifact.
        Returns the number of links deleted.
        """
        if not target_type or not target_id:
            raise ValueError("target_type and target_id are required.")

        deleted_links = 0
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Find provenance_ids linked to this target
            cursor.execute(
                "SELECT provenance_id FROM aedis_artifact_provenance_links WHERE target_type = ? AND target_id = ?",
                (target_type, target_id),
            )
            linked_prov_ids = [row[0] for row in cursor.fetchall()]

            if not linked_prov_ids:
                return 0

            # Delete the links
            cursor.execute(
                "DELETE FROM aedis_artifact_provenance_links WHERE target_type = ? AND target_id = ?",
                (target_type, target_id),
            )
            deleted_links = cursor.rowcount

            # For each provenance_id, check if it's still linked to any other target.
            # If not, delete the provenance record and its spans.
            for prov_id in linked_prov_ids:
                cursor.execute(
                    "SELECT COUNT(*) FROM aedis_artifact_provenance_links WHERE provenance_id = ?",
                    (prov_id,),
                )
                remaining_links = cursor.fetchone()[0]

                if remaining_links == 0:
                    # No more links to this provenance record, so delete it and its spans
                    cursor.execute("DELETE FROM aedis_evidence_spans WHERE provenance_id = ?", (prov_id,))
                    cursor.execute("DELETE FROM aedis_provenance_records WHERE id = ?", (prov_id,))
                    logger.info(f"Deleted unlinked ProvenanceRecord {prov_id}.")

            conn.commit()
        logger.info(f"Deleted {deleted_links} provenance links for target {target_type}:{target_id}.")
        return deleted_links

# Global service instance (best-effort lazy bootstrap for runtime wiring).
try:
    provenance_service: ProvenanceService | None = ProvenanceService()
except Exception:
    provenance_service = None


def get_provenance_service() -> ProvenanceService:
    global provenance_service
    if provenance_service is None:
        provenance_service = ProvenanceService()
    return provenance_service
