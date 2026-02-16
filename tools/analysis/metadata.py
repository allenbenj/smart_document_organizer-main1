"""
Metadata Extractor Module

This module analyzes Python files to extract code structure information,
quality metrics, and performance measurements.
"""

import ast
import os
import re
import time
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict, Counter
import logging
import tokenize
import io

logger = logging.getLogger(__name__)


class CodeStructureAnalyzer(ast.NodeVisitor):
    """AST-based code structure analysis."""
    
    def __init__(self):
        self.functions: List[Dict[str, Any]] = []
        self.classes: List[Dict[str, Any]] = []
        self.imports: List[Dict[str, Any]] = []
        self.decorators: List[Dict[str, Any]] = []
        self.docstrings: List[Dict[str, Any]] = []
        self.complexity: Dict[str, int] = {}
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Analyze function definitions."""
        func_info = {
            'name': node.name,
            'lineno': node.lineno,
            'col_offset': node.col_offset,
            'args_count': len(node.args.args),
            'has_docstring': ast.get_docstring(node) is not None,
            'decorator_list': [ast.unparse(dec) for dec in node.decorator_list],
            'is_async': node.is_async
        }
        
        # Calculate cyclomatic complexity
        func_info['complexity'] = self._calculate_cyclomatic_complexity(node)
        
        self.functions.append(func_info)
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Analyze class definitions."""
        class_info = {
            'name': node.name,
            'lineno': node.lineno,
            'col_offset': node.col_offset,
            'methods_count': len([n for n in node.body if isinstance(n, ast.FunctionDef)]),
            'has_docstring': ast.get_docstring(node) is not None,
            'bases': [ast.unparse(base) for base in node.bases],
            'decorator_list': [ast.unparse(dec) for dec in node.decorator_list]
        }
        
        self.classes.append(class_info)
        self.generic_visit(node)
    
    def visit_Import(self, node: ast.Import):
        """Analyze import statements."""
        for alias in node.names:
            self.imports.append({
                'type': 'import',
                'module': alias.name,
                'alias': alias.asname,
                'lineno': node.lineno,
                'col_offset': node.col_offset
            })
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Analyze from ... import statements."""
        for alias in node.names:
            self.imports.append({
                'type': 'from_import',
                'module': node.module,
                'name': alias.name,
                'alias': alias.asname,
                'lineno': node.lineno,
                'col_offset': node.col_offset
            })
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Analyze function calls for complexity."""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name not in self.complexity:
                self.complexity[func_name] = 0
            self.complexity[func_name] += 1
        self.generic_visit(node)
    
    def _calculate_cyclomatic_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity using a simple metric."""
        complexity = 1  # Start with 1 for the base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With,
                                ast.And, ast.Or, ast.ExceptHandler)):
                complexity += 1
        
        return complexity
    
    def get_structure(self) -> Dict[str, Any]:
        """Return the collected structure information."""
        return {
            'functions': self.functions,
            'classes': self.classes,
            'imports': self.imports,
            'complexity': self.complexity
        }


class QualityMetricsAnalyzer:
    """Analyze code quality metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {}
        self.documentation_coverage: Dict[str, float] = {}
        self.code_smells: List[str] = []
    
    def analyze_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Analyze quality metrics for a file."""
        self.metrics = {
            'file_path': file_path,
            'lines_of_code': 0,
            'lines_of_comments': 0,
            'docstring_coverage': 0.0,
            'function_count': 0,
            'class_count': 0,
            'average_cyclomatic_complexity': 0,
            'code_smells': []
        }
        
        # Analyze content
        self._analyze_content(content)
        
        return self.metrics
    
    def _analyze_content(self, content: str):
        """Analyze content for quality metrics."""
        lines = content.split('\n')
        in_multiline_comment = False
        comment_lines = 0
        code_lines = 0
        docstring_lines = 0
        
        # Tokenize to distinguish comments from code
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(content).readline))
            
            for token in tokens:
                if token.type == tokenize.COMMENT:
                    comment_lines += 1
                elif token.type == tokenize.STRING:
                    # Check if it's a docstring
                    if self._is_docstring(token, tokens):
                        docstring_lines += 1
                elif token.type == tokenize.NEWLINE or token.type == tokenize.NL:
                    continue
                elif token.string and not token.string.isspace():
                    code_lines += 1
        except Exception as e:
            logger.warning(f"Error tokenizing file: {e}")
            # Fallback to simple line counting
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('#'):
                    comment_lines += 1
                elif stripped:
                    code_lines += 1
        
        # Calculate metrics
        total_lines = code_lines + comment_lines + docstring_lines
        if total_lines > 0:
            docstring_coverage = docstring_lines / (code_lines + 1)  # Avoid division by zero
        else:
            docstring_coverage = 0.0
        
        self.metrics.update({
            'lines_of_code': code_lines,
            'lines_of_comments': comment_lines,
            'docstring_coverage': docstring_coverage,
            'comment_ratio': comment_lines / (total_lines + 1)
        })
        
        # Detect code smells
        self._detect_code_smells(content)
    
    def _is_docstring(self, token: tokenize.TokenInfo, tokens: List[tokenize.TokenInfo]) -> bool:
        """Check if a string token is a docstring."""
        if token.type != tokenize.STRING:
            return False
        
        # Check if it's the first statement in a function or class
        try:
            next_token = tokens[tokens.index(token) + 1]
            return next_token.type in (tokenize.NEWLINE, tokenize.NL, tokenize.INDENT)
        except (IndexError, ValueError):
            return False
    
    def _detect_code_smells(self, content: str):
        """Detect common code smells."""
        smells = []
        
        # Check for long functions
        functions = re.findall(r'def\s+\w+\s*\([^)]*\)\s*:', content)
        for func in functions:
            func_body = content.split(func, 1)[1].split('\n\n', 1)[0]
            if func_body.count('\n') > 20:  # More than 20 lines
                smells.append('long_function')
        
        # Check for complex functions
        complexity = self._calculate_semantic_complexity(content)
        if complexity > 5:
            smells.append('high_complexity')
        
        # Check for magic numbers
        numbers = re.findall(r'\b\d+\b(?=\s*[^\w\.])', content)
        if len(numbers) > 5:
            smells.append('magic_numbers')
        
        self.metrics['code_smells'] = smells
        self.metrics['complexity_score'] = complexity
    
    def _calculate_semantic_complexity(self, content: str) -> int:
        """Calculate semantic complexity based on code patterns."""
        complexity = 0
        
        # Count control structures
        complexity += content.count('if ')
        complexity += content.count('for ')
        complexity += content.count('while ')
        complexity += content.count('try:')
        complexity += content.count('except')
        complexity += content.count('with ')
        
        # Count nested structures
        nesting_level = self._calculate_nesting_level(content)
        complexity += nesting_level * 2
        
        return min(complexity, 10)  # Cap complexity at 10
    
    def _calculate_nesting_level(self, content: str) -> int:
        """Calculate maximum nesting level."""
        max_nesting = 0
        current_nesting = 0
        
        for line in content.split('\n'):
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            
            if stripped.startswith(('def ', 'class ', 'if ', 'for ', 'while ', 'try:')):
                current_nesting = indent // 4
                max_nesting = max(max_nesting, current_nesting)
        
        return max_nesting


class PerformanceMetricsAnalyzer:
    """Analyze performance-related metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {}
    
    def analyze_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Analyze performance metrics for a file."""
        start_time = time.time()
        
        self.metrics = {
            'file_path': file_path,
            'analysis_time_ms': 0,
            'line_count': len(content.split('\n')),
            'file_size_bytes': len(content.encode('utf-8')),
            'potential_bottlenecks': [],
            'io_operations': 0,
            'database_calls': 0
        }
        
        # Analyze for potential bottlenecks
        self._analyze_bottlenecks(content)
        
        # Measure analysis time
        analysis_time = time.time() - start_time
        self.metrics['analysis_time_ms'] = analysis_time * 1000
        
        return self.metrics
    
    def _analyze_bottlenecks(self, content: str):
        """Analyze content for potential performance bottlenecks."""
        bottlenecks = []
        
        # Check for inefficient string concatenation
        if re.search(r'\+\s*[\"\']', content):
            bottlenecks.append('inefficient_string_concat')
        
        # Check for list comprehensions in loops
        if re.search(r'for\s+\w+\s+in\s+.+:\s*.+\[.+\]\s+for', content, re.DOTALL):
            bottlenecks.append('nested_comprehensions')
        
        # Check for file I/O operations
        io_operations = len(re.findall(r'(open|read|write|close)\s*\(', content))
        self.metrics['io_operations'] = io_operations
        
        # Check for database operations
        db_calls = len(re.findall(r'(sqlite|psycopg2|mysql|mongo)\.(connect|query|execute)', content, re.IGNORECASE))
        self.metrics['database_calls'] = db_calls
        
        self.metrics['potential_bottlenecks'] = bottlenecks


class MetadataExtractor:
    """Main metadata extraction class."""
    
    def __init__(self):
        self.structure_analyzer = CodeStructureAnalyzer()
        self.quality_analyzer = QualityMetricsAnalyzer()
        self.performance_analyzer = PerformanceMetricsAnalyzer()
        self.file_metadata: Dict[str, Dict[str, Any]] = {}
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract all metadata for a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return {}
        
        # Parse AST
        try:
            tree = ast.parse(content, filename=file_path)
            self.structure_analyzer.visit(tree)
        except SyntaxError as e:
            logger.error(f"Syntax error in file {file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error parsing AST for file {file_path}: {e}")
            return {}
        
        # Extract structure
        structure = self.structure_analyzer.get_structure()
        
        # Analyze quality metrics
        quality_metrics = self.quality_analyzer.analyze_file(file_path, content)
        
        # Analyze performance metrics
        performance_metrics = self.performance_analyzer.analyze_file(file_path, content)
        
        # Combine all metadata
        metadata = {
            'file_path': file_path,
            'structure': structure,
            'quality': quality_metrics,
            'performance': performance_metrics,
            'timestamp': time.time()
        }
        
        self.file_metadata[file_path] = metadata
        return metadata
    
    def extract_metadata_for_files(self, file_paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """Extract metadata for multiple files."""
        results = {}
        
        for file_path in file_paths:
            results[file_path] = self.extract_metadata(file_path)
        
        return results
    
    def get_summary_statistics(self) -> Dict[str, Any]:
        """Get summary statistics across all analyzed files."""
        if not self.file_metadata:
            return {}
        
        summary = {
            'total_files': len(self.file_metadata),
            'total_functions': 0,
            'total_classes': 0,
            'average_cyclomatic_complexity': 0,
            'average_docstring_coverage': 0,
            'average_code_quality': 0,
            'potential_bottlenecks': Counter(),
            'code_smells': Counter()
        }
        
        complexity_sum = 0
        docstring_coverage_sum = 0
        quality_sum = 0
        
        for metadata in self.file_metadata.values():
            summary['total_functions'] += len(metadata['structure']['functions'])
            summary['total_classes'] += len(metadata['structure']['classes'])
            
            # Calculate average complexity
            for func in metadata['structure']['functions']:
                complexity_sum += func['complexity']
            
            docstring_coverage_sum += metadata['quality']['docstring_coverage']
            quality_sum += self._calculate_quality_score(metadata['quality'])
            
            # Count bottlenecks and smells
            for bottleneck in metadata['performance']['potential_bottlenecks']:
                summary['potential_bottlenecks'][bottleneck] += 1
            
            for smell in metadata['quality']['code_smells']:
                summary['code_smells'][smell] += 1
        
        if summary['total_functions'] > 0:
            summary['average_cyclomatic_complexity'] = complexity_sum / summary['total_functions']
        
        if summary['total_files'] > 0:
            summary['average_docstring_coverage'] = docstring_coverage_sum / summary['total_files']
            summary['average_code_quality'] = quality_sum / summary['total_files']
        
        return summary
    
    def _calculate_quality_score(self, quality_metrics: Dict[str, Any]) -> float:
        """Calculate a composite quality score."""
        score = 0.0
        
        # Docstring coverage
        score += quality_metrics.get('docstring_coverage', 0) * 0.3
        
        # Comment ratio
        score += quality_metrics.get('comment_ratio', 0) * 0.2
        
        # Complexity (inverted - lower is better)
        complexity = quality_metrics.get('complexity_score', 0)
        score += (1 - min(complexity / 10, 1)) * 0.3
        
        # Code smells penalty
        smell_penalty = len(quality_metrics.get('code_smells', []))
        score -= smell_penalty * 0.1
        
        return max(score, 0.0)


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


def extract_project_metadata(directory: str, exclude_patterns: List[str] = None) -> Dict[str, Any]:
    """Extract metadata for all Python files in a project."""
    extractor = MetadataExtractor()
    python_files = get_python_files(directory, exclude_patterns)
    
    metadata = extractor.extract_metadata_for_files(python_files)
    summary = extractor.get_summary_statistics()
    
    return {
        'metadata': metadata,
        'summary': summary,
        'timestamp': time.time()
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        directory = sys.argv[1]
        results = extract_project_metadata(directory)
        
        print(f"\n=== Project Metadata Analysis ===")
        print(f"Total files analyzed: {results['summary'].get('total_files', 0)}")
        print(f"Total functions: {results['summary'].get('total_functions', 0)}")
        print(f"Total classes: {results['summary'].get('total_classes', 0)}")
        print(f"Average cyclomatic complexity: {results['summary'].get('average_cyclomatic_complexity', 0):.2f}")
        print(f"Average docstring coverage: {results['summary'].get('average_docstring_coverage', 0):.2%}")
        print(f"Average code quality score: {results['summary'].get('average_code_quality', 0):.2f}")
        
        if results['summary'].get('code_smells'):
            print(f"\nCode smells detected:")
            for smell, count in results['summary']['code_smells'].items():
                print(f"  {smell}: {count} occurrences")
        
        if results['summary'].get('potential_bottlenecks'):
            print(f"\nPotential performance bottlenecks:")
            for bottleneck, count in results['summary']['potential_bottlenecks'].items():
                print(f"  {bottleneck}: {count} occurrences")
    else:
        print("Usage: python metadata.py <directory>")