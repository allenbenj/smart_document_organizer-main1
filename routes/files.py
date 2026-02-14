from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from services.dependencies import get_database_manager_strict_dep
from services.file_index_service import FileIndexService
from services.semantic_file_service import SemanticFileService
from services.taskmaster_service import TaskMasterService

router = APIRouter()


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
        return tm.run_file_pipeline(
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
        )

    service = FileIndexService(db)
    result = service.index_roots(
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
        return tm.run_file_pipeline(
            mode=mode,
            payload={
                "mode": mode,
                "stale_after_hours": stale_after_hours,
            },
        )

    service = FileIndexService(db)
    watch_res = service.run_watched_index() if run_watches else {"success": True, "indexed": 0, "errors": 0, "scanned": 0, "watches": 0}
    refresh_res = service.refresh_index(stale_after_hours=stale_after_hours)
    return {"success": True, "watch": watch_res, "refresh": refresh_res}


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
    name = str(rec.get("display_name") or "")

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
