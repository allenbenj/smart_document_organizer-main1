from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .base import BaseRepository


class WatchRepository(BaseRepository):
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
        def _op(conn: Any) -> None:
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

        self.write_with_retry(_op)

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
        def _op(conn: Any) -> int:
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
            return int(row[0]) if row else 0

        return self.write_with_retry(_op)

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
