from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from services.contracts.aedis_models import ProvenanceRecord, EvidenceSpan
from mem_db.database import get_database_manager

logger = logging.getLogger(__name__)

class ProvenanceService:
    """
    Mandatory service for creating and retrieving evidence-backed provenance chains.
    Enforces the AEDIS Phase 3 'Global Provenance Contract'.
    """

    def __init__(self, db_manager=None):
        self.db = db_manager or get_database_manager()

    def record_provenance(self, record: ProvenanceRecord, target_type: str, target_id: str) -> int:
        """
        Validate and persist a provenance record, linking it to a target artifact.
        
        This is the primary 'Write-Gate' for Phase 3.
        """
        if not record.spans:
            raise RuntimeError("Provenance Write-Gate Failure: at least one EvidenceSpan is required")

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
            raise RuntimeError(f"Provenance Write-Gate Failure: {e}")

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
