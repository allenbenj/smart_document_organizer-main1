from __future__ import annotations

import json
from typing import Any

from .base import BaseRepository


class CanonicalRepository(BaseRepository):
    """Repository for immutable canonical artifacts and append-only lineage events."""

    def create_artifact(
        self,
        *,
        artifact_id: str,
        sha256: str,
        source_uri: str | None,
        mime_type: str | None,
        metadata: dict[str, Any] | None,
        blob_locator: str | None,
        content_size_bytes: int | None,
    ) -> int:
        with self.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO canonical_artifacts (
                    artifact_id,
                    sha256,
                    source_uri,
                    mime_type,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    sha256,
                    source_uri,
                    mime_type,
                    json.dumps(metadata or {}),
                ),
            )
            artifact_row_id = int(cur.lastrowid)
            if blob_locator:
                conn.execute(
                    """
                    INSERT INTO canonical_artifact_blobs (
                        artifact_row_id,
                        blob_locator,
                        content_size_bytes
                    ) VALUES (?, ?, ?)
                    """,
                    (artifact_row_id, blob_locator, content_size_bytes),
                )
            conn.commit()
            return artifact_row_id

    def append_event(
        self,
        *,
        artifact_row_id: int,
        event_type: str,
        event_data: dict[str, Any] | None,
    ) -> int:
        with self.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO canonical_artifact_events (
                    artifact_row_id,
                    event_type,
                    event_data_json
                ) VALUES (?, ?, ?)
                """,
                (
                    int(artifact_row_id),
                    event_type,
                    json.dumps(event_data or {}),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def list_lineage(self, artifact_row_id: int) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, artifact_row_id, event_type, event_data_json, created_at
                FROM canonical_artifact_events
                WHERE artifact_row_id = ?
                ORDER BY id ASC
                """,
                (int(artifact_row_id),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["event_data"] = json.loads(item.get("event_data_json") or "{}")
            except Exception:
                item["event_data"] = {}
            out.append(item)
        return out
