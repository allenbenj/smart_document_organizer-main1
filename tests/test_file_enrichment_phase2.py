import zipfile

from mem_db.database import DatabaseManager
from services.file_index_service import FileIndexService
from services.file_parsers import OfficeOpenXmlParser
from services.file_tagging_rules import RuleTagger


def test_rule_tagger_returns_spans_and_tags():
    tagger = RuleTagger(
        rules=[
            {
                "id": "lab",
                "tag": "document:lab-report",
                "type": "regex",
                "pattern": r"\blab\s+report\b",
                "flags": ["IGNORECASE"],
                "sources": ["content"],
            }
        ]
    )
    out = tagger.apply(sources={"content": "This LAB report confirms findings."})
    assert out["rule_tags"] == ["document:lab-report"]
    assert len(out["rule_tag_hits"]) == 1
    hit = out["rule_tag_hits"][0]
    assert hit["start"] < hit["end"]
    assert "LAB report".lower() in hit["match_text"].lower()


def test_office_openxml_metadata_extraction(tmp_path):
    p = tmp_path / "sample.docx"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr(
            "docProps/core.xml",
            """<?xml version='1.0' encoding='UTF-8'?>
            <cp:coreProperties xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties' xmlns:dc='http://purl.org/dc/elements/1.1/' xmlns:dcterms='http://purl.org/dc/terms/' xmlns:dcmitype='http://purl.org/dc/dcmitype/' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'>
              <dc:title>Lab Report</dc:title>
              <dc:creator>Analyst One</dc:creator>
              <cp:lastModifiedBy>Reviewer</cp:lastModifiedBy>
              <cp:revision>7</cp:revision>
            </cp:coreProperties>""",
        )
        zf.writestr(
            "docProps/app.xml",
            """<?xml version='1.0' encoding='UTF-8'?>
            <Properties xmlns='http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'>
              <Template>Normal.dotm</Template>
              <Application>Microsoft Office Word</Application>
            </Properties>""",
        )

    parser = OfficeOpenXmlParser()
    meta = parser.extract_index_metadata(p, ext=".docx")
    assert meta["office"]["metadata_available"] is True
    assert meta["office"]["author"] == "Analyst One"
    assert meta["office"]["revision"] == "7"
    assert meta["office"]["template"] == "Normal.dotm"


def test_index_includes_rule_tags(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.db"))
    svc = FileIndexService(db)

    root = tmp_path / "docs"
    root.mkdir()
    f = root / "lab_report_case_ABC-123.md"
    f.write_text("# Lab Report\nDelta-9 THC result on 2026-02-01 by Jane Doe", encoding="utf-8")

    res = svc.index_roots([str(root)], allowed_exts={".md"})
    assert res["success"] is True
    assert res["indexed"] == 1

    items, total = db.list_indexed_files(limit=10)
    assert total == 1
    meta = items[0]["metadata_json"]
    assert "document:lab-report" in (meta.get("rule_tags") or [])
    assert len(meta.get("rule_tag_hits") or []) >= 1
