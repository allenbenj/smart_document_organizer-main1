"""
File Index - Fast SQLite-based file indexing for LLM analysis

This module provides:
1. Fast regex-based scanning of all files → SQLite storage
2. Aggregated statistics and patterns for LLM analysis
3. Smart querying to feed relevant data to the LLM
4. Content extraction for better document classification
"""

import sqlite3
import json
import hashlib
import re
import logging
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from collections import Counter

logger = logging.getLogger(__name__)

# Import content extractor
try:
    from .content_extractor import ContentExtractor, get_extractor
    CONTENT_EXTRACTION_AVAILABLE = True
except ImportError:
    CONTENT_EXTRACTION_AVAILABLE = False
    logger.info("Content extraction not available")


@dataclass
class IndexedFile:
    """A file in the index"""
    file_id: str
    path: str
    name: str
    extension: str
    size: int
    modified: str
    content_hash: Optional[str]
    entities: Dict[str, str]
    indexed_at: str


class FileIndex:
    """
    SQLite-based file index for fast scanning and LLM analysis.
    
    Workflow:
    1. scan_directory() - Fast regex extraction → SQLite
    2. get_statistics() - Aggregate patterns for LLM
    3. analyze_with_llm() - LLM reviews aggregated data
    4. apply_recommendations() - Execute LLM suggestions
    """
    
    def __init__(self, db_path: Path):
        """Initialize the file index"""
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Create index tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                -- Main file index
                CREATE TABLE IF NOT EXISTS files (
                    file_id TEXT PRIMARY KEY,
                    path TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    extension TEXT,
                    size INTEGER,
                    modified TEXT,
                    content_hash TEXT,
                    parent_folder TEXT,
                    depth INTEGER,
                    doc_type TEXT,
                    quality_score REAL,
                    suggested_name TEXT,
                    indexed_at TEXT
                );
            """)
            
            # Migrate existing databases - add new columns if they don't exist
            try:
                cursor = conn.execute("PRAGMA table_info(files)")
                columns = [row[1] for row in cursor.fetchall()]
                
                if 'doc_type' not in columns:
                    conn.execute("ALTER TABLE files ADD COLUMN doc_type TEXT")
                    logger.info("Added doc_type column to files table")
                
                if 'quality_score' not in columns:
                    conn.execute("ALTER TABLE files ADD COLUMN quality_score REAL")
                    logger.info("Added quality_score column to files table")
                
                if 'suggested_name' not in columns:
                    conn.execute("ALTER TABLE files ADD COLUMN suggested_name TEXT")
                    logger.info("Added suggested_name column to files table")
                
                conn.commit()
            except Exception as e:
                logger.debug(f"Migration check: {e}")
            
            # Continue with rest of schema
            conn.executescript("""
                
                -- Extracted entities per file
                CREATE TABLE IF NOT EXISTS file_entities (
                    file_id TEXT,
                    entity_type TEXT,
                    entity_value TEXT,
                    confidence REAL DEFAULT 1.0,
                    PRIMARY KEY (file_id, entity_type),
                    FOREIGN KEY (file_id) REFERENCES files(file_id)
                );
                
                -- Folder statistics
                CREATE TABLE IF NOT EXISTS folder_stats (
                    folder_path TEXT PRIMARY KEY,
                    file_count INTEGER,
                    total_size INTEGER,
                    extensions TEXT,  -- JSON list
                    entity_summary TEXT,  -- JSON summary
                    updated_at TEXT
                );
                
                -- LLM analysis results
                CREATE TABLE IF NOT EXISTS llm_analysis (
                    analysis_id TEXT PRIMARY KEY,
                    analysis_type TEXT,  -- structure, naming, clustering
                    input_summary TEXT,
                    recommendations TEXT,  -- JSON
                    applied BOOLEAN DEFAULT FALSE,
                    created_at TEXT
                );
                
                -- Proposed actions
                CREATE TABLE IF NOT EXISTS proposed_actions (
                    action_id TEXT PRIMARY KEY,
                    analysis_id TEXT,
                    action_type TEXT,  -- rename, move, create_folder
                    file_id TEXT,
                    current_value TEXT,
                    proposed_value TEXT,
                    confidence REAL,
                    status TEXT DEFAULT 'pending',  -- pending, approved, rejected, applied
                    FOREIGN KEY (analysis_id) REFERENCES llm_analysis(analysis_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);
                CREATE INDEX IF NOT EXISTS idx_files_parent ON files(parent_folder);
                CREATE INDEX IF NOT EXISTS idx_entities_type ON file_entities(entity_type);
                CREATE INDEX IF NOT EXISTS idx_entities_value ON file_entities(entity_value);
                CREATE INDEX IF NOT EXISTS idx_actions_status ON proposed_actions(status);
            """)
    
    def scan_directory(
        self,
        root_path: Path,
        patterns: List[Tuple[str, str]],  # [(pattern_type, regex), ...]
        recursive: bool = True,
        extensions: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
        reset_root: bool = False,
    ) -> Dict[str, Any]:
        """
        Fast scan directory and index all files.
        
        Args:
            root_path: Directory to scan
            patterns: List of (type, regex) patterns to extract
            recursive: Scan recursively
            extensions: Filter by extensions
            progress_callback: Function(processed, total, current_file)
            
        Returns:
            Scan statistics
        """
        import time
        start_time = time.time()

        if reset_root:
            self.clear_root(root_path)

        def iter_files(path: Path, recursive_scan: bool):
            if recursive_scan:
                def onerror(err):
                    logger.warning(f"Skipping unreadable path: {err}")
                for root, _dirs, files in os.walk(path, onerror=onerror):
                    for name in files:
                        yield Path(root) / name
            else:
                try:
                    for entry in path.iterdir():
                        if entry.is_file():
                            yield entry
                except FileNotFoundError as e:
                    logger.warning(f"Root path not found: {e}")

        # Compile patterns once
        compiled_patterns = []
        for pattern_type, regex in patterns:
            try:
                compiled_patterns.append((pattern_type, re.compile(regex)))
            except re.error as e:
                logger.warning(f"Invalid pattern {pattern_type}: {e}")
        
        # Count files first
        print("Counting files...")
        file_count = 0
        glob_pattern = "**/*" if recursive else "*"
        
        for f in iter_files(root_path, recursive):
            if extensions is None or f.suffix.lower() in extensions:
                file_count += 1
                if file_count % 10000 == 0:
                    print(f"\r  Counted {file_count:,}...", end="", flush=True)
        
        print(f"\r✓ Found {file_count:,} files to index")
        
        # Index files
        stats = {
            "total": file_count,
            "indexed": 0,
            "errors": 0,
            "entities_found": Counter(),
            "extensions": Counter(),
            "folders": set()
        }
        
        with sqlite3.connect(self.db_path) as conn:
            processed = 0
            batch = []
            batch_entities = []
            
            for file_path in iter_files(root_path, recursive):
                if extensions and file_path.suffix.lower() not in extensions:
                    continue
                
                processed += 1
                
                # Progress update
                if progress_callback and processed % 100 == 0:
                    progress_callback(processed, file_count, file_path.name)
                
                try:
                    # Generate file ID
                    file_id = hashlib.md5(str(file_path).encode()).hexdigest()
                    
                    # Get file info
                    stat = file_path.stat()
                    relative_path = file_path.relative_to(root_path)
                    parent = str(relative_path.parent) if relative_path.parent != Path('.') else ''
                    depth = len(relative_path.parts) - 1
                    
                    # Content extraction for richer classification
                    doc_type = None
                    quality_score = None
                    suggested_name = None
                    content_entities = {}
                    
                    if CONTENT_EXTRACTION_AVAILABLE:
                        extractor = get_extractor()
                        try:
                            # Use quick classify for speed
                            classify_result = extractor.quick_classify(file_path)
                            doc_type = classify_result.get('doc_type')
                            quality_score = classify_result.get('quality_score', 0.5)
                            content_entities = classify_result.get('entities', {})
                            
                            # Generate suggested name if poor quality
                            if quality_score < 0.4:
                                full_result = extractor.extract_content(file_path, max_chars=3000)
                                suggested_name = full_result.get('suggested_name')
                        except Exception as e:
                            logger.debug(f"Content extraction failed for {file_path}: {e}")
                    
                    # Add to batch (with new columns)
                    batch.append((
                        file_id,
                        str(file_path),
                        file_path.name,
                        file_path.suffix.lower(),
                        stat.st_size,
                        datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        None,  # content_hash - skip for speed
                        parent,
                        depth,
                        doc_type,
                        quality_score,
                        suggested_name,
                        datetime.now().isoformat()
                    ))
                    
                    stats["extensions"][file_path.suffix.lower()] += 1
                    stats["folders"].add(parent)
                    
                    # Extract entities from filename and content
                    text_to_search = file_path.name
                    
                    # For text files, also search content (if content extraction didn't do it)
                    if file_path.suffix.lower() in ['.txt', '.md', '.py', '.json', '.csv', '.log']:
                        try:
                            content = file_path.read_text(encoding='utf-8', errors='ignore')[:5000]
                            text_to_search += "\n" + content
                        except Exception:
                            pass
                    
                    # Apply regex patterns
                    for pattern_type, compiled in compiled_patterns:
                        match = compiled.search(text_to_search)
                        if match:
                            value = match.group(1) if match.groups() else match.group(0)
                            batch_entities.append((file_id, pattern_type, value, 1.0))
                            stats["entities_found"][pattern_type] += 1
                    
                    # Add entities from content extraction
                    for entity_type, values in content_entities.items():
                        for value in values[:3]:  # Limit per type
                            batch_entities.append((file_id, entity_type, str(value), 0.8))
                            stats["entities_found"][entity_type] = stats["entities_found"].get(entity_type, 0) + 1
                    
                    # Track doc_type as entity too
                    if doc_type:
                        batch_entities.append((file_id, 'doc_type', doc_type, 0.9))
                        stats["entities_found"]['doc_type'] = stats["entities_found"].get('doc_type', 0) + 1
                    
                    stats["indexed"] += 1
                    
                    # Commit in batches
                    if len(batch) >= 1000:
                        self._commit_batch(conn, batch, batch_entities)
                        batch = []
                        batch_entities = []
                        
                except Exception as e:
                    stats["errors"] += 1
                    logger.debug(f"Error indexing {file_path}: {e}")
            
            # Final batch
            if batch:
                self._commit_batch(conn, batch, batch_entities)
        
        # Update folder stats
        self._update_folder_stats()
        
        stats["elapsed"] = time.time() - start_time
        stats["rate"] = stats["indexed"] / stats["elapsed"] if stats["elapsed"] > 0 else 0
        stats["folders"] = len(stats["folders"])
        
        return stats
    
    def _commit_batch(self, conn, files_batch, entities_batch):
        """Commit a batch of files and entities"""
        conn.executemany("""
            INSERT OR REPLACE INTO files 
            (file_id, path, name, extension, size, modified, content_hash, parent_folder, depth, doc_type, quality_score, suggested_name, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, files_batch)
        
        if entities_batch:
            conn.executemany("""
                INSERT OR REPLACE INTO file_entities (file_id, entity_type, entity_value, confidence)
                VALUES (?, ?, ?, ?)
            """, entities_batch)
        
        conn.commit()
    
    def _update_folder_stats(self):
        """Update aggregated folder statistics"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get folder aggregates
            folders = conn.execute("""
                SELECT parent_folder, 
                       COUNT(*) as file_count,
                       SUM(size) as total_size,
                       GROUP_CONCAT(DISTINCT extension) as extensions
                FROM files
                GROUP BY parent_folder
            """).fetchall()
            
            for folder in folders:
                # Get entity summary for folder
                entities = conn.execute("""
                    SELECT fe.entity_type, fe.entity_value, COUNT(*) as count
                    FROM file_entities fe
                    JOIN files f ON fe.file_id = f.file_id
                    WHERE f.parent_folder = ?
                    GROUP BY fe.entity_type, fe.entity_value
                    ORDER BY count DESC
                    LIMIT 20
                """, (folder['parent_folder'],)).fetchall()
                
                entity_summary = {}
                for e in entities:
                    if e['entity_type'] not in entity_summary:
                        entity_summary[e['entity_type']] = []
                    entity_summary[e['entity_type']].append({
                        "value": e['entity_value'],
                        "count": e['count']
                    })
                
                conn.execute("""
                    INSERT OR REPLACE INTO folder_stats 
                    (folder_path, file_count, total_size, extensions, entity_summary, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    folder['parent_folder'],
                    folder['file_count'],
                    folder['total_size'],
                    folder['extensions'],
                    json.dumps(entity_summary),
                    datetime.now().isoformat()
                ))
            
            conn.commit()

    def clear_root(self, root_path: Path) -> None:
        """Remove indexed rows under the given root path."""
        root_filter, root_params = self._build_root_filter(root_path)
        if not root_filter:
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM file_entities
                WHERE file_id IN (
                    SELECT file_id FROM files
                    WHERE LOWER(path) LIKE LOWER(?)
                )
            """, root_params)
            conn.execute(
                "DELETE FROM files WHERE LOWER(path) LIKE LOWER(?)",
                root_params,
            )
            conn.commit()
    
    def get_statistics(self, root_path: Optional[Path] = None) -> Dict[str, Any]:
        """Get aggregated statistics for LLM analysis."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            stats = {}
            root_filter, root_params = self._build_root_filter(root_path)
            
            # Total counts
            row = conn.execute(
                f"SELECT COUNT(*) as count, SUM(size) as size FROM files{root_filter}",
                root_params,
            ).fetchone()
            stats["total_files"] = row['count']
            stats["total_size"] = row['size'] or 0
            stats["total_size_gb"] = round(stats["total_size"] / (1024**3), 2)
            
            # Extensions distribution
            extensions = conn.execute(f"""
                SELECT extension, COUNT(*) as count, SUM(size) as size
                FROM files
                {root_filter}
                GROUP BY extension
                ORDER BY count DESC
                LIMIT 20
            """, root_params).fetchall()
            stats["extensions"] = [dict(e) for e in extensions]
            
            # Folder structure
            if root_path:
                folders = conn.execute("""
                    SELECT parent_folder as folder_path,
                           COUNT(*) as file_count,
                           SUM(size) as total_size,
                           GROUP_CONCAT(DISTINCT extension) as extensions
                    FROM files
                    WHERE LOWER(path) LIKE LOWER(?)
                    GROUP BY parent_folder
                    ORDER BY file_count DESC
                    LIMIT 50
                """, root_params).fetchall()
                stats["top_folders"] = [
                    {
                        "folder_path": f["folder_path"],
                        "file_count": f["file_count"],
                        "total_size": f["total_size"],
                        "extensions": f["extensions"],
                        "entity_summary": {},
                    }
                    for f in folders
                ]
            else:
                folders = conn.execute("""
                    SELECT folder_path, file_count, total_size, extensions, entity_summary
                    FROM folder_stats
                    ORDER BY file_count DESC
                    LIMIT 50
                """).fetchall()
                stats["top_folders"] = [dict(f) for f in folders]
            
            # Entity distribution
            if root_path:
                entities = conn.execute("""
                    SELECT fe.entity_type, fe.entity_value, COUNT(*) as count
                    FROM file_entities fe
                    JOIN files f ON f.file_id = fe.file_id
                    WHERE LOWER(f.path) LIKE LOWER(?)
                    GROUP BY fe.entity_type, fe.entity_value
                    ORDER BY count DESC
                    LIMIT 100
                """, root_params).fetchall()
            else:
                entities = conn.execute("""
                    SELECT entity_type, entity_value, COUNT(*) as count
                    FROM file_entities
                    GROUP BY entity_type, entity_value
                    ORDER BY count DESC
                    LIMIT 100
                """).fetchall()
            
            entity_summary = {}
            for e in entities:
                if e['entity_type'] not in entity_summary:
                    entity_summary[e['entity_type']] = []
                entity_summary[e['entity_type']].append({
                    "value": e['entity_value'],
                    "count": e['count']
                })
            stats["entities"] = entity_summary
            
            # Depth distribution
            depths = conn.execute(f"""
                SELECT depth, COUNT(*) as count
                FROM files
                {root_filter}
                GROUP BY depth
                ORDER BY depth
            """, root_params).fetchall()
            stats["depth_distribution"] = [dict(d) for d in depths]
            
            # Potential duplicates (same name, different folders)
            duplicates = conn.execute(f"""
                SELECT name, COUNT(*) as count, GROUP_CONCAT(parent_folder, ' | ') as folders
                FROM files
                {root_filter}
                GROUP BY name
                HAVING count > 1
                ORDER BY count DESC
                LIMIT 50
            """, root_params).fetchall()
            stats["potential_duplicates"] = [dict(d) for d in duplicates]
            
            # Naming patterns (common prefixes/suffixes)
            stats["naming_samples"] = self._analyze_naming_patterns(conn, root_path=root_path)
            
            # Content extraction insights (if available)
            stats["content_analysis"] = self._get_content_analysis(conn, root_path=root_path)
            
            return stats

    def _build_root_filter(self, root_path: Optional[Path]) -> Tuple[str, List[Any]]:
        """Build SQL filter and params for a root path."""
        if not root_path:
            return "", []
        root_str = str(Path(root_path).resolve())
        root_prefix = root_str.rstrip("\\/") + os.sep + "%"
        return " WHERE LOWER(path) LIKE LOWER(?)", [root_prefix]
    
    def _get_content_analysis(self, conn, root_path: Optional[Path] = None) -> Dict[str, Any]:
        """Get statistics from content extraction."""
        try:
            # Check if quality_score column exists
            cursor = conn.execute("PRAGMA table_info(files)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'quality_score' not in columns:
                return {"available": False}
            
            root_filter, root_params = self._build_root_filter(root_path)
            where_clause = "WHERE quality_score IS NOT NULL"
            params: List[Any] = []
            if root_filter:
                where_clause += " AND LOWER(path) LIKE LOWER(?)"
                params = root_params

            # Get quality distribution
            quality_stats = conn.execute(f"""
                SELECT 
                    COUNT(*) as total,
                    AVG(quality_score) as avg_score,
                    SUM(CASE WHEN quality_score < 0.3 THEN 1 ELSE 0 END) as very_poor,
                    SUM(CASE WHEN quality_score >= 0.3 AND quality_score < 0.5 THEN 1 ELSE 0 END) as poor,
                    SUM(CASE WHEN quality_score >= 0.5 AND quality_score < 0.7 THEN 1 ELSE 0 END) as ok,
                    SUM(CASE WHEN quality_score >= 0.7 THEN 1 ELSE 0 END) as good,
                    SUM(CASE WHEN suggested_name IS NOT NULL AND suggested_name != '' THEN 1 ELSE 0 END) as needs_rename
                FROM files
                {where_clause}
            """, params).fetchone()
            
            # Get document type distribution
            doc_types = conn.execute(f"""
                SELECT doc_type, COUNT(*) as count
                FROM files
                WHERE doc_type IS NOT NULL AND doc_type != ''
                {("AND LOWER(path) LIKE LOWER(?)" if root_filter else "")}
                GROUP BY doc_type
                ORDER BY count DESC
                LIMIT 20
            """, params).fetchall()
            
            # Sample poorly named files
            poor_examples = conn.execute(f"""
                SELECT name, parent_folder, quality_score, doc_type, suggested_name
                FROM files
                WHERE quality_score IS NOT NULL AND quality_score < 0.4
                {("AND LOWER(path) LIKE LOWER(?)" if root_filter else "")}
                ORDER BY quality_score ASC
                LIMIT 10
            """, params).fetchall()
            
            return {
                "available": True,
                "filename_quality": {
                    "total_analyzed": quality_stats['total'] or 0,
                    "average_score": round(quality_stats['avg_score'] or 0, 2),
                    "very_poor_count": quality_stats['very_poor'] or 0,
                    "poor_count": quality_stats['poor'] or 0,
                    "ok_count": quality_stats['ok'] or 0,
                    "good_count": quality_stats['good'] or 0,
                    "needs_rename": quality_stats['needs_rename'] or 0,
                },
                "document_types": [{"type": d['doc_type'], "count": d['count']} for d in doc_types],
                "poor_filename_examples": [
                    {
                        "current": p['name'],
                        "folder": p['parent_folder'],
                        "score": round(p['quality_score'], 2),
                        "detected_type": p['doc_type'],
                        "suggested": p['suggested_name']
                    }
                    for p in poor_examples
                ]
            }
        except Exception as e:
            logger.debug(f"Content analysis failed: {e}")
            return {"available": False}
    
    def _analyze_naming_patterns(self, conn, root_path: Optional[Path] = None) -> Dict[str, Any]:
        """Analyze file naming patterns."""
        root_filter, root_params = self._build_root_filter(root_path)
        names = conn.execute(
            f"SELECT name FROM files{root_filter} LIMIT 1000",
            root_params,
        ).fetchall()
        names = [n[0] for n in names]
        
        # Common prefixes
        prefixes = Counter()
        suffixes = Counter()
        separators = Counter()
        
        for name in names:
            stem = Path(name).stem
            
            # Check for date prefixes
            if re.match(r'^\d{4}[-_]?\d{2}[-_]?\d{2}', stem):
                prefixes["date_prefix"] += 1
            elif re.match(r'^\d{2}[-_]?\d{2}[-_]?\d{4}', stem):
                prefixes["date_prefix_mdy"] += 1
            
            # Check separators
            if '_' in stem:
                separators["underscore"] += 1
            if '-' in stem:
                separators["hyphen"] += 1
            if ' ' in stem:
                separators["space"] += 1
            
            # Common suffixes
            parts = re.split(r'[_\-\s]', stem)
            if len(parts) > 1:
                suffixes[parts[-1].lower()] += 1
        
        return {
            "prefixes": dict(prefixes.most_common(10)),
            "suffixes": dict(suffixes.most_common(20)),
            "separators": dict(separators)
        }
    
    def get_files_for_analysis(
        self,
        folder: Optional[str] = None,
        extension: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get files matching criteria for detailed analysis"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = "SELECT f.*, GROUP_CONCAT(fe.entity_type || ':' || fe.entity_value, '; ') as entities FROM files f"
            query += " LEFT JOIN file_entities fe ON f.file_id = fe.file_id"
            
            conditions = []
            params = []
            
            if folder:
                conditions.append("f.parent_folder = ?")
                params.append(folder)
            if extension:
                conditions.append("f.extension = ?")
                params.append(extension)
            if entity_type:
                conditions.append("fe.entity_type = ?")
                params.append(entity_type)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " GROUP BY f.file_id"
            query += f" LIMIT {limit}"
            
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
    
    def store_llm_analysis(
        self,
        analysis_type: str,
        input_summary: str,
        recommendations: Dict[str, Any]
    ) -> str:
        """Store LLM analysis results"""
        import uuid
        analysis_id = str(uuid.uuid4())
        
        def to_string(val):
            """Convert value to string, handling lists and other types"""
            if val is None:
                return None
            if isinstance(val, list):
                return json.dumps(val)
            if isinstance(val, dict):
                return json.dumps(val)
            return str(val)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO llm_analysis (analysis_id, analysis_type, input_summary, recommendations, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                analysis_id,
                analysis_type,
                input_summary,
                json.dumps(recommendations),
                datetime.now().isoformat()
            ))
            
            # Store proposed actions - handle various LLM response formats
            for action in recommendations.get("actions", []):
                action_id = str(uuid.uuid4())
                action_type = action.get("type", "unknown")
                
                # Extract current/proposed based on action type
                if action_type in ["create_folder", "create_folders", "create_directory"]:
                    current = None
                    proposed = action.get("path", action.get("name", ""))
                elif action_type in ["move_pattern", "move", "move_files", "relocate", "reorganize", "reorganize_by_year", "archive"]:
                    current = action.get("from_pattern", action.get("from", action.get("file_pattern", action.get("source", action.get("files", "")))))
                    proposed = action.get("to", action.get("destination", action.get("target", "")))
                elif action_type in ["rename_pattern", "rename", "rename_files"]:
                    current = action.get("current_pattern", action.get("current", action.get("file", action.get("files", ""))))
                    proposed = action.get("new_pattern", action.get("new", action.get("suggested", action.get("rename_to", ""))))
                elif action_type in ["delete_files", "delete"]:
                    current = action.get("pattern", action.get("files", action.get("target", "")))
                    proposed = "DELETE"
                elif action_type in ["consolidate_folders", "consolidate", "consolidate_duplicates", "deduplicate"]:
                    current = action.get("folders", action.get("from", action.get("duplicates", action.get("files", ""))))
                    proposed = action.get("into", action.get("to", action.get("keep", "")))
                else:
                    # Generic fallback
                    current = action.get("current", action.get("from", action.get("source", str(action))))
                    proposed = action.get("proposed", action.get("to", action.get("target", "")))
                
                # Get reason/description
                reason = action.get("reason", action.get("description", action.get("purpose", "")))
                
                conn.execute("""
                    INSERT INTO proposed_actions 
                    (action_id, analysis_id, action_type, file_id, current_value, proposed_value, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    action_id,
                    analysis_id,
                    action_type,
                    to_string(reason),  # Store reason in file_id for now
                    to_string(current),
                    to_string(proposed),
                    action.get("confidence", 0.5)
                ))
        
        return analysis_id

    def create_analysis_record(
        self,
        analysis_type: str,
        input_summary: str,
        recommendations: Dict[str, Any],
    ) -> str:
        """Create an analysis record without LLM processing."""
        import uuid
        analysis_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO llm_analysis (analysis_id, analysis_type, input_summary, recommendations, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    analysis_type,
                    input_summary,
                    json.dumps(recommendations),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        return analysis_id

    def add_proposed_action(
        self,
        analysis_id: str,
        action_type: str,
        file_id: Optional[str],
        current_value: str,
        proposed_value: str,
        confidence: float = 0.5,
    ) -> str:
        """Insert a proposed action into the queue."""
        import uuid
        action_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO proposed_actions
                (action_id, analysis_id, action_type, file_id, current_value, proposed_value, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    analysis_id,
                    action_type,
                    file_id,
                    current_value,
                    proposed_value,
                    confidence,
                ),
            )
            conn.commit()
        return action_id
    
    def get_pending_actions(self, action_type: Optional[str] = None) -> List[Dict]:
        """Get pending actions from LLM analysis"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = """
                SELECT pa.*, f.path, f.name
                FROM proposed_actions pa
                LEFT JOIN files f ON pa.file_id = f.file_id
                WHERE pa.status = 'pending'
            """
            if action_type:
                query += " AND pa.action_type = ?"
                rows = conn.execute(query, (action_type,)).fetchall()
            else:
                rows = conn.execute(query).fetchall()
            
            return [dict(r) for r in rows]
    
    def update_action_status(self, action_id: str, status: str):
        """Update action status (approved, rejected, applied)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE proposed_actions SET status = ? WHERE action_id = ?",
                (status, action_id)
            )

    def clear_pending_actions(self, action_types: Optional[List[str]] = None) -> int:
        """Clear pending actions, optionally filtered by action_type."""
        with sqlite3.connect(self.db_path) as conn:
            if action_types:
                placeholders = ",".join("?" for _ in action_types)
                query = f"DELETE FROM proposed_actions WHERE status = 'pending' AND action_type IN ({placeholders})"
                cur = conn.execute(query, action_types)
            else:
                cur = conn.execute("DELETE FROM proposed_actions WHERE status = 'pending'")
            conn.commit()
            return cur.rowcount


class SmartAnalyzer:
    """
    Uses LLM to analyze indexed data and make smart recommendations.
    """
    
    def __init__(self, file_index: FileIndex, model_config: Any):
        """Initialize with file index and model config"""
        self.index = file_index
        self.model_config = model_config
        self._model = None
    
    def _get_model(self):
        """Get or initialize the LLM"""
        if self._model is None:
            from file_organizer.models.openai_model import OpenAIModel
            self._model = OpenAIModel(self.model_config)
            self._model.initialize()
        return self._model
    
    def analyze_structure(self, root_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Have LLM analyze the folder structure and suggest improvements.
        """
        stats = self.index.get_statistics(root_path=root_path)
        
        # Prepare summary for LLM
        summary = f"""
FILE INDEX SUMMARY
==================
Total Files: {stats['total_files']:,}
Total Size: {stats['total_size_gb']} GB
Unique Folders: {len(stats['top_folders'])}

TOP FILE EXTENSIONS:
{json.dumps(stats['extensions'][:10], indent=2)}

TOP FOLDERS (by file count):
{json.dumps(stats['top_folders'][:20], indent=2)}

EXTRACTED ENTITIES:
{json.dumps(stats['entities'], indent=2)}

DEPTH DISTRIBUTION:
{json.dumps(stats['depth_distribution'], indent=2)}

POTENTIAL DUPLICATES:
{json.dumps(stats['potential_duplicates'][:20], indent=2)}

NAMING PATTERNS:
{json.dumps(stats['naming_samples'], indent=2)}

CONTENT ANALYSIS (from document text extraction):
{json.dumps(stats.get('content_analysis', {}), indent=2)}
"""
        
        prompt = f"""You are an expert file organization consultant. Analyze this file index summary and provide actionable recommendations.

{summary}

Based on this data:

1. STRUCTURE ANALYSIS
- What patterns do you see in the current organization?
- What problems exist (overcrowded folders, inconsistent naming, etc.)?
- Pay attention to the CONTENT ANALYSIS which shows:
  * Filename quality scores (files with poor/generic names)
  * Document types detected from content (motion, order, complaint, etc.)
  * Suggested renames for poorly named files

2. RECOMMENDED FOLDER STRUCTURE
- Suggest an optimal folder hierarchy based on the entities found
- Use the detected document types to create type-based subfolders
- Consider case numbers, dates, document types from content analysis

3. NAMING CONVENTION
- Based on the naming patterns and quality analysis, suggest improvements
- Format: what components should be in filenames and in what order
- Address the poorly named files shown in content_analysis

4. SPECIFIC ACTIONS
- List specific folders to create (use document types from content analysis)
- List files that should be moved (group by destination and detected type)
- List rename patterns for poor quality filenames (reference suggested_name data)
- Prioritize fixing the {stats.get('content_analysis', {}).get('filename_quality', {}).get('needs_rename', 0)} files that need better names

Respond with JSON:
{{
    "analysis": {{
        "patterns_found": ["pattern1", "pattern2"],
        "problems_identified": ["problem1", "problem2"],
        "organization_score": 0-100
    }},
    "recommended_structure": {{
        "folders_to_create": [
            {{"path": "folder/path", "purpose": "description"}}
        ],
        "hierarchy_template": "describe the hierarchy"
    }},
    "naming_convention": {{
        "pattern": "{{date}}_{{case}}_{{type}}.{{ext}}",
        "components": ["date", "case_number", "document_type"],
        "separator": "_",
        "date_format": "YYYY-MM-DD"
    }},
    "actions": [
        {{"type": "create_folder", "path": "folder/path", "reason": "why"}},
        {{"type": "move_pattern", "from_pattern": "*.pdf in root", "to": "Documents/PDFs", "estimated_count": 100}},
        {{"type": "rename_pattern", "current_pattern": "doc*.txt", "new_pattern": "{{date}}_document.txt", "estimated_count": 50}}
    ],
    "priority_recommendations": ["most important action first"]
}}
"""
        
        model = self._get_model()
        response = model.generate(prompt)
        
        try:
            recommendations = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                recommendations = json.loads(match.group())
            else:
                recommendations = {"error": "Failed to parse LLM response", "raw": response}
        
        # Store analysis
        analysis_id = self.index.store_llm_analysis(
            "structure",
            summary[:5000],
            recommendations
        )
        
        recommendations["analysis_id"] = analysis_id
        return recommendations
    
    def analyze_folder(self, folder_path: str) -> Dict[str, Any]:
        """
        Detailed analysis of a specific folder.
        """
        files = self.index.get_files_for_analysis(folder=folder_path, limit=200)
        
        if not files:
            return {"error": f"No files found in {folder_path}"}
        
        # Prepare file list for LLM
        file_summary = []
        for f in files[:100]:  # Limit to 100 for prompt size
            file_summary.append({
                "name": f["name"],
                "extension": f["extension"],
                "size": f["size"],
                "entities": f.get("entities", "")
            })
        
        prompt = f"""Analyze this folder and suggest organization improvements.

FOLDER: {folder_path}
FILE COUNT: {len(files)}

FILES:
{json.dumps(file_summary, indent=2)}

Provide:
1. What types of documents are in this folder?
2. Should they be split into subfolders? If so, how?
3. Are there files that don't belong here?
4. What naming improvements would help?

Respond with JSON:
{{
    "folder_purpose": "what this folder contains",
    "document_types_found": ["type1", "type2"],
    "suggested_subfolders": [
        {{"name": "subfolder", "purpose": "description", "file_pattern": "which files go here"}}
    ],
    "misplaced_files": [
        {{"file": "filename", "suggested_location": "where it should go"}}
    ],
    "naming_issues": ["issue1", "issue2"],
    "actions": [
        {{"type": "create_subfolder", "name": "subfolder"}},
        {{"type": "move", "file_pattern": "*.xyz", "to": "subfolder"}}
    ]
}}
"""
        
        model = self._get_model()
        response = model.generate(prompt)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw_response": response}
    
    def suggest_renames_for_pattern(
        self,
        file_pattern: str = None,
        extension: str = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get rename suggestions for files matching a pattern.
        """
        files = self.index.get_files_for_analysis(extension=extension, limit=limit)
        
        if not files:
            return {"error": "No files found"}
        
        file_list = [{"name": f["name"], "entities": f.get("entities", "")} for f in files]
        
        prompt = f"""Suggest better filenames for these files.

FILES:
{json.dumps(file_list, indent=2)}

For each file that needs renaming, suggest a new name following this convention:
- Start with date (YYYY-MM-DD) if available
- Include case number if available
- Include document type
- Use underscores as separators
- Keep the original extension

Respond with JSON:
{{
    "naming_convention": "description of the pattern",
    "renames": [
        {{"current": "old_name.ext", "suggested": "new_name.ext", "reason": "why"}}
    ],
    "files_already_good": ["filename1", "filename2"]
}}
"""
        
        model = self._get_model()
        response = model.generate(prompt)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw_response": response}
    
    def cleanup(self):
        """Cleanup LLM resources"""
        if self._model:
            self._model.cleanup()
            self._model = None
