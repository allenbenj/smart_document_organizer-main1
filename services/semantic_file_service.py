"""Baseline semantic enrichment for indexed files."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from pathlib import Path
from typing import Any, Dict, List

from mem_db.database import DatabaseManager


class SemanticFileService:
    def __init__(self, db: DatabaseManager):
        self.db = db

    @staticmethod
    def _deterministic_embedding(text: str, dim: int = 64) -> List[float]:
        values: List[float] = []
        for i in range(dim):
            seed = hashlib.sha256(f"{i}:{text}".encode("utf-8")).digest()
            raw = int.from_bytes(seed[:8], "big")
            values.append((raw / ((1 << 64) - 1)) * 2.0 - 1.0)
        norm = sum(v * v for v in values) ** 0.5
        if norm <= 0:
            return [0.0 for _ in range(dim)]
        return [v / norm for v in values]

    @staticmethod
    def _markdown_chunks(content: str) -> List[Dict[str, Any]]:
        lines = content.splitlines()
        chunks: List[Dict[str, Any]] = []
        title = "Document"
        current: List[str] = []
        in_code = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code = not in_code
                current.append(line)
                continue
            m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if m and not in_code:
                if current:
                    body = "\n".join(current).strip()
                    if body:
                        chunks.append({"title": title, "content": body, "chunk_type": "markdown_section"})
                title = m.group(2).strip() or "Untitled"
                current = []
            else:
                current.append(line)

        if current:
            body = "\n".join(current).strip()
            if body:
                chunks.append({"title": title, "content": body, "chunk_type": "markdown_section"})

        if not chunks and content.strip():
            chunks.append({"title": "Document", "content": content.strip(), "chunk_type": "text"})
        return chunks

    @staticmethod
    def _sliding_chunks(content: str, size: int = 900, overlap: int = 150) -> List[Dict[str, Any]]:
        text = content.strip()
        if not text:
            return []
        chunks: List[Dict[str, Any]] = []
        start = 0
        idx = 0
        while start < len(text):
            end = min(len(text), start + size)
            part = text[start:end].strip()
            if part:
                chunks.append({"title": f"Chunk {idx + 1}", "content": part, "chunk_type": "text"})
                idx += 1
            if end == len(text):
                break
            start = max(start + 1, end - overlap)
        return chunks

    @staticmethod
    def _extract_tables(content: str, ext: str) -> List[Dict[str, Any]]:
        if ext not in {".csv", ".tsv"}:
            return []
        delim = "," if ext == ".csv" else "\t"
        try:
            reader = csv.reader(io.StringIO(content), delimiter=delim)
            rows = [r for r in reader if r]
        except Exception:
            rows = []
        if not rows:
            return []
        headers = rows[0]
        data_rows = rows[1:201]
        return [
            {
                "table_index": 0,
                "extraction_status": "extracted",
                "extraction_method": f"{ext[1:]}_parser_baseline",
                "headers": headers,
                "rows": data_rows,
                "metadata": {
                    "row_count": len(data_rows),
                    "column_count": len(headers),
                    "notes": "Baseline table parser extraction.",
                },
            }
        ]

    def enrich_file(self, file_id: int, embedding_model: str = "local-hash-v1") -> Dict[str, Any]:
        rec = self.db.get_indexed_file(file_id)
        if not rec:
            return {"success": False, "error": "file_not_found"}

        path = Path(str(rec.get("normalized_path") or ""))
        if not path.exists() or not path.is_file():
            return {"success": False, "error": "file_missing"}

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return {"success": False, "error": f"read_failed: {e}"}

        ext = str(rec.get("ext") or "").lower()
        if ext == ".md":
            chunk_seed = self._markdown_chunks(content)
        else:
            chunk_seed = self._sliding_chunks(content)

        chunk_payload: List[Dict[str, Any]] = []
        for i, c in enumerate(chunk_seed):
            txt = str(c.get("content") or "")
            chunk_payload.append(
                {
                    "chunk_index": i,
                    "chunk_type": c.get("chunk_type") or "text",
                    "title": c.get("title"),
                    "content": txt,
                    "token_estimate": max(1, len(txt) // 4),
                    "char_count": len(txt),
                    "metadata": {"pipeline": "semantic_baseline_v1"},
                }
            )

        chunk_ids = self.db.replace_file_chunks(file_id, chunk_payload)

        embeddings_created = 0
        for chunk_id, chunk in zip(chunk_ids, chunk_payload):
            emb = self._deterministic_embedding(str(chunk.get("content") or ""))
            self.db.upsert_chunk_embedding(
                file_id=file_id,
                chunk_id=chunk_id,
                embedding_model=embedding_model,
                embedding=emb,
            )
            embeddings_created += 1

        tables = self._extract_tables(content, ext)
        table_count = self.db.replace_file_tables(file_id, tables)

        return {
            "success": True,
            "file_id": file_id,
            "chunks": len(chunk_ids),
            "embeddings": embeddings_created,
            "tables": table_count,
            "embedding_model": embedding_model,
        }
