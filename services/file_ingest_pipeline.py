from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class IngestJobResult:
    success: bool
    file_path: str
    file_id: Optional[int] = None
    failed_stage: Optional[str] = None
    failure_reason: Optional[str] = None
    error: Optional[str] = None
    stage_results: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestContext:
    root_norm: str
    path: Path
    ext: str
    stat: Any
    path_hash: str
    prior_manifest: Optional[Dict[str, Any]] = None
    mime_type: Optional[str] = None
    mime_source: Optional[str] = None
    sha256: Optional[str] = None
    status: str = "ready"
    last_error: Optional[str] = None
    parser_meta: Dict[str, Any] = field(default_factory=dict)
    fs_meta: Dict[str, Any] = field(default_factory=dict)
    norm_meta: Dict[str, Any] = field(default_factory=dict)
    quality_meta: Dict[str, Any] = field(default_factory=dict)
    snippet_meta: Dict[str, Any] = field(default_factory=dict)
    class_meta: Dict[str, Any] = field(default_factory=dict)
    rule_meta: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class FileDiscoveryStage:
    name = "discovery"

    def run(self, svc: Any, ctx: IngestContext) -> Dict[str, Any]:
        return {
            "path": str(ctx.path),
            "ext": ctx.ext,
            "size": int(ctx.stat.st_size),
            "mtime": float(ctx.stat.st_mtime),
            "root": ctx.root_norm,
        }


class ValidationStage:
    name = "validation"

    def run(self, svc: Any, ctx: IngestContext) -> Dict[str, Any]:
        ctx.mime_type, ctx.mime_source = svc._detect_mime(ctx.path)
        ctx.status, ctx.last_error = svc._quick_validity(ctx.path, ctx.ext, ctx.mime_type)
        ctx.sha256 = svc._sha256(ctx.path)
        return {
            "mime_type": ctx.mime_type,
            "mime_source": ctx.mime_source,
            "status": ctx.status,
            "last_error": ctx.last_error,
        }


class ExtractionStage:
    name = "extraction"

    def run(self, svc: Any, ctx: IngestContext) -> Dict[str, Any]:
        ctx.parser_meta = svc._parser_metadata(ctx.path, ctx.ext, ctx.mime_type)
        ctx.fs_meta = svc._fs_metadata(ctx.path, ctx.stat)
        ocr_meta = svc._ocr_fallback(ctx.path, ctx.ext, ctx.mime_type, ctx.parser_meta, int(ctx.stat.st_size))
        thumb_meta = svc._thumbnail_for_image(ctx.path, ctx.ext, ctx.mime_type)
        ctx.parser_meta = {**ctx.parser_meta, **ocr_meta, **thumb_meta}
        return {
            "parser_keys": sorted(list(ctx.parser_meta.keys()))[:100],
            "ocr_used": bool(((ctx.parser_meta.get("ocr") or {}).get("used")) if isinstance(ctx.parser_meta.get("ocr"), dict) else False),
        }


class EnrichmentStage:
    name = "enrichment"

    def run(self, svc: Any, ctx: IngestContext) -> Dict[str, Any]:
        ctx.norm_meta = svc._normalization_quality_metadata(ctx.path, ctx.ext, ctx.mime_type)
        ctx.quality_meta = svc._extraction_confidence(ctx.status, ctx.parser_meta, ctx.norm_meta)
        ctx.snippet_meta = svc._preview_snippet(ctx.parser_meta, ctx.norm_meta)
        ctx.rule_meta = svc._rule_tags(ctx.path, ctx.parser_meta, ctx.norm_meta)
        ctx.parser_meta = {**ctx.parser_meta, **ctx.rule_meta}
        ctx.class_meta = svc._evidence_class_flags(ctx.path, ctx.ext, ctx.mime_type, ctx.parser_meta)
        return {
            "quality": ctx.quality_meta.get("extraction_quality") if isinstance(ctx.quality_meta, dict) else None,
            "rule_tags": (ctx.rule_meta.get("rule_tags") or []) if isinstance(ctx.rule_meta, dict) else [],
        }


class PersistenceStage:
    name = "persistence"

    def run(self, svc: Any, ctx: IngestContext) -> Dict[str, Any]:
        metadata = {
            "root": ctx.root_norm,
            **svc._preview_meta(ctx.path),
            **ctx.fs_meta,
            **svc._provenance_meta(),
            **ctx.parser_meta,
            **ctx.norm_meta,
            **ctx.quality_meta,
            **ctx.snippet_meta,
            **ctx.class_meta,
        }
        # Stage boundary: canonical file row first; dependent records cleanup on failure.
        file_id: Optional[int] = None
        try:
            file_id = svc.db.upsert_indexed_file(
                display_name=ctx.path.name,
                original_path=str(ctx.path),
                normalized_path=str(ctx.path),
                file_size=int(ctx.stat.st_size),
                mtime=float(ctx.stat.st_mtime),
                mime_type=ctx.mime_type,
                mime_source=ctx.mime_source,
                sha256=ctx.sha256,
                ext=ctx.ext,
                status=ctx.status,
                last_error=ctx.last_error,
                metadata=metadata,
            )
            svc.db.scan_manifest_upsert(
                path_hash=ctx.path_hash,
                normalized_path=str(ctx.path),
                file_size=int(ctx.stat.st_size),
                mtime=float(ctx.stat.st_mtime),
                sha256=ctx.sha256,
                last_status=ctx.status,
                last_error=ctx.last_error,
            )
        except Exception:
            if file_id:
                # Rollback policy for dependent records: never leave partial children.
                try:
                    svc.db.replace_file_chunks(file_id, [])
                except Exception:
                    pass
                try:
                    svc.db.replace_file_entities(file_id, [])
                except Exception:
                    pass
                try:
                    svc.db.replace_file_tables(file_id, [])
                except Exception:
                    pass
            raise

        return {"file_id": file_id, "status": ctx.status}


class FileIngestPipeline:
    def __init__(self) -> None:
        self.discovery = FileDiscoveryStage()
        self.validation = ValidationStage()
        self.extraction = ExtractionStage()
        self.enrichment = EnrichmentStage()
        self.persistence = PersistenceStage()

    def ingest_file(self, svc: Any, *, root_norm: str, path: Path, ext: str, st: Any) -> IngestJobResult:
        stage_results: Dict[str, Any] = {}
        path_hash = hashlib.sha1(str(path).encode("utf-8")).hexdigest()
        ctx = IngestContext(
            root_norm=root_norm,
            path=path,
            ext=ext,
            stat=st,
            path_hash=path_hash,
            prior_manifest=svc.db.scan_manifest_get(path_hash),
        )
        try:
            stage_results[self.discovery.name] = self.discovery.run(svc, ctx)
            stage_results[self.validation.name] = self.validation.run(svc, ctx)
            stage_results[self.extraction.name] = self.extraction.run(svc, ctx)
            stage_results[self.enrichment.name] = self.enrichment.run(svc, ctx)
            persist_out = self.persistence.run(svc, ctx)
            stage_results[self.persistence.name] = persist_out
            return IngestJobResult(
                success=True,
                file_path=str(path),
                file_id=persist_out.get("file_id"),
                stage_results=stage_results,
            )
        except Exception as e:
            failed_stage = next((s for s in ["persistence", "enrichment", "extraction", "validation", "discovery"] if s not in stage_results), "persistence")
            return IngestJobResult(
                success=False,
                file_path=str(path),
                failed_stage=failed_stage,
                failure_reason="stage_failure",
                error=str(e),
                stage_results=stage_results,
            )
