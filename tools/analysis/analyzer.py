"""
Dependency Analyzer Module

This module analyzes Python files to extract import dependencies, usage patterns,
and cross-file relationships using Abstract Syntax Tree (AST) parsing.
"""

import ast
import os
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ImportAnalyzer(ast.NodeVisitor):
    """AST-based import analysis visitor."""
    
    def __init__(self):
        self.imports: Dict[str, Set[str]] = defaultdict(set)
        self.aliases: Dict[str, str] = {}
        self.import_statements: List[ast.Import] = []
        self.import_from_statements: List[ast.ImportFrom] = []
    
    def visit_Import(self, node: ast.Import):
        """Handle regular import statements."""
        for alias in node.names:
            module_name = alias.name
            imported_name = alias.asname or alias.name
            self.imports[module_name].add(imported_name)
            self.aliases[imported_name] = module_name
            self.import_statements.append(node)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Handle from ... import statements."""
        if node.module:
            module_name = node.module
            for alias in node.names:
                imported_name = alias.asname or alias.name
                self.imports[module_name].add(imported_name)
                self.aliases[imported_name] = module_name
                self.import_from_statements.append(node)
        self.generic_visit(node)
    
    def get_imports(self) -> Dict[str, Set[str]]:
        """Return the collected imports."""
        return dict(self.imports)
    
    def get_aliases(self) -> Dict[str, str]:
        """Return the collected aliases."""
        return dict(self.aliases)


class UsageAnalyzer(ast.NodeVisitor):
    """AST-based usage pattern analysis visitor."""
    
    def __init__(self, aliases: Dict[str, str]):
        self.aliases = aliases
        self.usages: Dict[str, Set[str]] = defaultdict(set)
        self.function_calls: Dict[str, Set[str]] = defaultdict(set)
        self.class_instantiations: Dict[str, Set[str]] = defaultdict(set)
    
    def visit_Name(self, node: ast.Name):
        """Track variable usage."""
        if node.id in self.aliases:
            module = self.aliases[node.id]
            self.usages[module].add(node.id)
        self.generic_visit(node)
    
    def visit_Attribute(self, node: ast.Attribute):
        """Track attribute access patterns."""
        if isinstance(node.value, ast.Name) and node.value.id in self.aliases:
            module = self.aliases[node.value.id]
            self.usages[module].add(f"{node.value.id}.{node.attr}")
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Track function calls."""
        if isinstance(node.func, ast.Name) and node.func.id in self.aliases:
            module = self.aliases[node.func.id]
            self.function_calls[module].add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id in self.aliases:
                module = self.aliases[node.func.value.id]
                self.function_calls[module].add(f"{node.func.value.id}.{node.func.attr}")
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Track class definitions and instantiations."""
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in self.aliases:
                module = self.aliases[base.id]
                self.class_instantiations[module].add(base.id)
        self.generic_visit(node)
    
    def get_usages(self) -> Dict[str, Set[str]]:
        """Return the collected usages."""
        return dict(self.usages)
    
    def get_function_calls(self) -> Dict[str, Set[str]]:
        """Return the collected function calls."""
        return dict(self.function_calls)
    
    def get_class_instantiations(self) -> Dict[str, Set[str]]:
        """Return the collected class instantiations."""
        return dict(self.class_instantiations)


class DependencyAnalyzer:
    """Main dependency analysis class."""
    
    def __init__(self):
        self.import_analyzer = ImportAnalyzer()
        self.usage_analyzer = None
        self.file_dependencies: Dict[str, Set[str]] = {}
        self.cross_file_dependencies: Dict[str, Set[str]] = {}
    
    def analyze_file(self, file_path: str) -> Dict:
        """Analyze a single Python file for dependencies."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return {}
        
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as e:
            logger.error(f"Syntax error in file {file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error parsing AST for file {file_path}: {e}")
            return {}
        
        # Analyze imports
        self.import_analyzer.visit(tree)
        imports = self.import_analyzer.get_imports()
        aliases = self.import_analyzer.get_aliases()
        
        # Analyze usage patterns
        self.usage_analyzer = UsageAnalyzer(aliases)
        self.usage_analyzer.visit(tree)
        usages = self.usage_analyzer.get_usages()
        function_calls = self.usage_analyzer.get_function_calls()
        class_instantiations = self.usage_analyzer.get_class_instantiations()
        
        return {
            'file_path': file_path,
            'imports': imports,
            'usages': usages,
            'function_calls': function_calls,
            'class_instantiations': class_instantiations,
            'aliases': aliases
        }
    
    def analyze_files(self, file_paths: List[str]) -> Dict[str, Dict]:
        """Analyze multiple files and resolve cross-file dependencies."""
        results = {}
        
        # First pass: analyze all files
        for file_path in file_paths:
            results[file_path] = self.analyze_file(file_path)
        
        # Second pass: resolve cross-file dependencies
        self._resolve_cross_file_dependencies(results)
        
        return results
    
    def _resolve_cross_file_dependencies(self, results: Dict[str, Dict]):
        """Resolve dependencies between analyzed files."""
        # Build module map
        module_map: Dict[str, str] = {}
        for file_path, analysis in results.items():
            for module, imports in analysis.get('imports', {}).items():
                if module not in module_map:
                    module_map[module] = file_path
        
        # Resolve cross-file dependencies
        for file_path, analysis in results.items():
            dependencies = set()
            
            # Check imports
            for module in analysis.get('imports', {}).keys():
                if module in module_map and module_map[module] != file_path:
                    dependencies.add(module_map[module])
            
            # Check usage patterns
            for module in analysis.get('usages', {}).keys():
                if module in module_map and module_map[module] != file_path:
                    dependencies.add(module_map[module])
            
            self.cross_file_dependencies[file_path] = dependencies
    
    def get_file_dependencies(self) -> Dict[str, Set[str]]:
        """Get file-level dependencies."""
        return self.file_dependencies
    
    def get_cross_file_dependencies(self) -> Dict[str, Set[str]]:
        """Get cross-file dependencies."""
        return self.cross_file_dependencies
    
    def get_import_summary(self) -> Dict[str, int]:
        """Get summary of import usage across all files."""
        summary = defaultdict(int)
        
        for analysis in self.file_dependencies.values():
            for module in analysis:
                summary[module] += 1
        
        return dict(summary)


# Helper functions

def get_python_files(directory: str, exclude_patterns: List[str] = None) -> List[str]:
    """Get all Python files in a directory recursively."""
    python_files = []
    exclude_patterns = exclude_patterns or []
    
    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in exclude_patterns)]
        
        for file in files:
            if file.endswith('.py') and not any(pattern in file for pattern in exclude_patterns):
                python_files.append(os.path.join(root, file))
    
    return python_files


def analyze_project(directory: str, exclude_patterns: List[str] = None) -> Dict[str, Dict]:
    """Analyze all Python files in a project directory."""
    analyzer = DependencyAnalyzer()
    python_files = get_python_files(directory, exclude_patterns)
    return analyzer.analyze_files(python_files)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        directory = sys.argv[1]
        results = analyze_project(directory)
        
        for file_path, analysis in results.items():
            print(f"\n=== Analysis for {file_path} ===")
            print(f"Imports: {analysis.get('imports', {})}")
            print(f"Usages: {analysis.get('usages', {})}")
            print(f"Function Calls: {analysis.get('function_calls', {})}")
            print(f"Class Instantiations: {analysis.get('class_instantiations', {})}")
    else:
        print("Usage: python analyzer.py <directory>")