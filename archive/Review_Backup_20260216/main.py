"""
Main Analysis Controller

This module orchestrates the entire file analysis process, including
project scanning, dependency analysis, metadata extraction, and database
operations. It provides a command-line interface for configuration and
progress reporting.
"""

import argparse
import logging
import os
import sys
import time
from typing import Dict, List, Optional, Any
from pathlib import Path

# Import modules
from scanner import ProjectScanner
from analyzer import DependencyAnalyzer
from metadata import MetadataExtractor
from database import DatabaseManager

logger = logging.getLogger(__name__)


class AnalysisController:
    """Main analysis controller class."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_scanner = ProjectScanner(
            exclude_patterns=config.get('exclude_patterns', []),
            file_patterns=config.get('file_patterns', ['*.py'])
        )
        self.dependency_analyzer = DependencyAnalyzer()
        self.metadata_extractor = MetadataExtractor()
        self.db_manager = DatabaseManager(config.get('db_path', 'analysis_results.db'))
        self.project_id = None
    
    def run_analysis(self, project_path: str) -> bool:
        """Run the complete analysis process."""
        try:
            # Step 1: Scan project
            logger.info(f"Scanning project: {project_path}")
            start_time = time.time()
            
            files = self.project_scanner.scan_project(project_path)
            scan_time = time.time() - start_time
            
            if not files:
                logger.warning("No files found to analyze")
                return False
            
            logger.info(f"Found {len(files)} files in {scan_time:.2f} seconds")
            
            # Step 2: Add project to database
            self.project_id = self._add_project_to_database(project_path)
            if self.project_id < 0:
                logger.error("Failed to add project to database")
                return False
            
            # Step 3: Add files to database
            file_ids = self._add_files_to_database(files)
            if not file_ids:
                logger.error("Failed to add files to database")
                return False
            
            # Step 4: Analyze dependencies
            logger.info("Analyzing dependencies...")
            start_time = time.time()
            
            analysis_results = self.dependency_analyzer.analyze_files(list(file_ids.keys()))
            dependency_time = time.time() - start_time
            
            logger.info(f"Dependency analysis completed in {dependency_time:.2f} seconds")
            
            # Step 5: Extract metadata
            logger.info("Extracting metadata...")
            start_time = time.time()
            
            metadata_results = self.metadata_extractor.extract_metadata_for_files(list(file_ids.keys()))
            metadata_time = time.time() - start_time
            
            logger.info(f"Metadata extraction completed in {metadata_time:.2f} seconds")
            
            # Step 6: Store results in database
            logger.info("Storing results in database...")
            start_time = time.time()
            
            self._store_analysis_results(file_ids, analysis_results, metadata_results)
            storage_time = time.time() - start_time
            
            logger.info(f"Database storage completed in {storage_time:.2f} seconds")
            
            # Step 7: Generate summary
            logger.info("Generating analysis summary...")
            summary = self._generate_analysis_summary(file_ids)
            
            # Step 8: Add summary to database
            self.db_manager.add_analysis_summary(self.project_id, summary)
            
            # Step 9: Report results
            self._report_results(summary, scan_time, dependency_time, metadata_time, storage_time)
            
            return True
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return False
    
    def _add_project_to_database(self, project_path: str) -> int:
        """Add project information to the database."""
        project_name = os.path.basename(os.path.abspath(project_path))
        description = f"Analysis of project at {project_path}"
        
        return self.db_manager.add_project(
            name=project_name,
            description=description,
            root_path=os.path.abspath(project_path)
        )
    
    def _add_files_to_database(self, files: List[str]) -> Dict[str, int]:
        """Add files to the database and return a mapping of file paths to IDs."""
        file_ids = {}
        
        for file_path in files:
            file_info = {
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'directory_path': os.path.dirname(file_path),
                'file_extension': os.path.splitext(file_path)[1],
                'file_size': os.path.getsize(file_path),
                'modified_time': datetime.fromtimestamp(os.path.getmtime(file_path)),
                'created_time': datetime.fromtimestamp(os.path.getctime(file_path))
            }
            
            file_id = self.db_manager.add_file(self.project_id, file_path, file_info)
            if file_id > 0:
                file_ids[file_path] = file_id
            else:
                logger.warning(f"Failed to add file to database: {file_path}")
        
        return file_ids
    
    def _store_analysis_results(self, file_ids: Dict[str, int], 
                              analysis_results: Dict[str, Dict],
                              metadata_results: Dict[str, Dict]):
        """Store analysis results in the database."""
        
        for file_path, file_id in file_ids.items():
            analysis = analysis_results.get(file_path, {})
            metadata = metadata_results.get(file_path, {})
            
            try:
                # Store imports
                imports = []
                for module, imported_names in analysis.get('imports', {}).items():
                    for name in imported_names:
                        imp_type = 'from_import' if '.' in name else 'import'
                        imports.append({
                            'type': imp_type,
                            'module': module,
                            'name': name,
                            'alias': None,
                            'lineno': None
                        })
                self.db_manager.add_imports(file_id, imports)
                
                # Store functions
                functions = []
                for func in metadata.get('structure', {}).get('functions', []):
                    functions.append({
                        'name': func.get('name'),
                        'lineno': func.get('lineno'),
                        'col_offset': func.get('col_offset'),
                        'args_count': func.get('args_count'),
                        'is_async': func.get('is_async'),
                        'has_docstring': func.get('has_docstring'),
                        'complexity': func.get('complexity')
                    })
                self.db_manager.add_functions(file_id, functions)
                
                # Store classes
                classes = []
                for cls in metadata.get('structure', {}).get('classes', []):
                    classes.append({
                        'name': cls.get('name'),
                        'lineno': cls.get('lineno'),
                        'col_offset': cls.get('col_offset'),
                        'methods_count': cls.get('methods_count'),
                        'has_docstring': cls.get('has_docstring'),
                        'bases': cls.get('bases')
                    })
                self.db_manager.add_classes(file_id, classes)
                
                # Store quality metrics
                quality_metrics = metadata.get('quality', {})
                self.db_manager.add_quality_metrics(file_id, quality_metrics)
                
                # Store performance metrics
                performance_metrics = metadata.get('performance', {})
                self.db_manager.add_performance_metrics(file_id, performance_metrics)
                
                # Update file analysis status
                self.db_manager.update_file_analysis_status(
                    file_id, 'completed'
                )
                
            except Exception as e:
                logger.error(f"Error storing results for file {file_path}: {e}")
                self.db_manager.update_file_analysis_status(
                    file_id, 'failed', str(e)
                )
    
    def _generate_analysis_summary(self, file_ids: Dict[str, int]) -> Dict[str, Any]:
        """Generate analysis summary from metadata results."""
        
        total_files = len(file_ids)
        total_functions = 0
        total_classes = 0
        complexity_sum = 0
        docstring_coverage_sum = 0
        quality_sum = 0
        
        for file_path, file_id in file_ids.items():
            metadata = self.metadata_extractor.file_metadata.get(file_path, {})
            
            total_functions += len(metadata.get('structure', {}).get('functions', []))
            total_classes += len(metadata.get('structure', {}).get('classes', []))
            
            for func in metadata.get('structure', {}).get('functions', []):
                complexity_sum += func.get('complexity', 1)
            
            quality_metrics = metadata.get('quality', {})
            docstring_coverage_sum += quality_metrics.get('docstring_coverage', 0.0)
            quality_sum += self._calculate_quality_score(quality_metrics)
        
        summary = {
            'total_files': total_files,
            'total_functions': total_functions,
            'total_classes': total_classes,
        }
        
        if total_functions > 0:
            summary['average_cyclomatic_complexity'] = complexity_sum / total_functions
        
        if total_files > 0:
            summary['average_docstring_coverage'] = docstring_coverage_sum / total_files
            summary['average_code_quality'] = quality_sum / total_files
        
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
    
    def _report_results(self, summary: Dict[str, Any], 
                       scan_time: float, dependency_time: float,
                       metadata_time: float, storage_time: float):
        """Report analysis results."""
        
        print(f"\n=== Analysis Summary ===")
        print(f"Project: {self.db_manager.get_project_analysis_summary(self.project_id).get('name', 'Unknown')}")
        print(f"Total files analyzed: {summary.get('total_files', 0)}")
        print(f"Total functions: {summary.get('total_functions', 0)}")
        print(f"Total classes: {summary.get('total_classes', 0)}")
        print(f"Average cyclomatic complexity: {summary.get('average_cyclomatic_complexity', 0):.2f}")
        print(f"Average docstring coverage: {summary.get('average_docstring_coverage', 0):.2%}")
        print(f"Average code quality score: {summary.get('average_code_quality', 0):.2f}")
        
        print(f"\n=== Performance Metrics ===")
        print(f"Project scanning: {scan_time:.2f} seconds")
        print(f"Dependency analysis: {dependency_time:.2f} seconds")
        print(f"Metadata extraction: {metadata_time:.2f} seconds")
        print(f"Database storage: {storage_time:.2f} seconds")
        print(f"Total analysis time: {scan_time + dependency_time + metadata_time + storage_time:.2f} seconds")
    
    def get_analysis_results(self) -> Dict[str, Any]:
        """Get complete analysis results from the database."""
        if not self.project_id:
            return {}
        
        results = {
            'project_info': self.db_manager.get_project_analysis_summary(self.project_id),
            'files': self.db_manager.get_project_files(self.project_id),
            'dependencies': self.db_manager.get_dependency_graph(self.project_id),
            'summary': self.db_manager.get_project_analysis_summary(self.project_id)
        }
        
        return results


def main():
    """Main entry point for the analysis controller."""
    
    parser = argparse.ArgumentParser(description=
        "Python File Analysis System - Analyze Python projects for dependencies, structure, and quality metrics.")
    
    parser.add_argument('project_path', type=str, help=
        "Path to the Python project to analyze")
    parser.add_argument('--db-path', type=str, default='analysis_results.db', help=
        "Path to the SQLite database file")
    parser.add_argument('--exclude-patterns', type=str, nargs='*', default=[], help=
        "Patterns to exclude from analysis (e.g., __pycache__ .git)")
    parser.add_argument('--file-patterns', type=str, nargs='*', default=['*.py'], help=
        "File patterns to include in analysis")
    parser.add_argument('--log-level', type=str, default='INFO', choices=[
        'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help=
        "Logging level")
    parser.add_argument('--output-format', type=str, default='console', choices=[
        'console', 'json'], help=
        "Output format for results")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # Create configuration
    config = {
        'db_path': args.db_path,
        'exclude_patterns': args.exclude_patterns,
        'file_patterns': args.file_patterns
    }
    
    # Initialize controller
    controller = AnalysisController(config)
    
    # Run analysis
    success = controller.run_analysis(args.project_path)
    
    if success:
        print("✓ Analysis completed successfully!")
        
        if args.output_format == 'json':
            import json
            results = controller.get_analysis_results()
            print(json.dumps(results, indent=2, default=str))
            
    else:
        print("✗ Analysis failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()