from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from Start import INTEGRITY_LAYER_TARGETS, _run_integrity_check
from scripts.quality.forbidden_runtime_scan import scan_paths


class IntegrityReport(BaseModel):
    schema_version: str
    status: str
    layer: str
    checked_paths: list[str]
    files_scanned: int
    required_marker_hits: int
    fallback_count: int
    placeholder_count: int
    generated_at: str


def test_run_integrity_check_writes_report(tmp_path: Path) -> None:
    output = tmp_path / "integrity.json"
    rc = _run_integrity_check(layer="h1", output=str(output))

    assert rc in {0, 1}
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    IntegrityReport.model_validate(data)
    assert data["status"] in {"pass", "fail"}
    assert data["layer"] == "h1"
    assert "files_scanned" in data
    assert "fallback_count" in data


def test_forbidden_runtime_scan_reports_zero_violations(tmp_path: Path) -> None:
    services_dir = tmp_path / "services"
    services_dir.mkdir(parents=True, exist_ok=True)
    (services_dir / "ok_impl.py").write_text(
        "def run():\n"
        "    return {'success': True, 'message': 'all good'}\n",
        encoding="utf-8",
    )
    report = scan_paths(paths=["services"], root=tmp_path)
    assert report["status"] == "pass"
    assert report["violations"] == 0


def test_forbidden_runtime_scan_detects_violation(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "bad_runtime.py").write_text(
        "from unittest.mock import MagicMock\nx = MagicMock()\n",
        encoding="utf-8",
    )

    report = scan_paths(paths=["agents"], root=tmp_path)
    assert report["status"] == "fail"
    assert report["violations"] >= 1


def test_forbidden_runtime_scan_detects_structural_placeholder_return(
    tmp_path: Path,
) -> None:
    services_dir = tmp_path / "services"
    services_dir.mkdir(parents=True, exist_ok=True)
    (services_dir / "fake_logic.py").write_text(
        "def run():\n"
        "    return {'success': True, 'message': 'TODO: implement real logic'}\n",
        encoding="utf-8",
    )
    report = scan_paths(paths=["services"], root=tmp_path)
    assert report["status"] == "fail"
    assert any(x.get("type") == "forbidden_return_literal" for x in report["details"])


def test_forbidden_runtime_scan_ignores_abstract_not_implemented(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "abstract_ok.py").write_text(
        "from abc import ABC, abstractmethod\n\n"
        "class BaseWorker(ABC):\n"
        "    @abstractmethod\n"
        "    def run(self):\n"
        "        raise NotImplementedError\n",
        encoding="utf-8",
    )
    report = scan_paths(paths=["agents"], root=tmp_path)
    assert report["status"] == "pass"
    assert report["violations"] == 0


def test_forbidden_runtime_scan_detects_swallowed_exception_pass(
    tmp_path: Path,
) -> None:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "silent_fail.py").write_text(
        "def run():\n"
        "    try:\n"
        "        return 1\n"
        "    except Exception:\n"
        "        pass\n",
        encoding="utf-8",
    )
    report = scan_paths(paths=["agents"], root=tmp_path)
    assert report["status"] == "fail"
    assert any(x.get("type") == "swallowed_exception" for x in report["details"])


def test_integrity_check_all_layers_do_not_crash(tmp_path: Path) -> None:
    for layer in INTEGRITY_LAYER_TARGETS:
        output = tmp_path / f"{layer}.json"
        rc = _run_integrity_check(layer=layer, output=str(output))
        assert rc in {0, 1}
        assert output.exists()
        data = json.loads(output.read_text(encoding="utf-8"))
        IntegrityReport.model_validate(data)
        assert data["layer"] == layer
