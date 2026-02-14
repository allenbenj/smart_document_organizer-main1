import sys
import types

from routes.files import _extract_candidate_entities
from services.file_index_service import FileIndexService


def test_entity_extraction_accuracy_on_curated_samples():
    samples = [
        {
            "text": "Judge Alice Monroe signed the order on 2025-12-31 in Austin, TX.",
            "expected": {("Person", "Judge Alice Monroe"), ("Date", "2025-12-31"), ("Location", "Austin, TX")},
        },
        {
            "text": "Lab report for Case #B-4401: Delta-9 THC and CBD detected.",
            "expected": {("DomainTerm", "Lab report"), ("DomainTerm", "Delta-9"), ("DomainTerm", "THC"), ("DomainTerm", "CBD")},
        },
    ]

    tp = fp = fn = 0
    for sample in samples:
        found = {(c["label"], c["text"]) for c in _extract_candidate_entities(sample["text"]) }
        exp = sample["expected"]
        tp += len(found & exp)
        fp += len(found - exp)
        fn += len(exp - found)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0

    assert precision >= 0.60
    assert recall >= 0.85


def test_ocr_fallback_uses_engine_when_image_and_no_preview(monkeypatch, tmp_path):
    image_path = tmp_path / "scan.png"
    image_path.write_bytes(b"fakepng")

    pil_mod = types.ModuleType("PIL")

    class _Image:
        @staticmethod
        def open(path):
            return path

    pil_mod.Image = _Image

    tesseract_mod = types.ModuleType("pytesseract")
    tesseract_mod.image_to_string = lambda _img: "Scanned evidence text"

    monkeypatch.setitem(sys.modules, "PIL", pil_mod)
    monkeypatch.setitem(sys.modules, "pytesseract", tesseract_mod)

    out = FileIndexService._ocr_fallback(image_path, ".png", "image/png", parser_meta={})

    assert out["ocr"]["attempted"] is True
    assert out["ocr"]["used"] is True
    assert out["ocr"]["chars"] > 0
    assert out["preview"].startswith("Scanned evidence")


def test_ocr_fallback_skips_non_images():
    out = FileIndexService._ocr_fallback(path=None, ext=".txt", mime_type="text/plain", parser_meta={})
    assert out["ocr"]["attempted"] is False
    assert out["ocr"]["reason"] == "not_image"
