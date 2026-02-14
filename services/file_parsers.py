"""Pluggable parser registry for file scanner quick validation and metadata extraction."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Protocol


class FileParser(Protocol):
    """Contract for lightweight scanner parsers used during index/refresh."""

    name: str

    def supports(self, *, ext: str, mime_type: Optional[str] = None) -> bool:
        ...

    def quick_validate(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> tuple[str, Optional[str]]:
        ...

    def extract_index_metadata(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        ...


class BaseFileParser:
    name = "base"

    def supports(self, *, ext: str, mime_type: Optional[str] = None) -> bool:
        return False

    def quick_validate(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> tuple[str, Optional[str]]:
        return "ready", None

    def extract_index_metadata(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        return {}


class PdfParser(BaseFileParser):
    name = "pdf"

    def supports(self, *, ext: str, mime_type: Optional[str] = None) -> bool:
        return ext == ".pdf" or str(mime_type or "").lower() == "application/pdf"

    def quick_validate(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> tuple[str, Optional[str]]:
        with path.open("rb") as f:
            sig = f.read(5)
        if sig != b"%PDF-":
            return "damaged", "invalid_pdf_signature"
        return "ready", None

    def extract_index_metadata(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        out: Dict[str, Any] = {"pdf": {"metadata_available": False}}
        # Prefer pypdf to avoid PyMuPDF SIGBUS crashes seen on some WSL hosts.
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            meta = reader.metadata or {}
            out["pdf"] = {
                "metadata_available": True,
                "title": getattr(meta, "title", None) or meta.get("/Title"),
                "author": getattr(meta, "author", None) or meta.get("/Author"),
                "producer": getattr(meta, "producer", None) or meta.get("/Producer"),
                "creator": getattr(meta, "creator", None) or meta.get("/Creator"),
                "subject": getattr(meta, "subject", None) or meta.get("/Subject"),
                "keywords": getattr(meta, "keywords", None) or meta.get("/Keywords"),
                "page_count": len(reader.pages),
            }
            return out
        except Exception as e:
            out["pdf"] = {
                "metadata_available": False,
                "metadata_error": f"pypdf_error: {e}",
            }
            return out


class DocxParser(BaseFileParser):
    name = "docx"

    def supports(self, *, ext: str, mime_type: Optional[str] = None) -> bool:
        return ext == ".docx"

    def quick_validate(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> tuple[str, Optional[str]]:
        if not zipfile.is_zipfile(path):
            return "damaged", "invalid_docx_zip"
        return "ready", None


class TextLikeParser(BaseFileParser):
    name = "text-like"
    text_exts = {".txt", ".md", ".json", ".csv"}

    def supports(self, *, ext: str, mime_type: Optional[str] = None) -> bool:
        return ext in self.text_exts

    def quick_validate(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> tuple[str, Optional[str]]:
        with path.open("rb") as f:
            _ = f.read(4096)
        return "ready", None

    def extract_index_metadata(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return {}
        return {"preview": text[:500]}


class MarkdownParser(TextLikeParser):
    name = "markdown"

    def supports(self, *, ext: str, mime_type: Optional[str] = None) -> bool:
        return ext == ".md" or str(mime_type or "").lower() in {"text/markdown", "text/x-markdown"}

    def extract_index_metadata(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
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


class ImageExifParser(BaseFileParser):
    name = "image-exif"
    exts = {".jpg", ".jpeg", ".tif", ".tiff", ".webp"}

    def supports(self, *, ext: str, mime_type: Optional[str] = None) -> bool:
        mt = str(mime_type or "").lower()
        return ext in self.exts or mt.startswith("image/")

    def extract_index_metadata(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        out: Dict[str, Any] = {"exif": {"metadata_available": False}}
        try:
            from PIL import ExifTags, Image  # type: ignore

            with Image.open(path) as img:
                exif_raw = img.getexif() or {}
                tag_map = {ExifTags.TAGS.get(int(k), str(k)): v for k, v in exif_raw.items()}
                out["image"] = {"width": img.width, "height": img.height, "format": img.format}
                out["exif"] = {
                    "metadata_available": bool(tag_map),
                    "camera_make": tag_map.get("Make"),
                    "camera_model": tag_map.get("Model"),
                    "captured_at": tag_map.get("DateTimeOriginal") or tag_map.get("DateTime"),
                    "orientation": tag_map.get("Orientation"),
                    "gps_info": str(tag_map.get("GPSInfo")) if tag_map.get("GPSInfo") is not None else None,
                    "raw_tags": {k: str(v) for k, v in list(tag_map.items())[:100]},
                }
        except Exception as e:
            out["exif"] = {"metadata_available": False, "metadata_error": str(e)}
        return out


class OfficeOpenXmlParser(BaseFileParser):
    name = "office-openxml"
    exts = {".docx", ".xlsx", ".pptx"}

    def supports(self, *, ext: str, mime_type: Optional[str] = None) -> bool:
        return ext in self.exts

    @staticmethod
    def _xml_text(root: ET.Element, local_name: str) -> Optional[str]:
        for el in root.iter():
            if el.tag.rsplit("}", 1)[-1] == local_name:
                if el.text is not None:
                    return str(el.text)
        return None

    def extract_index_metadata(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        out: Dict[str, Any] = {"office": {"metadata_available": False, "ext": ext}}
        if not zipfile.is_zipfile(path):
            return out

        try:
            with zipfile.ZipFile(path, "r") as zf:
                core_xml = None
                app_xml = None
                try:
                    core_xml = zf.read("docProps/core.xml")
                except Exception:
                    core_xml = None
                try:
                    app_xml = zf.read("docProps/app.xml")
                except Exception:
                    app_xml = None

            core_root = ET.fromstring(core_xml) if core_xml else None
            app_root = ET.fromstring(app_xml) if app_xml else None
            out["office"] = {
                "metadata_available": (core_root is not None) or (app_root is not None),
                "ext": ext,
                "author": self._xml_text(core_root, "creator") if core_root is not None else None,
                "title": self._xml_text(core_root, "title") if core_root is not None else None,
                "subject": self._xml_text(core_root, "subject") if core_root is not None else None,
                "last_modified_by": self._xml_text(core_root, "lastModifiedBy") if core_root is not None else None,
                "revision": self._xml_text(core_root, "revision") if core_root is not None else None,
                "template": self._xml_text(app_root, "Template") if app_root is not None else None,
                "application": self._xml_text(app_root, "Application") if app_root is not None else None,
                "total_time": self._xml_text(app_root, "TotalTime") if app_root is not None else None,
                "pages": self._xml_text(app_root, "Pages") if app_root is not None else None,
                "words": self._xml_text(app_root, "Words") if app_root is not None else None,
            }
        except Exception as e:
            out["office"] = {"metadata_available": False, "metadata_error": str(e), "ext": ext}

        return out




class CsvXlsxParser(BaseFileParser):
    name = "tabular"

    def supports(self, *, ext: str, mime_type: Optional[str] = None) -> bool:
        return ext in {".csv", ".xlsx"}

    def extract_index_metadata(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        if ext == ".csv":
            try:
                import csv

                with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
                    rdr = csv.reader(f)
                    rows = list(rdr)
                row_count = len(rows)
                col_count = max((len(r) for r in rows), default=0)
                return {"table": {"metadata_available": True, "format": "csv", "rows": row_count, "columns": col_count}}
            except Exception as e:
                return {"table": {"metadata_available": False, "format": "csv", "metadata_error": str(e)}}

        if ext == ".xlsx":
            if not zipfile.is_zipfile(path):
                return {"table": {"metadata_available": False, "format": "xlsx", "metadata_error": "invalid_xlsx_zip"}}
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    workbook = zf.read("xl/workbook.xml")
                root = ET.fromstring(workbook)
                sheet_names = []
                for el in root.iter():
                    if el.tag.rsplit("}", 1)[-1] == "sheet":
                        nm = el.attrib.get("name")
                        if nm:
                            sheet_names.append(str(nm))
                return {"table": {"metadata_available": True, "format": "xlsx", "sheet_count": len(sheet_names), "sheets": sheet_names[:50]}}
            except Exception as e:
                return {"table": {"metadata_available": False, "format": "xlsx", "metadata_error": str(e)}}

        return {}


class MediaTagsParser(BaseFileParser):
    name = "media-tags"

    def supports(self, *, ext: str, mime_type: Optional[str] = None) -> bool:
        mt = str(mime_type or "").lower()
        return ext in {".mp3", ".m4a", ".wav", ".flac", ".mp4", ".mov", ".mkv", ".avi"} or mt.startswith("audio/") or mt.startswith("video/")

    def extract_index_metadata(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        out = {"media": {"metadata_available": False, "kind": "audio" if str(mime_type or "").startswith("audio/") else ("video" if str(mime_type or "").startswith("video/") else "unknown")}}
        try:
            from mutagen import File as MutagenFile  # type: ignore

            mf = MutagenFile(str(path))
            tags = {}
            if mf is not None and getattr(mf, "tags", None):
                for k, v in list(mf.tags.items())[:50]:
                    tags[str(k)] = str(v)
            duration = float(getattr(getattr(mf, "info", None), "length", 0.0) or 0.0) if mf is not None else 0.0
            out["media"] = {
                "metadata_available": bool(tags) or duration > 0,
                "kind": out["media"]["kind"],
                "duration_seconds": round(duration, 3) if duration else None,
                "tags": tags,
            }
        except Exception as e:
            out["media"]["metadata_error"] = str(e)
        return out

class FileParserRegistry:
    """Simple ordered parser registry with safe fallback semantics."""

    def __init__(self, parsers: Optional[Iterable[FileParser]] = None):
        self._parsers: list[FileParser] = list(parsers or [])

    def register(self, parser: FileParser) -> None:
        self._parsers.append(parser)

    def resolve(self, *, ext: str, mime_type: Optional[str] = None) -> Optional[FileParser]:
        for parser in self._parsers:
            try:
                if parser.supports(ext=ext, mime_type=mime_type):
                    return parser
            except Exception:
                continue
        return None

    def quick_validate(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> tuple[str, Optional[str]]:
        parser = self.resolve(ext=ext, mime_type=mime_type)
        if parser is None:
            return "ready", None
        return parser.quick_validate(path, ext=ext, mime_type=mime_type)

    def extract_index_metadata(self, path: Path, *, ext: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        parser = self.resolve(ext=ext, mime_type=mime_type)
        if parser is None:
            return {}
        return parser.extract_index_metadata(path, ext=ext, mime_type=mime_type)


def build_default_parser_registry() -> FileParserRegistry:
    registry = FileParserRegistry()
    registry.register(PdfParser())
    registry.register(DocxParser())
    registry.register(OfficeOpenXmlParser())
    registry.register(ImageExifParser())
    registry.register(MediaTagsParser())
    registry.register(CsvXlsxParser())
    registry.register(MarkdownParser())
    registry.register(TextLikeParser())
    return registry
