import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from mem_db.knowledge import get_knowledge_manager
from services.dependencies import get_database_manager_strict_dep, resolve_typed_service
from services.knowledge_service import KnowledgeService

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
    use_heuristics: Optional[bool] = True


class EntitiesImportPayload(BaseModel):
    items: List[Dict[str, Any]]
    use_heuristics: Optional[bool] = True


class ProposalPayload(BaseModel):
    kind: str  # 'entity' | 'relationship'
    data: Dict[str, Any]


class DecisionPayload(BaseModel):
    id: int


class KnowledgeItemPayload(BaseModel):
    term: str
    category: Optional[str] = None
    canonical_value: Optional[str] = None
    ontology_entity_id: Optional[str] = None
    framework_type: Optional[str] = None
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
    related_frameworks: Optional[List[str]] = None
    aliases: Optional[List[str]] = None
    description: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    relations: Optional[List[Dict[str, Any]]] = None
    sources: Optional[List[str]] = None
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


class OntologyLinkPayload(BaseModel):
    ontology_entity_id: str


# --- Dependency ---

async def get_knowledge_service(request: Request) -> KnowledgeService:
    """Dependency to get KnowledgeService."""
    try:
        from mem_db.knowledge.unified_knowledge_graph_manager import (  # noqa: E402
            UnifiedKnowledgeGraphManager,
        )

        manager = await resolve_typed_service(
            request,
            UnifiedKnowledgeGraphManager,
            fallback_factory=get_knowledge_manager,
        )
    except Exception:
        manager = get_knowledge_manager()
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
            use_heuristics=payload.use_heuristics
        )
    except Exception as e:
        logger.error(f"Import triples error: {e}")
        raise HTTPException(status_code=500, detail="Failed to import triples")


@router.post("/knowledge/import_entities")
async def import_entities(payload: EntitiesImportPayload, service: KnowledgeService = Depends(get_knowledge_service)) -> Dict[str, Any]:
    try:
        return await service.import_entities(
            items=payload.items,
            use_heuristics=payload.use_heuristics
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
        result = await service.approve_proposal(payload.id)
        if not result:
            raise HTTPException(status_code=404, detail="Proposal not found")
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
        item_id = db.knowledge_upsert(
            term=payload.term,
            category=payload.category,
            canonical_value=payload.canonical_value,
            ontology_entity_id=payload.ontology_entity_id,
            framework_type=payload.framework_type,
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
        ok = db.knowledge_set_verification(
            knowledge_id,
            verified=payload.verified,
            verified_by=payload.verified_by,
            user_notes=payload.user_notes,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Knowledge item not found")
        return {"success": True, "verified": payload.verified}
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
            w.writerow(["id", "term", "category", "canonical_value", "ontology_entity_id", "verified", "confidence", "status", "verified_by", "user_notes"])
            for it in items:
                w.writerow([
                    it.get("id"),
                    it.get("term"),
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
