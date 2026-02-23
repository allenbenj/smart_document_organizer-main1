import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from services.dependencies import get_database_manager_strict_dep, resolve_typed_service
from services.contracts.aedis_models import ProvenanceRecord
from services.jurisdiction_service import jurisdiction_service
from services.knowledge_service import KnowledgeService
from services.provenance_service import get_provenance_service

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Models ---

class EntityPayload(BaseModel):
    name: str
    entity_type: str
    content: Optional[str] = None
    jurisdiction: Optional[str] = None
    legal_domain: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class RelationshipPayload(BaseModel):
    source_id: str
    target_id: str
    relation_type: str
    properties: Optional[Dict[str, Any]] = None


class TriplesPayload(BaseModel):
    triples: List[Tuple[str, str, str]]
    entity_type: Optional[str] = "generic"
    entity_type_label: Optional[str] = None
    create_missing: Optional[bool] = True


class EntitiesImportPayload(BaseModel):
    items: List[Dict[str, Any]]


class ProposalPayload(BaseModel):
    kind: str  # 'entity' | 'relationship'
    data: Dict[str, Any]


class DecisionPayload(BaseModel):
    id: int
    provenance: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeItemPayload(BaseModel):
    term: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    canonical_value: Optional[str] = None
    ontology_entity_id: Optional[str] = None
    framework_type: Optional[str] = None
    jurisdiction: Optional[str] = None
    components: Optional[Dict[str, Any]] = None
    legal_use_cases: Optional[List[Dict[str, Any]]] = None
    preferred_perspective: Optional[str] = None
    is_canonical: Optional[bool] = False
    issue_category: Optional[str] = None
    severity: Optional[str] = None
    impact_description: Optional[str] = None
    root_cause: Optional[List[Dict[str, Any]]] = None
    fix_status: Optional[str] = None
    resolution_evidence: Optional[str] = None
    resolution_date: Optional[str] = None
    next_review_date: Optional[str] = None
    related_frameworks: Optional[List[Any]] = None
    aliases: Optional[List[str]] = None
    description: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    relations: Optional[List[Dict[str, Any]]] = None
    sources: Optional[List[Any]] = None
    notes: Optional[str] = None
    source: Optional[str] = None
    confidence: Optional[float] = 0.5
    status: Optional[str] = "proposed"
    verified: Optional[bool] = False
    verified_by: Optional[str] = None
    user_notes: Optional[str] = None


class KnowledgeQuestionPayload(BaseModel):
    question: str
    context: Optional[Dict[str, Any]] = None
    linked_term: Optional[str] = None
    asked_by: Optional[str] = "taskmaster"


class KnowledgeAnswerPayload(BaseModel):
    answer: str


class VerifyKnowledgePayload(BaseModel):
    verified: bool = True
    verified_by: Optional[str] = None
    user_notes: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)


class OntologyLinkPayload(BaseModel):
    ontology_entity_id: str


class KnowledgeItemUpdatePayload(BaseModel):
    term: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    canonical_value: Optional[str] = None
    ontology_entity_id: Optional[str] = None
    framework_type: Optional[str] = None
    jurisdiction: Optional[str] = None
    components: Optional[Dict[str, Any]] = None
    legal_use_cases: Optional[List[Dict[str, Any]]] = None
    preferred_perspective: Optional[str] = None
    is_canonical: Optional[bool] = None
    issue_category: Optional[str] = None
    severity: Optional[str] = None
    impact_description: Optional[str] = None
    root_cause: Optional[List[Dict[str, Any]]] = None
    fix_status: Optional[str] = None
    resolution_evidence: Optional[str] = None
    resolution_date: Optional[str] = None
    next_review_date: Optional[str] = None
    related_frameworks: Optional[List[Any]] = None
    aliases: Optional[List[str]] = None
    description: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    relations: Optional[List[Dict[str, Any]]] = None
    sources: Optional[List[Any]] = None
    source: Optional[str] = None
    confidence: Optional[float] = None
    status: Optional[str] = None
    verified: Optional[bool] = None
    verified_by: Optional[str] = None
    user_notes: Optional[str] = None
    notes: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)


def _require_curated_write_provenance(
    *,
    provenance: Dict[str, Any],
    target_type: str,
    target_id: str,
) -> Optional[int]:
    try:
        record = ProvenanceRecord.model_validate(provenance)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"provenance_required_for_curated_write: {exc}",
        ) from exc

    try:
        return get_provenance_service().record_provenance(
            record,
            target_type=target_type,
            target_id=target_id,
        )
    except RuntimeError as exc:
        # Degrade gracefully when provenance backing tables are unavailable.
        # Payload is validated above, so curation can continue in validated-only mode.
        logger.warning(
            "Provenance persistence unavailable for %s:%s; proceeding with validated-only provenance. %s",
            target_type,
            target_id,
            exc,
        )
        return None
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"provenance_required_for_curated_write: {exc}",
        ) from exc


# --- Dependency ---

async def get_knowledge_service(request: Request) -> KnowledgeService:
    """Dependency to get KnowledgeService."""
    from mem_db.knowledge.unified_knowledge_graph_manager import (  # noqa: E402
        UnifiedKnowledgeGraphManager,
    )

    manager = await resolve_typed_service(
        request,
        UnifiedKnowledgeGraphManager,
    )
    if manager is None:
        raise HTTPException(status_code=500, detail="knowledge_manager_unavailable")
    return KnowledgeService(knowledge_manager=manager)


# --- Routes ---

@router.get("/knowledge")
async def knowledge_status(service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    try:
        return await service.get_graph_status()
    except Exception as e:
        logger.error(f"Knowledge status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get knowledge status")


@router.post("/knowledge/init")
async def knowledge_init(service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    try:
        ok = await service.initialize_graph()
        return {"initialized": ok}
    except Exception as e:
        logger.error(f"Knowledge init error: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize knowledge manager")


@router.post("/knowledge/entities")
async def add_entity(payload: EntityPayload, service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    try:
        return await service.add_entity(
            name=payload.name,
            entity_type=payload.entity_type,
            attributes=payload.attributes,
            content=payload.content,
            jurisdiction=payload.jurisdiction,
            legal_domain=payload.legal_domain
        )
    except Exception as e:
        logger.error(f"Add entity error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add entity")


@router.get("/knowledge/entities")
async def list_entities(
    limit: int = 50,
    offset: int = 0,
    service: KnowledgeService = Depends(get_knowledge_service)
) -> Dict[str, Any]:
    try:
        return await service.list_entities(limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"List entities error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list entities")


@router.post("/knowledge/relationships")
async def add_relationship(payload: RelationshipPayload, service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    try:
        return await service.add_relationship(
            source_id=payload.source_id,
            target_id=payload.target_id,
            relation_type=payload.relation_type,
            properties=payload.properties
        )
    except Exception as e:
        logger.error(f"Add relationship error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add relationship")


@router.get("/knowledge/relationships")
async def list_relationships(
    limit: int = 50,
    offset: int = 0,
    service: KnowledgeService = Depends(get_knowledge_service)
) -> Dict[str, Any]:
    try:
        return await service.list_relationships(limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"List relationships error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list relationships")


@router.post("/knowledge/import_triples")
async def import_triples(payload: TriplesPayload, service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    try:
        return await service.import_triples(
            triples=payload.triples,
            entity_type=payload.entity_type,
            entity_type_label=payload.entity_type_label,
            create_missing=payload.create_missing,
        )
    except Exception as e:
        logger.error(f"Import triples error: {e}")
        raise HTTPException(status_code=500, detail="Failed to import triples")


@router.post("/knowledge/import_entities")
async def import_entities(payload: EntitiesImportPayload, service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    try:
        return await service.import_entities(
            items=payload.items,
        )
    except Exception as e:
        logger.error(f"Import entities error: {e}")
        raise HTTPException(status_code=500, detail="Failed to import entities")


@router.post("/knowledge/proposals")
async def add_proposal(payload: ProposalPayload, service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    try:
        return await service.add_proposal(kind=payload.kind, data=payload.data)
    except Exception as e:
        logger.error(f"Add proposal error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add proposal")


@router.get("/knowledge/proposals")
async def list_proposals(service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    try:
        return await service.list_proposals()
    except Exception as e:
        logger.error(f"List proposals error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list proposals")


@router.post("/knowledge/proposals/approve")
async def approve_proposal(payload: DecisionPayload, service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    try:
        provenance_id = _require_curated_write_provenance(
            provenance=payload.provenance,
            target_type="knowledge_proposal_approval",
            target_id=str(payload.id),
        )
        result = await service.approve_proposal(payload.id)
        if not result:
            raise HTTPException(status_code=404, detail="Proposal not found")
        result["provenance_id"] = provenance_id
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approve proposal error: {e}")
        raise HTTPException(status_code=500, detail="Failed to approve proposal")


@router.post("/knowledge/proposals/reject")
async def reject_proposal(payload: DecisionPayload, service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    try:
        success = await service.reject_proposal(payload.id)
        if not success:
            raise HTTPException(status_code=404, detail="Proposal not found")
        return {"rejected": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reject proposal error: {e}")
        raise HTTPException(status_code=500, detail="Failed to reject proposal")


@router.post("/knowledge/manager/items")
async def upsert_manager_knowledge(
    payload: KnowledgeItemPayload,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        term_value = (payload.term or payload.content or "").strip()
        if not term_value:
            raise HTTPException(status_code=422, detail="term or content is required")
        item_id = db.knowledge_upsert(
            term=term_value,
            category=payload.category,
            canonical_value=payload.canonical_value,
            ontology_entity_id=payload.ontology_entity_id,
            framework_type=payload.framework_type,
            jurisdiction=jurisdiction_service.resolve(
                payload.jurisdiction,
                metadata=payload.attributes,
            ),
            components=payload.components,
            legal_use_cases=payload.legal_use_cases,
            preferred_perspective=payload.preferred_perspective,
            is_canonical=bool(payload.is_canonical),
            issue_category=payload.issue_category,
            severity=payload.severity,
            impact_description=payload.impact_description,
            root_cause=payload.root_cause,
            fix_status=payload.fix_status,
            resolution_evidence=payload.resolution_evidence,
            resolution_date=payload.resolution_date,
            next_review_date=payload.next_review_date,
            related_frameworks=payload.related_frameworks,
            aliases=payload.aliases,
            description=payload.description,
            attributes=payload.attributes,
            relations=payload.relations,
            sources=payload.sources,
            notes=payload.notes,
            source=payload.source,
            confidence=float(payload.confidence or 0.5),
            status=payload.status or "proposed",
            verified=bool(payload.verified),
            verified_by=payload.verified_by,
            user_notes=payload.user_notes,
        )
        return {"success": True, "id": item_id}
    except Exception as e:
        logger.error(f"Manager knowledge upsert error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert manager knowledge")


@router.get("/knowledge/manager/items")
async def list_manager_knowledge(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        items = db.knowledge_list(status=status, category=category, query=q, limit=limit, offset=offset)
        return {"success": True, "total": len(items), "items": items}
    except Exception as e:
        logger.error(f"Manager knowledge list error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list manager knowledge")


@router.post("/knowledge/manager/questions")
async def add_manager_question(
    payload: KnowledgeQuestionPayload,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        qid = db.knowledge_add_question(
            question=payload.question,
            context=payload.context,
            linked_term=payload.linked_term,
            asked_by=payload.asked_by or "taskmaster",
        )
        return {"success": True, "id": qid}
    except Exception as e:
        logger.error(f"Manager question add error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add manager question")


@router.get("/knowledge/manager/questions")
async def list_manager_questions(
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        items = db.knowledge_list_questions(status=status, limit=limit, offset=offset)
        return {"success": True, "total": len(items), "items": items}
    except Exception as e:
        logger.error(f"Manager question list error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list manager questions")


@router.post("/knowledge/manager/questions/{question_id}/answer")
async def answer_manager_question(
    question_id: int,
    payload: KnowledgeAnswerPayload,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        ok = db.knowledge_answer_question(question_id, payload.answer)
        if not ok:
            raise HTTPException(status_code=404, detail="Question not found")
        return {"success": True, "answered": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manager question answer error: {e}")
        raise HTTPException(status_code=500, detail="Failed to answer manager question")


@router.post("/knowledge/manager/items/{knowledge_id}/verify")
async def verify_manager_knowledge(
    knowledge_id: int,
    payload: VerifyKnowledgePayload,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        provenance_id: Optional[int] = None
        if payload.verified:
            provenance_id = _require_curated_write_provenance(
                provenance=payload.provenance,
                target_type="manager_knowledge_verification",
                target_id=str(knowledge_id),
            )
        ok = db.knowledge_set_verification(
            knowledge_id,
            verified=payload.verified,
            verified_by=payload.verified_by,
            user_notes=payload.user_notes,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Knowledge item not found")
        out: Dict[str, Any] = {"success": True, "verified": payload.verified}
        if provenance_id is not None:
            out["provenance_id"] = provenance_id
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manager knowledge verify error: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify manager knowledge")


@router.get("/knowledge/manager/frameworks")
async def list_framework_knowledge(
    is_canonical: Optional[bool] = Query(None),
    framework_type: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        items = db.knowledge_list(category="framework", limit=limit, offset=offset)
        if framework_type:
            items = [i for i in items if str(i.get("framework_type") or "").lower() == framework_type.lower()]
        if is_canonical is not None:
            items = [i for i in items if bool(i.get("is_canonical")) == bool(is_canonical)]
        return {"success": True, "total": len(items), "items": items}
    except Exception as e:
        logger.error(f"Framework knowledge list error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list framework knowledge")


@router.get("/knowledge/manager/issues")
async def list_issue_knowledge(
    severity: Optional[str] = Query(None),
    fix_status: Optional[str] = Query(None),
    issue_category: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        items = db.knowledge_list(category="system_issue", limit=limit, offset=offset)
        if severity:
            items = [i for i in items if str(i.get("severity") or "").lower() == severity.lower()]
        if fix_status:
            items = [i for i in items if str(i.get("fix_status") or "").lower() == fix_status.lower()]
        if issue_category:
            items = [i for i in items if str(i.get("issue_category") or "").lower() == issue_category.lower()]
        return {"success": True, "total": len(items), "items": items}
    except Exception as e:
        logger.error(f"Issue knowledge list error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list issue knowledge")


@router.post("/knowledge/manager/items/{knowledge_id}/link-ontology")
async def link_manager_knowledge_ontology(
    knowledge_id: int,
    payload: OntologyLinkPayload,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        ok = db.knowledge_set_ontology_link(knowledge_id, payload.ontology_entity_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Knowledge item not found")
        return {"success": True, "ontology_entity_id": payload.ontology_entity_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manager knowledge ontology link error: {e}")
        raise HTTPException(status_code=500, detail="Failed to link ontology entity")


@router.get("/knowledge/manager/items/{knowledge_id}")
async def get_manager_knowledge_item(
    knowledge_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        item = db.knowledge_get_item(knowledge_id)
        if not item:
            raise HTTPException(status_code=404, detail="Knowledge item not found")
        return {"success": True, "item": item}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manager knowledge get error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get manager knowledge item")


@router.put("/knowledge/manager/items/{knowledge_id}")
async def update_manager_knowledge_item(
    knowledge_id: int,
    payload: KnowledgeItemUpdatePayload,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        status_value = str(payload.status or "").strip().lower()
        requires_provenance = bool(payload.verified) or status_value in {
            "verified",
            "curated",
            "approved",
        }
        provenance_id: Optional[int] = None
        if requires_provenance:
            provenance_id = _require_curated_write_provenance(
                provenance=payload.provenance,
                target_type="manager_knowledge_curation",
                target_id=str(knowledge_id),
            )
        ok = db.knowledge_update_item(
            knowledge_id,
            term=(payload.term if payload.term is not None else payload.content),
            category=payload.category,
            canonical_value=payload.canonical_value,
            ontology_entity_id=payload.ontology_entity_id,
            framework_type=payload.framework_type,
            jurisdiction=jurisdiction_service.resolve(
                payload.jurisdiction,
                metadata=payload.attributes,
            ),
            components=payload.components,
            legal_use_cases=payload.legal_use_cases,
            preferred_perspective=payload.preferred_perspective,
            is_canonical=payload.is_canonical,
            issue_category=payload.issue_category,
            severity=payload.severity,
            impact_description=payload.impact_description,
            root_cause=payload.root_cause,
            fix_status=payload.fix_status,
            resolution_evidence=payload.resolution_evidence,
            resolution_date=payload.resolution_date,
            next_review_date=payload.next_review_date,
            related_frameworks=payload.related_frameworks,
            aliases=payload.aliases,
            description=payload.description,
            attributes=payload.attributes,
            relations=payload.relations,
            sources=payload.sources,
            source=payload.source,
            confidence=payload.confidence,
            status=payload.status,
            verified=payload.verified,
            verified_by=payload.verified_by,
            user_notes=payload.user_notes,
            notes=payload.notes,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Knowledge item not found or no fields to update")
        item = db.knowledge_get_item(knowledge_id)
        out: Dict[str, Any] = {"success": True, "item": item}
        if provenance_id is not None:
            out["provenance_id"] = provenance_id
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manager knowledge update error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update manager knowledge item")


@router.delete("/knowledge/manager/items/{knowledge_id}")
async def delete_manager_knowledge_item(
    knowledge_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    try:
        ok = db.knowledge_delete_item(knowledge_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Knowledge item not found")
        return {"success": True, "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manager knowledge delete error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete manager knowledge item")


@router.get("/knowledge/manager/export")
async def export_manager_knowledge(
    format: str = Query("json"),
    db=Depends(get_database_manager_strict_dep),
):
    try:
        items = db.knowledge_list(limit=10000)
        if format.lower() == "csv":
            import csv
            import io

            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["id", "term", "content", "category", "canonical_value", "ontology_entity_id", "verified", "confidence", "status", "verified_by", "user_notes"])
            for it in items:
                w.writerow([
                    it.get("id"),
                    it.get("term"),
                    it.get("content") or it.get("term"),
                    it.get("category"),
                    it.get("canonical_value"),
                    it.get("ontology_entity_id"),
                    it.get("verified"),
                    it.get("confidence"),
                    it.get("status"),
                    it.get("verified_by"),
                    it.get("user_notes"),
                ])
            return {"success": True, "format": "csv", "csv": buf.getvalue()}

        return {"success": True, "format": "json", "items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Manager knowledge export error: {e}")
        raise HTTPException(status_code=500, detail="Failed to export manager knowledge")
