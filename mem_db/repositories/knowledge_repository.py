from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .base import BaseRepository


class KnowledgeRepository(BaseRepository):
    def add_proposal(
        self,
        *,
        proposal_type: str,
        payload: Dict[str, Any],
        confidence: Optional[float] = None,
        source: Optional[str] = None,
        status: str = "proposed",
    ) -> int:
        with self.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO knowledge_proposals (proposal_type, payload_json, confidence, source, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    proposal_type,
                    json.dumps(payload or {}),
                    float(confidence) if confidence is not None else None,
                    source,
                    status,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def list_proposals(self, *, status: Optional[str] = None, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM knowledge_proposals WHERE status = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (status, int(limit), int(offset)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM knowledge_proposals ORDER BY id DESC LIMIT ? OFFSET ?",
                    (int(limit), int(offset)),
                ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            try:
                item["payload_json"] = json.loads(item.get("payload_json") or "{}")
            except Exception:
                item["payload_json"] = {}
            out.append(item)
        return out

    def get_proposal(self, proposal_id: int) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_proposals WHERE id = ?",
                (int(proposal_id),),
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item["payload_json"] = json.loads(item.get("payload_json") or "{}")
        except Exception:
            item["payload_json"] = {}
        return item

    def update_proposal_status(self, proposal_id: int, *, status: str, review_note: Optional[str] = None) -> bool:
        with self.connection() as conn:
            cur = conn.execute(
                """
                UPDATE knowledge_proposals
                SET status = ?, review_note = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, review_note, int(proposal_id)),
            )
            conn.commit()
            return (cur.rowcount or 0) > 0

    def upsert(
        self,
        *,
        term: str,
        category: Optional[str] = None,
        canonical_value: Optional[str] = None,
        ontology_entity_id: Optional[str] = None,
        framework_type: Optional[str] = None,
        components: Optional[Dict[str, Any]] = None,
        legal_use_cases: Optional[List[Dict[str, Any]]] = None,
        preferred_perspective: Optional[str] = None,
        is_canonical: bool = False,
        issue_category: Optional[str] = None,
        severity: Optional[str] = None,
        impact_description: Optional[str] = None,
        root_cause: Optional[List[Dict[str, Any]]] = None,
        fix_status: Optional[str] = None,
        resolution_evidence: Optional[str] = None,
        resolution_date: Optional[str] = None,
        next_review_date: Optional[str] = None,
        related_frameworks: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None,
        description: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        relations: Optional[List[Dict[str, Any]]] = None,
        sources: Optional[List[str]] = None,
        notes: Optional[str] = None,
        source: Optional[str] = None,
        confidence: float = 0.5,
        status: str = "proposed",
        verified: bool = False,
        verified_by: Optional[str] = None,
        user_notes: Optional[str] = None,
    ) -> int:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO manager_knowledge (
                    term, category, canonical_value, ontology_entity_id,
                    framework_type, components_json, legal_use_cases_json, preferred_perspective, is_canonical,
                    issue_category, severity, impact_description, root_cause_json, fix_status,
                    resolution_evidence, resolution_date, next_review_date, related_frameworks_json,
                    aliases_json, description, attributes_json, relations_json, sources_json,
                    notes, source, confidence, status, verified, verified_by, user_notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(term, category) DO UPDATE SET
                    canonical_value=excluded.canonical_value,
                    ontology_entity_id=excluded.ontology_entity_id,
                    framework_type=excluded.framework_type,
                    components_json=excluded.components_json,
                    legal_use_cases_json=excluded.legal_use_cases_json,
                    preferred_perspective=excluded.preferred_perspective,
                    is_canonical=excluded.is_canonical,
                    issue_category=excluded.issue_category,
                    severity=excluded.severity,
                    impact_description=excluded.impact_description,
                    root_cause_json=excluded.root_cause_json,
                    fix_status=excluded.fix_status,
                    resolution_evidence=excluded.resolution_evidence,
                    resolution_date=excluded.resolution_date,
                    next_review_date=excluded.next_review_date,
                    related_frameworks_json=excluded.related_frameworks_json,
                    aliases_json=excluded.aliases_json,
                    description=excluded.description,
                    attributes_json=excluded.attributes_json,
                    relations_json=excluded.relations_json,
                    sources_json=excluded.sources_json,
                    notes=excluded.notes,
                    source=excluded.source,
                    confidence=excluded.confidence,
                    status=excluded.status,
                    verified=excluded.verified,
                    verified_by=excluded.verified_by,
                    user_notes=excluded.user_notes,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    term, category, canonical_value, ontology_entity_id, framework_type,
                    json.dumps(components or {}), json.dumps(legal_use_cases or []), preferred_perspective,
                    1 if is_canonical else 0, issue_category, severity, impact_description,
                    json.dumps(root_cause or []), fix_status, resolution_evidence, resolution_date,
                    next_review_date, json.dumps(related_frameworks or []), json.dumps(aliases or []),
                    description, json.dumps(attributes or {}), json.dumps(relations or []),
                    json.dumps(sources or []), notes, source, float(confidence), status,
                    1 if verified else 0, verified_by, user_notes,
                ),
            )
            row = conn.execute(
                "SELECT id FROM manager_knowledge WHERE term = ? AND category IS ?",
                (term, category),
            ).fetchone()
            conn.commit()
            return int(row[0]) if row else 0

    def list(
        self,
        *,
        status: Optional[str] = None,
        category: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            where = []
            params: List[Any] = []
            if status:
                where.append("status = ?")
                params.append(status)
            if category:
                where.append("category = ?")
                params.append(category)
            if query:
                where.append("(term LIKE ? OR canonical_value LIKE ? OR notes LIKE ?)")
                q = f"%{query}%"
                params.extend([q, q, q])
            where_clause = f"WHERE {' AND '.join(where)}" if where else ""
            rows = conn.execute(
                f"SELECT * FROM manager_knowledge {where_clause} ORDER BY updated_at DESC, created_at DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                for key, fallback in (("components_json", {}), ("legal_use_cases_json", []), ("root_cause_json", []), ("related_frameworks_json", []), ("aliases_json", []), ("attributes_json", {}), ("relations_json", []), ("sources_json", [])):
                    try:
                        item[key] = json.loads(item.get(key) or json.dumps(fallback))
                    except Exception:
                        item[key] = fallback
                item["verified"] = bool(item.get("verified"))
                out.append(item)
            return out

    def set_ontology_link(self, knowledge_id: int, ontology_entity_id: str) -> bool:
        with self.connection() as conn:
            cur = conn.execute(
                """
                UPDATE manager_knowledge
                SET ontology_entity_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (ontology_entity_id, knowledge_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def set_verification(self, knowledge_id: int, *, verified: bool, verified_by: Optional[str] = None, user_notes: Optional[str] = None) -> bool:
        with self.connection() as conn:
            cur = conn.execute(
                """
                UPDATE manager_knowledge
                SET verified = ?, verified_by = ?, user_notes = ?,
                    status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (1 if verified else 0, verified_by, user_notes, "verified" if verified else "rejected", knowledge_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def has_term(self, term: str, category: Optional[str] = None) -> bool:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM manager_knowledge WHERE term = ? AND (? IS NULL OR category = ?) LIMIT 1",
                (term, category, category),
            ).fetchone()
            return row is not None

    def add_question(self, *, question: str, context: Optional[Dict[str, Any]] = None, linked_term: Optional[str] = None, asked_by: str = "taskmaster") -> int:
        with self.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO manager_questions (question, context_json, linked_term, status, asked_by)
                VALUES (?, ?, ?, 'open', ?)
                """,
                (question, json.dumps(context or {}), linked_term, asked_by),
            )
            conn.commit()
            return int(cur.lastrowid)

    def answer_question(self, question_id: int, answer: str) -> bool:
        with self.connection() as conn:
            cur = conn.execute(
                """
                UPDATE manager_questions
                SET status='answered', answer=?, answered_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (answer, question_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def list_questions(self, *, status: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            where = "WHERE status = ?" if status else ""
            params: List[Any] = [status] if status else []
            rows = conn.execute(
                f"SELECT * FROM manager_questions {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                try:
                    item["context_json"] = json.loads(item.get("context_json") or "{}")
                except Exception:
                    item["context_json"] = {}
                out.append(item)
            return out
