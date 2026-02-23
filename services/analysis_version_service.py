from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
import json # Added for json.dumps/loads

from mem_db.database import get_database_manager, DatabaseManager
from services.contracts.aedis_models import AnalysisVersion, ProvenanceRecord
from services.provenance_service import get_provenance_service, ProvenanceService, ProvenanceGateError

logger = logging.getLogger(__name__)


class AnalysisVersionService:
    def __init__(self, db_manager: Optional[DatabaseManager] = None, provenance_service: Optional[ProvenanceService] = None):
        self.db = db_manager or get_database_manager()
        self.provenance_service = provenance_service or get_provenance_service()

    def create_analysis_version(self, analysis_version: AnalysisVersion) -> AnalysisVersion:
        # 1. Enforce Provenance Gate
        # The AnalysisVersion object already contains the ProvenanceRecord
        # The target_id for the provenance link will be the analysis_id itself.
        try:
            self.provenance_service.validate_write_gate(
                analysis_version.provenance,
                "analysis_version",
                analysis_version.analysis_id,
            )
        except ProvenanceGateError as e:
            logger.error(f"Provenance gate failed for AnalysisVersion {analysis_version.analysis_id}: {e}")
            raise # Re-raise to prevent creation without valid provenance

        # 2. Record Provenance
        # This will persist the ProvenanceRecord and create a link to the AnalysisVersion.
        # It should only proceed if validate_write_gate passed.
        prov_id = self.provenance_service.record_provenance(
            analysis_version.provenance,
            "analysis_version",
            analysis_version.analysis_id,
        )

        # 3. Prepare data for persistence
        analysis_version_data = analysis_version.model_dump()
        analysis_version_data["created_at"] = analysis_version_data.get("created_at") or datetime.now(timezone.utc).isoformat()
        analysis_version_data["payload_json"] = json.dumps(analysis_version_data.pop("payload"))
        analysis_version_data["audit_deltas_json"] = json.dumps(analysis_version_data.pop("audit_deltas"))
        # Ensure provenance is not stored directly in the table, but linked.
        analysis_version_data.pop("provenance")
        
        # This is a bit tricky. The original provenance record was part of the AnalysisVersion model.
        # The database table itself doesn't have a 'provenance' column, but 'payload_json' and 'metadata_json'
        # can contain it. The `aedis_artifact_provenance_links` table stores the link.
        # So we update the payload or metadata of the AnalysisVersion with the prov_id
        current_payload = json.loads(analysis_version_data["payload_json"])
        current_payload["provenance_id"] = prov_id
        analysis_version_data["payload_json"] = json.dumps(current_payload)


        # 4. Persist the AnalysisVersion
        new_id = self.db.add_analysis_version(analysis_version_data)
        
        # For consistency, retrieve the created item.
        created_analysis_version = self.db.get_analysis_version(analysis_version.analysis_id)
        if not created_analysis_version:
            raise RuntimeError("Failed to retrieve created analysis version.")
            
        # Add the provenance_id to the metadata of the returned object
        if "provenance_id" not in created_analysis_version.get("payload", {}):
            if "payload" not in created_analysis_version:
                created_analysis_version["payload"] = {}
            created_analysis_version["payload"]["provenance_id"] = prov_id
            
        return AnalysisVersion(**created_analysis_version)

    def get_analysis_version(self, analysis_id: str) -> Optional[AnalysisVersion]:
        data = self.db.get_analysis_version(analysis_id)
        if data:
            # Reconstruct ProvenanceRecord if needed.
            # For simplicity, just return the AnalysisVersion object.
            # Provenance retrieval can be done via get_provenance_for_artifact if the link is stored.
            return AnalysisVersion(**data)
        return None

    def update_analysis_version_status(self, analysis_id: str, status: str) -> bool:
        return self.db.update_analysis_version(analysis_id, status=status)

    def list_analysis_versions(
        self,
        *,
        artifact_row_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AnalysisVersion]:
        data_list = self.db.list_analysis_versions(
            artifact_row_id=artifact_row_id, status=status, limit=limit, offset=offset
        )
        return [AnalysisVersion(**data) for data in data_list]

    def delete_analysis_version(self, analysis_id: str) -> bool:
        return self.db.delete_analysis_version(analysis_id)
