"""
API routes for the Data Explorer.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from mem_db.memory.unified_memory_manager import UnifiedMemoryManager
from services.code_hotspot_service import code_hotspot_service
from services.data_integrity_service import data_integrity_service
from services.memory_cluster_service import memory_cluster_service

router = APIRouter()
_memory_manager_fallback: Optional[UnifiedMemoryManager] = None
_FILE_INDEX_DB_PATH = Path("databases") / "file_index.db"


async def get_memory_manager_dep(request: Request) -> UnifiedMemoryManager:
    """
    Resolve memory manager from service container first, then fallback to local init.
    """
    global _memory_manager_fallback

    services = getattr(request.app.state, "services", None)
    if services is not None and hasattr(services, "get_service"):
        for key in (UnifiedMemoryManager, "unified_memory_manager"):
            try:
                manager = await services.get_service(key)
                if manager is not None:
                    return manager
            except Exception:
                continue

    if _memory_manager_fallback is None:
        _memory_manager_fallback = UnifiedMemoryManager()
    initialized = await _memory_manager_fallback.initialize()
    if not initialized:
        raise HTTPException(status_code=503, detail="unified_memory_manager_unavailable")
    return _memory_manager_fallback

# DTOs
class QueryPayload(BaseModel):
    query: str

class MemoryLinkPayload(BaseModel):
    memory_record_id: str
    file_path: str
    relation_type: str = "references"
    confidence: float = 1.0
    source: str = "data_explorer_api"

class LinkedMemoryResponse(BaseModel):
    memory_record_id: str
    file_path: str
    relation_type: str
    link_confidence: float
    link_source: str
    linked_at: str
    namespace: str
    key: str
    content: str
    memory_type: str
    agent_id: Optional[str]
    document_id: Optional[str]
    metadata: Dict[str, Any]
    importance_score: float
    confidence_score: float
    updated_at: str

class LinkedFileResponse(BaseModel):
    memory_record_id: str
    file_path: str
    relation_type: str
    link_confidence: float
    link_source: str
    linked_at: str


class DataIntegrityIssueResponse(BaseModel):
    check_name: str
    issue_count: int
    severity: str
    details: str
    recommended_action: str


class DataIntegrityReportResponse(BaseModel):
    status: str
    total_checks: int
    total_issues: int
    highest_severity: str
    issues: List[DataIntegrityIssueResponse]
    actions: List[str]


class CodeHotspotResponse(BaseModel):
    file_path: str
    change_events: int
    issue_weight: int
    complexity_score: float
    hotspot_score: float
    risk_level: str
    recommended_action: str


class MemoryClusterResponse(BaseModel):
    cluster_id: str
    size: int
    memory_ids: List[str]
    memory_types: List[str]
    top_terms: List[str]
    summary: str

class SummarizeMemoriesPayload(BaseModel):
    memory_record_ids: List[str]
    summary_type: str = "concise"
    target_length: int = 150

class SummarizedMemoryResponse(BaseModel):
    record_id: str
    namespace: str
    key: str
    content: str
    memory_type: str
    agent_id: Optional[str]
    document_id: Optional[str]
    metadata: Dict[str, Any]

def _query_file_index(limit: int = 100) -> List[Dict[str, Any]]:
    if not _FILE_INDEX_DB_PATH.exists():
        return []
    sql = """
    SELECT
        f.file_path,
        COALESCE(f.file_type, '') AS file_type,
        COALESCE(f.file_category, '') AS file_category,
        COALESCE(a.primary_purpose, '') AS primary_purpose,
        COALESCE(a.analysis_timestamp, '') AS last_analyzed
    FROM files f
    LEFT JOIN (
        SELECT file_path, primary_purpose, analysis_timestamp
        FROM file_analysis
        WHERE id IN (SELECT MAX(id) FROM file_analysis GROUP BY file_path)
    ) a ON a.file_path = f.file_path
    ORDER BY f.last_scanned_at DESC
    LIMIT ?
    """
    with sqlite3.connect(str(_FILE_INDEX_DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, (limit,)).fetchall()
    return [dict(row) for row in rows]


@router.post("/query")
async def query_data(
    payload: QueryPayload,
    memory_manager: UnifiedMemoryManager = Depends(get_memory_manager_dep)
):
    """
    Accepts a natural language query and returns structured data from the project's databases.
    """
    query = payload.query.lower().strip()

    if any(token in query for token in ("file", "files", "code")):
        return {
            "source": "file_index",
            "data": _query_file_index(limit=100),
        }
    elif any(token in query for token in ("memory", "memories")):
        records = await memory_manager.get_all_records(limit=100)
        return {
            "source": "unified_memory",
            "data": [
                {
                    "record_id": record.record_id,
                    "namespace": record.namespace,
                    "key": record.key,
                    "content": record.content,
                    "memory_type": record.memory_type.value,
                    "agent_id": record.agent_id,
                    "document_id": record.document_id,
                }
                for record in records
            ],
        }
    else:
        return {"source": "unknown", "data": []}

@router.get("/file-memories", response_model=List[LinkedMemoryResponse])
async def lookup_file_memories(
    file_path: str,
    memory_manager: UnifiedMemoryManager = Depends(get_memory_manager_dep)
):
    """Retrieve memories linked to a file path from the memory-code edge table."""
    try:
        memories = await memory_manager.get_memories_for_file(file_path=file_path)
        return memories
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"file_memory_lookup_failed: {exc}")

@router.get("/memory-files", response_model=List[LinkedFileResponse])
async def lookup_memory_files(
    memory_record_id: str,
    memory_manager: UnifiedMemoryManager = Depends(get_memory_manager_dep)
):
    """Retrieve file paths linked to a memory record from the memory-code edge table."""
    try:
        files = await memory_manager.get_files_for_memory(memory_record_id=memory_record_id)
        return files
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"memory_file_lookup_failed: {exc}")


@router.post("/memory-links")
async def create_memory_link(
    payload: MemoryLinkPayload,
    memory_manager: UnifiedMemoryManager = Depends(get_memory_manager_dep)
):
    """Create or update a memory-code edge link."""
    try:
        ok = await memory_manager.link_memory_to_file(
            memory_record_id=payload.memory_record_id,
            file_path=payload.file_path,
            relation_type=payload.relation_type,
            confidence=payload.confidence,
            source=payload.source,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="memory_record_not_found")
        return {
            "success": True,
            "memory_record_id": payload.memory_record_id,
            "file_path": payload.file_path,
        }
    except HTTPException as h_exc:
        raise h_exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"memory_link_create_failed: {exc}")


@router.get("/integrity-report", response_model=DataIntegrityReportResponse)
async def get_data_integrity_report():
    """Generate and return a current integrity report with remediation actions."""
    try:
        return data_integrity_service.generate_report()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"integrity_report_failed: {exc}")


@router.get("/hotspots", response_model=List[CodeHotspotResponse])
async def get_code_hotspots(limit: int = 50):
    """Return ranked code hotspots based on change/issue/complexity signals."""
    try:
        return code_hotspot_service.get_hotspots(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"hotspot_report_failed: {exc}")


@router.get("/memory-clusters", response_model=List[MemoryClusterResponse])
async def get_memory_clusters(
    limit: int = 200,
    min_cluster_size: int = 2,
    n_clusters: int = 5, # Expose n_clusters to API
    memory_manager: UnifiedMemoryManager = Depends(get_memory_manager_dep),
):
    """Cluster memories and return condensed summaries."""
    try:
        return await memory_cluster_service.generate_clusters(
            memory_manager=memory_manager,
            limit=limit,
            min_cluster_size=min_cluster_size,
            n_clusters=n_clusters,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"memory_clusters_failed: {exc}")

@router.post("/memory-summaries", response_model=SummarizedMemoryResponse)
async def summarize_memories(
    payload: SummarizeMemoriesPayload,
    memory_manager: UnifiedMemoryManager = Depends(get_memory_manager_dep)
):
    """Summarize a list of memory records into a new, condensed memory record."""
    try:
        # Retrieve the actual MemoryRecord objects based on IDs
        memory_records = []
        for record_id in payload.memory_record_ids:
            record = await memory_manager.retrieve(record_id)
            if record:
                memory_records.append(record)
        
        if not memory_records:
            raise HTTPException(status_code=404, detail="no_memory_records_found_for_summarization")

        summary_record = await memory_manager.summarize_memories(
            memory_records=memory_records,
            summary_type=payload.summary_type,
            target_length=payload.target_length,
        )
        if not summary_record:
            raise HTTPException(status_code=500, detail="memory_summarization_failed")
        
        return SummarizedMemoryResponse(
            record_id=summary_record.record_id,
            namespace=summary_record.namespace,
            key=summary_record.key,
            content=summary_record.content,
            memory_type=summary_record.memory_type.value,
            agent_id=summary_record.agent_id,
            document_id=summary_record.document_id,
            metadata=summary_record.metadata,
        )
    except HTTPException as h_exc:
        raise h_exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"memory_summarization_failed: {exc}")
