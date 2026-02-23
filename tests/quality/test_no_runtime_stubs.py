from __future__ import annotations

import shutil
from pathlib import Path

from scripts.quality.forbidden_runtime_scan import scan_paths


AEDIS_SCAN_PATHS = ["services/contracts", "gui/services"]


def _build_scan_root(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    runtime_files = list((repo_root / "services" / "contracts").rglob("*.py"))

    aedis_gui_dir = repo_root / "gui" / "services" / "aedis"
    if aedis_gui_dir.exists():
        runtime_files.extend(aedis_gui_dir.rglob("*.py"))
    adapter_file = repo_root / "gui" / "services" / "aedis_contract_adapters.py"
    if adapter_file.exists():
        runtime_files.append(adapter_file)

    assert runtime_files, "Missing AEDIS runtime modules for gate scan"

    for src in runtime_files:
        rel_path = src.relative_to(repo_root)
        dst = tmp_path / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return tmp_path


def test_aedis_runtime_has_no_stubs_or_forbidden_patterns(tmp_path: Path) -> None:
    scan_root = _build_scan_root(tmp_path)
    report = scan_paths(paths=AEDIS_SCAN_PATHS, root=scan_root)

    assert report["status"] == "pass"
    assert report["violations"] == 0


def test_gate_negative_proof_detects_forbidden_import(tmp_path: Path) -> None:
    bad_file = tmp_path / "services" / "contracts" / "bad_import.py"
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    bad_file.write_text("import unittest.mock\n", encoding="utf-8")

    report = scan_paths(paths=AEDIS_SCAN_PATHS, root=tmp_path)

    assert report["status"] == "fail"
    assert any(item.get("type") == "forbidden_import" for item in report["details"])


def test_gate_negative_proof_detects_not_implemented_in_non_abstract_method(
    tmp_path: Path,
) -> None:
    bad_file = tmp_path / "services" / "contracts" / "bad_runtime.py"
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    bad_file.write_text(
        "class Worker:\n"
        "    def run(self):\n"
        "        raise NotImplementedError('runtime gap')\n",
        encoding="utf-8",
    )

    report = scan_paths(paths=AEDIS_SCAN_PATHS, root=tmp_path)

    assert report["status"] == "fail"
    assert any(item.get("type") == "not_implemented_error" for item in report["details"])
