from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from .memory_interfaces import MemoryRecord, MemoryType, SearchResult


class LightMemoryManager:
    """Minimal in-process async memory manager fallback.

    Used when full UnifiedMemoryManager cannot be initialized.
    """

    def __init__(self) -> None:
        self._records: Dict[str, MemoryRecord] = {}
        self._initialized = True

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def store(self, record: MemoryRecord) -> str:
        rid = record.record_id or str(uuid.uuid4())
        record.record_id = rid
        record.updated_at = datetime.now()
        self._records[rid] = record
        return rid

    async def retrieve(self, record_id: str) -> Optional[MemoryRecord]:
        rec = self._records.get(record_id)
        if rec:
            rec.update_access()
        return rec

    async def search(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        namespace: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.0,
    ) -> List[SearchResult]:
        q = (query or "").lower().strip()
        out: List[SearchResult] = []
        for rec in self._records.values():
            if memory_type and rec.memory_type != memory_type:
                continue
            if namespace and rec.namespace != namespace:
                continue
            if agent_id and rec.agent_id != agent_id:
                continue
            text = f"{rec.key} {rec.content}".lower()
            sim = 1.0 if q and q in text else (0.65 if q else 0.5)
            if sim < min_similarity:
                continue
            out.append(
                SearchResult(
                    record=rec,
                    similarity_score=sim,
                    relevance_score=min(1.0, rec.confidence_score),
                    match_type="keyword",
                )
            )
        out.sort(key=lambda x: x.combined_score, reverse=True)
        return out[:limit]

    async def update(self, record: MemoryRecord) -> bool:
        if record.record_id not in self._records:
            return False
        record.updated_at = datetime.now()
        self._records[record.record_id] = record
        return True

    async def delete(self, record_id: str) -> bool:
        return self._records.pop(record_id, None) is not None

    async def get_statistics(self) -> Dict[str, Any]:
        return {"total_records": len(self._records), "backend": "light-memory"}

    async def cleanup_expired(self) -> int:
        return 0

    async def get_all_records(
        self,
        memory_type: Optional[MemoryType] = None,
        namespace: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[MemoryRecord]:
        vals = list(self._records.values())
        out = []
        for rec in vals:
            if memory_type and rec.memory_type != memory_type:
                continue
            if namespace and rec.namespace != namespace:
                continue
            if agent_id and rec.agent_id != agent_id:
                continue
            out.append(rec)
        return out[:limit]

    async def batch_store(self, records: List[MemoryRecord]) -> List[str]:
        ids = []
        for r in records:
            ids.append(await self.store(r))
        return ids

    async def batch_delete(self, record_ids: List[str]) -> int:
        n = 0
        for rid in record_ids:
            if await self.delete(rid):
                n += 1
        return n

    async def export_data(self, format: str = "json") -> bytes:
        # lightweight stub
        return b"[]"

    async def import_data(self, data: bytes, format: str = "json") -> int:
        return 0

    async def get_shared_knowledge(self, agent_id: str, limit: int = 20):
        # return records from other agents
        out = [r for r in self._records.values() if r.agent_id and r.agent_id != agent_id]
        return out[:limit]

    async def close(self) -> None:
        return None
