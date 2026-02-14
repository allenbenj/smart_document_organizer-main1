from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_gui_fallback_tabs_keep_import_guards():
    guarded_tabs = [
        "gui/tabs/entity_extraction_tab.py",
        "gui/tabs/legal_reasoning_tab.py",
    ]

    for rel in guarded_tabs:
        content = _read(rel)
        assert "try:" in content
        assert "except ImportError" in content
        assert "Fallback for systems without PySide6" in content


def test_web_v2_docs_mark_pyside_as_legacy_fallback():
    architecture = _read("documents/reports/ARCHITECTURE_SPEC_V2_MEMORY_FIRST.md")
    launch = _read("documents/guides/WEB_GUI_V2_LAUNCH.md")

    assert "legacy / maintenance mode" in architecture
    assert "legacy fallback" in launch
