from __future__ import annotations

from datetime import UTC, datetime

from gui.services.aedis_contract_adapters import (
    analysis_version_from_api,
    canonical_artifact_from_api,
    to_api_payload,
)


def test_gui_adapter_aligns_with_aedis_contracts() -> None:
    now = datetime(2026, 2, 19, 0, 0, tzinfo=UTC).isoformat()
    sha = "b" * 64

    artifact = canonical_artifact_from_api(
        {
            "row_id": 10,
            "artifact_id": "artifact-10",
            "sha256": sha,
            "content_type": "application/pdf",
            "byte_size": 4096,
            "created_at": now,
        }
    )
    artifact_payload = to_api_payload(artifact)

    assert artifact_payload["artifact_id"] == "artifact-10"
    assert artifact_payload["sha256"] == sha

    analysis = analysis_version_from_api(
        {
            "analysis_id": "analysis-10",
            "artifact_row_id": 10,
            "version": 2,
            "status": "draft",
            "payload": {"result": "ok"},
            "provenance": {
                "source_artifact_row_id": 10,
                "source_sha256": sha,
                "captured_at": now,
                "extractor": "gui-test",
                "spans": [
                    {
                        "artifact_row_id": 10,
                        "start_char": 0,
                        "end_char": 5,
                        "quote": "hello",
                    }
                ],
            },
            "audit_deltas": [],
            "created_at": now,
        }
    )

    assert analysis.artifact_row_id == 10
    assert analysis.provenance.spans[0].end_char == 5
