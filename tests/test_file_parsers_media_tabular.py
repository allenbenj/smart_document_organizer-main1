import zipfile

from services.file_parsers import CsvXlsxParser, MediaTagsParser


def test_csv_parser_extracts_shape(tmp_path):
    p = tmp_path / "data.csv"
    p.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    parser = CsvXlsxParser()
    meta = parser.extract_index_metadata(p, ext=".csv")
    assert meta["table"]["metadata_available"] is True
    assert meta["table"]["rows"] == 3
    assert meta["table"]["columns"] == 2


def test_xlsx_parser_extracts_sheet_names(tmp_path):
    p = tmp_path / "book.xlsx"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets></workbook>',
        )
    parser = CsvXlsxParser()
    meta = parser.extract_index_metadata(p, ext=".xlsx")
    assert meta["table"]["metadata_available"] is True
    assert meta["table"]["sheet_count"] == 1


def test_media_parser_returns_media_block_when_lib_missing(tmp_path):
    p = tmp_path / "clip.mp3"
    p.write_bytes(b"not-real-media")
    parser = MediaTagsParser()
    meta = parser.extract_index_metadata(p, ext=".mp3", mime_type="audio/mpeg")
    assert "media" in meta
    assert "metadata_available" in meta["media"]
