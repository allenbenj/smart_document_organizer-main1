import importlib
import pkgutil
from pathlib import Path

import agents.extractors as extractors


def test_extractors_import_cleanly():
    # Import each extractor module to ensure no import-time failures
    for finder, name, ispkg in pkgutil.iter_modules(extractors.__path__):
        importlib.import_module(f"agents.extractors.{name}")


def test_quality_classifier_uses_xtext_not_x_text():
    content = Path("agents/extractors/quality_classifier.py").read_text(encoding="utf-8")
    assert "X_text" not in content
    assert "Xtext" in content


def test_hybrid_extractor_has_required_dataclass_imports():
    content = Path("agents/extractors/hybrid_extractor.py").read_text(encoding="utf-8")
    import_line = next(
        (line for line in content.splitlines() if "from dataclasses import" in line),
        "",
    )
    assert import_line
    assert "asdict" in import_line
    assert "dataclass" in import_line
    assert "field" in import_line
