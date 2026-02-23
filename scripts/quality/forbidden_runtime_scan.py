from __future__ import annotations

import argparse
import ast
import json
from datetime import datetime, timezone
from pathlib import Path

FORBIDDEN_PATTERNS = [
    "import mock",
    "from mock import",
    "import unittest.mock",
    "from unittest.mock import",
]

FORBIDDEN_RETURN_TEXT_MARKERS = [
    "todo: implement",
    "fixme: real logic",
    "stub",
]


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_abstract_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if _base_name(base) in {"ABC", "ABCMeta"}:
            return True
    for kw in node.keywords:
        if kw.arg == "metaclass" and isinstance(kw.value, ast.Name):
            if kw.value.id == "ABCMeta":
                return True
    return False


def _is_abstract_method(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        if _base_name(dec) == "abstractmethod":
            return True
    return False


def _iter_string_literals(expr: ast.AST) -> list[str]:
    out: list[str] = []
    for child in ast.walk(expr):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            out.append(child.value)
    return out


class _ForbiddenAstVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self.class_stack: list[tuple[str, bool]] = []
        self.func_stack: list[tuple[str, bool]] = []
        self.violations: list[dict[str, object]] = []

    def _in_abstract_context(self) -> bool:
        class_abstract = any(is_abs for _, is_abs in self.class_stack)
        method_abstract = self.func_stack[-1][1] if self.func_stack else False
        return class_abstract and method_abstract

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_stack.append((node.name, _is_abstract_class(node)))
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.func_stack.append((node.name, _is_abstract_method(node)))
        self.generic_visit(node)
        self.func_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.func_stack.append((node.name, _is_abstract_method(node)))
        self.generic_visit(node)
        self.func_stack.pop()

    def visit_Raise(self, node: ast.Raise) -> None:
        exc = node.exc
        is_not_impl = False
        if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
            is_not_impl = True
        elif isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
            if exc.func.id == "NotImplementedError":
                is_not_impl = True

        if is_not_impl and not self._in_abstract_context():
            self.violations.append(
                {
                    "file": self.rel_path,
                    "line": node.lineno,
                    "type": "not_implemented_error",
                    "message": "NotImplementedError outside abstract method/class context",
                }
            )
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is None:
            return
        for value in _iter_string_literals(node.value):
            lowered = value.lower()
            for marker in FORBIDDEN_RETURN_TEXT_MARKERS:
                if marker in lowered:
                    self.violations.append(
                        {
                            "file": self.rel_path,
                            "line": node.lineno,
                            "type": "forbidden_return_literal",
                            "marker": marker,
                        }
                    )
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Detect swallowed exceptions (silent failure patterns)."""
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.violations.append(
                {
                    "file": self.rel_path,
                    "line": node.lineno,
                    "type": "swallowed_exception",
                    "message": "Exception handler contains only 'pass'",
                }
            )
        self.generic_visit(node)


def _scan_ast(content: str, rel_path: str) -> list[dict[str, object]]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    visitor = _ForbiddenAstVisitor(rel_path=rel_path)
    visitor.visit(tree)
    return visitor.violations


def scan_paths(paths: list[str], root: Path) -> dict:
    violations: list[dict[str, object]] = []
    files_scanned = 0

    for rel in paths:
        base = (root / rel).resolve()
        if not base.exists():
            continue
        for file_path in base.rglob("*.py"):
            files_scanned += 1
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lower = content.lower()
            rel_path = str(file_path.relative_to(root))
            hits = [p for p in FORBIDDEN_PATTERNS if p in lower]
            if hits:
                violations.append(
                    {
                        "file": rel_path,
                        "type": "forbidden_import",
                        "patterns": hits,
                    }
                )
            violations.extend(_scan_ast(content=content, rel_path=rel_path))

    return {
        "status": "pass" if not violations else "fail",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files_scanned": files_scanned,
        "violations": len(violations),
        "details": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan runtime code for forbidden mock imports.")
    parser.add_argument(
        "--paths",
        nargs="+",
        default=["agents", "services", "routes"],
        help="Paths to scan, relative to repo root.",
    )
    parser.add_argument("--output", required=False, default="", help="Optional output JSON path.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    report = scan_paths(paths=args.paths, root=repo_root)
    body = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body + "\n", encoding="utf-8")
        print(f"[forbidden-scan] wrote report: {out}")
    print(body)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
