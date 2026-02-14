import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)


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
