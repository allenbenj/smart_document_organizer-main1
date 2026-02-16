"""File indexing service for canonical file selection and prechecks."""

from __future__ import annotations

import datetime as dt
import hashlib
import mimetypes
import os
import platform
import re
import socket
import stat
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from mem_db.database import DatabaseManager
from services.extraction_contracts import build_extraction_contract
from services.file_ingest_pipeline import FileIngestPipeline
from services.file_parsers import FileParserRegistry, build_default_parser_registry
from services.file_tagging_rules import RuleTagger

try:
    import magic  # type: ignore
    MAGIC_AVAILABLE = True
except Exception:
    magic = None
    MAGIC_AVAILABLE = False

_WIN_DRIVE_RE = re.compile(r"^([A-Za-z]):[\\/](.*)$")


def normalize_runtime_path(path_str: str) -> str:
    s = str(path_str).strip().strip('"').strip("'")
    m = _WIN_DRIVE_RE.match(s)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2).replace("\\", "/").lstrip("/")
        return f"/mnt/{drive}/{rest}"
    return str(Path(s).expanduser())


DEFAULT_DOC_EXTS = {
    ".pdf",
    ".docx",
    ".txt",
    ".md",
    ".csv",
    ".xlsx",
    ".json",
    ".pptx",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".webp",
    ".png",
    ".mp3",
    ".m4a",
    ".wav",
    ".flac",
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
}

class FileIndexService:
    def __init__(self, db: DatabaseManager, parser_registry: Optional[FileParserRegistry] = None):
        self.db = db
        self.parser_registry = parser_registry or build_default_parser_registry()
        self.rule_tagger = RuleTagger()
        self.ingest_pipeline = FileIngestPipeline()

    def _legacy_quick_validity(self, path: Path, ext: str) -> tuple[str, Optional[str]]:
        try:
            if ext == ".pdf":
                with path.open("rb") as f:
                    sig = f.read(5)
                if sig != b"%PDF-":
                    return "damaged", "invalid_pdf_signature"
            elif ext == ".docx":
                if not zipfile.is_zipfile(path):
                    return "damaged", "invalid_docx_zip"
            elif ext in {".txt", ".md", ".json", ".csv"}:
                with path.open("rb") as f:
                    _ = f.read(4096)
            return "ready", None
        except Exception as e:
            return "damaged", str(e)

    def _quick_validity(self, path: Path, ext: str, mime_type: Optional[str] = None) -> tuple[str, Optional[str]]:
        try:
            return self.parser_registry.quick_validate(path, ext=ext, mime_type=mime_type)
        except Exception:
            return self._legacy_quick_validity(path, ext)

    @staticmethod
    def _preview_meta(path: Path) -> Dict[str, Any]:
        return {
            "parent": str(path.parent),
            "stem": path.stem,
        }

    @staticmethod
    def _provenance_meta() -> Dict[str, Any]:
        parser_version = "registry_v1"
        return {
            "scanner": {
                "scanner_version": "file_index_service_v1",
                "parser_version": parser_version,
                "mime_detector": "magic" if MAGIC_AVAILABLE else "mimetypes",
            },
            "runtime": {
                "host": socket.gethostname() or platform.node(),
                "platform": platform.platform(),
                "python_version": sys.version.split()[0],
                "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
        }

    @staticmethod
    def _ts_to_iso(ts: Optional[float]) -> Optional[str]:
        if ts is None:
            return None
        try:
            return dt.datetime.fromtimestamp(float(ts), tz=dt.timezone.utc).isoformat()
        except Exception:
            return None

    @staticmethod
    def _fs_metadata(path: Path, st: os.stat_result) -> Dict[str, Any]:
        mode_raw = int(st.st_mode)
        mode_bits = stat.S_IMODE(mode_raw)

        owner_user: Optional[str] = None
        owner_group: Optional[str] = None
        try:
            import pwd  # type: ignore

            owner_user = pwd.getpwuid(int(st.st_uid)).pw_name
        except Exception:
            owner_user = None
        try:
            import grp  # type: ignore

            owner_group = grp.getgrgid(int(st.st_gid)).gr_name
        except Exception:
            owner_group = None

        file_attrs = {
            "is_file": bool(stat.S_ISREG(mode_raw)),
            "is_dir": bool(stat.S_ISDIR(mode_raw)),
            "is_symlink": bool(path.is_symlink()),
            "is_hidden": path.name.startswith("."),
            "inode": getattr(st, "st_ino", None),
            "device": getattr(st, "st_dev", None),
            "nlink": getattr(st, "st_nlink", None),
            "st_flags": getattr(st, "st_flags", None),
            "st_file_attributes": getattr(st, "st_file_attributes", None),
        }

        meta: Dict[str, Any] = {
            "owner_uid": int(st.st_uid),
            "owner_gid": int(st.st_gid),
            "owner_user": owner_user,
            "owner_group": owner_group,
            "mode": mode_bits,
            "mode_octal": format(mode_bits, "04o"),
            "permissions": stat.filemode(mode_raw),
            "fs_attrs": file_attrs,
            "atime": float(st.st_atime),
            "atime_iso": FileIndexService._ts_to_iso(float(st.st_atime)),
            "ctime": float(st.st_ctime),
            "ctime_iso": FileIndexService._ts_to_iso(float(st.st_ctime)),
            "mtime": float(st.st_mtime),
            "mtime_iso": FileIndexService._ts_to_iso(float(st.st_mtime)),
            "created": None,
            "created_iso": None,
        }

        created_ts: Optional[float] = None
        for attr in ("st_birthtime", "st_birthtime_ns"):
            if hasattr(st, attr):
                raw = getattr(st, attr)
                if raw is not None:
                    created_ts = float(raw / 1_000_000_000) if attr.endswith("_ns") else float(raw)
                    break
        if created_ts is None and os.name == "nt":
            created_ts = float(st.st_ctime)

        if created_ts is not None:
            meta["created"] = created_ts
            meta["created_iso"] = FileIndexService._ts_to_iso(created_ts)

        return meta

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _legacy_markdown_chunks(path: Path) -> Dict[str, Any]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return {"chunk_count": 0, "headings": [], "preview": "", "code_block_count": 0, "chunk_titles": []}

        lines = text.splitlines()
        headings = []
        chunks = []
        current_title = "Document"
        current_lines = []
        in_code_block = False
        code_blocks = 0

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                if in_code_block:
                    code_blocks += 1
                current_lines.append(line)
                continue

            m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if m and not in_code_block:
                if current_lines:
                    chunks.append({"title": current_title, "content": "\n".join(current_lines)})
                    current_lines = []
                current_title = m.group(2).strip() or "Untitled"
                headings.append({"level": len(m.group(1)), "title": current_title})
            current_lines.append(line)

        if current_lines:
            chunks.append({"title": current_title, "content": "\n".join(current_lines)})

        if not chunks and text.strip():
            chunks = [{"title": "Document", "content": text}]

        return {
            "chunk_count": len(chunks),
            "headings": headings[:100],
            "chunk_titles": [c.get("title") for c in chunks[:100]],
            "code_block_count": code_blocks,
            "preview": text[:500],
        }

    def _parser_metadata(self, path: Path, ext: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        parser_name = "legacy"
        payload: Dict[str, Any] = {}
        try:
            parser = self.parser_registry.resolve(ext=ext, mime_type=mime_type)
            if parser is not None:
                parser_name = str(getattr(parser, "name", "registry-parser"))
            payload = self.parser_registry.extract_index_metadata(path, ext=ext, mime_type=mime_type)
        except Exception:
            if ext == ".md":
                payload = self._legacy_markdown_chunks(path)

        payload = dict(payload or {})
        payload["extraction_contract"] = build_extraction_contract(
            kind="index_metadata",
            parser_name=parser_name,
            payload={"keys": sorted(list(payload.keys()))[:50]},
        )
        return payload

    @staticmethod
    def _safe_read_text_sample(path: Path, max_chars: int = 32000) -> tuple[str, str]:
        """Read a best-effort text sample for normalization and timeline enrichment."""
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return path.read_text(encoding=enc, errors="replace")[:max_chars], enc
            except Exception:
                continue
        return "", "unknown"

    @staticmethod
    def _normalization_quality_metadata(path: Path, ext: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        text_like_exts = {".txt", ".md", ".csv", ".json"}
        if ext not in text_like_exts and not str(mime_type or "").startswith("text/"):
            return {
                "normalization": {
                    "applied": False,
                    "reason": "non_text",
                    "text_quality_score": None,
                }
            }

        sample, encoding = FileIndexService._safe_read_text_sample(path)
        if not sample:
            return {
                "normalization": {
                    "applied": False,
                    "reason": "empty_or_unreadable",
                    "detected_encoding": encoding,
                    "text_quality_score": 0.0,
                }
            }

        replacement_count = sample.count("�")
        control_chars = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\n\r\t")
        total_chars = max(len(sample), 1)
        control_ratio = control_chars / total_chars

        cleaned = "".join(ch if (ord(ch) >= 32 or ch in "\n\r\t") else " " for ch in sample)
        lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
        nonempty_lines = len(lines)
        avg_line_length = round(sum(len(ln) for ln in lines) / nonempty_lines, 2) if nonempty_lines else 0.0

        score = 1.0
        score -= min(0.6, replacement_count / 1000.0)
        score -= min(0.3, control_ratio * 5.0)
        if nonempty_lines == 0:
            score -= 0.2
        score = max(0.0, round(score, 3))

        return {
            "normalization": {
                "applied": True,
                "detected_encoding": encoding,
                "replacement_char_count": replacement_count,
                "control_char_ratio": round(control_ratio, 5),
                "nonempty_line_count": nonempty_lines,
                "avg_line_length": avg_line_length,
                "normalized_preview": cleaned[:500],
                "text_quality_score": score,
            }
        }

    @staticmethod
    def _rule_sources(path: Path, parser_meta: Dict[str, Any], normalization_meta: Dict[str, Any]) -> Dict[str, str]:
        content_sources = []
        for key in ("preview", "title", "subject", "keywords"):
            val = parser_meta.get(key)
            if isinstance(val, str) and val.strip():
                content_sources.append(val)

        for grouped_key in ("pdf", "office", "exif"):
            group = parser_meta.get(grouped_key)
            if isinstance(group, dict):
                for key in ("title", "author", "subject", "keywords", "camera_make", "camera_model", "captured_at"):
                    val = group.get(key)
                    if isinstance(val, str) and val.strip():
                        content_sources.append(val)

        norm = normalization_meta.get("normalization") if isinstance(normalization_meta.get("normalization"), dict) else {}
        normalized_preview = norm.get("normalized_preview") if isinstance(norm, dict) else None
        if isinstance(normalized_preview, str) and normalized_preview.strip():
            content_sources.append(normalized_preview)

        return {
            "name": path.name,
            "path": str(path),
            "content": "\n".join(content_sources),
        }

    def _rule_tags(self, path: Path, parser_meta: Dict[str, Any], normalization_meta: Dict[str, Any]) -> Dict[str, Any]:
        return self.rule_tagger.apply(sources=self._rule_sources(path, parser_meta, normalization_meta))

    @staticmethod
    def _detect_mime(path: Path) -> tuple[Optional[str], str]:
        if MAGIC_AVAILABLE and magic is not None:
            try:
                return str(magic.from_file(str(path), mime=True)), "magic"
            except Exception:
                pass
        mime, _ = mimetypes.guess_type(str(path))
        return mime, "mimetypes"



    @staticmethod
    def _preview_snippet(parser_meta: Dict[str, Any], normalization_meta: Dict[str, Any]) -> Dict[str, Any]:
        preview = parser_meta.get("preview") if isinstance(parser_meta.get("preview"), str) else ""
        norm_preview = ((normalization_meta.get("normalization") or {}).get("normalized_preview") if isinstance(normalization_meta.get("normalization"), dict) else "")
        snippet = (norm_preview or preview or "").strip()
        return {"preview_snippet": {"text": snippet[:220], "source": "normalized_preview" if norm_preview else ("preview" if preview else "none")}}

    @staticmethod
    def _extraction_confidence(status: str, parser_meta: Dict[str, Any], normalization_meta: Dict[str, Any]) -> Dict[str, Any]:
        score = 0.9 if status == "ready" else 0.3
        if isinstance(parser_meta.get("preview"), str) and parser_meta.get("preview").strip():
            score += 0.05
        text_q = ((normalization_meta.get("normalization") or {}).get("text_quality_score") if isinstance(normalization_meta.get("normalization"), dict) else None)
        if isinstance(text_q, (int, float)):
            score = min(1.0, (score * 0.7) + (float(text_q) * 0.3))
        return {"extraction_quality": {"confidence": round(max(0.0, min(1.0, score)), 3), "completeness": 1.0 if status == "ready" else 0.4}}

    @staticmethod
    def _ocr_quality_score(text: str) -> float:
        sample = str(text or "")
        if not sample.strip():
            return 0.0
        useful = sum(1 for ch in sample if ch.isalnum() or ch in " .,;:-_/\n")
        density = useful / max(1, len(sample))
        words = len([w for w in re.split(r"\s+", sample) if w.strip()])
        long_words = len([w for w in re.split(r"\s+", sample) if len(w) >= 3])
        vocab = len(set(re.findall(r"[A-Za-z]{3,}", sample)))
        score = 0.45 * density + 0.25 * min(1.0, words / 40.0) + 0.2 * min(1.0, long_words / 30.0) + 0.1 * min(1.0, vocab / 25.0)
        return round(max(0.0, min(1.0, score)), 3)

    @staticmethod
    def _run_tesseract_attempt(image_obj: Any, *, psm: int = 6) -> str:
        import pytesseract  # type: ignore

        return str(pytesseract.image_to_string(image_obj, config=f"--psm {int(psm)}") or "")

    @staticmethod
    def _thumbnail_for_image(path: Path, ext: str, mime_type: Optional[str]) -> Dict[str, Any]:
        is_image = ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"} or str(mime_type or "").startswith("image/")
        if not is_image:
            return {"thumbnail": {"generated": False, "reason": "not_image"}}
        try:
            import base64
            import io
            from PIL import Image  # type: ignore

            with Image.open(path) as img:
                src_w, src_h = int(img.width), int(img.height)
                thumb = img.convert("RGB")
                thumb.thumbnail((192, 192))
                out_buf = io.BytesIO()
                thumb.save(out_buf, format="JPEG", quality=70)
                b = out_buf.getvalue()
                b64 = base64.b64encode(b).decode("ascii")
                return {
                    "thumbnail": {
                        "generated": True,
                        "format": "jpeg",
                        "width": int(thumb.width),
                        "height": int(thumb.height),
                        "source_width": src_w,
                        "source_height": src_h,
                        "byte_size": len(b),
                        "data_uri": f"data:image/jpeg;base64,{b64}",
                    }
                }
        except Exception as e:
            return {"thumbnail": {"generated": False, "error": str(e)}}

    @staticmethod
    def _metadata_first_profile(ext: str, mime_type: Optional[str], file_size: Optional[int]) -> Dict[str, Any]:
        size = int(file_size or 0)
        mt = str(mime_type or "").lower()
        large_threshold = 30 * 1024 * 1024
        media_mime = mt.startswith("audio/") or mt.startswith("video/")
        media_ext = ext in {".mp3", ".m4a", ".wav", ".flac", ".mp4", ".mov", ".mkv", ".avi"}
        binaryish_ext = ext in {".bin", ".iso", ".dmg", ".exe", ".dll"}
        metadata_first = bool(size >= large_threshold or media_mime or media_ext or binaryish_ext)
        reason = "large_binary" if size >= large_threshold else ("media_file" if (media_mime or media_ext) else ("binary_extension" if binaryish_ext else "n/a"))
        return {
            "processing_profile": {
                "metadata_first": metadata_first,
                "reason": reason if metadata_first else None,
                "size_bytes": size,
                "large_threshold_bytes": large_threshold,
            }
        }

    @staticmethod
    def _evidence_class_flags(path: Path, ext: str, mime_type: Optional[str], parser_meta: Dict[str, Any]) -> Dict[str, Any]:
        mt = str(mime_type or "").lower()
        name = path.name.lower()
        flags: list[str] = []
        if mt.startswith("image/") or ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}:
            flags.append("evidence:photo")
        if ext in {".pdf", ".docx", ".txt", ".md"} and ("report" in name or "lab" in name):
            flags.append("evidence:report")
        if ext in {".xlsx", ".csv"}:
            flags.append("evidence:spreadsheet")
        if ext in {".md", ".txt", ".pdf", ".docx"} and any(k in name for k in ("instruction", "manual", "guide", "sop")):
            flags.append("evidence:instructions")

        for tag in parser_meta.get("rule_tags") or []:
            if "lab-report" in str(tag):
                flags.append("evidence:report")

        unique = sorted(set(flags))
        return {"evidence_classes": unique, "evidence_profile": {"flag_count": len(unique), "flagged": bool(unique)}}

    def _ocr_fallback(self, path: Path, ext: str, mime_type: Optional[str], parser_meta: Dict[str, Any], file_size: Optional[int] = None) -> Dict[str, Any]:
        existing_preview = parser_meta.get("preview") if isinstance(parser_meta.get("preview"), str) else ""
        metadata_profile = self._metadata_first_profile(ext, mime_type, file_size)
        is_image = ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"} or str(mime_type or "").startswith("image/")
        is_pdf = ext == ".pdf" or str(mime_type or "").lower() == "application/pdf"
        if not (is_image or is_pdf):
            return {**metadata_profile, "ocr": {"attempted": False, "reason": "unsupported_type"}}
        if existing_preview.strip():
            return {**metadata_profile, "ocr": {"attempted": False, "reason": "existing_preview"}}
        if metadata_profile.get("processing_profile", {}).get("metadata_first") and not is_pdf:
            return {**metadata_profile, "ocr": {"attempted": False, "reason": "metadata_first"}}

        try:
            from PIL import Image, ImageOps  # type: ignore

            attempts: list[Dict[str, Any]] = []
            best_text = ""
            best_score = 0.0

            def _consider(text: str, label: str) -> None:
                nonlocal best_text, best_score
                t = str(text or "").strip()
                score = self._ocr_quality_score(t)
                attempts.append({"attempt": label, "chars": len(t), "quality": score})
                if score > best_score:
                    best_score = score
                    best_text = t

            if is_image:
                with Image.open(path) as img:
                    _consider(self._run_tesseract_attempt(img, psm=6), "raw_psm6")
                    if best_score < 0.45:
                        gray = ImageOps.grayscale(img)
                        _consider(self._run_tesseract_attempt(gray, psm=6), "grayscale_psm6")
                    if best_score < 0.45:
                        high_contrast = ImageOps.autocontrast(ImageOps.grayscale(img))
                        _consider(self._run_tesseract_attempt(high_contrast, psm=11), "autocontrast_psm11")
            elif is_pdf:
                # PyMuPDF OCR rendering can SIGBUS on some WSL hosts; keep disabled by default.
                import os
                allow_pdf_ocr = str(os.getenv("ALLOW_PDF_OCR", "0")).strip().lower() in {"1", "true", "yes", "on"}
                if not allow_pdf_ocr:
                    return {
                        **metadata_profile,
                        "ocr": {
                            "attempted": False,
                            "used": False,
                            "error": "pdf_ocr_disabled_for_stability",
                        },
                    }
                try:
                    import fitz  # type: ignore
                except Exception as e:
                    return {**metadata_profile, "ocr": {"attempted": True, "used": False, "error": f"pdf_render_unavailable: {e}"}}
                doc = fitz.open(str(path))
                page_count = int(doc.page_count)
                pages_processed = 0
                for i in range(min(page_count, 3)):
                    page = doc.load_page(i)
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    _consider(self._run_tesseract_attempt(img, psm=6), f"pdf_page_{i+1}_raw")
                    if best_score < 0.45:
                        _consider(self._run_tesseract_attempt(ImageOps.autocontrast(ImageOps.grayscale(img)), psm=11), f"pdf_page_{i+1}_retry")
                    pages_processed += 1
                    if best_score >= 0.6:
                        break
                doc.close()
                attempts.append({"pdf_pages_processed": pages_processed, "pdf_page_count": page_count})

            if best_text:
                return {
                    **metadata_profile,
                    "ocr": {"attempted": True, "used": True, "chars": len(best_text), "engine": "pytesseract", "attempts": attempts},
                    "preview": best_text[:500],
                    "ocr_quality": {"confidence": best_score, "retry_performed": len(attempts) > 1},
                }
            return {**metadata_profile, "ocr": {"attempted": True, "used": True, "chars": 0, "engine": "pytesseract", "attempts": attempts}, "ocr_quality": {"confidence": best_score}}
        except Exception as e:
            return {**metadata_profile, "ocr": {"attempted": True, "used": False, "error": str(e)}}

    def index_roots(
        self,
        roots: Iterable[str],
        *,
        recursive: bool = True,
        allowed_exts: Optional[set[str]] = None,
        include_paths: Optional[list[str]] = None,
        exclude_paths: Optional[list[str]] = None,
        min_size_bytes: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
        modified_after_ts: Optional[float] = None,
        max_files: int = 5000,
        max_depth: Optional[int] = None,
        max_runtime_seconds: Optional[float] = None,
        follow_symlinks: bool = False,
        progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        # best-effort tracer (do not fail if opentelemetry not available)
        try:
            from opentelemetry import trace as _otel_trace  # type: ignore
            _file_index_tracer = _otel_trace.get_tracer(__name__)
        except Exception:
            _file_index_tracer = None

        indexed = 0
        errors = 0
        scanned = 0
        skipped = 0
        permission_errors = 0
        effective_exts = {e.lower() for e in (allowed_exts or DEFAULT_DOC_EXTS)}
        started_monotonic = time.monotonic()
        visited_dirs: set[str] = set()

        for root in roots:
            root_norm = normalize_runtime_path(root)
            root_path = Path(root_norm)
            if not root_path.exists() or not root_path.is_dir():
                errors += 1
                self.db.upsert_indexed_file(
                    display_name=root_path.name or root_norm,
                    original_path=root,
                    normalized_path=root_norm,
                    file_size=None,
                    mtime=None,
                    mime_type=None,
                    mime_source=None,
                    sha256=None,
                    ext=None,
                    status="missing",
                    last_error="root_not_found_or_not_directory",
                    metadata={"is_root": True, **self._provenance_meta()},
                )
                continue

            walk_errors: list[str] = []
            if recursive:
                walker = os.walk(root_norm, onerror=lambda e: walk_errors.append(str(e)), followlinks=follow_symlinks)
            else:
                try:
                    walker = [(root_norm, [], os.listdir(root_norm))]
                except PermissionError as pe:
                    errors += 1
                    permission_errors += 1
                    self.db.upsert_indexed_file(
                        display_name=root_path.name or root_norm,
                        original_path=root,
                        normalized_path=root_norm,
                        file_size=None,
                        mtime=None,
                        mime_type=None,
                        mime_source=None,
                        sha256=None,
                        ext=None,
                        status="unreadable",
                        last_error=f"permission_denied: {pe}",
                        metadata={"is_root": True, **self._provenance_meta()},
                    )
                    continue

            for dirpath, dirnames, filenames in walker:
                if max_runtime_seconds is not None and (time.monotonic() - started_monotonic) >= float(max_runtime_seconds):
                    return {"success": True, "indexed": indexed, "errors": errors, "scanned": scanned, "skipped": skipped, "truncated": True, "runtime_budget_hit": True, "dedupe": self.db.refresh_exact_duplicate_relationships()}

                try:
                    real_dir = os.path.realpath(dirpath)
                    if real_dir in visited_dirs:
                        dirnames[:] = []
                        continue
                    visited_dirs.add(real_dir)
                except Exception:
                    pass

                if max_depth is not None:
                    rel = os.path.relpath(dirpath, root_norm)
                    depth = 0 if rel == "." else rel.count(os.sep) + 1
                    if depth >= int(max_depth):
                        dirnames[:] = []

                for name in filenames:
                    if should_stop and should_stop():
                        return {
                            "success": False,
                            "indexed": indexed,
                            "errors": errors,
                            "scanned": scanned,
                            "truncated": False,
                            "cancelled": True,
                            "dedupe": self.db.refresh_exact_duplicate_relationships(),
                        }

                    if indexed >= max_files:
                        return {
                            "success": True,
                            "indexed": indexed,
                            "errors": errors,
                            "scanned": scanned,
                            "truncated": True,
                            "dedupe": self.db.refresh_exact_duplicate_relationships(),
                        }

                    scanned += 1
                    if progress_cb and scanned % 100 == 0:
                        progress_cb({"stage": "index", "scanned": scanned, "indexed": indexed, "errors": errors})
                    p = Path(dirpath) / name
                    if p.is_symlink() and not follow_symlinks:
                        skipped += 1
                        continue
                    p_str = str(p)
                    ext = p.suffix.lower()
                    if ext not in effective_exts:
                        continue
                    if include_paths and not any(s in p_str for s in include_paths):
                        continue
                    if exclude_paths and any(s in p_str for s in exclude_paths):
                        continue

                    try:
                        st = p.stat()
                        if min_size_bytes is not None and int(st.st_size) < int(min_size_bytes):
                            continue
                        if max_size_bytes is not None and int(st.st_size) > int(max_size_bytes):
                            continue
                        if modified_after_ts is not None and float(st.st_mtime) < float(modified_after_ts):
                            continue
                        path_hash = hashlib.sha1(str(p).encode("utf-8")).hexdigest()
                        prev = self.db.scan_manifest_get(path_hash)
                        if prev and prev.get("mtime") is not None and float(prev.get("mtime")) == float(st.st_mtime) and prev.get("file_size") is not None and int(prev.get("file_size")) == int(st.st_size):
                            skipped += 1
                            continue

                        if _file_index_tracer:
                            with _file_index_tracer.start_as_current_span("file_index.ingest_file", attributes={"path": str(p), "ext": ext}):
                                ingest = self.ingest_pipeline.ingest_file(self, root_norm=root_norm, path=p, ext=ext, st=st)
                        else:
                            ingest = self.ingest_pipeline.ingest_file(self, root_norm=root_norm, path=p, ext=ext, st=st)

                        if ingest.success:
                            indexed += 1
                        else:
                            errors += 1
                            self.db.upsert_indexed_file(
                                display_name=p.name,
                                original_path=str(p),
                                normalized_path=str(p),
                                file_size=None,
                                mtime=None,
                                mime_type=None,
                                mime_source=None,
                                sha256=None,
                                ext=ext,
                                status="unreadable",
                                last_error=f"{ingest.failed_stage}:{ingest.error or ingest.failure_reason}",
                                metadata={
                                    "root": root_norm,
                                    **self._preview_meta(p),
                                    **self._provenance_meta(),
                                    "ingest_result": {
                                        "failed_stage": ingest.failed_stage,
                                        "failure_reason": ingest.failure_reason,
                                        "stage_results": ingest.stage_results,
                                    },
                                },
                            )
                            try:
                                self.db.scan_manifest_upsert(
                                    path_hash=path_hash,
                                    normalized_path=str(p),
                                    file_size=None,
                                    mtime=None,
                                    sha256=None,
                                    last_status="unreadable",
                                    last_error=f"{ingest.failed_stage}:{ingest.error or ingest.failure_reason}",
                                )
                            except Exception:
                                pass
                    except Exception as e:
                        errors += 1
                        self.db.upsert_indexed_file(
                            display_name=p.name,
                            original_path=str(p),
                            normalized_path=str(p),
                            file_size=None,
                            mtime=None,
                            mime_type=None,
                            mime_source=None,
                            sha256=None,
                            ext=ext,
                            status="unreadable",
                            last_error=str(e),
                            metadata={"root": root_norm, **self._preview_meta(p), **self._provenance_meta(), "ingest_result": {"failed_stage": "unknown", "failure_reason": "exception", "error": str(e)}},
                        )
                        try:
                            self.db.scan_manifest_upsert(
                                path_hash=hashlib.sha1(str(p).encode("utf-8")).hexdigest(),
                                normalized_path=str(p),
                                file_size=None,
                                mtime=None,
                                sha256=None,
                                last_status="unreadable",
                                last_error=str(e),
                            )
                        except Exception:
                            pass

            if walk_errors:
                permission_errors += len(walk_errors)
                errors += len(walk_errors)

        dedupe = self.db.refresh_exact_duplicate_relationships()
        return {
            "success": True,
            "indexed": indexed,
            "errors": errors,
            "permission_errors": permission_errors,
            "scanned": scanned,
            "skipped": skipped,
            "truncated": False,
            "dedupe": dedupe,
        }

    def add_watch(
        self,
        *,
        path: str,
        recursive: bool = True,
        keywords: Optional[list[str]] = None,
        allowed_exts: Optional[list[str]] = None,
        active: bool = True,
    ) -> int:
        normalized = normalize_runtime_path(path)
        return self.db.upsert_watched_directory(
            original_path=path,
            normalized_path=normalized,
            recursive=recursive,
            keywords=keywords or [],
            allowed_exts=allowed_exts or [],
            active=active,
        )

    def run_watched_index(self, max_files_per_watch: int = 5000) -> Dict[str, Any]:
        watches = self.db.list_watched_directories(active_only=True)
        total = {"success": True, "indexed": 0, "errors": 0, "permission_errors": 0, "scanned": 0, "watches": len(watches)}
        for w in watches:
            allowed = {e.lower() if str(e).startswith(".") else f".{str(e).lower()}" for e in (w.get("allowed_exts_json") or [])}
            if not allowed:
                allowed = set(DEFAULT_DOC_EXTS)
            res = self.index_roots(
                [w.get("normalized_path")],
                recursive=bool(w.get("recursive", 1)),
                allowed_exts=allowed or None,
                max_files=max_files_per_watch,
            )
            total["indexed"] += int(res.get("indexed", 0))
            total["errors"] += int(res.get("errors", 0))
            total["permission_errors"] += int(res.get("permission_errors", 0))
            total["scanned"] += int(res.get("scanned", 0))
        return total

    def refresh_index(
        self,
        stale_after_hours: int = 24,
        progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        rows = self.db.list_all_indexed_files()
        missing = 0
        updated = 0
        damaged = 0
        now = dt.datetime.now(dt.timezone.utc)

        for i, row in enumerate(rows, start=1):
            if should_stop and should_stop():
                return {
                    "success": False,
                    "updated": updated,
                    "missing": missing,
                    "damaged": damaged,
                    "stale": 0,
                    "total": len(rows),
                    "cancelled": True,
                    "dedupe": self.db.refresh_exact_duplicate_relationships(),
                }
            if progress_cb and i % 100 == 0:
                progress_cb({"stage": "refresh", "processed": i, "total": len(rows), "updated": updated, "missing": missing, "damaged": damaged})
            p = Path(row.get("normalized_path") or "")
            ext = str(row.get("ext") or "").lower()
            if not p.exists() or not p.is_file():
                self.db.upsert_indexed_file(
                    display_name=row.get("display_name") or p.name,
                    original_path=row.get("original_path") or str(p),
                    normalized_path=str(p),
                    file_size=None,
                    mtime=None,
                    mime_type=row.get("mime_type"),
                    mime_source=row.get("mime_source"),
                    sha256=row.get("sha256"),
                    ext=ext,
                    status="missing",
                    last_error="file_missing",
                    metadata=row.get("metadata_json") or {},
                )
                missing += 1
                continue

            st = p.stat()
            mime, mime_source = self._detect_mime(p)
            status, err = self._quick_validity(p, ext, mime)
            sha256 = self._sha256(p)
            parser_meta = self._parser_metadata(p, ext, mime)
            fs_meta = self._fs_metadata(p, st)
            if status == "damaged":
                damaged += 1

            ocr_meta = self._ocr_fallback(p, ext, mime, parser_meta, int(st.st_size))
            parser_meta = {**parser_meta, **ocr_meta}
            thumb_meta = self._thumbnail_for_image(p, ext, mime)
            parser_meta = {**parser_meta, **thumb_meta}
            norm_meta = self._normalization_quality_metadata(p, ext, mime)
            quality_meta = self._extraction_confidence(status, parser_meta, norm_meta)
            snippet_meta = self._preview_snippet(parser_meta, norm_meta)
            rule_meta = self._rule_tags(p, parser_meta, norm_meta)
            parser_meta = {**parser_meta, **rule_meta}
            self.db.upsert_indexed_file(
                display_name=row.get("display_name") or p.name,
                original_path=row.get("original_path") or str(p),
                normalized_path=str(p),
                file_size=int(st.st_size),
                mtime=float(st.st_mtime),
                mime_type=mime or row.get("mime_type"),
                mime_source=mime_source,
                sha256=sha256,
                ext=ext,
                status=status,
                last_error=err,
                metadata={**(row.get("metadata_json") or {}), **fs_meta, **self._provenance_meta(), **parser_meta, **norm_meta, **quality_meta, **snippet_meta, **rule_meta},
            )
            updated += 1

        stale_cutoff = now.timestamp() - (stale_after_hours * 3600)
        stale = 0
        for row in self.db.list_all_indexed_files():
            checked = row.get("last_checked_at")
            try:
                ts = dt.datetime.fromisoformat(str(checked).replace("Z", "+00:00")).timestamp()
                if ts < stale_cutoff:
                    stale += 1
            except Exception:
                pass

        dedupe = self.db.refresh_exact_duplicate_relationships()
        return {
            "success": True,
            "updated": updated,
            "missing": missing,
            "damaged": damaged,
            "stale": stale,
            "total": len(rows),
            "dedupe": dedupe,
        }
