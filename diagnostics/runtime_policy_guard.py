from __future__ import annotations

from pathlib import Path
from typing import Dict, List


RULE_PATTERNS = (
    "mock",
    "fake",
    "fallback",
    "dummy",
    "heuristic",
)

SCAN_PATHS = (
    "Start.py",
    "agents",
    "core",
    "gui",
    "mem_db",
    "routes",
    "services",
)

SKIP_PARTS = (
    "__pycache__",
    "archive",
    "tests",
    "documents",
    ".git",
)


def _iter_python_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for rel in SCAN_PATHS:
        target = root / rel
        if not target.exists():
            continue
        if target.is_file() and target.suffix == ".py":
            files.append(target)
            continue
        for p in target.rglob("*.py"):
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            files.append(p)
    return files


def scan_runtime_policy(base_dir: str | Path | None = None) -> List[Dict[str, object]]:
    root = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
    violations: List[Dict[str, object]] = []
    for py_file in _iter_python_files(root):
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, start=1):
            lower = line.lower()
            for pat in RULE_PATTERNS:
                if pat in lower:
                    violations.append(
                        {
                            "file": str(py_file.relative_to(root)),
                            "line": idx,
                            "pattern": pat,
                            "snippet": line.strip()[:200],
                        }
                    )
                    break
    return violations
