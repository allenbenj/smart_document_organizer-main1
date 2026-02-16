"""
File Index Manager - Comprehensive application file tracking and analysis

This is NOT a database for the application's documents.
This is a database to track the application's own source files for development purposes.

Combines capabilities from:
- database_models.py (data structures)
- unified_database_manager.py (database operations)
- ai_database_updater.py (AI analysis integration)
- enhanced_database_schema.sql (comprehensive schema)
- configuration/manager.py (configuration management)
- logging/logger.py (structured logging)
"""

import asyncio
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class FileRecord:
    """Represents a file in the index."""
    id: Optional[int] = None
    file_path: str = ""
    file_name: str = ""
    file_extension: str = ""
    relative_path: str = ""
    absolute_path: str = ""
    file_size: int = 0
    lines_of_code: int = 0
    content_hash: str = ""
    file_type: str = ""
    file_category: str = ""
    is_active: bool = True
    is_test_file: bool = False
    modified_at: Optional[datetime] = None
    last_scanned_at: Optional[datetime] = None

@dataclass
class AnalysisResult:
    """Represents AI analysis results for a file."""
    file_id: int
    file_path: str
    primary_purpose: str = ""
    key_functionality: str = ""
    main_classes: List[str] = field(default_factory=list)
    main_functions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    complexity_score: float = 0.0
    maintainability_score: float = 0.0
    ai_model_used: str = ""
    analysis_confidence: float = 1.0

@dataclass
class FileIssue:
    """Represents an issue found in a file."""
    file_id: int
    issue_type: str
    severity: str
    title: str
    description: str = ""
    location: str = ""
    detected_by: str = "automated_scan"
    status: str = "open"

# ============================================================================
# FILE INDEX MANAGER
# ============================================================================

class FileIndexManager:
    """
    Manages the file index database for tracking application source files.
    
    Features:
    - File discovery and indexing
    - Content hash tracking for change detection
    - AI-powered file analysis
    - Relationship mapping (imports, dependencies)
    - Issue tracking
    - File tagging and categorization
    - Full-text search
    - Performance metrics
    """
    
    def __init__(self, db_path: str = "databases/file_index.db", project_root: str = "."):
        """
        Initialize the file index manager.
        
        Args:
            db_path: Path to the SQLite database file
            project_root: Root directory of the project to index
        """
        self.db_path = Path(db_path)
        self.project_root = Path(project_root).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # File patterns to exclude from indexing
        self.exclude_patterns = [
            r'__pycache__',
            r'\.pyc$',
            r'\.git',
            r'node_modules',
            r'\.venv',
            r'venv',
            r'\.idea',
            r'\.vscode',
            r'\.pytest_cache',
            r'\.egg-info',
            r'dist',
            r'build',
            r'\.DS_Store',
        ]
        
        # File extensions to index
        self.indexed_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx',
            '.sql', '.md', '.txt', '.yaml', '.yml',
            '.json', '.toml', '.ini', '.cfg',
            '.html', '.css', '.scss',
            '.sh', '.bash', '.ps1',
            '.env', '.conf'
        }
        
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize the database with schema if it doesn't exist."""
        schema_path = Path(__file__).parent / "file_index_schema.sql"
        
        if schema_path.exists():
            with sqlite3.connect(self.db_path) as conn:
                # Add REGEXP function support
                self._register_regexp_function(conn)
                schema_sql = schema_path.read_text(encoding='utf-8')
                conn.executescript(schema_sql)
                conn.commit()
            print(f"✓ File index database initialized: {self.db_path}")
        else:
            print(f"⚠ Warning: Schema file not found at {schema_path}")
    
    @staticmethod
    def _register_regexp_function(conn: sqlite3.Connection):
        """Register REGEXP function for SQLite."""
        def regexp(pattern, text):
            if pattern is None or text is None:
                return False
            try:
                return re.search(pattern, text) is not None
            except Exception:
                return False
        conn.create_function("REGEXP", 2, regexp)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Add REGEXP function support
        self._register_regexp_function(conn)
        return conn
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _count_lines(self, file_path: Path) -> int:
        """Count lines of code in a file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return len(f.readlines())
        except Exception:
            return 0
    
    def _should_index_file(self, file_path: Path) -> bool:
        """Determine if a file should be indexed."""
        # Check if file matches exclude patterns
        rel_path = str(file_path.relative_to(self.project_root))
        for pattern in self.exclude_patterns:
            if re.search(pattern, rel_path):
                return False
        
        # Check if extension is in indexed extensions
        return file_path.suffix in self.indexed_extensions
    
    def _classify_file(self, file_path: Path) -> Dict[str, str]:
        """Classify file type and category."""
        ext = file_path.suffix
        name = file_path.name
        path_str = str(file_path)
        
        # Determine file type
        type_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript_react',
            '.tsx': 'typescript_react',
            '.sql': 'sql',
            '.md': 'markdown',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.ini': 'ini',
            '.html': 'html',
            '.css': 'css',
            '.sh': 'shell',
            '.bash': 'shell',
            '.ps1': 'powershell',
            '.env': 'environment',
        }
        file_type = type_map.get(ext, 'other')
        
        # Determine file category
        category = 'other'
        if 'test' in name.lower() or '/tests/' in path_str or '/test/' in path_str:
            category = 'test'
        elif '/agent' in path_str:
            category = 'agent'
        elif '/gui/' in path_str:
            category = 'gui'
        elif '/core/' in path_str:
            category = 'core'
        elif '/tools/' in path_str:
            category = 'tool'
        elif '/config/' in path_str or ext in {'.json', '.yaml', '.yml', '.toml', '.ini', '.env'}:
            category = 'config'
        elif '/database' in path_str or 'db' in path_str:
            category = 'database'
        elif '/docs/' in path_str or ext == '.md':
            category = 'doc'
        elif '/utils/' in path_str or 'helper' in name.lower() or 'util' in name.lower():
            category = 'utility'
        elif '/services/' in path_str or '/service/' in path_str:
            category = 'service'
        elif '/api/' in path_str or 'route' in name.lower():
            category = 'api'
        
        return {
            'file_type': file_type,
            'file_category': category
        }
    
    def scan_files(self, incremental: bool = True) -> Dict[str, int]:
        """
        Scan and index all files in the project.
        
        Args:
            incremental: If True, only scan changed/new files. If False, full rescan.
            
        Returns:
            Dictionary with scan statistics
        """
        stats = {
            'scanned': 0,
            'added': 0,
            'updated': 0,
            'removed': 0,
            'skipped': 0
        }
        
        scan_id = self._start_scan('incremental' if incremental else 'full')
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get existing files for incremental scan
            existing_files = {}
            if incremental:
                cursor.execute("SELECT file_path, content_hash FROM files WHERE is_active = TRUE")
                existing_files = {row['file_path']: row['content_hash'] for row in cursor.fetchall()}
            
            # Scan all files in project
            indexed_paths = set()
            
            for file_path in self.project_root.rglob('*'):
                try:
                    if not file_path.is_file():
                        continue
                except (OSError, PermissionError) as e:
                    # Skip files that can't be accessed (permissions, broken symlinks, etc.)
                    stats['skipped'] += 1
                    continue
                
                if not self._should_index_file(file_path):
                    stats['skipped'] += 1
                    continue
                
                rel_path = str(file_path.relative_to(self.project_root))
                indexed_paths.add(rel_path)
                stats['scanned'] += 1
                
                # Calculate file hash
                content_hash = self._calculate_file_hash(file_path)
                
                # Check if file needs updating
                if incremental and rel_path in existing_files:
                    if existing_files[rel_path] == content_hash:
                        continue  # File unchanged
                
                # Get file metadata
                file_stat = file_path.stat()
                classification = self._classify_file(file_path)
                
                file_record = FileRecord(
                    file_path=rel_path,
                    file_name=file_path.name,
                    file_extension=file_path.suffix,
                    relative_path=rel_path,
                    absolute_path=str(file_path),
                    file_size=file_stat.st_size,
                    lines_of_code=self._count_lines(file_path),
                    content_hash=content_hash,
                    file_type=classification['file_type'],
                    file_category=classification['file_category'],
                    is_test_file='test' in file_path.name.lower(),
                    modified_at=datetime.fromtimestamp(file_stat.st_mtime),
                    last_scanned_at=datetime.now()
                )
                
                # Insert or update file record
                if rel_path in existing_files:
                    self._update_file_record(cursor, file_record)
                    stats['updated'] += 1
                else:
                    self._insert_file_record(cursor, file_record)
                    stats['added'] += 1
            
            # Mark removed files as inactive
            if incremental:
                for rel_path in existing_files.keys():
                    if rel_path not in indexed_paths:
                        cursor.execute(
                            "UPDATE files SET is_active = FALSE WHERE file_path = ?",
                            (rel_path,)
                        )
                        stats['removed'] += 1
            
            conn.commit()
            self._complete_scan(scan_id, stats)
            
            print(f"\n📊 File Index Scan Complete:")
            print(f"   Scanned: {stats['scanned']}")
            print(f"   Added: {stats['added']}")
            print(f"   Updated: {stats['updated']}")
            print(f"   Removed: {stats['removed']}")
            print(f"   Skipped: {stats['skipped']}")
            
        except Exception as e:
            self._fail_scan(scan_id, str(e))
            print(f"❌ Scan failed: {e}")
            raise
        
        return stats
    
    def _insert_file_record(self, cursor: sqlite3.Cursor, record: FileRecord):
        """Insert a new file record."""
        cursor.execute("""
            INSERT INTO files (
                file_path, file_name, file_extension, relative_path, absolute_path,
                file_size, lines_of_code, content_hash, file_type, file_category,
                is_test_file, is_active, modified_at, last_scanned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.file_path, record.file_name, record.file_extension,
            record.relative_path, record.absolute_path, record.file_size,
            record.lines_of_code, record.content_hash, record.file_type,
            record.file_category, record.is_test_file, record.is_active,
            record.modified_at, record.last_scanned_at
        ))
    
    def _update_file_record(self, cursor: sqlite3.Cursor, record: FileRecord):
        """Update an existing file record."""
        cursor.execute("""
            UPDATE files SET
                file_name = ?, file_extension = ?, absolute_path = ?,
                file_size = ?, lines_of_code = ?, content_hash = ?,
                file_type = ?, file_category = ?, is_test_file = ?,
                modified_at = ?, last_scanned_at = ?
            WHERE file_path = ?
        """, (
            record.file_name, record.file_extension, record.absolute_path,
            record.file_size, record.lines_of_code, record.content_hash,
            record.file_type, record.file_category, record.is_test_file,
            record.modified_at, record.last_scanned_at, record.file_path
        ))
    
    def _start_scan(self, scan_type: str) -> int:
        """Record start of a scan."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO scan_history (scan_type, started_at, status) VALUES (?, ?, ?)",
            (scan_type, datetime.now(), 'running')
        )
        scan_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return scan_id
    
    def _complete_scan(self, scan_id: int, stats: Dict[str, int]):
        """Record completion of a scan."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        completed_at = datetime.now()
        cursor.execute(
            "SELECT started_at FROM scan_history WHERE id = ?",
            (scan_id,)
        )
        started_at = datetime.fromisoformat(cursor.fetchone()['started_at'])
        duration = (completed_at - started_at).total_seconds()
        
        cursor.execute("""
            UPDATE scan_history SET
                completed_at = ?,
                duration_seconds = ?,
                status = ?,
                files_scanned = ?,
                files_added = ?,
                files_updated = ?,
                files_removed = ?
            WHERE id = ?
        """, (
            completed_at, duration, 'completed',
            stats['scanned'], stats['added'], stats['updated'], stats['removed'],
            scan_id
        ))
        conn.commit()
        conn.close()
    
    def _fail_scan(self, scan_id: int, error_message: str):
        """Record scan failure."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE scan_history SET status = ?, error_message = ?, completed_at = ? WHERE id = ?",
            ('failed', error_message, datetime.now(), scan_id)
        )
        conn.commit()
        conn.close()
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get complete information about a file."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM v_files_complete WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def search_files(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search files by name, purpose, or functionality."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Use FTS if query looks like full-text search
        if len(query.split()) > 1:
            cursor.execute("""
                SELECT f.* FROM files f
                JOIN file_search fs ON f.id = fs.rowid
                WHERE file_search MATCH ?
                LIMIT ?
            """, (query, limit))
        else:
            # Simple pattern search
            pattern = f"%{query}%"
            cursor.execute("""
                SELECT * FROM files
                WHERE file_path LIKE ? OR file_name LIKE ?
                LIMIT ?
            """, (pattern, pattern, limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall file index statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # File counts
        cursor.execute("SELECT COUNT(*) as total, SUM(lines_of_code) as total_lines FROM files WHERE is_active = TRUE")
        row = cursor.fetchone()
        stats['total_files'] = row['total']
        stats['total_lines_of_code'] = row['total_lines'] or 0
        
        # By type
        cursor.execute("""
            SELECT file_type, COUNT(*) as count, SUM(lines_of_code) as lines
            FROM files WHERE is_active = TRUE
            GROUP BY file_type
            ORDER BY count DESC
        """)
        stats['by_type'] = [dict(row) for row in cursor.fetchall()]
        
        # By category
        cursor.execute("""
            SELECT file_category, COUNT(*) as count
            FROM files WHERE is_active = TRUE
            GROUP BY file_category
            ORDER BY count DESC
        """)
        stats['by_category'] = [dict(row) for row in cursor.fetchall()]
        
        # Recent changes
        cursor.execute("""
            SELECT COUNT(*) as recent_changes
            FROM file_change_history
            WHERE detected_at > datetime('now', '-7 days')
        """)
        stats['recent_changes'] = cursor.fetchone()['recent_changes']
        
        # Issues
        cursor.execute("""
            SELECT severity, COUNT(*) as count
            FROM file_issues
            WHERE status = 'open'
            GROUP BY severity
        """)
        stats['open_issues'] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return stats
    
    def add_tag(self, file_path: str, tag_name: str, tag_category: str = "custom", created_by: str = "user"):
        """Add a tag to a file."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM files WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        if not row:
            print(f"File not found: {file_path}")
            return
        
        file_id = row['id']
        
        cursor.execute("""
            INSERT OR IGNORE INTO file_tags (file_id, tag_name, tag_category, created_by)
            VALUES (?, ?, ?, ?)
        """, (file_id, tag_name, tag_category, created_by))
        
        conn.commit()
        conn.close()
        print(f"✓ Tagged {file_path} with '{tag_name}'")
    
    def get_files_by_tag(self, tag_name: str) -> List[Dict[str, Any]]:
        """Get all files with a specific tag."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT f.* FROM files f
            JOIN file_tags ft ON f.id = ft.file_id
            WHERE ft.tag_name = ? AND f.is_active = TRUE
        """, (tag_name,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def close(self):
        """Close any open connections."""
        pass  # Connections are closed after each operation


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_file_index(project_root: str = ".", db_path: str = "databases/file_index.db") -> FileIndexManager:
    """Create and initialize a file index manager."""
    manager = FileIndexManager(db_path=db_path, project_root=project_root)
    return manager


def quick_scan(project_root: str = ".") -> Dict[str, int]:
    """Quick scan and index files in a project."""
    manager = create_file_index(project_root=project_root)
    return manager.scan_files(incremental=True)


if __name__ == "__main__":
    # Example usage
    print("File Index Manager - Application File Tracker\n")
    print("=" * 60)
    
    # Create manager
    manager = create_file_index()
    
    # Perform initial scan
    print("\n🔍 Scanning files...")
    stats = manager.scan_files(incremental=False)
    
    # Show statistics
    print("\n📊 Statistics:")
    overall_stats = manager.get_statistics()
    print(f"   Total Files: {overall_stats['total_files']}")
    print(f"   Total Lines: {overall_stats['total_lines_of_code']:,}")
    print(f"   Recent Changes: {overall_stats['recent_changes']}")
    
    print("\n📁 Files by Category:")
    for cat in overall_stats['by_category'][:5]:
        print(f"   {cat['file_category']}: {cat['count']} files")
    
    print("\n✓ File index is ready!")
    print(f"   Database: databases/file_index.db")
