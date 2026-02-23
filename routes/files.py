from datetime import datetime, timezone
import asyncio
import functools
import logging
import re
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from services.dependencies import get_database_manager_strict_dep
from services.file_index_service import FileIndexService
from services.organization_service import OrganizationService
from services.semantic_file_service import SemanticFileService
from services.taskmaster_service import TaskMasterService

router = APIRouter()
logger = logging.getLogger(__name__)


class FileIndexRequest(BaseModel):
    roots: List[str]
    recursive: bool = True
    allowed_exts: Optional[List[str]] = None
    include_paths: Optional[List[str]] = None
    exclude_paths: Optional[List[str]] = None
    min_size_bytes: Optional[int] = None
    max_size_bytes: Optional[int] = None
    modified_after_ts: Optional[float] = None
    max_files: int = 5000
    max_depth: Optional[int] = None
    max_runtime_seconds: Optional[float] = None
    follow_symlinks: bool = False


class WatchRequest(BaseModel):
    path: str
    recursive: bool = True
    keywords: Optional[List[str]] = None
    allowed_exts: Optional[List[str]] = None
    active: bool = True


class SemanticEnrichRequest(BaseModel):
    embedding_model: str = "local-hash-v1"


class SemanticSearchRequest(BaseModel):
    embedding: List[float]
    embedding_model: str = "local-hash-v1"
    top_k: int = 10
    min_similarity: float = 0.0
    file_id: Optional[int] = None


class SemanticBulkEnrichRequest(BaseModel):
    embedding_model: str = "local-hash-v1"
    batch_size: int = 100
    max_files: int = 100000
    offset: int = 0
    sleep_ms: int = 0
    status: Optional[str] = "ready"
    ext: Optional[str] = None
    q: Optional[str] = None


class CrawlRequest(BaseModel):
    roots: List[str]
    recursive: bool = True
    allowed_exts: Optional[List[str]] = None
    include_paths: Optional[List[str]] = None
    exclude_paths: Optional[List[str]] = None
    min_size_bytes: Optional[int] = None
    max_size_bytes: Optional[int] = None
    modified_after_ts: Optional[float] = None
    max_files_total: int = 100000
    batch_size: int = 2000
    max_runtime_seconds_per_pass: float = 20.0
    max_passes: int = 200
    sleep_ms: int = 0
    max_depth: Optional[int] = None
    follow_symlinks: bool = False
    start_after_path: Optional[str] = None


class ReorgAutopilotRequest(BaseModel):
    root_prefix: str
    allowed_exts: Optional[List[str]] = None
    max_files_total: int = 100000
    crawl_batch_size: int = 2000
    crawl_pass_runtime_seconds: float = 20.0
    crawl_max_passes: int = 300
    crawl_sleep_ms: int = 25
    embedding_model: str = "Qwen3-Embedding"
    embedding_batch_size: int = 64
    embedding_sleep_ms: int = 25
    generate_limit: int = 5000
    apply_limit: int = 100000
    dry_run: bool = False
    follow_symlinks: bool = False


def _human_size(n: Optional[int]) -> Optional[str]:
    if n is None:
        return None
    units = ["B", "KB", "MB", "GB", "TB"]
    val = float(n)
    for u in units:
        if val < 1024.0 or u == units[-1]:
            return f"{val:.1f} {u}" if u != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{n} B"


def _to_iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return None


def _extract_embedded_dates(text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    seen = set()
    if not text:
        return events

    patterns = [
        (r"\b(\d{4})-(\d{2})-(\d{2})\b", "%Y-%m-%d"),
        (r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", None),
    ]

    for pat, fmt in patterns:
        for m in re.finditer(pat, text):
            raw = m.group(0)
            if raw in seen:
                continue
            seen.add(raw)
            ts_iso = None
            try:
                if fmt:
                    dtv = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                else:
                    a, b, c = raw.split("/")
                    year = int(c) + 2000 if len(c) == 2 else int(c)
                    dtv = datetime(year, int(a), int(b), tzinfo=timezone.utc)
                ts_iso = dtv.isoformat()
            except Exception:
                ts_iso = None

            events.append({
                "type": "embedded_date",
                "ts": ts_iso,
                "detail": f"Date found in file text/path: {raw}",
                "raw": raw,
                "confidence": 0.7 if ts_iso else 0.3,
            })
    return events


def _extract_candidate_entities(text: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    if not text:
        return candidates

    seen: set[tuple[str, str]] = set()

    def _push(label: str, value: str, confidence: float, provenance: str) -> None:
        key = (label, value.strip())
        if not value.strip() or key in seen:
            return
        seen.add(key)
        candidates.append(
            {
                "label": label,
                "text": value.strip(),
                "confidence": confidence,
                "provenance": provenance,
            }
        )

    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", text):
        _push("Person", m.group(0), 0.55, "regex:title_case_name")

    for m in re.finditer(r"\b(?:[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:Inc|LLC|Ltd|Corp|Corporation|Department|Agency|University)\b", text):
        _push("Organization", m.group(0), 0.65, "regex:org_suffix")

    for m in re.finditer(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}|\d{1,5}\s+[A-Z][A-Za-z0-9\s]+\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Lane|Ln))\b", text):
        _push("Location", m.group(0), 0.6, "regex:location_pattern")

    for ev in _extract_embedded_dates(text):
        raw = str(ev.get("raw") or "")
        if raw:
            _push("Date", raw, float(ev.get("confidence") or 0.6), "regex:date")

    for m in re.finditer(r"\b(?:THC|CBD|HHC|Delta-?9|lab report|case\s*#?\s*[A-Za-z0-9\-]+)\b", text, flags=re.IGNORECASE):
        _push("DomainTerm", m.group(0), 0.7, "regex:domain_term")

    return candidates


def _file_system_view(meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "owner_uid": meta.get("owner_uid"),
        "owner_gid": meta.get("owner_gid"),
        "owner_user": meta.get("owner_user"),
        "owner_group": meta.get("owner_group"),
        "mode": meta.get("mode"),
        "mode_octal": meta.get("mode_octal"),
        "permissions": meta.get("permissions"),
        "fs_attrs": meta.get("fs_attrs") or {},
        "timestamps": {
            "modified": meta.get("mtime"),
            "modified_iso": meta.get("mtime_iso") or _to_iso(meta.get("mtime")),
            "accessed": meta.get("atime"),
            "accessed_iso": meta.get("atime_iso") or _to_iso(meta.get("atime")),
            "changed": meta.get("ctime"),
            "changed_iso": meta.get("ctime_iso") or _to_iso(meta.get("ctime")),
            "created": meta.get("created"),
            "created_iso": meta.get("created_iso") or _to_iso(meta.get("created")),
        },
    }


@router.post("/index")
async def index_files(
    payload: FileIndexRequest,
    use_taskmaster: bool = Query(True),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    allowed = [e.lower() if e.startswith(".") else f".{e.lower()}" for e in (payload.allowed_exts or [])]
    if use_taskmaster:
        tm = TaskMasterService(db)
        return await run_in_threadpool(
            functools.partial(
                tm.run_file_pipeline,
                mode="index",
                payload={
                    "mode": "index",
                    "roots": payload.roots,
                    "recursive": payload.recursive,
                    "allowed_exts": allowed,
                    "include_paths": payload.include_paths,
                    "exclude_paths": payload.exclude_paths,
                    "min_size_bytes": payload.min_size_bytes,
                    "max_size_bytes": payload.max_size_bytes,
                    "modified_after_ts": payload.modified_after_ts,
                    "max_files": payload.max_files,
                    "max_depth": payload.max_depth,
                    "max_runtime_seconds": payload.max_runtime_seconds,
                    "follow_symlinks": payload.follow_symlinks,
                },
            ),
        )

    service = FileIndexService(db)
    result = await run_in_threadpool(
        functools.partial(
            service.index_roots,
            payload.roots,
            recursive=payload.recursive,
            allowed_exts=set(allowed) or None,
            include_paths=payload.include_paths,
            exclude_paths=payload.exclude_paths,
            min_size_bytes=payload.min_size_bytes,
            max_size_bytes=payload.max_size_bytes,
            modified_after_ts=payload.modified_after_ts,
            max_files=payload.max_files,
            max_depth=payload.max_depth,
            max_runtime_seconds=payload.max_runtime_seconds,
            follow_symlinks=payload.follow_symlinks,
        ),
    )
    return result


@router.post("/watch")
async def add_watch(
    payload: WatchRequest,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    service = FileIndexService(db)
    watch_id = service.add_watch(
        path=payload.path,
        recursive=payload.recursive,
        keywords=payload.keywords or [],
        allowed_exts=payload.allowed_exts or [],
        active=payload.active,
    )
    return {"success": True, "watch_id": watch_id}


@router.get("/watch")
async def list_watches(db=Depends(get_database_manager_strict_dep)) -> Dict[str, Any]:
    items = db.list_watched_directories(active_only=False)
    return {"success": True, "total": len(items), "items": items}


@router.post("/refresh")
async def refresh_index(
    stale_after_hours: int = Query(24, ge=1, le=24 * 30),
    run_watches: bool = Query(True),
    use_taskmaster: bool = Query(True),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    if use_taskmaster:
        tm = TaskMasterService(db)
        mode = "watch_refresh" if run_watches else "refresh"
        return await run_in_threadpool(
            functools.partial(
                tm.run_file_pipeline,
                mode=mode,
                payload={
                    "mode": mode,
                    "stale_after_hours": stale_after_hours,
                },
            ),
        )

    service = FileIndexService(db)
    watch_res = (
        await run_in_threadpool(service.run_watched_index)
        if run_watches
        else {"success": True, "indexed": 0, "errors": 0, "scanned": 0, "watches": 0}
    )
    refresh_res = await run_in_threadpool(
        functools.partial(service.refresh_index, stale_after_hours=stale_after_hours),
    )
    return {"success": True, "watch": watch_res, "refresh": refresh_res}


@router.post("/crawl")
async def crawl_files(
    payload: CrawlRequest,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    """
    High-scale resumable crawler.
    Crawls in bounded passes with a lexical cursor to avoid reprocessing the same head slice.
    """
    service = FileIndexService(db)
    allowed = [e.lower() if e.startswith(".") else f".{e.lower()}" for e in (payload.allowed_exts or [])]
    batch_size = max(1, min(int(payload.batch_size), 20000))
    max_files_total = max(1, int(payload.max_files_total))
    max_passes = max(1, int(payload.max_passes))
    sleep_ms = max(0, int(payload.sleep_ms))
    max_runtime = max(1.0, float(payload.max_runtime_seconds_per_pass))

    total_indexed = 0
    total_errors = 0
    total_scanned = 0
    total_skipped = 0
    total_perm = 0
    passes_run = 0
    cursor = payload.start_after_path
    last_result: Dict[str, Any] = {}
    logger.info(
        "[crawler] start roots=%s max_files_total=%s batch_size=%s max_passes=%s pass_runtime=%.1fs sleep_ms=%s start_after=%s",
        payload.roots,
        max_files_total,
        batch_size,
        max_passes,
        max_runtime,
        sleep_ms,
        cursor,
    )

    started = time.monotonic()
    while passes_run < max_passes and total_indexed < max_files_total:
        passes_run += 1
        pass_budget = min(batch_size, max_files_total - total_indexed)
        logger.info(
            "[crawler] pass %s/%s begin budget=%s cursor=%s",
            passes_run,
            max_passes,
            pass_budget,
            cursor,
        )
        out = await run_in_threadpool(
            functools.partial(
                service.index_roots,
                payload.roots,
                recursive=payload.recursive,
                allowed_exts=set(allowed) or None,
                include_paths=payload.include_paths,
                exclude_paths=payload.exclude_paths,
                min_size_bytes=payload.min_size_bytes,
                max_size_bytes=payload.max_size_bytes,
                modified_after_ts=payload.modified_after_ts,
                max_files=pass_budget,
                max_depth=payload.max_depth,
                max_runtime_seconds=max_runtime,
                start_after_path=cursor,
                follow_symlinks=payload.follow_symlinks,
            )
        )
        last_result = out
        total_indexed += int(out.get("indexed", 0))
        total_errors += int(out.get("errors", 0))
        total_scanned += int(out.get("scanned", 0))
        total_skipped += int(out.get("skipped", 0))
        total_perm += int(out.get("permission_errors", 0))
        cursor = out.get("next_cursor") or cursor
        logger.info(
            "[crawler] pass %s end indexed=%s scanned=%s skipped=%s errors=%s truncated=%s next_cursor=%s total_indexed=%s/%s",
            passes_run,
            int(out.get("indexed", 0)),
            int(out.get("scanned", 0)),
            int(out.get("skipped", 0)),
            int(out.get("errors", 0)),
            bool(out.get("truncated", False)),
            cursor,
            total_indexed,
            max_files_total,
        )

        if not bool(out.get("truncated", False)):
            break
        if sleep_ms > 0:
            logger.info("[crawler] sleeping %sms before next pass", sleep_ms)
            await asyncio.sleep(sleep_ms / 1000.0)

    elapsed = round(time.monotonic() - started, 3)
    logger.info(
        "[crawler] complete passes=%s indexed=%s scanned=%s skipped=%s errors=%s elapsed=%.3fs completed=%s next_cursor=%s",
        passes_run,
        total_indexed,
        total_scanned,
        total_skipped,
        total_errors,
        elapsed,
        not bool(last_result.get("truncated", False)),
        cursor,
    )
    return {
        "success": True,
        "mode": "crawler",
        "passes_run": passes_run,
        "indexed": total_indexed,
        "errors": total_errors,
        "permission_errors": total_perm,
        "scanned": total_scanned,
        "skipped": total_skipped,
        "max_files_total": max_files_total,
        "batch_size": batch_size,
        "sleep_ms": sleep_ms,
        "elapsed_seconds": elapsed,
        "next_cursor": cursor,
        "completed": not bool(last_result.get("truncated", False)),
        "last_pass": last_result,
    }


@router.get("")
async def list_indexed_files(
    status: Optional[str] = Query(None),
    ext: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    sort_by: str = Query("mtime"),
    sort_dir: str = Query("desc"),
    stale_after_hours: int = Query(24, ge=1, le=24 * 30),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    items, total = db.list_indexed_files(
        limit=limit,
        offset=offset,
        status=status,
        ext=(ext.lower() if ext else None),
        query=q,
        sort_by=sort_by,
        sort_dir=sort_dir,
        keyword=keyword,
    )

    cutoff = datetime.now(timezone.utc).timestamp() - stale_after_hours * 3600
    ui_items = []
    for it in items:
        mtime_ts = it.get("mtime")
        checked_raw = it.get("last_checked_at")
        checked_iso = None
        checked_ts = None
        try:
            checked_iso = str(checked_raw)
            checked_ts = datetime.fromisoformat(checked_iso.replace("Z", "+00:00")).timestamp()
        except Exception:
            checked_ts = None

        meta = it.get("metadata_json") or {}
        ui_items.append(
            {
                **it,
                "file_size_human": _human_size(it.get("file_size")),
                "mtime_iso": _to_iso(mtime_ts),
                "is_stale": (checked_ts is None) or (checked_ts < cutoff),
                "filesystem": _file_system_view(meta),
                "scanner_provenance": meta.get("scanner") or {},
                "runtime_provenance": meta.get("runtime") or {},
                "quick_preview": {
                    "name": it.get("display_name"),
                    "ext": it.get("ext"),
                    "path": it.get("normalized_path"),
                },
            }
        )
    return {"success": True, "total": total, "items": ui_items}


@router.get("/{file_id}/quality")
async def file_quality(
    file_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    rec = db.get_indexed_file(file_id)
    if not rec:
        return {"success": False, "error": "file_not_found"}
    meta = rec.get("metadata_json") or {}
    norm = meta.get("normalization") or {}
    text_score = norm.get("text_quality_score")
    completeness_checks = [
        rec.get("status") == "ready",
        bool(rec.get("sha256")),
        bool(rec.get("mime_type")),
        meta.get("owner_uid") is not None and meta.get("owner_gid") is not None,
        bool(meta.get("permissions") or meta.get("mode")),
    ]
    completeness = round(sum(1 for c in completeness_checks if c) / len(completeness_checks), 3)
    overall_score = round((0.6 * completeness) + (0.4 * float(text_score if text_score is not None else completeness)), 3)

    return {
        "success": True,
        "file_id": file_id,
        "status": rec.get("status"),
        "last_error": rec.get("last_error"),
        "quality": {
            "readable": rec.get("status") == "ready",
            "has_sha256": bool(rec.get("sha256")),
            "mime_detected": bool(rec.get("mime_type")),
            "mime_source": rec.get("mime_source"),
            "markdown_chunk_count": meta.get("chunk_count", 0),
            "headings_count": len(meta.get("headings", []) or []),
            "has_owner": meta.get("owner_uid") is not None and meta.get("owner_gid") is not None,
            "has_permissions": bool(meta.get("permissions") or meta.get("mode")),
            "has_fs_attrs": bool(meta.get("fs_attrs")),
            "has_exif": bool((meta.get("exif") or {}).get("metadata_available")),
            "has_pdf_props": bool((meta.get("pdf") or {}).get("metadata_available")),
            "has_office_props": bool((meta.get("office") or {}).get("metadata_available")),
            "rule_tag_hit_count": len(meta.get("rule_tag_hits") or []),
            "normalization": norm,
            "completeness_score": completeness,
            "overall_score": overall_score,
        },
    }


@router.get("/{file_id}/entities")
async def file_entities(
    file_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    rec = db.get_indexed_file(file_id)
    if not rec:
        return {"success": False, "error": "file_not_found"}

    ontology_labels: List[str] = []
    try:
        from agents.extractors.ontology import LegalEntityType  # noqa: E402

        ontology_labels = [et.value.label for et in LegalEntityType]
    except Exception:
        ontology_labels = []

    ontology_set = {str(label).lower(): str(label) for label in ontology_labels}
    ontology_synonyms = {
        "org": "organization",
        "company": "organization",
        "person": "person",
        "name": "person",
        "date": "date",
        "location": "location",
    }

    meta = rec.get("metadata_json") or {}
    text_parts = [
        str(rec.get("display_name") or ""),
        str(rec.get("normalized_path") or ""),
        str(meta.get("preview") or ""),
        str((meta.get("normalization") or {}).get("normalized_preview") or ""),
    ]
    corpus = "\n".join([p for p in text_parts if p])

    matched: List[Dict[str, Any]] = []

    # Ontology label matching against corpus.
    corpus_low = corpus.lower()
    for low_label, canonical_label in ontology_set.items():
        if low_label in corpus_low:
            matched.append(
                {
                    "label": canonical_label,
                    "text": canonical_label,
                    "entity_type": canonical_label,
                    "ontology_id": low_label.replace(" ", "_"),
                    "confidence": 0.75,
                    "provenance": "rule:label_match",
                }
            )

    # Candidate extraction (names/dates/locations/orgs/domain terms)
    for cand in _extract_candidate_entities(corpus):
        cand_label_low = str(cand.get("label") or "").lower()
        mapped = ontology_synonyms.get(cand_label_low, cand_label_low)
        if mapped in ontology_set:
            canonical = ontology_set[mapped]
            matched.append(
                {
                    "label": canonical,
                    "text": cand.get("text"),
                    "entity_type": cand.get("label"),
                    "ontology_id": mapped.replace(" ", "_"),
                    "confidence": float(cand.get("confidence") or 0.6),
                    "provenance": cand.get("provenance") or "regex:candidate",
                }
            )

    # De-duplicate on ontology+text
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for ent in matched:
        key = (str(ent.get("ontology_id") or ""), str(ent.get("text") or ent.get("label") or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ent)

    unknown_candidates: List[str] = []
    for tok in set(re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", corpus)):
        if tok.lower() not in ontology_set:
            unknown_candidates.append(tok)
            try:
                if not db.knowledge_has_term(tok):
                    db.knowledge_add_question(
                        question=f"Unknown entity candidate '{tok}' found in file {file_id}. Map to ontology or ignore?",
                        context={"file_id": file_id, "file": rec.get("display_name")},
                        linked_term=tok,
                        asked_by="entity_resolver",
                    )
            except Exception:
                pass

    for ent in deduped:
        try:
            db.knowledge_upsert(
                term=str(ent.get("text") or ent.get("label") or ""),
                category="entity",
                ontology_entity_id=ent.get("ontology_id"),
                confidence=float(ent.get("confidence") or 0.5),
                status="proposed",
                source=f"file:{file_id}",
            )
        except Exception:
            pass

    if hasattr(db, "replace_file_entities"):
        try:
            db.replace_file_entities(file_id=file_id, entities=deduped)
            if hasattr(db, "refresh_file_entity_links"):
                db.refresh_file_entity_links()
        except Exception:
            pass

    return {
        "success": True,
        "file_id": file_id,
        "entities": deduped,
        "count": len(deduped),
        "unknown_candidates": sorted(set(unknown_candidates))[:25],
    }


@router.post("/{file_id}/semantic/enrich")
async def enrich_file_semantic(
    file_id: int,
    payload: SemanticEnrichRequest,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    svc = SemanticFileService(db)
    return svc.enrich_file(file_id=file_id, embedding_model=payload.embedding_model)


@router.get("/{file_id}/chunks")
async def file_chunks(
    file_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    rec = db.get_indexed_file(file_id)
    if not rec:
        return {"success": False, "error": "file_not_found"}
    chunks = db.list_file_chunks(file_id)
    return {"success": True, "file_id": file_id, "count": len(chunks), "items": chunks}


@router.get("/{file_id}/tables")
async def file_tables(
    file_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    rec = db.get_indexed_file(file_id)
    if not rec:
        return {"success": False, "error": "file_not_found"}
    tables = db.list_file_tables(file_id)
    return {"success": True, "file_id": file_id, "count": len(tables), "items": tables}


@router.post("/semantic/search")
async def semantic_similarity_search(
    payload: SemanticSearchRequest,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    results = db.semantic_similarity_search(
        query_embedding=payload.embedding,
        embedding_model=payload.embedding_model,
        limit=max(1, payload.top_k),
        min_similarity=payload.min_similarity,
        file_id=payload.file_id,
    )
    return {
        "success": True,
        "count": len(results),
        "embedding_model": payload.embedding_model,
        "results": results,
    }


@router.post("/semantic/enrich_all")
async def semantic_enrich_all(
    payload: SemanticBulkEnrichRequest,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    """
    Bulk semantic enrichment for indexed files with safe throttling controls.
    """
    batch_size = max(1, min(int(payload.batch_size), 1000))
    max_files = max(1, int(payload.max_files))
    offset = max(0, int(payload.offset))
    sleep_ms = max(0, int(payload.sleep_ms))
    embedding_model = str(payload.embedding_model or "local-hash-v1").strip()

    svc = SemanticFileService(db)

    started = time.monotonic()
    processed = 0
    success_count = 0
    failed_count = 0
    failures: List[Dict[str, Any]] = []
    limit_failures = 200
    cursor = offset

    _, total_available = db.list_indexed_files(
        limit=1,
        offset=offset,
        status=payload.status,
        ext=(payload.ext.lower() if payload.ext else None),
        query=payload.q,
        sort_by="id",
        sort_dir="asc",
        keyword=None,
    )
    remaining = max(0, min(max_files, max(0, int(total_available) - offset)))

    while processed < remaining:
        page_limit = min(batch_size, remaining - processed)
        items, _ = db.list_indexed_files(
            limit=page_limit,
            offset=cursor,
            status=payload.status,
            ext=(payload.ext.lower() if payload.ext else None),
            query=payload.q,
            sort_by="id",
            sort_dir="asc",
            keyword=None,
        )
        if not items:
            break

        for rec in items:
            file_id = int(rec.get("id") or 0)
            if file_id <= 0:
                failed_count += 1
                if len(failures) < limit_failures:
                    failures.append({"file_id": file_id, "error": "invalid_file_id"})
                continue
            try:
                out = await run_in_threadpool(
                    functools.partial(
                        svc.enrich_file,
                        file_id=file_id,
                        embedding_model=embedding_model,
                    )
                )
                if out.get("success"):
                    success_count += 1
                else:
                    failed_count += 1
                    if len(failures) < limit_failures:
                        failures.append(
                            {
                                "file_id": file_id,
                                "error": str(out.get("error") or "enrich_failed"),
                            }
                        )
            except Exception as e:
                failed_count += 1
                if len(failures) < limit_failures:
                    failures.append({"file_id": file_id, "error": str(e)})

        processed += len(items)
        cursor += len(items)

        if sleep_ms > 0 and processed < remaining:
            await asyncio.sleep(sleep_ms / 1000.0)

    elapsed = round(time.monotonic() - started, 3)
    return {
        "success": True,
        "embedding_model": embedding_model,
        "batch_size": batch_size,
        "sleep_ms": sleep_ms,
        "offset": offset,
        "max_files": max_files,
        "processed": processed,
        "succeeded": success_count,
        "failed": failed_count,
        "failures": failures,
        "total_available": int(total_available),
        "next_offset": cursor,
        "elapsed_seconds": elapsed,
    }


@router.post("/reorg/autopilot")
async def reorg_autopilot(
    payload: ReorgAutopilotRequest,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    """
    One-shot reorg pipeline:
    1) Crawl/index scope
    2) Semantic enrichment (embeddings)
    3) Entity extraction pass
    4) Dedupe refresh
    5) Generate organization proposals
    6) Auto-approve + apply
    """
    started = time.monotonic()
    root_prefix = str(payload.root_prefix or "").strip()
    if not root_prefix:
        return {"success": False, "error": "root_prefix_required"}

    file_index = FileIndexService(db)
    semantic = SemanticFileService(db)
    org = OrganizationService(db)
    logger.info(
        "[autopilot] start root=%s max_files_total=%s crawl_batch=%s embed_model=%s embed_batch=%s dry_run=%s",
        root_prefix,
        payload.max_files_total,
        payload.crawl_batch_size,
        payload.embedding_model,
        payload.embedding_batch_size,
        payload.dry_run,
    )

    # 1) Crawl in bounded resumable passes.
    crawl_allowed = [
        e.lower() if str(e).startswith(".") else f".{str(e).lower()}"
        for e in (payload.allowed_exts or [])
    ]
    total_indexed = 0
    total_errors = 0
    total_scanned = 0
    total_skipped = 0
    cursor: Optional[str] = None
    last_crawl: Dict[str, Any] = {}

    max_files_total = max(1, int(payload.max_files_total))
    crawl_batch = max(1, min(int(payload.crawl_batch_size), 20000))
    crawl_passes = max(1, int(payload.crawl_max_passes))
    crawl_runtime = max(1.0, float(payload.crawl_pass_runtime_seconds))
    crawl_sleep_ms = max(0, int(payload.crawl_sleep_ms))

    for i in range(crawl_passes):
        if total_indexed >= max_files_total:
            break
        pass_budget = min(crawl_batch, max_files_total - total_indexed)
        logger.info(
            "[autopilot] crawl pass %s/%s budget=%s cursor=%s",
            i + 1,
            crawl_passes,
            pass_budget,
            cursor,
        )
        out = await run_in_threadpool(
            functools.partial(
                file_index.index_roots,
                [root_prefix],
                recursive=True,
                allowed_exts=set(crawl_allowed) or None,
                max_files=pass_budget,
                max_runtime_seconds=crawl_runtime,
                start_after_path=cursor,
                follow_symlinks=bool(payload.follow_symlinks),
            )
        )
        last_crawl = out
        total_indexed += int(out.get("indexed", 0))
        total_errors += int(out.get("errors", 0))
        total_scanned += int(out.get("scanned", 0))
        total_skipped += int(out.get("skipped", 0))
        cursor = out.get("next_cursor") or cursor
        logger.info(
            "[autopilot] crawl pass %s end indexed=%s scanned=%s errors=%s truncated=%s total_indexed=%s/%s",
            i + 1,
            int(out.get("indexed", 0)),
            int(out.get("scanned", 0)),
            int(out.get("errors", 0)),
            bool(out.get("truncated", False)),
            total_indexed,
            max_files_total,
        )

        if not bool(out.get("truncated", False)):
            break
        if crawl_sleep_ms > 0:
            logger.info("[autopilot] crawl sleep %sms", crawl_sleep_ms)
            await asyncio.sleep(crawl_sleep_ms / 1000.0)

    # Scope query for indexed files.
    q_scope = root_prefix.replace("\\", "/")
    _, total_scoped = db.list_indexed_files(
        limit=1,
        offset=0,
        status="ready",
        ext=None,
        query=q_scope,
        sort_by="id",
        sort_dir="asc",
        keyword=None,
    )

    # 2) Semantic enrichment pass.
    embed_batch = max(1, min(int(payload.embedding_batch_size), 1000))
    embed_sleep_ms = max(0, int(payload.embedding_sleep_ms))
    embed_model = str(payload.embedding_model or "Qwen3-Embedding").strip()
    enriched_ok = 0
    enriched_failed = 0
    enriched_failures: List[Dict[str, Any]] = []
    offset = 0
    while offset < int(total_scoped):
        items, _ = db.list_indexed_files(
            limit=embed_batch,
            offset=offset,
            status="ready",
            ext=None,
            query=q_scope,
            sort_by="id",
            sort_dir="asc",
            keyword=None,
        )
        if not items:
            break
        for rec in items:
            fid = int(rec.get("id") or 0)
            if fid <= 0:
                enriched_failed += 1
                continue
            out = await run_in_threadpool(
                functools.partial(
                    semantic.enrich_file,
                    file_id=fid,
                    embedding_model=embed_model,
                )
            )
            if out.get("success"):
                enriched_ok += 1
            else:
                enriched_failed += 1
                if len(enriched_failures) < 200:
                    enriched_failures.append(
                        {"file_id": fid, "error": str(out.get("error") or "enrich_failed")}
                    )
        offset += len(items)
        logger.info(
            "[autopilot] semantic progress processed=%s/%s ok=%s failed=%s model=%s",
            offset,
            int(total_scoped),
            enriched_ok,
            enriched_failed,
            embed_model,
        )
        if embed_sleep_ms > 0 and offset < int(total_scoped):
            await asyncio.sleep(embed_sleep_ms / 1000.0)

    # 3) Entity extraction pass (reuses existing endpoint logic to persist entity links/knowledge entries).
    entities_ok = 0
    entities_failed = 0
    entity_offset = 0
    while entity_offset < int(total_scoped):
        items, _ = db.list_indexed_files(
            limit=embed_batch,
            offset=entity_offset,
            status="ready",
            ext=None,
            query=q_scope,
            sort_by="id",
            sort_dir="asc",
            keyword=None,
        )
        if not items:
            break
        for rec in items:
            fid = int(rec.get("id") or 0)
            if fid <= 0:
                entities_failed += 1
                continue
            try:
                ent = await file_entities(file_id=fid, db=db)
                if ent.get("success"):
                    entities_ok += 1
                else:
                    entities_failed += 1
            except Exception:
                entities_failed += 1
        entity_offset += len(items)
        logger.info(
            "[autopilot] entity progress processed=%s/%s ok=%s failed=%s",
            entity_offset,
            int(total_scoped),
            entities_ok,
            entities_failed,
        )
        if embed_sleep_ms > 0 and entity_offset < int(total_scoped):
            await asyncio.sleep(embed_sleep_ms / 1000.0)

    # 4) Dedupe refresh.
    dedupe = db.refresh_exact_duplicate_relationships()

    # 5) Generate proposals from scoped corpus.
    generate_limit = max(1, int(payload.generate_limit))
    generated = org.generate_proposals(limit=generate_limit, root_prefix=root_prefix)
    generated_count = int(generated.get("created", 0))

    # 6) Auto-approve generated proposals, then apply.
    proposals = db.organization_list_proposals(status="proposed", limit=100000, offset=0)
    prefixes = org._scope_prefixes(root_prefix)  # noqa: SLF001
    if prefixes:
        proposals = [
            p
            for p in proposals
            if org._path_matches_prefixes(p.get("current_path"), prefixes)  # noqa: SLF001
        ]
    approved = 0
    approve_failed = 0
    for p in proposals:
        pid = int(p.get("id") or 0)
        if pid <= 0:
            continue
        out = org.approve_proposal(pid)
        if out.get("success"):
            approved += 1
        else:
            approve_failed += 1
        if (approved + approve_failed) % 250 == 0:
            logger.info(
                "[autopilot] approve progress processed=%s/%s approved=%s failed=%s",
                approved + approve_failed,
                len(proposals),
                approved,
                approve_failed,
            )

    apply_out = org.apply_approved(
        limit=max(1, int(payload.apply_limit)),
        dry_run=bool(payload.dry_run),
        root_prefix=root_prefix,
    )

    elapsed = round(time.monotonic() - started, 3)
    logger.info(
        "[autopilot] complete elapsed=%.3fs crawl_indexed=%s semantic_ok=%s entity_ok=%s generated=%s approved=%s apply_success=%s",
        elapsed,
        total_indexed,
        enriched_ok,
        entities_ok,
        generated_count,
        approved,
        bool(apply_out.get("success", False)),
    )
    return {
        "success": bool(apply_out.get("success", False)),
        "root_prefix": root_prefix,
        "elapsed_seconds": elapsed,
        "crawl": {
            "indexed": total_indexed,
            "errors": total_errors,
            "scanned": total_scanned,
            "skipped": total_skipped,
            "next_cursor": cursor,
            "last_pass": last_crawl,
        },
        "semantic": {
            "embedding_model": embed_model,
            "succeeded": enriched_ok,
            "failed": enriched_failed,
            "failures": enriched_failures,
        },
        "entities": {
            "succeeded": entities_ok,
            "failed": entities_failed,
        },
        "dedupe": dedupe,
        "organization": {
            "generated": generated_count,
            "approved": approved,
            "approve_failed": approve_failed,
            "apply": apply_out,
        },
    }


@router.get("/{file_id}/rule-tags")
async def file_rule_tags(
    file_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    rec = db.get_indexed_file(file_id)
    if not rec:
        return {"success": False, "error": "file_not_found"}

    meta = rec.get("metadata_json") or {}
    return {
        "success": True,
        "file_id": file_id,
        "tags": meta.get("rule_tags") or [],
        "hits": meta.get("rule_tag_hits") or [],
        "summary": meta.get("rule_tag_summary") or {},
    }


@router.get("/{file_id}/duplicates")
async def file_duplicates(
    file_id: int,
    include_near: bool = Query(True),
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    rel = db.get_file_duplicate_relationships(file_id)
    if not rel.get("found"):
        return {"success": False, "error": "file_not_found"}

    file_rec = rel.get("file") or {}
    duplicate_of = rel.get("duplicate_of")
    exact_duplicates = rel.get("canonical_for") or []
    near_duplicates = rel.get("near_duplicates") if include_near else []

    return {
        "success": True,
        "file_id": file_id,
        "file": {
            "id": file_rec.get("id"),
            "display_name": file_rec.get("display_name"),
            "normalized_path": file_rec.get("normalized_path"),
            "sha256": file_rec.get("sha256"),
            "status": file_rec.get("status"),
        },
        "duplicate_of": duplicate_of,
        "exact_duplicates": exact_duplicates,
        "near_duplicates": near_duplicates,
        "near_duplicate_status": "placeholder",
    }


@router.get("/{file_id}/timeline-events")
async def file_timeline_events(
    file_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    rec = db.get_indexed_file(file_id)
    if not rec:
        return {"success": False, "error": "file_not_found"}

    meta = rec.get("metadata_json") or {}
    ts_map = [
        ("filesystem_created", meta.get("created_iso") or _to_iso(meta.get("created")), "File creation time (when available)"),
        ("filesystem_mtime", meta.get("mtime_iso") or _to_iso(meta.get("mtime") if meta.get("mtime") is not None else rec.get("mtime")), "File modified time"),
        ("filesystem_atime", meta.get("atime_iso") or _to_iso(meta.get("atime")), "File access time"),
        ("filesystem_ctime", meta.get("ctime_iso") or _to_iso(meta.get("ctime")), "File metadata/status change time"),
    ]

    events = [{"type": t, "ts": ts, "detail": d, "confidence": 1.0} for t, ts, d in ts_map if ts]
    if rec.get("last_checked_at"):
        events.append({"type": "scanner_checked", "ts": str(rec.get("last_checked_at")), "detail": "Scanner validation timestamp", "confidence": 1.0})

    text_blob = "\n".join([
        str(rec.get("display_name") or ""),
        str(rec.get("normalized_path") or ""),
        str(meta.get("preview") or ""),
        str((meta.get("normalization") or {}).get("normalized_preview") or ""),
    ])
    events.extend(_extract_embedded_dates(text_blob))

    events_sorted = sorted(events, key=lambda e: (e.get("ts") is None, str(e.get("ts") or "")))
    return {"success": True, "file_id": file_id, "events": events_sorted, "count": len(events_sorted)}


@router.get("/{file_id}/relationships")
async def file_relationships(
    file_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    rec = db.get_indexed_file(file_id)
    if not rec:
        return {"success": False, "error": "file_not_found"}

    items = db.list_all_indexed_files()
    target_path = str(rec.get("normalized_path") or "")
    parent = target_path.rsplit("/", 1)[0] if "/" in target_path else ""

    siblings = []
    parent_children = []
    for it in items:
        p = str(it.get("normalized_path") or "")
        if int(it.get("id", -1)) == int(file_id):
            continue
        if parent and p.startswith(parent + "/"):
            parent_children.append({"file_id": it.get("id"), "display_name": it.get("display_name"), "normalized_path": p})
            if p.rsplit("/", 1)[0] == parent:
                siblings.append({"file_id": it.get("id"), "display_name": it.get("display_name"), "normalized_path": p})

    references = []
    text_blob = "\n".join([
        str((rec.get("metadata_json") or {}).get("preview") or ""),
        str((rec.get("metadata_json") or {}).get("normalization", {}).get("normalized_preview") or ""),
    ])
    for it in items:
        if int(it.get("id", -1)) == int(file_id):
            continue
        candidate = str(it.get("display_name") or "")
        if candidate and candidate in text_blob:
            references.append({
                "file_id": it.get("id"),
                "display_name": candidate,
                "normalized_path": it.get("normalized_path"),
                "basis": "name_mention",
                "confidence": 0.65,
            })

    entity_links = []
    if hasattr(db, "list_file_entity_links"):
        try:
            entity_links = db.list_file_entity_links(file_id)
        except Exception:
            entity_links = []

    return {
        "success": True,
        "file_id": file_id,
        "relationships": {
            "parent_path": parent,
            "siblings": siblings[:100],
            "parent_children": parent_children[:200],
            "references": references[:50],
            "entity_links": entity_links[:100],
        },
    }


@router.get("/{file_id}/anomalies")
async def file_anomalies(
    file_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    rec = db.get_indexed_file(file_id)
    if not rec:
        return {"success": False, "error": "file_not_found"}

    items = db.list_all_indexed_files()
    target_path = str(rec.get("normalized_path") or "")
    parent = target_path.rsplit("/", 1)[0] if "/" in target_path else ""

    sizes = [int(i.get("file_size") or 0) for i in items if i.get("file_size") is not None]
    avg_size = (sum(sizes) / len(sizes)) if sizes else 0
    size_now = int(rec.get("file_size") or 0)

    same_parent = [i for i in items if str(i.get("normalized_path") or "").startswith(parent + "/")]
    target_mtime = float(rec.get("mtime") or 0)
    burst_count = sum(1 for i in same_parent if abs(float(i.get("mtime") or 0) - target_mtime) <= 60)

    flags = []
    if avg_size > 0 and size_now > (avg_size * 5):
        flags.append({"type": "oversized_outlier", "severity": "medium", "detail": f"file_size={size_now} > 5x avg={round(avg_size, 1)}"})
    if burst_count >= 10:
        flags.append({"type": "mtime_burst_cluster", "severity": "low", "detail": f"{burst_count} files changed within ±60s in same parent"})

    return {
        "success": True,
        "file_id": file_id,
        "anomaly_flags": flags,
        "count": len(flags),
        "baseline": {
            "global_avg_size": round(avg_size, 2),
            "same_parent_mtime_burst_count": burst_count,
        },
    }


@router.get("/{file_id}/normalization")
async def file_normalization(
    file_id: int,
    db=Depends(get_database_manager_strict_dep),
) -> Dict[str, Any]:
    rec = db.get_indexed_file(file_id)
    if not rec:
        return {"success": False, "error": "file_not_found"}

    meta = rec.get("metadata_json") or {}
    norm = meta.get("normalization") or {}
    return {
        "success": True,
        "file_id": file_id,
        "normalization": norm,
        "has_normalization": bool(norm),
    }
