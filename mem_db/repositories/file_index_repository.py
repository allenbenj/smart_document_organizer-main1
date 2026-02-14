from __future__ import annotations

import hashlib
import json
import math
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseRepository


class FileIndexRepository(BaseRepository):
    def upsert_indexed_file(
        self,
        *,
        display_name: str,
        original_path: str,
        normalized_path: str,
        file_size: Optional[int],
        mtime: Optional[float],
        mime_type: Optional[str],
        mime_source: Optional[str],
        sha256: Optional[str],
        ext: Optional[str],
        status: str,
        last_error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        path_hash = hashlib.sha1(normalized_path.encode("utf-8")).hexdigest()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO files_index (
                    display_name, original_path, normalized_path, path_hash,
                    file_size, mtime, mime_type, mime_source, sha256, ext, status, last_checked_at, last_error, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
                ON CONFLICT(path_hash) DO UPDATE SET
                    display_name=excluded.display_name,
                    original_path=excluded.original_path,
                    normalized_path=excluded.normalized_path,
                    file_size=excluded.file_size,
                    mtime=excluded.mtime,
                    mime_type=excluded.mime_type,
                    mime_source=excluded.mime_source,
                    sha256=excluded.sha256,
                    ext=excluded.ext,
                    status=excluded.status,
                    last_checked_at=CURRENT_TIMESTAMP,
                    last_error=excluded.last_error,
                    metadata_json=excluded.metadata_json
                """,
                (
                    display_name,
                    original_path,
                    normalized_path,
                    path_hash,
                    file_size,
                    mtime,
                    mime_type,
                    mime_source,
                    sha256,
                    ext,
                    status,
                    last_error,
                    json.dumps(metadata or {}),
                ),
            )
            row = conn.execute(
                "SELECT id FROM files_index WHERE path_hash = ?", (path_hash,)
            ).fetchone()
            conn.commit()
            return int(row[0]) if row else 0

    def get_indexed_file(self, file_id: int) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM files_index WHERE id = ?", (file_id,)).fetchone()
            if not row:
                return None
            out = dict(row)
            try:
                out["metadata_json"] = json.loads(out.get("metadata_json") or "{}")
            except Exception:
                out["metadata_json"] = {}
            return out

    def list_indexed_files(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        ext: Optional[str] = None,
        query: Optional[str] = None,
        sort_by: str = "last_checked_at",
        sort_dir: str = "desc",
        keyword: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        with self.connection() as conn:
            where = []
            params: List[Any] = []
            if status:
                where.append("status = ?")
                params.append(status)
            if ext:
                where.append("ext = ?")
                params.append(ext.lower())
            if query:
                where.append("(display_name LIKE ? OR normalized_path LIKE ?)")
                q = f"%{query}%"
                params.extend([q, q])
            where_clause = f"WHERE {' AND '.join(where)}" if where else ""

            total = conn.execute(
                f"SELECT COUNT(*) FROM files_index {where_clause}", params
            ).fetchone()[0]

            sort_field_map = {
                "mtime": "mtime",
                "name": "display_name",
                "status": "status",
                "last_checked_at": "last_checked_at",
            }
            sf = sort_field_map.get((sort_by or "").lower(), "last_checked_at")
            sd = "ASC" if (sort_dir or "").lower() == "asc" else "DESC"

            if keyword:
                rows = conn.execute(
                    f"""
                    SELECT *,
                           CASE
                               WHEN lower(display_name) LIKE lower(?) THEN 2
                               WHEN lower(normalized_path) LIKE lower(?) THEN 1
                               ELSE 0
                           END AS keyword_score
                    FROM files_index {where_clause}
                    ORDER BY keyword_score DESC, {sf} {sd}
                    LIMIT ? OFFSET ?
                    """,
                    [f"%{keyword}%", f"%{keyword}%", *params, limit, offset],
                ).fetchall()
            else:
                rows = conn.execute(
                    f"""
                    SELECT * FROM files_index {where_clause}
                    ORDER BY {sf} {sd}
                    LIMIT ? OFFSET ?
                    """,
                    [*params, limit, offset],
                ).fetchall()

            items = []
            for row in rows:
                item = dict(row)
                try:
                    item["metadata_json"] = json.loads(item.get("metadata_json") or "{}")
                except Exception:
                    item["metadata_json"] = {}
                items.append(item)
            return items, int(total)

    def list_all_indexed_files(self) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM files_index").fetchall()
            out: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                try:
                    item["metadata_json"] = json.loads(item.get("metadata_json") or "{}")
                except Exception:
                    item["metadata_json"] = {}
                out.append(item)
            return out

    def replace_file_chunks(self, file_id: int, chunks: List[Dict[str, Any]]) -> List[int]:
        chunk_ids: List[int] = []
        with self.connection() as conn:
            conn.execute("DELETE FROM file_chunk_embeddings WHERE file_id = ?", (file_id,))
            conn.execute("DELETE FROM file_extracted_tables WHERE file_id = ?", (file_id,))
            conn.execute("DELETE FROM file_content_chunks WHERE file_id = ?", (file_id,))

            for idx, chunk in enumerate(chunks):
                cur = conn.execute(
                    """
                    INSERT INTO file_content_chunks (
                        file_id, chunk_index, chunk_type, title, content,
                        token_estimate, char_count, metadata_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        file_id,
                        int(chunk.get("chunk_index", idx)),
                        str(chunk.get("chunk_type") or "text"),
                        chunk.get("title"),
                        str(chunk.get("content") or ""),
                        int(chunk.get("token_estimate") or 0),
                        int(chunk.get("char_count") or len(str(chunk.get("content") or ""))),
                        json.dumps(chunk.get("metadata") or {}),
                    ),
                )
                chunk_ids.append(int(cur.lastrowid))
            conn.commit()
        return chunk_ids

    def list_file_chunks(self, file_id: int) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM file_content_chunks WHERE file_id = ? ORDER BY chunk_index ASC",
                (file_id,),
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                try:
                    item["metadata_json"] = json.loads(item.get("metadata_json") or "{}")
                except Exception:
                    item["metadata_json"] = {}
                out.append(item)
            return out

    def replace_file_entities(self, file_id: int, entities: List[Dict[str, Any]]) -> int:
        with self.connection() as conn:
            conn.execute("DELETE FROM file_entities WHERE file_id = ?", (file_id,))
            inserted = 0
            for entity in entities:
                entity_text = str(entity.get("entity_text") or entity.get("text") or "").strip()
                if not entity_text:
                    continue
                conn.execute(
                    """
                    INSERT INTO file_entities (
                        file_id, entity_text, entity_type, ontology_id, confidence, provenance, metadata_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        file_id,
                        entity_text,
                        entity.get("entity_type") or entity.get("label"),
                        entity.get("ontology_id"),
                        float(entity.get("confidence") or 0.5),
                        entity.get("provenance"),
                        json.dumps(entity.get("metadata") or {}),
                    ),
                )
                inserted += 1
            conn.commit()
            return inserted

    def list_file_entities(self, file_id: int) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM file_entities WHERE file_id = ? ORDER BY confidence DESC, entity_text ASC",
                (file_id,),
            ).fetchall()
            out = []
            for row in rows:
                item = dict(row)
                try:
                    item["metadata_json"] = json.loads(item.get("metadata_json") or "{}")
                except Exception:
                    item["metadata_json"] = {}
                out.append(item)
            return out

    def refresh_file_entity_links(self) -> int:
        with self.connection() as conn:
            conn.execute("DELETE FROM file_entity_links")
            rows = conn.execute(
                """
                SELECT a.file_id AS source_file_id, b.file_id AS target_file_id, a.ontology_id
                FROM file_entities a
                JOIN file_entities b
                  ON a.ontology_id = b.ontology_id
                 AND a.file_id < b.file_id
                WHERE a.ontology_id IS NOT NULL AND a.ontology_id != ''
                GROUP BY a.file_id, b.file_id, a.ontology_id
                """
            ).fetchall()
            inserted = 0
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO file_entity_links (
                        source_file_id, target_file_id, ontology_id, link_basis, confidence, metadata_json, updated_at
                    ) VALUES (?, ?, ?, 'shared_entity', 0.7, ?, CURRENT_TIMESTAMP)
                    """,
                    (row["source_file_id"], row["target_file_id"], row["ontology_id"], json.dumps({"ontology_id": row["ontology_id"]})),
                )
                inserted += 1
            conn.commit()
            return inserted

    def list_file_entity_links(self, file_id: int) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM file_entity_links
                WHERE source_file_id = ? OR target_file_id = ?
                ORDER BY confidence DESC, id ASC
                """,
                (file_id, file_id),
            ).fetchall()
            out = []
            for row in rows:
                item = dict(row)
                try:
                    item["metadata_json"] = json.loads(item.get("metadata_json") or "{}")
                except Exception:
                    item["metadata_json"] = {}
                out.append(item)
            return out

    def refresh_materialized_file_summaries(self, stale_after_hours: int = 24) -> Dict[str, int]:
        with self.connection() as conn:
            rows = conn.execute("SELECT id, status, mtime, last_checked_at, metadata_json FROM files_index").fetchall()
            conn.execute("DELETE FROM mv_timeline_summary")
            conn.execute("DELETE FROM mv_keyword_entity_summary")
            conn.execute("DELETE FROM mv_file_health_summary")

            now_ts = time.time()
            stale_cutoff = now_ts - (int(stale_after_hours) * 3600)
            batch_size = 250

            for idx, row in enumerate(rows, start=1):
                file_id = int(row["id"])
                try:
                    meta = json.loads(row["metadata_json"] or "{}")
                except Exception:
                    meta = {}

                ts_values = [
                    meta.get("created_iso") or None,
                    meta.get("mtime_iso") or None,
                    meta.get("atime_iso") or None,
                    meta.get("ctime_iso") or None,
                    str(row["last_checked_at"]) if row["last_checked_at"] else None,
                ]
                ts_values = sorted([t for t in ts_values if t])
                conn.execute(
                    "INSERT INTO mv_timeline_summary (file_id, first_event_ts, last_event_ts, event_count, refreshed_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (file_id, ts_values[0] if ts_values else None, ts_values[-1] if ts_values else None, len(ts_values)),
                )

                rule_tag_count = len((meta.get("rule_tags") or [])) if isinstance(meta, dict) else 0
                entity_count = conn.execute("SELECT COUNT(*) FROM file_entities WHERE file_id = ?", (file_id,)).fetchone()[0]
                unresolved = len(set(re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", str(meta.get("preview") or ""))))
                conn.execute(
                    "INSERT INTO mv_keyword_entity_summary (file_id, rule_tag_count, entity_count, unresolved_candidate_count, refreshed_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (file_id, int(rule_tag_count), int(entity_count), int(unresolved)),
                )

                checked_ts = None
                try:
                    checked_ts = datetime.fromisoformat(str(row["last_checked_at"]).replace("Z", "+00:00")).timestamp() if row["last_checked_at"] else None
                except Exception:
                    checked_ts = None
                is_stale = bool(checked_ts is not None and checked_ts < stale_cutoff)
                status = str(row["status"] or "")
                conn.execute(
                    "INSERT INTO mv_file_health_summary (file_id, status, is_missing, is_damaged, is_stale, refreshed_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (
                        file_id,
                        status,
                        1 if status == "missing" else 0,
                        1 if status == "damaged" else 0,
                        1 if is_stale else 0,
                    ),
                )

                if idx % batch_size == 0:
                    conn.commit()

            conn.commit()
            return {"files": len(rows)}

    def replace_file_tables(self, file_id: int, tables: List[Dict[str, Any]]) -> int:
        with self.connection() as conn:
            conn.execute("DELETE FROM file_extracted_tables WHERE file_id = ?", (file_id,))
            inserted = 0
            for i, table in enumerate(tables):
                conn.execute(
                    """
                    INSERT INTO file_extracted_tables (
                        file_id, source_chunk_id, table_index, extraction_status,
                        extraction_method, headers_json, rows_json, metadata_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        file_id,
                        table.get("source_chunk_id"),
                        int(table.get("table_index", i)),
                        str(table.get("extraction_status") or "placeholder"),
                        table.get("extraction_method"),
                        json.dumps(table.get("headers") or []),
                        json.dumps(table.get("rows") or []),
                        json.dumps(table.get("metadata") or {}),
                    ),
                )
                inserted += 1
            conn.commit()
            return inserted

    def list_file_tables(self, file_id: int) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM file_extracted_tables WHERE file_id = ? ORDER BY table_index ASC",
                (file_id,),
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                for key, fallback in (("headers_json", []), ("rows_json", []), ("metadata_json", {})):
                    try:
                        item[key] = json.loads(item.get(key) or json.dumps(fallback))
                    except Exception:
                        item[key] = fallback
                out.append(item)
            return out

    def upsert_chunk_embedding(self, *, file_id: int, chunk_id: int, embedding_model: str, embedding: List[float]) -> int:
        vector = [float(v) for v in embedding]
        vector_dim = len(vector)
        emb_hash = hashlib.sha1(json.dumps(vector, sort_keys=False).encode("utf-8")).hexdigest()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO file_chunk_embeddings (
                    file_id, chunk_id, embedding_model, vector_dim, embedding_json, embedding_hash, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chunk_id, embedding_model) DO UPDATE SET
                    file_id=excluded.file_id,
                    vector_dim=excluded.vector_dim,
                    embedding_json=excluded.embedding_json,
                    embedding_hash=excluded.embedding_hash,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (file_id, chunk_id, embedding_model, vector_dim, json.dumps(vector), emb_hash),
            )
            row = conn.execute(
                "SELECT id FROM file_chunk_embeddings WHERE chunk_id = ? AND embedding_model = ?",
                (chunk_id, embedding_model),
            ).fetchone()
            conn.commit()
            return int(row[0]) if row else 0

    def semantic_similarity_search(
        self,
        *,
        query_embedding: List[float],
        embedding_model: str,
        limit: int = 10,
        min_similarity: float = 0.0,
        file_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        q = [float(v) for v in query_embedding]
        q_norm = math.sqrt(sum(v * v for v in q))
        if q_norm == 0:
            return []

        with self.connection() as conn:
            where = ["e.embedding_model = ?", "e.vector_dim = ?"]
            params: List[Any] = [embedding_model, len(q)]
            if file_id is not None:
                where.append("e.file_id = ?")
                params.append(file_id)

            rows = conn.execute(
                f"""
                SELECT e.*, c.chunk_index, c.chunk_type, c.title, c.content, f.display_name, f.normalized_path
                FROM file_chunk_embeddings e
                JOIN file_content_chunks c ON c.id = e.chunk_id
                JOIN files_index f ON f.id = e.file_id
                WHERE {' AND '.join(where)}
                """,
                params,
            ).fetchall()

            scored: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                try:
                    vec = [float(v) for v in json.loads(item.get("embedding_json") or "[]")]
                except Exception:
                    continue
                if len(vec) != len(q):
                    continue
                v_norm = math.sqrt(sum(v * v for v in vec))
                if v_norm == 0:
                    continue
                similarity = sum(a * b for a, b in zip(q, vec)) / (q_norm * v_norm)
                if similarity < float(min_similarity):
                    continue
                scored.append(
                    {
                        "embedding_id": item.get("id"),
                        "file_id": item.get("file_id"),
                        "chunk_id": item.get("chunk_id"),
                        "chunk_index": item.get("chunk_index"),
                        "chunk_type": item.get("chunk_type"),
                        "title": item.get("title"),
                        "content": item.get("content"),
                        "display_name": item.get("display_name"),
                        "normalized_path": item.get("normalized_path"),
                        "similarity": float(similarity),
                    }
                )

            scored.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
            return scored[: max(1, int(limit))]

    def refresh_exact_duplicate_relationships(self) -> Dict[str, int]:
        with self.connection() as conn:
            conn.execute("DELETE FROM file_duplicate_relationships WHERE relationship_type = 'exact'")

            groups = conn.execute(
                """
                SELECT sha256, GROUP_CONCAT(id) AS ids
                FROM files_index
                WHERE sha256 IS NOT NULL AND sha256 != '' AND status = 'ready'
                GROUP BY sha256
                HAVING COUNT(*) > 1
                """
            ).fetchall()

            inserted = 0
            for row in groups:
                ids_raw = str(row["ids"] or "")
                ids = sorted([int(x) for x in ids_raw.split(",") if str(x).strip().isdigit()])
                if len(ids) < 2:
                    continue
                canonical_id = ids[0]
                for dup_id in ids[1:]:
                    conn.execute(
                        """
                        INSERT INTO file_duplicate_relationships (
                            canonical_file_id, duplicate_file_id, relationship_type, confidence, match_basis, updated_at
                        ) VALUES (?, ?, 'exact', 1.0, 'sha256', CURRENT_TIMESTAMP)
                        ON CONFLICT(canonical_file_id, duplicate_file_id, relationship_type)
                        DO UPDATE SET confidence=excluded.confidence, match_basis=excluded.match_basis, updated_at=CURRENT_TIMESTAMP
                        """,
                        (canonical_id, dup_id),
                    )
                    inserted += 1

            conn.commit()
            return {"groups": len(groups), "relationships": inserted}

    def get_file_duplicate_relationships(self, file_id: int) -> Dict[str, Any]:
        with self.connection() as conn:
            rec = conn.execute("SELECT * FROM files_index WHERE id = ?", (file_id,)).fetchone()
            if not rec:
                return {"found": False}

            duplicate_of = conn.execute(
                """
                SELECT r.*, f.display_name AS canonical_name, f.normalized_path AS canonical_path
                FROM file_duplicate_relationships r
                JOIN files_index f ON f.id = r.canonical_file_id
                WHERE r.duplicate_file_id = ? AND r.relationship_type = 'exact'
                ORDER BY r.canonical_file_id ASC
                LIMIT 1
                """,
                (file_id,),
            ).fetchone()

            exact_duplicates = conn.execute(
                """
                SELECT r.*, f.display_name, f.normalized_path, f.sha256, f.status
                FROM file_duplicate_relationships r
                JOIN files_index f ON f.id = r.duplicate_file_id
                WHERE r.canonical_file_id = ? AND r.relationship_type = 'exact'
                ORDER BY r.duplicate_file_id ASC
                """,
                (file_id,),
            ).fetchall()

            near_duplicates = conn.execute(
                """
                SELECT r.*, f.display_name, f.normalized_path
                FROM file_duplicate_relationships r
                JOIN files_index f ON f.id = r.duplicate_file_id
                WHERE r.canonical_file_id = ? AND r.relationship_type = 'near'
                ORDER BY r.confidence DESC, r.duplicate_file_id ASC
                """,
                (file_id,),
            ).fetchall()

            return {
                "found": True,
                "file": dict(rec),
                "duplicate_of": dict(duplicate_of) if duplicate_of else None,
                "exact_duplicates": [dict(r) for r in exact_duplicates],
                "near_duplicates": [dict(r) for r in near_duplicates],
            }

    def scan_manifest_get(self, path_hash: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM scan_manifest WHERE path_hash = ?", (path_hash,)).fetchone()
            return dict(row) if row else None

    def scan_manifest_upsert(
        self,
        *,
        path_hash: str,
        normalized_path: str,
        file_size: Optional[int],
        mtime: Optional[float],
        sha256: Optional[str],
        last_status: Optional[str],
        last_error: Optional[str],
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO scan_manifest (path_hash, normalized_path, file_size, mtime, sha256, last_status, last_error, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(path_hash) DO UPDATE SET
                    normalized_path=excluded.normalized_path,
                    file_size=excluded.file_size,
                    mtime=excluded.mtime,
                    sha256=excluded.sha256,
                    last_status=excluded.last_status,
                    last_error=excluded.last_error,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (path_hash, normalized_path, file_size, mtime, sha256, last_status, last_error),
            )
            conn.commit()

    def search_file_chunks_fulltext(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        q = str(query or "").strip()
        if not q:
            return []
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT c.file_id, c.id AS chunk_id, c.chunk_index, c.title, c.content
                FROM file_content_chunks_fts f
                JOIN file_content_chunks c ON c.id = f.rowid
                WHERE file_content_chunks_fts MATCH ?
                LIMIT ?
                """,
                (q, max(1, int(limit))),
            ).fetchall()
            return [dict(r) for r in rows]

    def upsert_watched_directory(
        self,
        *,
        original_path: str,
        normalized_path: str,
        recursive: bool = True,
        keywords: Optional[List[str]] = None,
        allowed_exts: Optional[List[str]] = None,
        active: bool = True,
    ) -> int:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO watched_directories (
                    original_path, normalized_path, recursive, keywords_json, allowed_exts_json, active, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(normalized_path) DO UPDATE SET
                    original_path=excluded.original_path,
                    recursive=excluded.recursive,
                    keywords_json=excluded.keywords_json,
                    allowed_exts_json=excluded.allowed_exts_json,
                    active=excluded.active,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    original_path,
                    normalized_path,
                    1 if recursive else 0,
                    json.dumps(keywords or []),
                    json.dumps(allowed_exts or []),
                    1 if active else 0,
                ),
            )
            row = conn.execute(
                "SELECT id FROM watched_directories WHERE normalized_path = ?",
                (normalized_path,),
            ).fetchone()
            conn.commit()
            return int(row[0]) if row else 0

    def list_watched_directories(self, active_only: bool = True) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            where = "WHERE active = 1" if active_only else ""
            rows = conn.execute(
                f"SELECT * FROM watched_directories {where} ORDER BY created_at DESC"
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                for key in ("keywords_json", "allowed_exts_json"):
                    try:
                        item[key] = json.loads(item.get(key) or "[]")
                    except Exception:
                        item[key] = []
                out.append(item)
            return out
