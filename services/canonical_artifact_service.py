from __future__ import annotations

from typing import Any

from mem_db.repositories.canonical_repository import CanonicalRepository


class CanonicalArtifactService:
    """Service enforcing immutable canonical artifact semantics."""

    def __init__(self, repository: CanonicalRepository):
        self._repo = repository

    def ingest_artifact(
        self,
        *,
        artifact_id: str,
        sha256: str,
        source_uri: str | None = None,
        mime_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        blob_locator: str | None = None,
        content_size_bytes: int | None = None,
    ) -> int:
        artifact_row_id = self._repo.create_artifact(
            artifact_id=artifact_id,
            sha256=sha256,
            source_uri=source_uri,
            mime_type=mime_type,
            metadata=metadata,
            blob_locator=blob_locator,
            content_size_bytes=content_size_bytes,
        )
        self._repo.append_event(
            artifact_row_id=artifact_row_id,
            event_type="ingested",
            event_data={"sha256": sha256},
        )
        return artifact_row_id

    def append_lineage_event(
        self,
        *,
        artifact_row_id: int,
        event_type: str,
        event_data: dict[str, Any] | None = None,
    ) -> int:
        return self._repo.append_event(
            artifact_row_id=artifact_row_id,
            event_type=event_type,
            event_data=event_data,
        )

    def get_lineage(self, artifact_row_id: int) -> list[dict[str, Any]]:
        return self._repo.list_lineage(artifact_row_id)

    def update_artifact(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("Canonical artifacts are immutable.")

    def delete_artifact(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("Canonical artifacts are immutable.")
