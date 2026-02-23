"""
Duplicate Detection Module

This module implements comprehensive duplicate detection:
- Exact duplicates (same content hash)
- Near-duplicates (similar content)
- Perceptual duplicates (for images)
- Semantic duplicates (similar meaning)
- Deduplication strategies
"""

import logging
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    import imagehash
    from PIL import Image
    PERCEPTUAL_HASH_AVAILABLE = True
except ImportError:
    PERCEPTUAL_HASH_AVAILABLE = False
    logger.info("imagehash not available. Install with: pip install imagehash pillow")


@dataclass
class DuplicateGroup:
    """A group of duplicate files"""
    duplicate_id: str
    files: List[str]  # file_ids
    similarity_type: str
    similarity_score: float
    recommended_action: str  # keep_first, keep_newest, keep_largest, manual_review


class DuplicateDetector:
    """
    Detect and manage duplicate files.
    
    Features:
    - Exact duplicate detection via SHA-256
    - Content-based duplicate detection
    - Perceptual hashing for images
    - Semantic similarity for documents
    - Smart deduplication recommendations
    """
    
    def __init__(self, db_conn: sqlite3.Connection):
        """
        Initialize duplicate detector.
        
        Args:
            db_conn: Database connection
        """
        self.conn = db_conn
    
    def calculate_file_hashes(self, file_path: Path, file_id: str) -> Dict[str, str]:
        """
        Calculate all hash types for a file.
        
        Args:
            file_path: Path to file
            file_id: File identifier
            
        Returns:
            Dictionary of hash types to hash values
        """
        hashes = {}
        
        try:
            # Read file content
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # MD5
            hashes['md5_hash'] = hashlib.md5(content).hexdigest()
            
            # SHA-256
            hashes['sha256_hash'] = hashlib.sha256(content).hexdigest()
            
            # Content hash (normalize text content)
            if file_path.suffix.lower() in ['.txt', '.md', '.py', '.java', '.cpp', '.c']:
                try:
                    text = content.decode('utf-8', errors='ignore')
                    # Normalize: lowercase, remove whitespace variations
                    normalized = ' '.join(text.lower().split())
                    hashes['content_hash'] = hashlib.md5(normalized.encode()).hexdigest()
                except Exception as e:
                    logger.debug(f"Content normalization failed: {e}")
            
            # Perceptual hash for images
            if PERCEPTUAL_HASH_AVAILABLE and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
                try:
                    img = Image.open(file_path)
                    # Average hash (fast, good for similar images)
                    avg_hash = imagehash.average_hash(img)
                    hashes['perceptual_hash'] = str(avg_hash)
                except Exception as e:
                    logger.debug(f"Perceptual hash failed: {e}")
            
        except Exception as e:
            logger.error(f"Hash calculation failed for {file_path}: {e}")
        
        return hashes
    
    def store_file_hashes(self, file_id: str, hashes: Dict[str, str]):
        """Store file hashes in database"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO file_hashes (
                file_id, md5_hash, sha256_hash, content_hash,
                perceptual_hash, hash_updated_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            file_id,
            hashes.get('md5_hash'),
            hashes.get('sha256_hash'),
            hashes.get('content_hash'),
            hashes.get('perceptual_hash'),
            datetime.now().isoformat()
        ))
        
        self.conn.commit()
        logger.debug(f"Stored hashes for {file_id}")
    
    def find_exact_duplicates(self) -> List[DuplicateGroup]:
        """
        Find exact duplicates based on SHA-256 hash.
        
        Returns:
            List of duplicate groups
        """
        cursor = self.conn.cursor()
        
        # Find files with same SHA-256 hash
        cursor.execute("""
            SELECT sha256_hash, GROUP_CONCAT(file_id) as file_ids, COUNT(*) as count
            FROM file_hashes
            WHERE sha256_hash IS NOT NULL
            GROUP BY sha256_hash
            HAVING count > 1
        """)
        
        duplicate_groups = []
        
        for row in cursor.fetchall():
            sha256 = row['sha256_hash']
            file_ids = row['file_ids'].split(',')
            
            group = DuplicateGroup(
                duplicate_id=f"exact_{sha256[:16]}",
                files=file_ids,
                similarity_type="exact",
                similarity_score=1.0,
                recommended_action=self._recommend_action(file_ids, "exact")
            )
            
            duplicate_groups.append(group)
            
            # Store in database
            self._store_duplicate_group(group)
        
        logger.info(f"Found {len(duplicate_groups)} exact duplicate groups")
        return duplicate_groups
    
    def find_content_duplicates(self, threshold: float = 0.95) -> List[DuplicateGroup]:
        """
        Find near-duplicates based on content hash.
        
        Args:
            threshold: Minimum similarity for content duplicates
            
        Returns:
            List of duplicate groups
        """
        cursor = self.conn.cursor()
        
        # Find files with same content hash
        cursor.execute("""
            SELECT content_hash, GROUP_CONCAT(file_id) as file_ids, COUNT(*) as count
            FROM file_hashes
            WHERE content_hash IS NOT NULL
            GROUP BY content_hash
            HAVING count > 1
        """)
        
        duplicate_groups = []
        
        for row in cursor.fetchall():
            content_hash = row['content_hash']
            file_ids = row['file_ids'].split(',')
            
            group = DuplicateGroup(
                duplicate_id=f"content_{content_hash[:16]}",
                files=file_ids,
                similarity_type="content",
                similarity_score=threshold,
                recommended_action=self._recommend_action(file_ids, "content")
            )
            
            duplicate_groups.append(group)
            
            # Store in database
            self._store_duplicate_group(group)
        
        logger.info(f"Found {len(duplicate_groups)} content duplicate groups")
        return duplicate_groups
    
    def find_perceptual_duplicates(self, hamming_threshold: int = 5) -> List[DuplicateGroup]:
        """
        Find perceptually similar images.
        
        Args:
            hamming_threshold: Maximum hamming distance for duplicates
            
        Returns:
            List of duplicate groups
        """
        if not PERCEPTUAL_HASH_AVAILABLE:
            logger.warning("Perceptual hashing not available")
            return []
        
        cursor = self.conn.cursor()
        
        # Get all perceptual hashes
        cursor.execute("""
            SELECT file_id, perceptual_hash
            FROM file_hashes
            WHERE perceptual_hash IS NOT NULL
        """)
        
        hashes = [(row['file_id'], imagehash.hex_to_hash(row['perceptual_hash']))
                  for row in cursor.fetchall()]
        
        # Compare all pairs
        duplicate_pairs = []
        seen = set()
        
        for i, (fid1, hash1) in enumerate(hashes):
            for fid2, hash2 in hashes[i+1:]:
                # Calculate hamming distance
                distance = hash1 - hash2
                
                if distance <= hamming_threshold:
                    pair = tuple(sorted([fid1, fid2]))
                    if pair not in seen:
                        seen.add(pair)
                        duplicate_pairs.append((fid1, fid2, distance))
        
        # Group connected duplicates
        groups = self._group_connected_pairs(duplicate_pairs)
        
        duplicate_groups = []
        for i, file_ids in enumerate(groups):
            group = DuplicateGroup(
                duplicate_id=f"perceptual_{i}_{datetime.now().timestamp()}",
                files=list(file_ids),
                similarity_type="perceptual",
                similarity_score=1.0 - (hamming_threshold / 64.0),  # Normalize
                recommended_action=self._recommend_action(list(file_ids), "perceptual")
            )
            
            duplicate_groups.append(group)
            self._store_duplicate_group(group)
        
        logger.info(f"Found {len(duplicate_groups)} perceptual duplicate groups")
        return duplicate_groups
    
    def find_semantic_duplicates(
        self,
        similarity_engine,
        threshold: float = 0.85
    ) -> List[DuplicateGroup]:
        """
        Find semantically similar documents using embeddings.
        
        Args:
            similarity_engine: ContentSimilarityEngine instance
            threshold: Minimum similarity score
            
        Returns:
            List of duplicate groups
        """
        cursor = self.conn.cursor()
        
        # Get all file IDs with embeddings
        cursor.execute("""
            SELECT DISTINCT file_id
            FROM document_embeddings
        """)
        
        file_ids = [row['file_id'] for row in cursor.fetchall()]
        
        # Find similar pairs
        duplicate_pairs = []
        seen = set()
        
        for file_id in file_ids:
            similar = similarity_engine.find_similar_documents(
                file_id,
                threshold=threshold,
                limit=20
            )
            
            for sim_doc in similar:
                pair = tuple(sorted([file_id, sim_doc['file_id']]))
                if pair not in seen:
                    seen.add(pair)
                    duplicate_pairs.append((file_id, sim_doc['file_id'], sim_doc['similarity_score']))
        
        # Group connected pairs
        groups = self._group_connected_pairs(duplicate_pairs)
        
        duplicate_groups = []
        for i, file_ids in enumerate(groups):
            group = DuplicateGroup(
                duplicate_id=f"semantic_{i}_{datetime.now().timestamp()}",
                files=list(file_ids),
                similarity_type="semantic",
                similarity_score=threshold,
                recommended_action=self._recommend_action(list(file_ids), "semantic")
            )
            
            duplicate_groups.append(group)
            self._store_duplicate_group(group)
        
        logger.info(f"Found {len(duplicate_groups)} semantic duplicate groups")
        return duplicate_groups
    
    def _group_connected_pairs(
        self,
        pairs: List[Tuple[str, str, float]]
    ) -> List[Set[str]]:
        """
        Group pairs into connected components.
        
        If A is similar to B, and B is similar to C, then {A, B, C} form a group.
        """
        # Build adjacency list
        graph = defaultdict(set)
        for fid1, fid2, _ in pairs:
            graph[fid1].add(fid2)
            graph[fid2].add(fid1)
        
        # Find connected components via DFS
        visited = set()
        groups = []
        
        def dfs(node, component):
            visited.add(node)
            component.add(node)
            for neighbor in graph[node]:
                if neighbor not in visited:
                    dfs(neighbor, component)
        
        for node in graph:
            if node not in visited:
                component = set()
                dfs(node, component)
                if len(component) > 1:
                    groups.append(component)
        
        return groups
    
    def _recommend_action(self, file_ids: List[str], similarity_type: str) -> str:
        """
        Recommend action for duplicate group.
        
        Args:
            file_ids: List of duplicate file IDs
            similarity_type: Type of duplication
            
        Returns:
            Recommended action
        """
        # Get file metadata
        cursor = self.conn.cursor()
        
        # For exact duplicates, keep the first seen or one in preferred location
        if similarity_type == "exact":
            return "keep_first_delete_rest"
        
        # For content/semantic duplicates, recommend manual review
        if similarity_type in ["content", "semantic"]:
            return "manual_review"
        
        # For perceptual duplicates (images), keep highest quality
        if similarity_type == "perceptual":
            return "keep_largest"
        
        return "manual_review"
    
    def _store_duplicate_group(self, group: DuplicateGroup):
        """Store duplicate group in database"""
        cursor = self.conn.cursor()
        
        # Store pairwise duplicates
        for i, fid1 in enumerate(group.files):
            for fid2 in group.files[i+1:]:
                dup_id = hashlib.md5(f"{fid1}_{fid2}".encode()).hexdigest()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO duplicates (
                        duplicate_id, file_id_1, file_id_2, similarity_type,
                        similarity_score, hash_type, detected_timestamp,
                        resolution_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    dup_id,
                    fid1,
                    fid2,
                    group.similarity_type,
                    group.similarity_score,
                    group.similarity_type,
                    datetime.now().isoformat(),
                    'unresolved'
                ))
        
        self.conn.commit()
    
    def get_duplicate_groups(
        self,
        similarity_type: Optional[str] = None,
        status: str = 'unresolved'
    ) -> List[DuplicateGroup]:
        """
        Get duplicate groups from database.
        
        Args:
            similarity_type: Filter by type (exact, content, perceptual, semantic)
            status: Filter by resolution status
            
        Returns:
            List of duplicate groups
        """
        cursor = self.conn.cursor()
        
        query = """
            SELECT * FROM duplicates
            WHERE resolution_status = ?
        """
        params = [status]
        
        if similarity_type:
            query += " AND similarity_type = ?"
            params.append(similarity_type)
        
        cursor.execute(query, params)
        
        # Group by file relationships
        groups_dict = defaultdict(set)
        
        for row in cursor.fetchall():
            fid1 = row['file_id_1']
            fid2 = row['file_id_2']
            sim_type = row['similarity_type']
            
            # Add to group
            key = (sim_type, row['duplicate_id'])
            groups_dict[key].add(fid1)
            groups_dict[key].add(fid2)
        
        # Convert to DuplicateGroup objects
        groups = []
        for (sim_type, dup_id), file_ids in groups_dict.items():
            groups.append(DuplicateGroup(
                duplicate_id=dup_id,
                files=list(file_ids),
                similarity_type=sim_type,
                similarity_score=1.0,  # Could retrieve from DB
                recommended_action="manual_review"
            ))
        
        return groups
    
    def resolve_duplicates(
        self,
        duplicate_id: str,
        action: str,
        keep_file_id: Optional[str] = None
    ):
        """
        Mark duplicates as resolved.
        
        Args:
            duplicate_id: Duplicate group ID
            action: Resolution action (merged, kept_both, deleted)
            keep_file_id: File ID to keep (if applicable)
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE duplicates
            SET resolution_status = ?,
                resolution_timestamp = ?,
                resolution_action = ?
            WHERE duplicate_id = ?
        """, (
            action,
            datetime.now().isoformat(),
            f"keep:{keep_file_id}" if keep_file_id else action,
            duplicate_id
        ))
        
        self.conn.commit()
        logger.info(f"Resolved duplicate {duplicate_id} with action {action}")
    
    def deduplicate_batch(
        self,
        duplicate_groups: List[DuplicateGroup],
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Perform batch deduplication.
        
        Args:
            duplicate_groups: Groups to deduplicate
            dry_run: If True, only show what would be done
            
        Returns:
            Deduplication summary
        """
        summary = {
            'total_groups': len(duplicate_groups),
            'files_to_delete': [],
            'files_to_keep': [],
            'actions': []
        }
        
        for group in duplicate_groups:
            action = group.recommended_action
            
            if action == "keep_first_delete_rest":
                keep = group.files[0]
                delete = group.files[1:]
                
                summary['files_to_keep'].append(keep)
                summary['files_to_delete'].extend(delete)
                summary['actions'].append({
                    'group': group.duplicate_id,
                    'action': 'delete',
                    'keep': keep,
                    'delete': delete
                })
                
                if not dry_run:
                    self.resolve_duplicates(group.duplicate_id, 'merged', keep)
            
            elif action == "manual_review":
                summary['actions'].append({
                    'group': group.duplicate_id,
                    'action': 'review_required',
                    'files': group.files
                })
        
        logger.info(f"Deduplication summary: {len(summary['files_to_delete'])} files to delete, "
                   f"{len(summary['files_to_keep'])} files to keep")
        
        return summary


__all__ = [
    'DuplicateDetector',
    'DuplicateGroup',
]
