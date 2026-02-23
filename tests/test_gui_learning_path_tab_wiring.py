from __future__ import annotations

import ast
from pathlib import Path


TAB_PATH = Path("gui/tabs/learning_path_tab.py")
MANAGER_PATH = Path("gui/professional_manager.py")
API_PATH = Path("gui/services/__init__.py")


def test_learning_path_tab_class_exists() -> None:
    src = TAB_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert "LearningPathTab" in names


def test_professional_manager_wires_learning_path_tab() -> None:
    src = MANAGER_PATH.read_text(encoding="utf-8")
    assert "LearningPathTab" in src
    assert "🎯 Learning Paths" in src


def test_api_client_exposes_learning_path_methods() -> None:
    src = API_PATH.read_text(encoding="utf-8")
    assert "def generate_learning_path(" in src
    assert "def get_learning_path(" in src
    assert "def update_learning_step(" in src
    assert "def get_learning_recommendations(" in src
