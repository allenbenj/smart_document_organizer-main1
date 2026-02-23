from __future__ import annotations

import ast
from pathlib import Path


SERVICE_PATH = Path("services/heuristic_governance_service.py")


def test_gui_governance_contract_exposes_lifecycle_actions() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

    assert "register_heuristic" in names
    assert "update_evidence" in names
    assert "activate_heuristic" in names
    assert "deprecate_heuristic" in names


def test_gui_governance_contract_exposes_dissent_tracking() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "detect_collisions" in src
    assert "dissent_from" in src
