"""
Knowledge Service
=================
Handles operations on the Knowledge Graph.
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple

from mem_db.database import get_database_manager
from mem_db.knowledge import get_knowledge_manager

logger = logging.getLogger(__name__)

class KnowledgeService:
    """
    Service for Knowledge Graph interactions.
    Encapsulates logic from routes/knowledge.py.
    """
    def __init__(self, knowledge_manager=None):
        self.knowledge_manager = knowledge_manager or get_knowledge_manager()
        self.db = get_database_manager()

    def _check_available(self) -> bool:
        """Checks if manager is available."""
        return self.knowledge_manager is not None

    async def get_graph_status(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge graph.
        """
        if not self._check_available():
            return {
                "available": False,
                "initialized": False,
                "reason": "dependencies_missing",
                "degradation": {
                    "component": "knowledge_graph",
                    "lost_features": [
                        "graph-based legal entity/relationship storage",
                        "KG queries and visualization",
                        "relationship proposals with enforcement",
                    ],
                    "fits_workflow": False,
                    "suggested_actions": [
                        "Install networkx and required KG deps",
                        "Initialize Knowledge Manager",
                    ],
                },
            }

        if hasattr(self.knowledge_manager, "get_status"):
            return await self.knowledge_manager.get_status()
        return {"available": True, "initialized": False, "stats": {}}

    async def initialize_graph(self) -> bool:
        """Initialize the graph manager."""
        if not self._check_available():
            raise RuntimeError("Knowledge Manager unavailable")

        return await self.knowledge_manager.initialize()

    async def add_entity(self,
                         name: str,
                         entity_type: str,
                         attributes: Dict[str, Any] = None,
                         content: str = None,
                         jurisdiction: str = None,
                         legal_domain: str = None) -> Dict[str, Any]:
        """
        Add an entity to the graph.
        """
        if not self._check_available():
            raise RuntimeError("Knowledge manager unavailable")

        metadata = dict(attributes or {})
        if legal_domain:
            metadata.setdefault("legal_domain", legal_domain)

        ent_id = await self.knowledge_manager.add_entity(
            name=name,
            entity_type=entity_type,
            content=content,
            jurisdiction=jurisdiction,
            metadata=metadata,
        )

        return {"id": ent_id}

    async def list_entities(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List entities with pagination."""
        if not self._check_available():
            raise RuntimeError("Knowledge manager unavailable")

        entities = await self.knowledge_manager.list_entities(limit=limit, offset=offset)
        total = len(entities)
        if hasattr(self.knowledge_manager, "get_status"):
            try:
                status = await self.knowledge_manager.get_status()
                total = int(status.get("stats", {}).get("total_entities", total))
            except Exception:
                pass
        return {"items": entities, "count": total}

    async def add_relationship(self,
                               source_id: str,
                               target_id: str,
                               relation_type: str,
                               properties: Dict[str, Any] = None) -> Dict[str, Any]:
        """Add a relationship between entities."""
        if not self._check_available():
            raise RuntimeError("Knowledge manager unavailable")

        rel_id = await self.knowledge_manager.add_relationship(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            metadata=properties or {},
        )
        return {"id": rel_id}

    async def list_relationships(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List relationships with pagination."""
        if not self._check_available():
            raise RuntimeError("Knowledge manager unavailable")
        rels = await self.knowledge_manager.list_relationships(limit=limit, offset=offset)
        total = len(rels)
        if hasattr(self.knowledge_manager, "get_status"):
            try:
                status = await self.knowledge_manager.get_status()
                total = int(status.get("stats", {}).get("total_relationships", total))
            except Exception:
                pass
        return {"items": rels, "count": total}

    async def _find_entity_id_by_name(self, name: str) -> Optional[str]:
        if hasattr(self.knowledge_manager, "find_entity_id_by_name"):
            return await self.knowledge_manager.find_entity_id_by_name(name)
        return None

    @staticmethod
    def _infer_entity_type_label(name: str) -> Optional[str]:
        try:
            text = (name or "").strip()
            low = text.lower()
            # Dates
            if re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", low):
                return "DateEntity"
            # Money
            if re.search(r"\$\s*\d|\b(usd|eur|gbp)\b|\d[,\d]*\.\d{2}", low):
                return "MonetaryAmount"
            # Court / Case
            if " court" in low or "court o" in low or "appeals" in low:
                return "Court"
            if re.search(r"\b(v\.|vs|versus)\b", low):
                return "Case"
            # Statute / Regulation
            if " u.s.c" in low or " code" in low or " statute" in low or "§" in text:
                return "Statute"
            if " regulation" in low or " cfr" in low:
                return "Regulation"
            # Law Enforcement
            if "police" in low or "sheri" in low or "fbi" in low:
                return "LawEnforcementAgency"
            # Org / Party
            if re.search(r"\b(inc\.|llc|corp\.|ltd\.|company|incorporated)\b", low):
                return "Party"
            # Document types
            if low.startswith("motion ") or " motion" in low:
                return "Motion"
            if " order" in low:
                return "Order"
            # Location
            if re.search(r"\b(county|city|street|avenue|road|st\.|ave\.|rd\.)\b", low):
                return "LocationEntity"
            # Person (two capitalized words heuristic)
            if re.match(r"^[A-Z][a-z]+\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)?$", text):
                return "Person"
        except Exception:
            pass
        return None

    @staticmethod
    def _infer_relationship_type(rel: str) -> str:
        s = (rel or "").strip().lower()
        if "cite" in s:
            return "cites"
        if "overrule" in s:
            return "overrules"
        if "distinguish" in s:
            return "distinguishes"
        if "follow" in s:
            return "follows"
        if "filed" in s:
            return "filed_by"
        if "represent" in s:
            return "represents"
        if "decid" in s:
            return "decided_by"
        if "support" in s:
            return "supports"
        if "conflict" in s:
            return "conflicts_with"
        if "relat" in s:
            return "related_to"
        return s or "related_to"

    @staticmethod
    def _extract_entity_attributes(name: str, etype_label: str) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {}
        text = name or ""
        if etype_label == "DateEntity":
            m = re.search(r"(\d{4}-\d{2}-\d{2}|\b\d{1,2}/\d{1,2}/\d{2,4}\b)", text)
            if m:
                attrs["date_value"] = m.group(1)
        elif etype_label == "MonetaryAmount":
            m = re.search(r"(\$\s*\d[\d,]*\.?\d{0,2})", text)
            if m:
                attrs["amount"] = m.group(1)
            c = re.search(r"\b(USD|EUR|GBP|usd|eur|gbp)\b", text)
            if c:
                attrs["currency"] = c.group(1).upper()
        elif etype_label == "Statute":
            m = re.search(r"(§\s*\d+[\w\.-]*|\b\d+\s*U\.S\.C\.\s*§?\s*\d+[\w\.-]*)", text)
            if m:
                attrs["citation"] = m.group(1)
        elif etype_label == "Court":
            attrs["court_name"] = text
        elif etype_label == "Case":
            m = re.search(r"(No\.?\s*[A-Za-z0-9\-]+)", text)
            if m:
                attrs["case_number"] = m.group(1)
        elif etype_label == "LocationEntity":
            attrs["location_name"] = text
        elif etype_label in ("Person", "Party"):
            attrs["name"] = text
        return attrs

    async def import_triples(self, triples: List[Tuple[str, str, str]],
                             entity_type: str = "generic",
                             entity_type_label: str = None,
                             create_missing: bool = True,
                             use_heuristics: bool = True) -> Dict[str, int]:

        if not self._check_available():
            raise RuntimeError("Knowledge manager unavailable")

        created_entities = 0
        created_rels = 0

        default_type = entity_type or "generic"
        if entity_type_label:
            try:
                from agents.extractors.ontology import get_entity_type_by_label
                et = get_entity_type_by_label(entity_type_label)
                if et is not None:
                    default_type = et.value.label
            except Exception:
                pass

        for head, rel, tail in triples:
            h_id = await self._find_entity_id_by_name(head)
            t_id = await self._find_entity_id_by_name(tail)

            if create_missing:
                if not h_id:
                    inferred = self._infer_entity_type_label(head) if use_heuristics else None
                    etype = default_type
                    if inferred:
                        try:
                            from agents.extractors.ontology import get_entity_type_by_label
                            if get_entity_type_by_label(inferred):
                                etype = inferred
                        except Exception:
                            pass
                    attrs = self._extract_entity_attributes(head, etype)
                    res = await self.add_entity(name=head, entity_type=etype, attributes=attrs)
                    h_id = res.get("id")
                    created_entities += 1

                if not t_id:
                    inferred = self._infer_entity_type_label(tail) if use_heuristics else None
                    etype = default_type
                    if inferred:
                        try:
                            from agents.extractors.ontology import get_entity_type_by_label
                            if get_entity_type_by_label(inferred):
                                etype = inferred
                        except Exception:
                            pass
                    attrs = self._extract_entity_attributes(tail, etype)
                    res = await self.add_entity(name=tail, entity_type=etype, attributes=attrs)
                    t_id = res.get("id")
                    created_entities += 1

            if not h_id or not t_id:
                continue

            rel_norm = self._infer_relationship_type(rel)
            res = await self.add_relationship(source_id=h_id, target_id=t_id, relation_type=rel_norm)
            if res.get("id"):
                created_rels += 1

        return {
            "created_entities": created_entities,
            "created_relationships": created_rels,
        }

    async def import_entities(self, items: List[Dict[str, Any]], use_heuristics: bool = True) -> Dict[str, int]:
        if not self._check_available():
            raise RuntimeError("Knowledge manager unavailable")

        created = 0
        for it in items:
            name = str(it.get("name", "")).strip()
            if not name:
                continue
            etype = (it.get("entity_type") or "generic").strip()
            label = (it.get("entity_type_label") or "").strip() or None
            if label:
                try:
                    from agents.extractors.ontology import get_entity_type_by_label
                    et = get_entity_type_by_label(label)
                    if et is not None:
                        etype = et.value.label
                except Exception:
                    pass
            attrs = it.get("attributes") or {}
            if use_heuristics and label and not attrs:
                attrs = self._extract_entity_attributes(name, label)
            res = await self.add_entity(name=name, entity_type=etype, attributes=attrs)
            if res.get("id"):
                created += 1
        return {"created": created}

    async def add_proposal(self, kind: str, data: Dict[str, Any]) -> Dict[str, int]:
        pid = self.db.knowledge_add_proposal(
            proposal_type=kind,
            payload=data,
            source="knowledge_service",
            status="proposed",
        )
        return {"id": int(pid)}

    async def list_proposals(self) -> Dict[str, Any]:
        items = self.db.knowledge_list_proposals(status="proposed", limit=1000, offset=0)
        normalized = [
            {"id": int(x.get("id")), "kind": x.get("proposal_type"), "data": x.get("payload_json") or {}}
            for x in items
        ]
        return {"items": normalized, "count": len(normalized)}

    async def approve_proposal(self, proposal_id: int) -> Dict[str, Any]:
        prop = self.db.knowledge_get_proposal(proposal_id)
        if not prop:
            return None
        if str(prop.get("status")) != "proposed":
            return {"approved": False, "reason": f"Proposal is {prop.get('status')}"}

        kind = str(prop.get("proposal_type") or "")
        data = prop.get("payload_json") or {}

        if kind == "entity":
            res = await self.add_entity(
                name=data.get("name"),
                entity_type=data.get("entity_type"),
                attributes=data.get("attributes"),
                content=data.get("content"),
                jurisdiction=data.get("jurisdiction"),
                legal_domain=data.get("legal_domain"),
            )
            self.db.knowledge_update_proposal_status(proposal_id, status="approved")
            return {"approved": True, "created": res}

        if kind == "relationship":
            res = await self.add_relationship(
                source_id=data.get("source_id"),
                target_id=data.get("target_id"),
                relation_type=data.get("relation_type"),
                properties=data.get("properties"),
            )
            self.db.knowledge_update_proposal_status(proposal_id, status="approved")
            return {"approved": True, "created": res}

        self.db.knowledge_update_proposal_status(proposal_id, status="rejected", review_note="Unknown proposal kind")
        return {"approved": False, "reason": "Unknown proposal kind"}

    async def reject_proposal(self, proposal_id: int) -> bool:
        return self.db.knowledge_update_proposal_status(
            proposal_id,
            status="rejected",
            review_note="Rejected by user",
        )

    async def query_subgraph(self, node_id: str, depth: int = 1) -> Dict[str, Any]:
        """
        Retrieve a subgraph centered around a node.
        """
        if not self._check_available():
            raise RuntimeError("Knowledge manager unavailable")

        # Assuming manager API
        return await self.knowledge_manager.get_subgraph(node_id, depth)

    async def get_graph_data(self) -> Dict[str, Any]:
        """
        Get full graph data for visualization.
        """
        if not self._check_available():
            raise RuntimeError("Knowledge manager unavailable")

        if hasattr(self.knowledge_manager, "export_graph_data"):
            return await self.knowledge_manager.export_graph_data()
        return {"nodes": [], "edges": []}

