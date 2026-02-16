#!/usr/bin/env python3
"""
Enhanced Database Client for Documentation System
=================================================

Advanced database integration that leverages the full power of file_tracker.db
for intelligent documentation workflow management.
"""

import sqlite3
import json
import time
import hashlib
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
from pathlib import Path

# Use the comprehensive database
DB_PATH = "/mnt/e/Coding_Project/review/file_tracker.db"

class EnhancedDocumentationClient:
    """
    Enhanced client for database-driven documentation with intelligent prioritization,
    progress tracking, and comprehensive analytics.
    """
    
    def __init__(self, db_path: str): # It now requires a path to be given
        self.db_path = db_path
        # Optional: Add the directory creation logic here for robustness
        from pathlib import Path
        import os
        db_parent_dir = Path(self.db_path).parent
        if not db_parent_dir.exists():
            os.makedirs(db_parent_dir, exist_ok=True)
    
    def get_files_to_document(self, priority_filter: str = "all") -> List[Dict[str, Any]]:
        """
        Get files that need documentation with intelligent prioritization.
        
        Args:
            priority_filter: "high", "medium", "low", "all", "agents_only", "new_files"
        
        Returns:
            List of file information dictionaries with priority scoring
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Base query with comprehensive file information
        base_query = """
            SELECT 
                f.file_path,
                f.file_size,
                f.file_extension,
                f.content_hash,
                f.modified_time,
                f.file_type,
                f.status,
                fa.complexity_score,
                fa.lines_of_code,
                fa.classes_found,
                fa.functions_found,
                a.agent_name,
                a.agent_type,
                ar.overall_runability_score
            FROM files f
            LEFT JOIN file_analysis fa ON f.file_path = fa.file_path
            LEFT JOIN agents a ON f.file_path = a.file_path
            LEFT JOIN agent_runability ar ON a.agent_name = ar.agent_name
        """
        
        # Apply filters based on priority
        if priority_filter == "agents_only":
            where_clause = "WHERE a.agent_name IS NOT NULL AND (f.status = 'pending' OR f.status IS NULL)"
        elif priority_filter == "new_files":
            where_clause = "WHERE fa.analysis_timestamp IS NULL AND f.file_extension = '.py'"
        elif priority_filter == "high":
            where_clause = """
                WHERE (f.status = 'pending' OR f.status IS NULL) 
                AND f.file_extension = '.py'
                AND (fa.complexity_score > 7 OR a.agent_name IS NOT NULL OR f.file_size > 10000)
            """
        elif priority_filter == "medium":
            where_clause = """
                WHERE (f.status = 'pending' OR f.status IS NULL) 
                AND f.file_extension = '.py'
                AND (fa.complexity_score BETWEEN 4 AND 7 OR f.file_size BETWEEN 1000 AND 10000)
            """
        elif priority_filter == "low":
            where_clause = """
                WHERE (f.status = 'pending' OR f.status IS NULL) 
                AND f.file_extension = '.py'
                AND (fa.complexity_score < 4 OR f.file_size < 1000)
            """
        else:  # "all"
            where_clause = "WHERE (f.status = 'pending' OR f.status IS NULL OR f.status = 'modified') AND f.file_extension = '.py'"
        
        query = f"{base_query} {where_clause} ORDER BY fa.complexity_score DESC, f.file_size DESC"
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        files_to_document = []
        for row in results:
            file_info = {
                'file_path': row[0],
                'file_size': row[1] or 0,
                'file_extension': row[2],
                'content_hash': row[3],
                'modified_time': row[4],
                'file_type': row[5],
                'status': row[6],
                'complexity_score': row[7] or 0,
                'lines_of_code': row[8] or 0,
                'classes_found': row[9],
                'functions_found': row[10],
                'agent_name': row[11],
                'agent_type': row[12],
                'runability_score': row[13] or 0,
                'priority_score': self._calculate_priority_score(row)
            }
            files_to_document.append(file_info)
        
        # Sort by priority score
        files_to_document.sort(key=lambda x: x['priority_score'], reverse=True)
        
        conn.close()
        return files_to_document
    
    def _calculate_priority_score(self, row: tuple) -> float:
        """Calculate priority score based on multiple factors."""
        complexity = row[7] or 0
        size = row[1] or 0
        is_agent = 1 if row[11] else 0
        runability = row[13] or 0
        
        # Priority scoring algorithm
        priority_score = (
            complexity * 2.0 +           # Complexity is important
            (size / 1000) * 0.5 +       # Size factor (scaled)
            is_agent * 5.0 +             # Agents get priority
            runability * 0.5             # Runnable agents get bonus
        )
        
        return min(priority_score, 10.0)  # Cap at 10
    
    def get_documentation_progress(self) -> Dict[str, Any]:
        """Get comprehensive documentation progress statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Overall progress
        cursor.execute("SELECT COUNT(*) FROM files WHERE file_extension = '.py'")
        total_python_files = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM files WHERE file_extension = '.py' AND status = 'documented'")
        documented_files = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM files WHERE file_extension = '.py' AND (status = 'pending' OR status IS NULL)")
        pending_files = cursor.fetchone()[0]
        
        # Agent-specific progress
        cursor.execute("SELECT COUNT(*) FROM agents")
        total_agents = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM agents a 
            JOIN files f ON a.file_path = f.file_path 
            WHERE f.status = 'documented'
        """)
        documented_agents = cursor.fetchone()[0]
        
        # Complexity distribution
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN fa.complexity_score >= 8 THEN 1 END) as high_complexity,
                COUNT(CASE WHEN fa.complexity_score BETWEEN 4 AND 7 THEN 1 END) as medium_complexity,
                COUNT(CASE WHEN fa.complexity_score < 4 THEN 1 END) as low_complexity
            FROM file_analysis fa
            JOIN files f ON fa.file_path = f.file_path
            WHERE f.file_extension = '.py'
        """)
        complexity_stats = cursor.fetchone()
        
        # Recent documentation activity
        cursor.execute("""
            SELECT COUNT(*) FROM file_operations 
            WHERE operation_type LIKE '%DOC%' OR operation_type = 'documented'
        """)
        recent_doc_operations = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'overall_progress': {
                'total_python_files': total_python_files,
                'documented_files': documented_files,
                'pending_files': pending_files,
                'completion_percentage': (documented_files / max(1, total_python_files)) * 100
            },
            'agent_progress': {
                'total_agents': total_agents,
                'documented_agents': documented_agents,
                'agent_completion_percentage': (documented_agents / max(1, total_agents)) * 100
            },
            'complexity_distribution': {
                'high_complexity': complexity_stats[0] or 0,
                'medium_complexity': complexity_stats[1] or 0,
                'low_complexity': complexity_stats[2] or 0
            },
            'recent_activity': {
                'documentation_operations': recent_doc_operations
            }
        }
    
    def update_documentation_status(
        self, 
        file_path: str, 
        status: str, 
        doc_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update documentation status with comprehensive tracking.
        
        Args:
            file_path: File being documented
            status: New status (documented, in_progress, error, etc.)
            doc_metadata: Additional documentation metadata
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Update file status
        cursor.execute("""
            UPDATE files 
            SET status = ?, analysis_date = ?
            WHERE file_path = ?
        """, (status, time.time(), file_path))
        
        # Log the documentation operation
        cursor.execute("""
            INSERT INTO file_operations 
            (file_path, operation_type, timestamp, notes)
            VALUES (?, ?, ?, ?)
        """, (
            file_path,
            f"DOCUMENTATION_{status.upper()}",
            datetime.now().isoformat(),
            json.dumps(doc_metadata) if doc_metadata else "Documentation status updated"
        ))
        
        conn.commit()
        conn.close()
        
        print(f" Updated documentation status for {Path(file_path).name} to '{status}'")
    
    def store_documentation_results(
        self,
        file_path: str,
        doc_results: Dict[str, Any]
    ) -> None:
        """
        Store comprehensive documentation results.
        
        Args:
            file_path: File that was documented
            doc_results: Results including docstrings, rst files, etc.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Update or insert file analysis with documentation info
        cursor.execute("""
            INSERT OR REPLACE INTO file_analysis (
                file_path, file_name, file_type, analysis_timestamp,
                analysis_notes
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            file_path,
            Path(file_path).name,
            "python_documented",
            time.time(),
            json.dumps(doc_results)
        ))
        
        # Log successful documentation
        cursor.execute("""
            INSERT INTO file_operations 
            (file_path, operation_type, timestamp, notes)
            VALUES (?, ?, ?, ?)
        """, (
            file_path,
            "DOCUMENTATION_COMPLETED",
            datetime.now().isoformat(),
            f"Generated documentation for {len(doc_results.get('functions', []))} functions"
        ))
        
        conn.commit()
        conn.close()
        
        print(f" Stored documentation results for {Path(file_path).name}")
    
    def get_documentation_recommendations(self) -> List[Dict[str, Any]]:
        """Get intelligent recommendations for what to document next."""
        files = self.get_files_to_document("all")
        
        recommendations = []
        
        # High-priority recommendations
        for file_info in files[:10]:  # Top 10 by priority
            reasons = []
            
            if file_info['agent_name']:
                reasons.append(f"Agent file: {file_info['agent_name']}")
            
            if file_info['complexity_score'] > 7:
                reasons.append(f"High complexity: {file_info['complexity_score']}/10")
            
            if file_info['file_size'] > 20000:
                reasons.append(f"Large file: {file_info['file_size']:,} bytes")
            
            if file_info['runability_score'] > 8:
                reasons.append(f"Highly runnable: {file_info['runability_score']}/10")
            
            if not reasons:
                reasons.append("Standard documentation candidate")
            
            recommendations.append({
                'file_path': file_info['file_path'],
                'file_name': Path(file_info['file_path']).name,
                'priority_score': file_info['priority_score'],
                'reasons': reasons,
                'estimated_effort': self._estimate_documentation_effort(file_info)
            })
        
        return recommendations
    
    def _estimate_documentation_effort(self, file_info: Dict[str, Any]) -> str:
        """Estimate documentation effort based on file characteristics."""
        size = file_info['file_size']
        complexity = file_info['complexity_score']
        
        if size > 50000 or complexity > 8:
            return "High (2-3 hours)"
        elif size > 10000 or complexity > 5:
            return "Medium (1-2 hours)"
        else:
            return "Low (30-60 minutes)"
    
    def generate_documentation_report(self) -> str:
        """Generate a comprehensive documentation status report."""
        progress = self.get_documentation_progress()
        recommendations = self.get_documentation_recommendations()
        
        report = f"""
 DOCUMENTATION STATUS REPORT
{'=' * 40}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

 OVERALL PROGRESS
• Python Files: {progress['overall_progress']['total_python_files']:,}
• Documented: {progress['overall_progress']['documented_files']:,}
• Pending: {progress['overall_progress']['pending_files']:,}
• Completion: {progress['overall_progress']['completion_percentage']:.1f}%

 AGENT DOCUMENTATION
• Total Agents: {progress['agent_progress']['total_agents']}
• Documented: {progress['agent_progress']['documented_agents']}
• Agent Completion: {progress['agent_progress']['agent_completion_percentage']:.1f}%

 COMPLEXITY BREAKDOWN
• High Complexity: {progress['complexity_distribution']['high_complexity']} files
• Medium Complexity: {progress['complexity_distribution']['medium_complexity']} files
• Low Complexity: {progress['complexity_distribution']['low_complexity']} files

 TOP RECOMMENDATIONS
"""
        
        for i, rec in enumerate(recommendations[:5], 1):
            reasons_str = ", ".join(rec['reasons'])
            report += f"{i}. {rec['file_name']} (Priority: {rec['priority_score']:.1f})\n"
            report += f"   Reasons: {reasons_str}\n"
            report += f"   Effort: {rec['estimated_effort']}\n\n"
        
        return report


# Legacy compatibility functions
def get_files_to_document() -> List[Tuple[str, str]]:
    """Legacy compatibility function."""
    client = EnhancedDocumentationClient()
    files = client.get_files_to_document("all")
    return [(f['file_path'], f['content_hash']) for f in files]

def update_doc_status(file_path: str, new_status: str):
    """Legacy compatibility function."""
    client = EnhancedDocumentationClient()
    client.update_documentation_status(file_path, new_status)

def store_analysis_results(file_path: str, analysis_data: dict):
    """Legacy compatibility function."""
    client = EnhancedDocumentationClient()
    client.store_documentation_results(file_path, analysis_data)


if __name__ == '__main__':
    # Demonstration of enhanced capabilities
    client = EnhancedDocumentationClient()
    
    print(" Enhanced Documentation Client Demo")
    print("=" * 45)
    
    # Show documentation progress
    progress = client.get_documentation_progress()
    print(f" Documentation Progress:")
    print(f"   • {progress['overall_progress']['completion_percentage']:.1f}% of Python files documented")
    print(f"   • {progress['agent_progress']['agent_completion_percentage']:.1f}% of agents documented")
    
    # Show high-priority files
    high_priority = client.get_files_to_document("high")
    print(f"\n High Priority Files: {len(high_priority)}")
    for i, file_info in enumerate(high_priority[:5], 1):
        name = Path(file_info['file_path']).name
        print(f"   {i}. {name} (Priority: {file_info['priority_score']:.1f})")
    
    # Show recommendations
    recommendations = client.get_documentation_recommendations()
    print(f"\n Top Recommendation:")
    if recommendations:
        rec = recommendations[0]
        print(f"    {rec['file_name']}")
        print(f"    Priority Score: {rec['priority_score']:.1f}")
        print(f"    Reasons: {', '.join(rec['reasons'])}")
        print(f"    Estimated Effort: {rec['estimated_effort']}")
    
    # Generate full report
    report_file = "documentation_status_report.txt"
    with open(report_file, 'w') as f:
        f.write(client.generate_documentation_report())
    
    print(f"\n Full report saved to: {report_file}")