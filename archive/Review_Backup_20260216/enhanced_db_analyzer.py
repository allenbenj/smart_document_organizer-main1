#!/usr/bin/env python3
"""
Enhanced Database Analyzer for file_tracker.db
==============================================

Advanced analytics and insights for the comprehensive file tracking database.
"""
import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

class DatabaseAnalyzer:
    """Advanced analyzer for the file tracking database."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        db_parent_dir = Path(self.db_path).parent
        if not db_parent_dir.exists():
            print(f"Directory not found. Creating: {db_parent_dir}")
        os.makedirs(db_parent_dir, exist_ok=True)
        
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Basic counts
        cursor.execute("SELECT COUNT(*) FROM files")
        stats['total_files'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM agents")
        stats['total_agents'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM file_operations")
        stats['total_operations'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM file_analysis")
        stats['analyzed_files'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM agent_runability")
        stats['tested_agents'] = cursor.fetchone()[0]
        
        # File size analytics
        cursor.execute("SELECT SUM(file_size), AVG(file_size), MAX(file_size) FROM files WHERE file_size > 0")
        total_size, avg_size, max_size = cursor.fetchone()
        stats['file_sizes'] = {
            'total_bytes': total_size or 0,
            'total_mb': (total_size or 0) / (1024 * 1024),
            'average_bytes': avg_size or 0,
            'largest_file_bytes': max_size or 0
        }
        
        # File type distribution
        cursor.execute("SELECT file_extension, COUNT(*) FROM files GROUP BY file_extension ORDER BY COUNT(*) DESC")
        stats['file_types'] = dict(cursor.fetchall())
        
        # Agent runability summary
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN overall_runability_score >= 8 THEN 1 ELSE 0 END) as fully_runnable,
                SUM(CASE WHEN overall_runability_score BETWEEN 5 AND 7 THEN 1 ELSE 0 END) as partially_runnable,
                SUM(CASE WHEN overall_runability_score < 5 THEN 1 ELSE 0 END) as needs_work
            FROM agent_runability
        """)
        runability = cursor.fetchone()
        stats['agent_runability'] = {
            'fully_runnable': runability[0] or 0,
            'partially_runnable': runability[1] or 0,
            'needs_work': runability[2] or 0
        }
        
        # Recent operations
        cursor.execute("""
            SELECT operation_type, COUNT(*) 
            FROM file_operations 
            GROUP BY operation_type 
            ORDER BY COUNT(*) DESC
        """)
        stats['operations_by_type'] = dict(cursor.fetchall())
        
        # Project health indicators
        cursor.execute("SELECT COUNT(*) FROM files WHERE status = 'completed'")
        completed_files = cursor.fetchone()[0]
        stats['project_health'] = {
            'completion_rate': completed_files / max(1, stats['total_files']),
            'analysis_coverage': stats['analyzed_files'] / max(1, stats['total_files']),
            'agent_test_coverage': stats['tested_agents'] / max(1, stats['total_agents'])
        }
        
        conn.close()
        return stats
    
    def get_operation_timeline(self) -> List[Dict[str, Any]]:
        """Get chronological timeline of all operations."""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, operation_type, file_path, new_size, notes
            FROM file_operations 
            ORDER BY timestamp DESC
            LIMIT 50
        """)
        
        timeline = []
        for row in cursor.fetchall():
            timeline.append({
                'timestamp': row[0],
                'operation': row[1],
                'file_path': row[2],
                'size': row[3],
                'notes': row[4][:100] + "..." if row[4] and len(row[4]) > 100 else row[4]
            })
        
        conn.close()
        return timeline
    
    def get_agent_insights(self) -> Dict[str, Any]:
        """Get detailed insights about agents."""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Join agents with runability data
        cursor.execute("""
            SELECT 
                a.agent_name,
                a.agent_type,
                a.lines_of_code,
                a.functions_count,
                r.overall_runability_score,
                r.syntax_valid,
                r.imports_resolvable,
                r.dependencies_available
            FROM agents a
            LEFT JOIN agent_runability r ON a.agent_name = r.agent_name
            ORDER BY r.overall_runability_score DESC, a.lines_of_code DESC
        """)
        
        agents = []
        for row in cursor.fetchall():
            agents.append({
                'name': row[0],
                'type': row[1],
                'lines_of_code': row[2] or 0,
                'functions_count': row[3] or 0,
                'runability_score': row[4] or 0,
                'syntax_valid': bool(row[5]) if row[5] is not None else None,
                'imports_resolvable': bool(row[6]) if row[6] is not None else None,
                'dependencies_available': bool(row[7]) if row[7] is not None else None
            })
        
        # Calculate insights
        total_lines = sum(a['lines_of_code'] for a in agents)
        total_functions = sum(a['functions_count'] for a in agents)
        avg_runability = sum(a['runability_score'] for a in agents if a['runability_score'] > 0) / max(1, len([a for a in agents if a['runability_score'] > 0]))
        
        insights = {
            'agents': agents,
            'summary': {
                'total_lines_of_code': total_lines,
                'total_functions': total_functions,
                'average_runability_score': avg_runability,
                'top_agent_by_size': max(agents, key=lambda x: x['lines_of_code'])['name'] if agents else None,
                'most_runnable_agent': max(agents, key=lambda x: x['runability_score'])['name'] if agents else None
            }
        }
        
        conn.close()
        return insights
    
    def get_file_hotspots(self) -> Dict[str, Any]:
        """Identify file hotspots and patterns."""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Most operated-on files
        cursor.execute("""
            SELECT file_path, COUNT(*) as operation_count
            FROM file_operations
            GROUP BY file_path
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """)
        hotspot_files = [{'path': row[0], 'operations': row[1]} for row in cursor.fetchall()]
        
        # Largest files
        cursor.execute("""
            SELECT file_path, file_size, file_extension
            FROM files
            WHERE file_size > 0
            ORDER BY file_size DESC
            LIMIT 10
        """)
        largest_files = [{'path': row[0], 'size': row[1], 'extension': row[2]} for row in cursor.fetchall()]
        
        # Directory analysis
        cursor.execute("""
            SELECT parent_directory, COUNT(*) as file_count, SUM(file_size) as total_size
            FROM files
            WHERE parent_directory IS NOT NULL
            GROUP BY parent_directory
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """)
        directory_stats = [{'directory': row[0], 'files': row[1], 'total_size': row[2] or 0} for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'hotspot_files': hotspot_files,
            'largest_files': largest_files,
            'directory_stats': directory_stats
        }
    
    def generate_health_report(self) -> str:
        """Generate a comprehensive health report."""
        
        stats = self.get_comprehensive_stats()
        agent_insights = self.get_agent_insights()
        hotspots = self.get_file_hotspots()
        
        report = f"""
 FILE TRACKER DATABASE HEALTH REPORT
{'=' * 50}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

 OVERVIEW STATISTICS
• Total Files Tracked: {stats['total_files']:,}
• Total Agents: {stats['total_agents']}
• Total Operations: {stats['total_operations']}
• Files Analyzed: {stats['analyzed_files']} ({stats['analyzed_files']/max(1,stats['total_files'])*100:.1f}%)
• Agents Tested: {stats['tested_agents']} ({stats['tested_agents']/max(1,stats['total_agents'])*100:.1f}%)

 STORAGE METRICS
• Total Project Size: {stats['file_sizes']['total_mb']:.1f} MB
• Average File Size: {stats['file_sizes']['average_bytes']:,.0f} bytes
• Largest File: {stats['file_sizes']['largest_file_bytes']:,.0f} bytes

 FILE TYPE DISTRIBUTION
"""
        
        for ext, count in list(stats['file_types'].items())[:10]:
            percentage = count / stats['total_files'] * 100
            report += f"• {ext or 'no extension'}: {count:,} files ({percentage:.1f}%)\n"
        
        report += f"""
 AGENT HEALTH STATUS
• Fully Runnable: {stats['agent_runability']['fully_runnable']} agents
• Partially Runnable: {stats['agent_runability']['partially_runnable']} agents  
• Need Work: {stats['agent_runability']['needs_work']} agents
• Average Runability Score: {agent_insights['summary']['average_runability_score']:.1f}/10

 PROJECT HEALTH INDICATORS
• File Completion Rate: {stats['project_health']['completion_rate']*100:.1f}%
• Analysis Coverage: {stats['project_health']['analysis_coverage']*100:.1f}%
• Agent Test Coverage: {stats['project_health']['agent_test_coverage']*100:.1f}%

 TOP ACTIVITY HOTSPOTS
"""
        
        for i, hotspot in enumerate(hotspots['hotspot_files'][:5], 1):
            report += f"{i}. {Path(hotspot['path']).name}: {hotspot['operations']} operations\n"
        
        report += f"""
 TOP PERFORMERS
• Largest Agent: {agent_insights['summary']['top_agent_by_size']} ({agent_insights['summary']['total_lines_of_code']:,} LOC total)
• Most Runnable: {agent_insights['summary']['most_runnable_agent']}
• Total Functions: {agent_insights['summary']['total_functions']:,}

 RECENT OPERATIONS
"""
        
        for op_type, count in list(stats['operations_by_type'].items())[:5]:
            report += f"• {op_type}: {count} operations\n"
        
        return report
    
    def export_insights_json(self, output_file: str = "database_insights.json"):
        """Export all insights to JSON file."""
        
        insights = {
            'generated_at': datetime.now().isoformat(),
            'stats': self.get_comprehensive_stats(),
            'agent_insights': self.get_agent_insights(),
            'hotspots': self.get_file_hotspots(),
            'timeline': self.get_operation_timeline()
        }
        
        with open(output_file, 'w') as f:
            json.dump(insights, f, indent=2, default=str)
        
        print(f" Insights exported to {output_file}")
        return output_file

def main():
    """Main function for command-line usage."""
    
    analyzer = DatabaseAnalyzer()
    
    print(" Analyzing file_tracker.db...")
    
    # Generate and display health report
    report = analyzer.generate_health_report()
    print(report)
    
    # Export detailed insights
    json_file = analyzer.export_insights_json()
    
    print(f"\n The file_tracker.db is incredibly comprehensive!")
    print(f" Detailed insights saved to: {json_file}")
    print(f" Use this data to guide development priorities")

if __name__ == "__main__":
    main()