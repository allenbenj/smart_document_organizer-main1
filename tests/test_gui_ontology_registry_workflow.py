from __future__ import annotations

import ast
from pathlib import Path


GUI_TAB_PATH = Path("gui/tabs/knowledge_graph_tab.py")


def _load_tree() -> ast.Module:
    src = GUI_TAB_PATH.read_text(encoding="utf-8")
    return ast.parse(src)


def test_gui_ontology_tab_fetches_registry_entities_via_api_client() -> None:
    tree = _load_tree()
    source = GUI_TAB_PATH.read_text(encoding="utf-8")

    assert "def _load_ontology_types" in source
    assert "api_client.get_ontology_entities()" in source

    method_names = {
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
    }
    assert "_load_ontology_types" in method_names


def test_gui_ontology_tab_populates_type_selector_from_labels() -> None:
    source = GUI_TAB_PATH.read_text(encoding="utf-8")

    assert "self.kg_type_combo.clear()" in source
    assert "self.kg_type_combo.addItems(labels)" in source
