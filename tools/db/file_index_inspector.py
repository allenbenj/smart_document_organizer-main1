"""
File Index Inspector - Query and visualize the application file index

Interactive tool for exploring the file index database.
Combines inspection capabilities from inspector.py and inspector_detailed.py
"""

import argparse
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class FileIndexInspector:
    """Inspector for the file index database."""
    
    def __init__(self, db_path: str = "databases/file_index.db"):
        """Initialize inspector."""
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def print_header(self, title: str):
        """Print formatted section header."""
        print(f"\n{'=' * 80}")
        print(f"  {title}")
        print(f"{'=' * 80}\n")
    
    def show_overview(self):
        """Show database overview."""
        self.print_header("FILE INDEX OVERVIEW")
        
        cursor = self.conn.cursor()
        
        # Database info
        cursor.execute("SELECT value FROM system_config WHERE key = 'db_version'")
        version = cursor.fetchone()
        print(f"Database Version: {version['value'] if version else 'Unknown'}")
        print(f"Database Path: {self.db_path}")
        print(f"Database Size: {self.db_path.stat().st_size / 1024:.1f} KB")
        
        # File counts
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN is_active THEN 1 END) as active,
                COUNT(CASE WHEN is_deprecated THEN 1 END) as deprecated,
                COUNT(CASE WHEN is_test_file THEN 1 END) as tests,
                SUM(lines_of_code) as total_lines,
                SUM(file_size) as total_size
            FROM files
        """)
        stats = dict(cursor.fetchone())
        
        print(f"\n📁 Files:")
        print(f"   Total: {stats['total']}")
        print(f"   Active: {stats['active']}")
        print(f"   Deprecated: {stats['deprecated']}")
        print(f"   Test Files: {stats['tests']}")
        print(f"   Total Lines of Code: {stats['total_lines']:,}")
        print(f"   Total Size: {stats['total_size'] / 1024 / 1024:.2f} MB")
        
        # Analysis stats
        cursor.execute("SELECT COUNT(*) as analyzed FROM file_analysis")
        analyzed = cursor.fetchone()['analyzed']
        print(f"\n🔍 Analysis:")
        print(f"   Files Analyzed: {analyzed}")
        print(f"   Analysis Coverage: {analyzed / max(stats['total'], 1) * 100:.1f}%")
        
        # Issue stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open,
                COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical,
                COUNT(CASE WHEN severity = 'high' THEN 1 END) as high
            FROM file_issues
        """)
        issues = dict(cursor.fetchone())
        print(f"\n⚠ Issues:")
        print(f"   Total: {issues['total']}")
        print(f"   Open: {issues['open']}")
        print(f"   Critical: {issues['critical']}")
        print(f"   High: {issues['high']}")
        
        # Recent activity
        cursor.execute("""
            SELECT COUNT(*) as scans
            FROM scan_history
            WHERE started_at > datetime('now', '-7 days')
        """)
        recent_scans = cursor.fetchone()['scans']
        print(f"\n📊 Recent Activity (7 days):")
        print(f"   Scans: {recent_scans}")
        
        cursor.execute("""
            SELECT COUNT(*) as changes
            FROM file_change_history
            WHERE detected_at > datetime('now', '-7 days')
        """)
        recent_changes = cursor.fetchone()['changes']
        print(f"   File Changes: {recent_changes}")
    
    def show_file_types(self):
        """Show file type distribution."""
        self.print_header("FILE TYPE DISTRIBUTION")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                file_type,
                COUNT(*) as count,
                SUM(lines_of_code) as total_lines,
                AVG(lines_of_code) as avg_lines,
                SUM(file_size) as total_size
            FROM files
            WHERE is_active = TRUE
            GROUP BY file_type
            ORDER BY count DESC
        """)
        
        print(f"{'Type':<20} {'Files':<10} {'Lines':<15} {'Avg Lines':<12} {'Size (KB)':<12}")
        print("-" * 80)
        
        for row in cursor.fetchall():
            print(f"{row['file_type']:<20} {row['count']:<10} "
                  f"{row['total_lines']:<15,} {row['avg_lines']:<12,.0f} "
                  f"{row['total_size'] / 1024:<12,.1f}")
    
    def show_file_categories(self):
        """Show file category distribution."""
        self.print_header("FILE CATEGORY DISTRIBUTION")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                file_category,
                COUNT(*) as count,
                SUM(lines_of_code) as total_lines,
                COUNT(CASE WHEN is_test_file THEN 1 END) as test_count
            FROM files
            WHERE is_active = TRUE
            GROUP BY file_category
            ORDER BY count DESC
        """)
        
        print(f"{'Category':<20} {'Files':<10} {'Lines':<15} {'Tests':<10}")
        print("-" * 60)
        
        for row in cursor.fetchall():
            print(f"{row['file_category']:<20} {row['count']:<10} "
                  f"{row['total_lines']:<15,} {row['test_count']:<10}")
    
    def show_recent_changes(self, limit: int = 20):
        """Show recent file changes."""
        self.print_header(f"RECENT FILE CHANGES (Last {limit})")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                file_path,
                change_type,
                detected_at,
                lines_added,
                lines_removed
            FROM file_change_history
            ORDER BY detected_at DESC
            LIMIT ?
        """, (limit,))
        
        print(f"{'Date':<20} {'Type':<12} {'File':<40}")
        print("-" * 80)
        
        for row in cursor.fetchall():
            date_str = row['detected_at'][:19] if row['detected_at'] else 'Unknown'
            file_short = row['file_path'][:37] + '...' if len(row['file_path']) > 40 else row['file_path']
            print(f"{date_str:<20} {row['change_type']:<12} {file_short:<40}")
    
    def show_top_files(self, metric: str = 'lines', limit: int = 20):
        """Show top files by metric (lines, size, complexity)."""
        metric_map = {
            'lines': ('lines_of_code', 'Lines of Code'),
            'size': ('file_size', 'Size (KB)'),
            'issues': ('issue_count', 'Open Issues')
        }
        
        if metric not in metric_map:
            print(f"Invalid metric. Choose from: {', '.join(metric_map.keys())}")
            return
        
        column, title = metric_map[metric]
        self.print_header(f"TOP {limit} FILES BY {title.upper()}")
        
        cursor = self.conn.cursor()
        
        if metric ==  'issues':
            cursor.execute(f"""
                SELECT 
                    file_path,
                    issue_count,
                    tags
                FROM v_files_complete
                WHERE issue_count > 0
                ORDER BY issue_count DESC
                LIMIT ?
            """, (limit,))
            
            print(f"{'#':<4} {'Issues':<10} {'File':<50} {'Tags':<20}")
            print("-" * 90)
            
            for i, row in enumerate(cursor.fetchall(), 1):
                file_short = row['file_path'][:47] + '...' if len(row['file_path']) > 50 else row['file_path']
                tags = row['tags'][:17] + '...' if row['tags'] and len(row['tags']) > 20 else (row['tags'] or '')
                print(f"{i:<4} {row['issue_count']:<10} {file_short:<50} {tags:<20}")
        else:
            cursor.execute(f"""
                SELECT 
                    file_path,
                    {column},
                    file_type
                FROM files
                WHERE is_active = TRUE
                ORDER BY {column} DESC
                LIMIT ?
            """, (limit,))
            
            print(f"{'#':<4} {title:<15} {'Type':<15} {'File':<45}")
            print("-" * 85)
            
            for i, row in enumerate(cursor.fetchall(), 1):
                value = row[column]
                if metric == 'size':
                    value_str = f"{value / 1024:.1f}"
                else:
                    value_str = f"{value:,}"
                
                file_short = row['file_path'][:42] + '...' if len(row['file_path']) > 45 else row['file_path']
                print(f"{i:<4} {value_str:<15} {row['file_type']:<15} {file_short:<45}")
    
    def show_tags(self):
        """Show all tags and their usage."""
        self.print_header("TAG USAGE")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                tag_category,
                tag_name,
                COUNT(*) as usage_count
            FROM file_tags
            GROUP BY tag_category, tag_name
            ORDER BY tag_category, usage_count DESC
        """)
        
        current_category = None
        for row in cursor.fetchall():
            if current_category != row['tag_category']:
                current_category = row['tag_category']
                print(f"\n{current_category.upper()}:")
            
            print(f"  {row['tag_name']:<30} ({row['usage_count']} files)")
    
    def show_file_details(self, file_path: str):
        """Show detailed information about a specific file."""
        self.print_header(f"FILE DETAILS: {file_path}")
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM v_files_complete WHERE file_path = ?", (file_path,))
        file_info = cursor.fetchone()
        
        if not file_info:
            print(f"❌ File not found: {file_path}")
            return
        
        file_info = dict(file_info)
        
        print(f"📄 Basic Information:")
        print(f"   Path: {file_info['file_path']}")
        print(f"   Name: {file_info['file_name']}")
        print(f"   Type: {file_info['file_type']}")
        print(f"   Category: {file_info['file_category']}")
        print(f"   Extension: {file_info['file_extension']}")
        print(f"   Lines of Code: {file_info['lines_of_code']:,}")
        
        if file_info['primary_purpose']:
            print(f"\n🎯 Purpose:")
            print(f"   {file_info['primary_purpose']}")
        
        if file_info['tags']:
            print(f"\n🏷 Tags:")
            print(f"   {file_info['tags']}")
        
        if file_info['complexity_score']:
            print(f"\n📊 Metrics:")
            print(f"   Complexity: {file_info['complexity_score']:.2f}")
            print(f"   Maintainability: {file_info['maintainability_score']:.2f}")
        
        if file_info['issue_count'] > 0:
            print(f"\n⚠ Open Issues: {file_info['issue_count']}")
            cursor.execute("""
                SELECT issue_type, severity, title
                FROM file_issues
                WHERE file_id = (SELECT id FROM files WHERE file_path = ?)
                AND status = 'open'
            """, (file_path,))
            
            for issue in cursor.fetchall():
                print(f"   [{issue['severity']}] {issue['issue_type']}: {issue['title']}")
        
        # Show relationships
        cursor.execute("""
            SELECT relationship_type, COUNT(*) as count
            FROM file_relationships
            WHERE source_file_id = (SELECT id FROM files WHERE file_path = ?)
            GROUP BY relationship_type
        """, (file_path,))
        
        relationships = cursor.fetchall()
        if relationships:
            print(f"\n🔗 Relationships:")
            for rel in relationships:
                print(f"   {rel['relationship_type']}: {rel['count']}")
    
    def search_files(self, query: str, limit: int = 50):
        """Search for files."""
        self.print_header(f"SEARCH RESULTS: '{query}'")
        
        cursor = self.conn.cursor()
        pattern = f"%{query}%"
        cursor.execute("""
            SELECT file_path, file_type, file_category, lines_of_code
            FROM files
            WHERE file_path LIKE ? OR file_name LIKE ?
            AND is_active = TRUE
            ORDER BY file_path
            LIMIT ?
        """, (pattern, pattern, limit))
        
        results = cursor.fetchall()
        
        if not results:
            print("No files found.")
            return
        
        print(f"Found {len(results)} file(s):\n")
        print(f"{'Type':<15} {'Category':<15} {'Lines':<10} {'Path':<50}")
        print("-" * 95)
        
        for row in results:
            path_short = row['file_path'][:47] + '...' if len(row['file_path']) > 50 else row['file_path']
            print(f"{row['file_type']:<15} {row['file_category']:<15} "
                  f"{row['lines_of_code']:<10,} {path_short:<50}")
    
    def show_scan_history(self, limit: int = 10):
        """Show scan history."""
        self.print_header(f"SCAN HISTORY (Last {limit})")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                scan_type,
                started_at,
                duration_seconds,
                files_scanned,
                files_added,
                files_updated,
                status
            FROM scan_history
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))
        
        print(f"{'Date':<20} {'Type':<12} {'Duration':<12} {'Scanned':<10} {'Added':<8} {'Updated':<10} {'Status':<10}")
        print("-" * 95)
        
        for row in cursor.fetchall():
            date_str = row['started_at'][:19] if row['started_at'] else 'Unknown'
            duration = f"{row['duration_seconds']:.1f}s" if row['duration_seconds'] else 'N/A'
            print(f"{date_str:<20} {row['scan_type']:<12} {duration:<12} "
                  f"{row['files_scanned']:<10} {row['files_added']:<8} "
                  f"{row['files_updated']:<10} {row['status']:<10}")
    
    def show_issues_summary(self):
        """Show summary of issues."""
        self.print_header("ISSUES SUMMARY")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                issue_type,
                severity,
                COUNT(*) as count
            FROM file_issues
            WHERE status = 'open'
            GROUP BY issue_type, severity
            ORDER BY 
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                count DESC
        """)
        
        print(f"{'Type':<20} {'Severity':<12} {'Count':<10}")
        print("-" * 45)
        
        for row in cursor.fetchall():
            print(f"{row['issue_type']:<20} {row['severity']:<12} {row['count']:<10}")
    
    def export_to_json(self, output_file: str = "file_index_export.json"):
        """Export file index to JSON."""
        import json
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM v_files_complete")
        
        files = [dict(row) for row in cursor.fetchall()]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(files, f, indent=2, default=str)
        
        print(f"✓ Exported {len(files)} files to {output_file}")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="File Index Inspector")
    parser.add_argument('--db', default='databases/file_index.db', help='Database path')
    parser.add_argument('--overview', action='store_true', help='Show overview')
    parser.add_argument('--types', action='store_true', help='Show file types')
    parser.add_argument('--categories', action='store_true', help='Show file categories')
    parser.add_argument('--changes', type=int, metavar='N', help='Show last N changes')
    parser.add_argument('--top', choices=['lines', 'size', 'issues'], help='Show top files by metric')
    parser.add_argument('--tags', action='store_true', help='Show tags')
    parser.add_argument('--file', metavar='PATH', help='Show file details')
    parser.add_argument('--search', metavar='QUERY', help='Search files')
    parser.add_argument('--scans', type=int, metavar='N', help='Show last N scans')
    parser.add_argument('--issues', action='store_true', help='Show issues summary')
    parser.add_argument('--export', metavar='FILE', help='Export to JSON')
    parser.add_argument('--limit', type=int, default=20, help='Limit for top/changes')
    
    args = parser.parse_args()
    
    try:
        inspector = FileIndexInspector(args.db)
        
        # If no specific command, show overview
        if not any([args.overview, args.types, args.categories, args.changes, 
                   args.top, args.tags, args.file, args.search, args.scans, 
                   args.issues, args.export]):
            args.overview = True
        
        if args.overview:
            inspector.show_overview()
        
        if args.types:
            inspector.show_file_types()
        
        if args.categories:
            inspector.show_file_categories()
        
        if args.changes:
            inspector.show_recent_changes(args.changes)
        
        if args.top:
            inspector.show_top_files(args.top, args.limit)
        
        if args.tags:
            inspector.show_tags()
        
        if args.file:
            inspector.show_file_details(args.file)
        
        if args.search:
            inspector.search_files(args.search)
        
        if args.scans:
            inspector.show_scan_history(args.scans)
        
        if args.issues:
            inspector.show_issues_summary()
        
        if args.export:
            inspector.export_to_json(args.export)
        
        inspector.close()
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("\n💡 Tip: Run 'python tools/db/file_index_manager.py' first to create the index.")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
