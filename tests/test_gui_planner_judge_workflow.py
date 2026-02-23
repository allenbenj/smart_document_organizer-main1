from __future__ import annotations

import ast
from pathlib import Path


SERVICE_PATH = Path("services/planner_judge_service.py")


def test_gui_workflow_contract_has_planner_and_judge_entrypoints() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

    assert "create_plan" in names
    assert "judge_plan" in names
    assert "activate_ruleset" in names


def test_gui_workflow_contract_mentions_remediation_on_failures() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "remediation" in src
    assert "missing required key" in src
