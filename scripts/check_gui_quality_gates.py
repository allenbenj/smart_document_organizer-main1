from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = ROOT / "gui"

# Ambiguous labels that caused user-facing confusion.
FORBIDDEN_BUTTON_LABELS = {
    "Save All Visible",
    "Save Unified All Visible",
    "Verify All Visible",
    "Apply to All Visible",
    "Multi-Edit",
    "Advanced Search",
    "Predefined Filters",
    "Clear Results",
    "Review Proposals",
    "Bulk Approve",
    "Bulk Reject",
}


def iter_py_files(base: Path) -> list[Path]:
    return [p for p in base.rglob("*.py") if p.is_file()]


def check_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    # Gate 1: No silent exception swallowing.
    silent_patterns = [
        re.compile(r"^\s*except\s+Exception\s*:\s*pass\s*$"),
        re.compile(r"^\s*except\s*:\s*pass\s*$"),
    ]
    for idx, line in enumerate(lines, start=1):
        for pat in silent_patterns:
            if pat.match(line):
                errors.append(
                    f"{path.relative_to(ROOT)}:{idx}: silent exception swallow is forbidden"
                )

    # Gate 2: No ambiguous button labels.
    for idx, line in enumerate(lines, start=1):
        if "QPushButton(" not in line:
            continue
        for label in FORBIDDEN_BUTTON_LABELS:
            if f'"{label}"' in line:
                errors.append(
                    f"{path.relative_to(ROOT)}:{idx}: ambiguous button label '{label}'"
                )
    return errors


def main() -> int:
    if not GUI_ROOT.exists():
        print("gui/ directory not found")
        return 2

    all_errors: list[str] = []
    for py_file in iter_py_files(GUI_ROOT):
        all_errors.extend(check_file(py_file))

    if all_errors:
        print("GUI quality gate failed:")
        for err in all_errors:
            print(f" - {err}")
        return 1

    print("GUI quality gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
