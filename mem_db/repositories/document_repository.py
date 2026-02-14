from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from utils.models import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    SearchQuery,
    TagCreate,
    TagResponse,
)

from .base import BaseRepository

logger = logging.getLogger(__name__)


class DocumentRepository(BaseRepository):
    def create_document(self, document: DocumentCreate) -> DocumentResponse:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO documents (file_name, file_type, category, file_path, primary_purpose)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    document.file_name,
                    document.file_type,
                    document.category,
                    document.file_path,
                    document.primary_purpose,
                ),
            )
            document_id = cursor.lastrowid
            if document_id is None:
                raise ValueError("Failed to create document - no ID returned")

            if document.content_text:
                conn.execute(
                    """
                    INSERT INTO document_content (document_id, content_text, content_type)
                    VALUES (?, ?, ?)
                """,
                    (document_id, document.content_text, document.content_type),
                )
                self._update_search_index(conn, int(document_id), document.content_text)
                self._compute_and_store_analytics(conn, int(document_id), document.content_text)

            conn.commit()
            created_doc = self.get_document(int(document_id))
            if created_doc is None:
                raise ValueError("Failed to retrieve created document")
            return created_doc

    def get_document(self, document_id: int) -> Optional[DocumentResponse]:
        with self.connection() as conn:
            doc_row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
            if not doc_row:
                return None

            content_row = conn.execute(
                "SELECT content_text, content_type FROM document_content WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            tag_rows = conn.execute(
                "SELECT id, document_id, tag_name, tag_value, created_at FROM document_tags WHERE document_id = ?",
                (document_id,),
            ).fetchall()

            doc_dict = dict(doc_row)
            doc_dict["content_text"] = content_row["content_text"] if content_row else None
            doc_dict["content_type"] = content_row["content_type"] if content_row else None
            doc_dict["tags"] = [
                TagResponse(
                    id=tag["id"],
                    document_id=tag["document_id"],
                    tag_name=tag["tag_name"],
                    tag_value=tag["tag_value"],
                    created_at=datetime.fromisoformat(tag["created_at"]),
                )
                for tag in tag_rows
            ]
            return DocumentResponse(**doc_dict)

    def update_document(self, document_id: int, document: DocumentUpdate) -> Optional[DocumentResponse]:
        with self.connection() as conn:
            if not self.get_document(document_id):
                return None

            update_fields = []
            update_values = []
            for field, value in document.dict(exclude_unset=True).items():
                if field in ["content_text", "content_type"]:
                    continue
                update_fields.append(f"{field} = ?")
                update_values.append(value)

            if update_fields:
                update_values.append(datetime.now().isoformat())
                update_fields.append("updated_at = ?")
                update_values.append(document_id)
                conn.execute(
                    f"UPDATE documents SET {', '.join(update_fields)} WHERE id = ?",
                    update_values,
                )

            if document.content_text is not None or document.content_type is not None:
                content_exists = conn.execute(
                    "SELECT 1 FROM document_content WHERE document_id = ?",
                    (document_id,),
                ).fetchone()

                if content_exists:
                    content_updates = []
                    content_values = []
                    if document.content_text is not None:
                        content_updates.append("content_text = ?")
                        content_values.append(document.content_text)
                    if document.content_type is not None:
                        content_updates.append("content_type = ?")
                        content_values.append(document.content_type)
                    if content_updates:
                        content_values.append(document_id)
                        conn.execute(
                            f"UPDATE document_content SET {', '.join(content_updates)} WHERE document_id = ?",
                            content_values,
                        )
                        if document.content_text is not None:
                            self._update_search_index(conn, document_id, document.content_text)
                            self._compute_and_store_analytics(conn, document_id, document.content_text or "")
                else:
                    conn.execute(
                        "INSERT INTO document_content (document_id, content_text, content_type) VALUES (?, ?, ?)",
                        (document_id, document.content_text or "", document.content_type or "text/plain"),
                    )
                    if document.content_text:
                        self._update_search_index(conn, document_id, document.content_text)

            conn.commit()
            return self.get_document(document_id)

    def delete_document(self, document_id: int) -> bool:
        with self.connection() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_documents(
        self,
        limit: int = 20,
        offset: int = 0,
        category: Optional[str] = None,
        file_type: Optional[str] = None,
    ) -> Tuple[List[DocumentResponse], int]:
        with self.connection() as conn:
            where_conditions = []
            params = []
            if category:
                where_conditions.append("category = ?")
                params.append(category)
            if file_type:
                where_conditions.append("file_type = ?")
                params.append(file_type)
            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

            count_query = f"SELECT COUNT(*) FROM documents {where_clause}"
            total_count = conn.execute(count_query, params).fetchone()[0]

            params.extend([limit, offset])
            documents_query = f"SELECT * FROM documents {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?"
            doc_rows = conn.execute(documents_query, params).fetchall()

            documents = []
            for row in doc_rows:
                doc_dict = dict(row)
                doc_dict["content_text"] = None
                doc_dict["content_type"] = None
                doc_dict["tags"] = []
                documents.append(DocumentResponse(**doc_dict))
            return documents, total_count

    def get_document_analytics(self, document_id: int) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT document_id, char_count, word_count, sentence_count, top_terms, computed_at FROM document_analytics WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            try:
                data["top_terms"] = json.loads(data.get("top_terms") or "[]")
            except Exception:
                data["top_terms"] = []
            return data

    def recompute_document_analytics(self, document_id: int) -> bool:
        with self.connection() as conn:
            content_row = conn.execute(
                "SELECT content_text FROM document_content WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            if not content_row or not (content := (content_row[0] or "")):
                self._compute_and_store_analytics(conn, document_id, "")
                conn.commit()
                return True
            self._compute_and_store_analytics(conn, document_id, content)
            conn.commit()
            return True

    def add_document_tags(self, document_id: int, tags: List[TagCreate]) -> List[TagResponse]:
        with self.connection() as conn:
            created_tags = []
            for tag in tags:
                try:
                    cursor = conn.execute(
                        "INSERT INTO document_tags (document_id, tag_name, tag_value) VALUES (?, ?, ?)",
                        (document_id, tag.tag_name, tag.tag_value),
                    )
                    tag_row = conn.execute("SELECT * FROM document_tags WHERE id = ?", (cursor.lastrowid,)).fetchone()
                    created_tags.append(
                        TagResponse(
                            id=tag_row["id"],
                            document_id=tag_row["document_id"],
                            tag_name=tag_row["tag_name"],
                            tag_value=tag_row["tag_value"],
                            created_at=datetime.fromisoformat(tag_row["created_at"]),
                        )
                    )
                except sqlite3.IntegrityError:
                    logger.warning("Tag '%s' already exists for document %s", tag.tag_name, document_id)
                    continue
            conn.commit()
            return created_tags

    def get_document_tags(self, document_id: int) -> List[TagResponse]:
        with self.connection() as conn:
            tag_rows = conn.execute("SELECT * FROM document_tags WHERE document_id = ?", (document_id,)).fetchall()
            return [
                TagResponse(
                    id=row["id"],
                    document_id=row["document_id"],
                    tag_name=row["tag_name"],
                    tag_value=row["tag_value"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in tag_rows
            ]

    def delete_document_tag(self, document_id: int, tag_name: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM document_tags WHERE document_id = ? AND tag_name = ?",
                (document_id, tag_name),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_all_tags(self) -> List[str]:
        with self.connection() as conn:
            rows = conn.execute("SELECT DISTINCT tag_name FROM document_tags ORDER BY tag_name").fetchall()
            return [row["tag_name"] for row in rows]

    def get_documents_by_tag(self, tag_name: str, limit: int = 20, offset: int = 0) -> Tuple[List[DocumentResponse], int]:
        with self.connection() as conn:
            total_count = conn.execute(
                "SELECT COUNT(DISTINCT d.id) FROM documents d JOIN document_tags dt ON d.id = dt.document_id WHERE dt.tag_name = ?",
                (tag_name,),
            ).fetchone()[0]
            doc_rows = conn.execute(
                """
                SELECT DISTINCT d.* FROM documents d
                JOIN document_tags dt ON d.id = dt.document_id
                WHERE dt.tag_name = ?
                ORDER BY d.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (tag_name, limit, offset),
            ).fetchall()
            documents = []
            for row in doc_rows:
                doc_dict = dict(row)
                doc_dict["content_text"] = None
                doc_dict["content_type"] = None
                doc_dict["tags"] = []
                documents.append(DocumentResponse(**doc_dict))
            return documents, total_count

    def search_documents(self, query: SearchQuery) -> Tuple[List[DocumentResponse], int]:
        with self.connection() as conn:
            where_conditions = []
            params = []
            joins = []
            if query.query:
                joins.append("LEFT JOIN document_content dc ON d.id = dc.document_id")
                joins.append("LEFT JOIN search_indices si ON d.id = si.document_id")
                where_conditions.append(
                    "(d.file_name LIKE ? OR d.category LIKE ? OR d.primary_purpose LIKE ? OR dc.content_text LIKE ? OR si.search_terms LIKE ?)"
                )
                search_term = f"%{query.query}%"
                params.extend([search_term] * 5)
            if query.category:
                where_conditions.append("d.category = ?")
                params.append(query.category)
            if query.file_type:
                where_conditions.append("d.file_type = ?")
                params.append(query.file_type)
            if query.tags:
                tag_conditions = []
                for tag in query.tags:
                    tag_conditions.append("dt.tag_name = ?")
                    params.append(tag)
                joins.append("JOIN document_tags dt ON d.id = dt.document_id")
                where_conditions.append(f"({' OR '.join(tag_conditions)})")

            join_clause = " ".join(joins)
            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

            count_query = f"SELECT COUNT(DISTINCT d.id) FROM documents d {join_clause} {where_clause}"
            total_count = conn.execute(count_query, params).fetchone()[0]

            params.extend([query.limit, query.offset])
            search_query = f"SELECT DISTINCT d.* FROM documents d {join_clause} {where_clause} ORDER BY d.created_at DESC LIMIT ? OFFSET ?"
            doc_rows = conn.execute(search_query, params).fetchall()
            documents = []
            for row in doc_rows:
                doc_dict = dict(row)
                doc_dict["content_text"] = None
                doc_dict["content_type"] = None
                doc_dict["tags"] = []
                documents.append(DocumentResponse(**doc_dict))
            return documents, total_count

    def get_search_suggestions(self, query: str) -> Dict[str, List[str]]:
        with self.connection() as conn:
            search_term = f"%{query}%"
            categories = conn.execute(
                "SELECT DISTINCT category FROM documents WHERE category LIKE ? ORDER BY category LIMIT 5",
                (search_term,),
            ).fetchall()
            tags = conn.execute(
                "SELECT DISTINCT tag_name FROM document_tags WHERE tag_name LIKE ? ORDER BY tag_name LIMIT 5",
                (search_term,),
            ).fetchall()
            suggestions = conn.execute(
                "SELECT DISTINCT file_name FROM documents WHERE file_name LIKE ? ORDER BY file_name LIMIT 5",
                (search_term,),
            ).fetchall()
            return {
                "suggestions": [row["file_name"] for row in suggestions],
                "categories": [row["category"] for row in categories],
                "tags": [row["tag_name"] for row in tags],
            }

    def get_database_stats(self) -> Dict[str, Any]:
        with self.connection() as conn:
            stats: Dict[str, Any] = {}
            stats["total_documents"] = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            stats["total_tags"] = conn.execute("SELECT COUNT(*) FROM document_tags").fetchone()[0]
            stats["unique_tags"] = conn.execute("SELECT COUNT(DISTINCT tag_name) FROM document_tags").fetchone()[0]

            category_rows = conn.execute(
                "SELECT category, COUNT(*) as count FROM documents GROUP BY category ORDER BY count DESC"
            ).fetchall()
            stats["categories"] = {row["category"]: row["count"] for row in category_rows}

            type_rows = conn.execute(
                "SELECT file_type, COUNT(*) as count FROM documents GROUP BY file_type ORDER BY count DESC"
            ).fetchall()
            stats["file_types"] = {row["file_type"]: row["count"] for row in type_rows}
            return stats

    def _compute_and_store_analytics(self, conn: sqlite3.Connection, document_id: int, text: str) -> None:
        try:
            import re
            from collections import Counter

            char_count = len(text)
            tokens = [t.lower() for t in re.split(r"[^A-Za-z0-9]+", text) if t]
            word_count = len(tokens)
            sentence_count = len([s for s in re.split(r"[\.!?]+\s+", text.strip()) if s]) if text.strip() else 0

            stop = {
                "the", "a", "an", "and", "or", "but", "i", "in", "on", "at", "to", "o", "for", "by",
                "with", "is", "are", "was", "were", "be", "been", "it", "this", "that", "as", "from", "not",
            }
            terms = [t for t in tokens if t not in stop and len(t) > 2]
            top = Counter(terms).most_common(15)
            top_terms = [{"term": term, "count": cnt} for term, cnt in top]

            conn.execute(
                """
                INSERT INTO document_analytics (document_id, char_count, word_count, sentence_count, top_terms, computed_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(document_id) DO UPDATE SET
                    char_count=excluded.char_count,
                    word_count=excluded.word_count,
                    sentence_count=excluded.sentence_count,
                    top_terms=excluded.top_terms,
                    computed_at=CURRENT_TIMESTAMP
                """,
                (document_id, char_count, word_count, sentence_count, json.dumps(top_terms)),
            )
        except Exception as e:
            logger.warning("Failed to compute analytics for %s: %s", document_id, e)

    def _update_search_index(self, conn: sqlite3.Connection, document_id: int, content: str) -> None:
        keywords = set()
        for word in content.lower().split():
            cleaned_word = "".join(c for c in word if c.isalnum())
            if len(cleaned_word) > 3:
                keywords.add(cleaned_word)
        search_terms = " ".join(keywords)
        conn.execute(
            "INSERT OR REPLACE INTO search_indices (document_id, search_terms, updated_at) VALUES (?, ?, ?)",
            (document_id, search_terms, datetime.now().isoformat()),
        )
