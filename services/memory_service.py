"""
Memory Service
==============
Handles memory proposal lifecycle and memory management.
Encapsulates interaction with proposals database and main memory manager.
"""

import json
import logging
import uuid
import collections
from datetime import datetime
from typing import Any, Dict, List, Optional

from mem_db.memory import proposals_db
from mem_db.memory.memory_interfaces import MemoryRecord, MemoryType

logger = logging.getLogger(__name__)

# Simple sensitive terms and patterns for auto-flagging
SENSITIVE_TERMS = [
    "privileged",
    "confidential",
    "attorney-client",
    "sealed",
    "SSN",
    "social security",
    "medical",
    "HIPAA",
    "trade secret",
    "proprietary",
]

class MemoryService:
    """
    Service for Memory Proposal interactions and Memory Management.
    """
    def __init__(self, memory_manager: Any = None, config_manager: Any = None):
        self.memory_manager = memory_manager
        self.config_manager = config_manager
        self._approved_index: Dict[str, str] = {}
        # Ensure schema exists
        try:
            proposals_db.init_schema()
        except Exception as e:
            logger.error(f"Failed to init proposals db schema: {e}")

    def set_managers(self, memory_manager: Any, config_manager: Any):
        """Post-init injection if needed."""
        self.memory_manager = memory_manager
        self.config_manager = config_manager

    async def _store_memory_record(self, payload_dict: Dict[str, Any]) -> Optional[str]:
        """Store a record into the main MemoryManager."""
        try:
            # Convert string type to Enum
            m_type = MemoryType.ANALYSIS
            try:
                m_type_str = payload_dict.get("memory_type", "analysis")
                m_type = MemoryType(m_type_str)
            except Exception:
                pass

            rec = MemoryRecord(
                record_id=str(uuid.uuid4()),
                namespace=payload_dict.get("namespace", "default"),
                key=payload_dict.get("key", "unknown"),
                content=payload_dict.get("content", ""),
                memory_type=m_type,
                agent_id=payload_dict.get("agent_id"),
                document_id=payload_dict.get("document_id"),
                metadata=payload_dict.get("metadata") or {},
                importance_score=float(payload_dict.get("importance_score", 1.0)),
                confidence_score=float(payload_dict.get("confidence_score", 1.0)),
            )
            
            if self.memory_manager:
                rid = await self.memory_manager.store(rec)
                return rid
            return None
        except Exception as e:
            logger.error(f"Error storing memory record: {e}")
            return None

    def _norm_key(self, namespace: str, key: str) -> str:
        return f"{namespace}::{key}"

    def _normalize_content(self, content: str) -> str:
        return (content or "").strip().lower()

    def _auto_flags(self, payload: Dict[str, Any]) -> List[str]:
        flags: List[str] = []
        # Low confidence
        try:
            val = float(payload.get("confidence_score", 1.0))
            if val < 0.5:
                flags.append("low_confidence")
        except Exception:
            pass
        # High impact heuristic
        try:
            val = float(payload.get("importance_score", 1.0))
            if val >= 0.85:
                flags.append("high_impact")
        except Exception:
            pass
        # Sensitive content
        content_l = self._normalize_content(payload.get("content", ""))
        for term in SENSITIVE_TERMS:
            if term.lower() in content_l:
                flags.append("sensitive")
                break # Optimization: one hit is enough for 'sensitive' flag usually, or all? 
                      # Logic in route was: if any(...). So yes.
        
        # Conflict with approved index
        nk = self._norm_key(payload.get("namespace", ""), payload.get("key", ""))
        prev = self._approved_index.get(nk)
        if prev is not None and prev != content_l:
            flags.append("conflict")
        return flags

    async def get_pending_proposals(self, limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
        """Get memory proposals awaiting review."""
        try:
            return proposals_db.list_proposals(limit=limit, offset=offset)
        except Exception as e:
            logger.error(f"Error listing proposals: {e}")
            return []

    async def create_proposal(self, proposal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new memory proposal.
        Auto-approves if confidence is high enough.
        """
        threshold = 0.7
        try:
            if self.config_manager:
                 # Helper to safely get float
                 val = self.config_manager.get_float("memory.approval_threshold", threshold)
                 threshold = float(val)
        except Exception:
            pass

        # Prepare proposal dict
        proposal = {
            "namespace": proposal_data.get("namespace"),
            "key": proposal_data.get("key"),
            "content": proposal_data.get("content"),
            "memory_type": proposal_data.get("memory_type", "analysis"),
            "agent_id": proposal_data.get("agent_id"),
            "document_id": proposal_data.get("document_id"),
            "metadata": proposal_data.get("metadata"),
            "confidence_score": float(proposal_data.get("confidence_score", 1.0)),
            "importance_score": float(proposal_data.get("importance_score", 1.0)),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }
        
        proposal["flags"] = self._auto_flags(proposal)

        stored_record_id: Optional[str] = None
        
        # Auto-approve logic only if memory_manager is present
        if proposal["confidence_score"] >= threshold and self.memory_manager:
            rid = await self._store_memory_record(proposal)
            if rid:
                stored_record_id = rid
                proposal["status"] = "approved"
                proposal["stored_record_id"] = rid
                # Update approved index
                self._approved_index[self._norm_key(proposal["namespace"], proposal["key"])] = (
                    self._normalize_content(proposal["content"])
                )

        # Store in DB
        try:
            db_id = proposals_db.add_proposal(proposal)
            proposal["id"] = db_id
        except Exception as e:
            logger.error(f"Failed to add proposal to DB: {e}")
            proposal["id"] = -1

        return {
            "id": proposal.get("id"),
            "status": proposal.get("status"),
            "stored_record_id": stored_record_id,
        }

    async def approve_proposal(self, proposal_id: int, corrections: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Approve a proposal, potentially with corrections."""
        # Find proposal
        all_props = proposals_db.list_proposals(limit=1000)
        p = next((x for x in all_props if x.get("id") == proposal_id), None)
        
        if not p:
            raise ValueError("Proposal not found")
        
        if p.get("status") == "approved":
            return {
                "id": p["id"],
                "status": p["status"],
                "stored_record_id": p.get("stored_record_id"),
            }

        # Construct payload for storage - handling DB row vs Dict
        # DB rows usually return keys as strings in sqlite3.Row, but need to be careful with JSON fields
        
        # Helper to get field
        def get_field(row, key, default=None):
            if isinstance(row, dict):
                return row.get(key, default)
            return row[key] if key in row.keys() else default

        metadata_json = get_field(p, "metadata_json", "{}")
        metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else (metadata_json or {})

        payload_dict = {
            "namespace": get_field(p, "namespace"),
            "key": get_field(p, "key"),
            "content": get_field(p, "content"),
            "memory_type": get_field(p, "memory_type"),
            "agent_id": get_field(p, "agent_id"),
            "document_id": get_field(p, "document_id"),
            "metadata": metadata,
            "confidence_score": get_field(p, "confidence", 1.0), # mapped name in DB
            "importance_score": get_field(p, "importance", 1.0), # mapped name in DB
        }

        # Apply corrections
        if corrections:
            payload_dict.update(corrections)

        if not self.memory_manager:
            raise ValueError("Memory Manager unavailable")

        rid = await self._store_memory_record(payload_dict)
        if not rid:
            raise ValueError("Failed to store memory record")
        
        approved_at = datetime.now().isoformat()
        
        # Update DB
        proposals_db.approve_proposal(proposal_id, rid, approved_at)
        
        # Update index
        self._approved_index[self._norm_key(payload_dict["namespace"], payload_dict["key"])] = (
             self._normalize_content(payload_dict["content"])
        )

        return {
            "id": proposal_id,
            "status": "approved",
            "stored_record_id": rid
        }

    async def reject_proposal(self, proposal_id: int) -> Dict[str, Any]:
        p = None
        all_props = proposals_db.list_proposals(limit=1000)
        p = next((x for x in all_props if x.get("id") == proposal_id), None)
        
        if not p:
            raise ValueError("Proposal not found")
            
        rejected_at = datetime.now().isoformat()
        proposals_db.reject_proposal(proposal_id, rejected_at)
        return {"id": proposal_id, "status": "rejected"}

    async def correct_record(self, record_id: str, updates: Dict[str, Any]) -> bool:
        if not self.memory_manager:
            return False
        
        rec = await self.memory_manager.retrieve(record_id)
        if not rec:
            return False
            
        if "content" in updates:
            rec.content = updates["content"]
        if "metadata" in updates:
            if rec.metadata:
                rec.metadata.update(updates["metadata"])
            else:
                rec.metadata = updates["metadata"]
        if "importance_score" in updates:
            rec.importance_score = float(updates["importance_score"])
        if "confidence_score" in updates:
            rec.confidence_score = float(updates["confidence_score"])
            
        return await self.memory_manager.update(rec)

    async def delete_record(self, record_id: str) -> bool:
        if not self.memory_manager:
            return False
        return await self.memory_manager.delete(record_id)

    async def get_flagged_proposals(self) -> Dict[str, Any]:
        items = proposals_db.list_proposals(limit=1000)
        flagged = []
        counts: Dict[str, int] = collections.defaultdict(int)
        
        for p in items:
            flags = None
            if isinstance(p, dict):
                flags = p.get("flags_json")
            else:
                try:
                    flags = p["flags_json"]
                except:
                    pass

            if isinstance(flags, str):
                try:
                    flags_list = json.loads(flags)
                except:
                    flags_list = []
            else:
                flags_list = flags if isinstance(flags, list) else []
            
            # DB rows might need conversion to dict to modify
            p_dict = dict(p) if not isinstance(p, dict) else p.copy()
            
            if flags_list:
                p_dict["flags"] = flags_list
                flagged.append(p_dict)
                for f in flags_list:
                    counts[f] += 1
                    
        return {"count": len(flagged), "flags": dict(counts), "items": flagged}

    async def get_stats(self) -> Dict[str, Any]:
        try:
            return proposals_db.stats()
        except:
            items = proposals_db.list_proposals(limit=1000)
            by_status = collections.defaultdict(int)
            for p in items:
                status = p.get("status") if isinstance(p, dict) else p["status"]
                by_status[status or "pending"] += 1
            return {
                "total": len(items),
                "by_status": dict(by_status),
                "approved_index_size": len(self._approved_index)
            }
