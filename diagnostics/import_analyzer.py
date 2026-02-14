"""
Import Analyzer Script
======================

This module analyzes Python import statements in a project directory,
detecting module dependencies, cycles, and potential issues.

Usage:
    python -m diagnostics.import_analyzer <project_directory>

Or run directly:
    python diagnostics/import_analyzer.py
"""

import ast
import json  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
from collections import defaultdict  # noqa: E402
from pathlib import Path  # noqa: E402


def analyze_imports(project_root):  # noqa: C901
    """
    Analyze import statements in all Python files under the project root.

    Returns a JSON string containing:
    - modules: List of module information with imports and imported_by
    - edges: List of import edges (from, to, style)
    - cycles: List of detected import cycles
    - imports_from_backup: List of imports from backup directories
    - entrypoints: Known entrypoint files
    - environment: Environment notes
    """
    modules = {}
    edges = []
    errors = []  # noqa: F841
    imports_from_backup = []

    project_root_abs = os.path.abspath(project_root)
    # Add project root to sys.path to help resolve top-level modules
    # This is temporary for the script's execution
    if project_root_abs not in sys.path:
        sys.path.insert(0, project_root_abs)

    # Create a mapping from module name to file path for faster lookups
    module_to_path_map = {}
    for root, _, files in os.walk(project_root):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                repo_relative_path = os.path.relpath(file_path, project_root).replace(
                    "\\", "/"
                )

                module_name = os.path.splitext(repo_relative_path.replace("/", "."))[0]
                if module_name.endswith(".__init__"):
                    module_name = module_name[:-9]

                module_to_path_map[module_name] = repo_relative_path

    for root, _, files in os.walk(project_root):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                repo_relative_path = os.path.relpath(file_path, project_root).replace(
                    "\\", "/"
                )

                if repo_relative_path.startswith(
                    ("_backup/", ".kilocode/", "__pycache__/")
                ):
                    continue

                current_module_name = os.path.splitext(
                    repo_relative_path.replace("/", ".")
                )[0]
                if current_module_name.endswith(".__init__"):
                    current_module_name = current_module_name[:-9]

                modules[repo_relative_path] = {
                    "path": repo_relative_path,
                    "imports": [],
                    "imported_by": [],
                    "errors": [],
                    "notes": "",
                }

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        tree = ast.parse(content, filename=file_path)
                except Exception as e:
                    modules[repo_relative_path]["errors"].append(
                        {"module": "", "message": f"Error parsing file: {e}"}
                    )
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            import_info = {
                                "module": alias.name,
                                "symbols": [
                                    alias.asname if alias.asname else alias.name
                                ],
                                "style": "absolute",
                            }
                            modules[repo_relative_path]["imports"].append(import_info)
                            edges.append([repo_relative_path, alias.name, "absolute"])
                            if alias.name.startswith("_backup"):
                                imports_from_backup.append(
                                    {"from": repo_relative_path, "to": alias.name}
                                )

                    elif isinstance(node, ast.ImportFrom):
                        level = node.level
                        style = "relative" if level > 0 else "absolute"

                        base_module = node.module if node.module else ""

                        resolved_module = ""
                        if style == "relative":
                            # Resolve relative path
                            source_dir_parts = (
                                os.path.dirname(current_module_name).split(".")
                                if "." in current_module_name
                                else []
                            )
                            if level > len(source_dir_parts) + 1:
                                resolved_module = (
                                    "Error: Relative import beyond top-level package"
                                )
                                modules[repo_relative_path]["errors"].append(
                                    {
                                        "module": f"{'.' * level}{base_module}",
                                        "message": resolved_module,
                                    }
                                )
                            else:
                                # from .. import foo -> level=2, source_dir_parts needs to be sliced
                                # from . import foo -> level=1
                                if len(source_dir_parts) > 0:
                                    base_path_parts = source_dir_parts[
                                        : len(source_dir_parts) - (level - 1)
                                    ]
                                    resolved_module_parts = base_path_parts + (
                                        [base_module] if base_module else []
                                    )
                                    resolved_module = ".".join(resolved_module_parts)
                                else:  # Relative import from top-level
                                    resolved_module = base_module

                        else:  # Absolute import
                            resolved_module = base_module

                        symbols = [alias.name for alias in node.names]
                        import_info = {
                            "module": resolved_module,
                            "symbols": symbols,
                            "style": style,
                        }
                        modules[repo_relative_path]["imports"].append(import_info)
                        edges.append([repo_relative_path, resolved_module, style])
                        if resolved_module.startswith("_backup"):
                            imports_from_backup.append(
                                {"from": repo_relative_path, "to": resolved_module}
                            )

                    elif isinstance(node, ast.Call):
                        func = node.func
                        func_name = ""
                        if isinstance(func, ast.Name):
                            func_name = func.id
                        elif isinstance(func, ast.Attribute):
                            func_name = func.attr

                        if func_name in ["__import__", "import_module"]:
                            if node.args and isinstance(node.args[0], ast.Constant):
                                arg_val = (
                                    node.args[0].s
                                    if isinstance(node.args[0], ast.Str)
                                    else node.args[0].value
                                )
                                modules[repo_relative_path][
                                    "notes"
                                ] += f"Dynamic import found: {func_name}('{arg_val}')\n"
                                edges.append([repo_relative_path, arg_val, "dynamic"])

    # Build imported_by list
    for from_path, to_module_str, _ in edges:
        if not to_module_str or "Error" in to_module_str:
            continue

        to_path = module_to_path_map.get(to_module_str)
        if not to_path:
            # Could be a standard library or third-party module
            continue

        if to_path in modules and from_path not in modules[to_path]["imported_by"]:
            modules[to_path]["imported_by"].append(from_path)

    # Cycle detection
    adj = defaultdict(list)
    path_to_module = {v: k for k, v in module_to_path_map.items()}  # noqa: F841

    for from_path, to_module_str, style in edges:
        if not to_module_str or "Error" in to_module_str:
            continue

        to_path = module_to_path_map.get(to_module_str)
        if to_path:
            adj[from_path].append(to_path)

    cycles = []
    visiting = set()
    visited = set()

    def find_cycles_util(node, path):
        visiting.add(node)
        path.append(node)

        for neighbor in adj.get(node, []):
            if neighbor in visiting:
                try:
                    cycle_start_index = path.index(neighbor)
                    cycle = path[cycle_start_index:]
                    # Normalize by sorting to avoid duplicate cycles with different start points
                    sorted_cycle = tuple(sorted(cycle))
                    if sorted_cycle not in seen_cycles:
                        cycles.append(cycle)
                        seen_cycles.add(sorted_cycle)
                except ValueError:
                    pass  # Should not happen
            elif neighbor not in visited:
                find_cycles_util(neighbor, path)

        path.pop()
        visiting.remove(node)
        visited.add(node)

    all_nodes = list(adj.keys())
    seen_cycles = set()
    for node in all_nodes:
        if node not in visited:
            find_cycles_util(node, [])

    result = {
        "modules": list(modules.values()),
        "edges": edges,
        "cycles": cycles,
        "imports_from_backup": imports_from_backup,
        "entrypoints": ["start_app.py", "main.py"],
        "environment": "NOTE: This analysis assumes a standard python environment. Any runtime sys.path modifications in the code are noted in the module's 'notes' field but may not be fully resolved here.",
    }

    if project_root_abs in sys.path:
        sys.path.remove(project_root_abs)

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    # Allow overriding project directory via command line argument
    if len(sys.argv) > 1:
        project_directory = sys.argv[1]
    else:
        # Default to parent directory of this script
        project_directory = str(Path(__file__).resolve().parent.parent)

    print(f"Analyzing project: {project_directory}")
    json_output = analyze_imports(project_directory)
    print(json_output)
