import pytest

from routes.files import (
    file_anomalies,
    file_normalization,
    file_quality,
    file_relationships,
    file_timeline_events,
)


class _FakeDB:
    def __init__(self):
        self.rows = {
            1: {
                "id": 1,
                "display_name": "report_A.txt",
                "normalized_path": "/tmp/case/report_A.txt",
                "file_size": 9000,
                "mtime": 1735689600.0,
                "status": "ready",
                "sha256": "abc",
                "mime_type": "text/plain",
                "mime_source": "mimetypes",
                "last_error": None,
                "last_checked_at": "2026-01-01T00:00:00+00:00",
                "metadata_json": {
                    "preview": "See invoice_B.pdf dated 2025-12-31",
                    "normalization": {
                        "applied": True,
                        "text_quality_score": 0.88,
                        "normalized_preview": "See invoice_B.pdf dated 2025-12-31",
                    },
                    "owner_uid": 1000,
                    "owner_gid": 1000,
                    "permissions": "-rw-r--r--",
                },
            },
            2: {
                "id": 2,
                "display_name": "invoice_B.pdf",
                "normalized_path": "/tmp/case/invoice_B.pdf",
                "file_size": 1200,
                "mtime": 1735689605.0,
                "status": "ready",
                "sha256": "def",
                "mime_type": "application/pdf",
                "mime_source": "magic",
                "last_error": None,
                "last_checked_at": "2026-01-01T00:00:01+00:00",
                "metadata_json": {},
            },
        }

    def get_indexed_file(self, file_id):
        return self.rows.get(file_id)

    def list_all_indexed_files(self):
        return list(self.rows.values())


@pytest.mark.asyncio
async def test_relationships_timeline_quality_and_normalization_baseline():
    db = _FakeDB()

    rel = await file_relationships(file_id=1, db=db)
    assert rel["success"] is True
    assert rel["relationships"]["siblings"]
    assert rel["relationships"]["references"]

    tl = await file_timeline_events(file_id=1, db=db)
    assert tl["success"] is True
    assert any(e["type"] == "embedded_date" for e in tl["events"])

    quality = await file_quality(file_id=1, db=db)
    assert quality["success"] is True
    assert quality["quality"]["overall_score"] > 0
    assert quality["quality"]["normalization"]["text_quality_score"] == 0.88

    norm = await file_normalization(file_id=1, db=db)
    assert norm["success"] is True
    assert norm["normalization"]["applied"] is True

    anom = await file_anomalies(file_id=1, db=db)
    assert anom["success"] is True
    assert "anomaly_flags" in anom
