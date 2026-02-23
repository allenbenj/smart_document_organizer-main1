import logging
import sqlite3
from typing import Any, Dict, List
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mem_db.repositories.canonical_repository import CanonicalRepository
from services.canonical_artifact_service import CanonicalArtifactService
from services.ontology_registry_service import OntologyRegistryService

router = APIRouter()
logger = logging.getLogger(__name__)
registry_service = OntologyRegistryService()


_CANONICAL_DB_PATH = (
    Path(__file__).resolve().parents[1] / "mem_db" / "data" / "documents.db"
)


def _canonical_connection_factory() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_CANONICAL_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


canonical_service = CanonicalArtifactService(
    CanonicalRepository(_canonical_connection_factory),
)


class OntologyVersionCreatePayload(BaseModel):
    description: str | None = Field(default=None, max_length=500)


class OntologyVersionActionPayload(BaseModel):
    version: int = Field(..., ge=1)


class CanonicalArtifactCreatePayload(BaseModel):
    artifact_id: str = Field(..., min_length=1, max_length=255)
    sha256: str = Field(..., min_length=64, max_length=64)
    source_uri: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] | None = None
    blob_locator: str | None = None
    content_size_bytes: int | None = Field(default=None, ge=0)


class CanonicalLineagePayload(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=100)
    event_data: dict[str, Any] | None = None


@router.get("/ontology/entities")
async def list_entity_types() -> Dict[str, Any]:
    """List ontology entity types with attributes and prompt hints."""
    try:
        from agents.extractors.ontology import LegalEntityType

        items: List[Dict[str, Any]] = []
        for et in LegalEntityType:
            items.append(
                {
                    "label": et.value.label,
                    "attributes": list(et.attributes),
                    "prompt_hint": et.prompt_hint,
                }
            )
        return {"items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Ontology load failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load ontology")


@router.get("/ontology/prompt")
async def get_ontology_extraction_prompt() -> Dict[str, Any]:
    """Return a consolidated extraction prompt built from the ontology."""
    try:
        from agents.extractors.ontology import get_extraction_prompt

        return {"prompt": get_extraction_prompt()}
    except Exception as e:
        logger.error(f"Ontology prompt failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to build ontology prompt")


@router.get("/ontology/relationships")
async def list_relationship_types() -> Dict[str, Any]:
    """List ontology relationship types with properties and prompt hints."""
    try:
        from agents.extractors.ontology import LegalRelationshipType

        items: List[Dict[str, Any]] = []
        for rt in LegalRelationshipType:
            items.append(
                {
                    "label": rt.value.label,
                    "properties": list(rt.properties),
                    "prompt_hint": rt.prompt_hint,
                }
            )
        return {"items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Ontology relationship load failed: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to load relationship types"
        )


@router.get("/ontology/registry")
async def list_registry() -> Dict[str, Any]:
    try:
        items = registry_service.list_registry()
        return {"items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Ontology registry list failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list ontology registry")


@router.post("/ontology/registry/{ontology_type}/versions")
async def create_registry_version(
    ontology_type: str,
    payload: OntologyVersionCreatePayload,
) -> Dict[str, Any]:
    try:
        created = registry_service.create_version(
            ontology_type=ontology_type,
            description=payload.description,
        )
        return {"success": True, "item": created}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Ontology registry create version failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ontology version")


@router.post("/ontology/registry/{ontology_type}/activate")
async def activate_registry_version(
    ontology_type: str,
    payload: OntologyVersionActionPayload,
) -> Dict[str, Any]:
    try:
        item = registry_service.activate_version(
            ontology_type=ontology_type,
            version=payload.version,
        )
        return {"success": True, "item": item}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Ontology registry activation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate ontology version")


@router.post("/ontology/registry/{ontology_type}/deprecate")
async def deprecate_registry_version(
    ontology_type: str,
    payload: OntologyVersionActionPayload,
) -> Dict[str, Any]:
    try:
        item = registry_service.deprecate_version(
            ontology_type=ontology_type,
            version=payload.version,
        )
        return {"success": True, "item": item}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Ontology registry deprecation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to deprecate ontology version")


@router.post("/ontology/canonical/artifacts/ingest")
async def ingest_canonical_artifact(payload: CanonicalArtifactCreatePayload) -> Dict[str, Any]:
    try:
        artifact_row_id = canonical_service.ingest_artifact(
            artifact_id=payload.artifact_id,
            sha256=payload.sha256,
            source_uri=payload.source_uri,
            mime_type=payload.mime_type,
            metadata=payload.metadata,
            blob_locator=payload.blob_locator,
            content_size_bytes=payload.content_size_bytes,
        )
        return {"success": True, "artifact_row_id": artifact_row_id}
    except Exception as e:
        logger.error(f"Canonical ingest failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to ingest canonical artifact")


@router.post("/ontology/canonical/artifacts/{artifact_row_id}/lineage")
async def append_canonical_lineage_event(
    artifact_row_id: int,
    payload: CanonicalLineagePayload,
) -> Dict[str, Any]:
    try:
        event_row_id = canonical_service.append_lineage_event(
            artifact_row_id=artifact_row_id,
            event_type=payload.event_type,
            event_data=payload.event_data,
        )
        return {"success": True, "event_row_id": event_row_id}
    except Exception as e:
        logger.error(f"Canonical lineage append failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to append lineage event")


@router.get("/ontology/canonical/artifacts/{artifact_row_id}/lineage")
async def list_canonical_lineage(artifact_row_id: int) -> Dict[str, Any]:
    try:
        items = canonical_service.get_lineage(artifact_row_id=artifact_row_id)
        return {"items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Canonical lineage fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch canonical lineage")
