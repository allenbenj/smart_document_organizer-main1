"""
Legal Storage - SQLite Persistence with Cryptographic File Anchoring

This module implements the storage layer for Legal Mode, providing:
- Entity-relationship graph storage
- Cryptographic file anchoring (SHA-256)
- Provenance tracking
- Lifecycle state persistence

The database is the source of truth; folders are a view of that truth.
"""

import sqlite3
import hashlib
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from ..routing import LifecycleState
from ..legal.extraction import Entity, Relationship

logger = logging.getLogger(__name__)


@dataclass
class FileRecord:
    """Represents a file record with provenance"""
    file_id: str
    sha256_hash: str
    ingestion_ts: str  # ISO8601 timestamp
    first_seen_path: str
    current_path: str
    lifecycle_state: str
    case_number: Optional[str] = None
    confidence: float = 0.0
    last_modified_ts: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class LegalDatabase:
    """
    SQLite database for legal record governance.
    
    Provides cryptographic file anchoring and provenance tracking.
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize legal database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Create database schema if it doesn't exist"""
        # Allow access across worker threads (index intake/plan runs in background threads)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # Initialize enhanced schema
        try:
            from .enhanced_db_schema import EnhancedDatabaseSchema
            enhanced_schema = EnhancedDatabaseSchema(self.db_path)
            enhanced_schema.add_to_existing_db(self.conn)
            logger.info("Enhanced database schema integrated")
        except Exception as e:
            logger.warning(f"Could not integrate enhanced schema: {e}")
        
        # Files table with cryptographic anchoring
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                sha256_hash TEXT NOT NULL,
                ingestion_ts TEXT NOT NULL,
                first_seen_path TEXT NOT NULL,
                current_path TEXT NOT NULL,
                lifecycle_state TEXT NOT NULL,
                case_number TEXT,
                confidence REAL DEFAULT 0.0,
                last_modified_ts TEXT,
                UNIQUE(sha256_hash, first_seen_path)
            )
        """)
        
        # Entities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                text TEXT NOT NULL,
                start_pos INTEGER,
                end_pos INTEGER,
                confidence REAL,
                extraction_method TEXT,
                attributes TEXT,  -- JSON
                created_ts TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        # Relationships table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                relationship_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                source_entity_id TEXT NOT NULL,
                target_entity_id TEXT NOT NULL,
                confidence REAL,
                properties TEXT,  -- JSON
                created_ts TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(file_id),
                FOREIGN KEY (source_entity_id) REFERENCES entities(entity_id),
                FOREIGN KEY (target_entity_id) REFERENCES entities(entity_id)
            )
        """)
        
        # Events table (audit trail)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,  -- JSON
                timestamp TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        # Citations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS citations (
                citation_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                citation_type TEXT NOT NULL,
                citation_text TEXT NOT NULL,
                target_file_id TEXT,
                created_ts TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(file_id),
                FOREIGN KEY (target_file_id) REFERENCES files(file_id)
            )
        """)
        
        # Governance violations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                violation_id TEXT PRIMARY KEY,
                file_id TEXT,
                violation_type TEXT NOT NULL,
                attempted_action TEXT NOT NULL,
                lifecycle_state TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                blocked INTEGER NOT NULL,
                user TEXT
            )
        """)
        
        # Plans table (audit for batch actions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                plan_id TEXT PRIMARY KEY,
                created_ts TEXT NOT NULL,
                applied_ts TEXT,
                status TEXT NOT NULL, -- CREATED, APPLIED, CANCELLED, PARTIALLY_APPLIED
                plan_data TEXT NOT NULL -- JSON blob of plan items
            )
        """)
        
        # Plan executions table (track execution history)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plan_executions (
                execution_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                started_ts TEXT NOT NULL,
                completed_ts TEXT,
                status TEXT NOT NULL,  -- RUNNING, COMPLETED, FAILED, ROLLED_BACK
                backup_id TEXT,  -- Reference to undo checkpoint
                result_summary TEXT,  -- JSON with success/failure counts
                FOREIGN KEY (plan_id) REFERENCES plans(plan_id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files(sha256_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_case ON files(case_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_state ON files(lifecycle_state)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_file ON entities(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_file ON relationships(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_file ON events(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_citations_file ON citations(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plan_executions_plan ON plan_executions(plan_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plan_executions_status ON plan_executions(status)")
        
        self.conn.commit()
        logger.info(f"Initialized legal database at {self.db_path}")
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA-256 hash of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex-encoded SHA-256 hash
        """
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def ingest_file(
        self,
        file_id: str,
        file_path: Path,
        lifecycle_state: LifecycleState,
        case_number: Optional[str] = None,
        confidence: float = 0.0
    ) -> FileRecord:
        """
        Ingest a file into the legal database with cryptographic anchoring.
        
        Args:
            file_id: Unique file identifier
            file_path: Path to file
            lifecycle_state: Initial lifecycle state
            case_number: Optional case number
            confidence: Extraction confidence
            
        Returns:
            FileRecord
        """
        # Calculate file hash
        file_hash = self.calculate_file_hash(file_path)
        now = datetime.now().isoformat()
        
        # Check if file already exists
        existing = self.get_file_by_hash(file_hash)
        if existing:
            logger.warning(f"File with hash {file_hash} already exists: {existing['file_id']}")
            # Update current path if moved
            if existing['current_path'] != str(file_path):
                self.update_file_path(existing['file_id'], file_path)
            return self._row_to_file_record(existing)
        
        # Insert new file record
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO files (
                file_id, sha256_hash, ingestion_ts, first_seen_path,
                current_path, lifecycle_state, case_number, confidence,
                last_modified_ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_id,
            file_hash,
            now,
            str(file_path),
            str(file_path),
            lifecycle_state.value,
            case_number,
            confidence,
            now
        ))
        self.conn.commit()
        
        # Log ingestion event
        self.log_event(file_id, "ingestion", {
            "path": str(file_path),
            "hash": file_hash,
            "state": lifecycle_state.value
        })
        
        logger.info(f"Ingested file {file_id} with hash {file_hash[:16]}...")
        
        return FileRecord(
            file_id=file_id,
            sha256_hash=file_hash,
            ingestion_ts=now,
            first_seen_path=str(file_path),
            current_path=str(file_path),
            lifecycle_state=lifecycle_state.value,
            case_number=case_number,
            confidence=confidence,
            last_modified_ts=now
        )
    
    def verify_file_integrity(self, file_id: str, current_path: Path) -> tuple[bool, str]:
        """
        Verify file integrity by comparing current hash with stored hash.
        
        Returns:
            (is_valid, message)
        """
        record = self.get_file(file_id)
        if not record:
            return False, f"File {file_id} not found in database"
        
        if not current_path.exists():
            return False, f"File not found at {current_path}"
        
        current_hash = self.calculate_file_hash(current_path)
        stored_hash = record['sha256_hash']
        
        if current_hash == stored_hash:
            return True, "File integrity verified"
        else:
            logger.error(f"File integrity violation: {file_id} hash mismatch")
            self.log_event(file_id, "integrity_violation", {
                "expected_hash": stored_hash,
                "actual_hash": current_hash,
                "path": str(current_path)
            })
            return False, f"Hash mismatch: expected {stored_hash[:16]}..., got {current_hash[:16]}..."
    
    def store_entities(self, file_id: str, entities: List[Entity]):
        """Store extracted entities"""
        import json
        
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        for entity in entities:
            cursor.execute("""
                INSERT OR REPLACE INTO entities (
                    entity_id, file_id, entity_type, text, start_pos, end_pos,
                    confidence, extraction_method, attributes, created_ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entity.entity_id,
                file_id,
                entity.entity_type,
                entity.text,
                entity.start_pos,
                entity.end_pos,
                entity.confidence,
                entity.extraction_method,
                json.dumps(entity.attributes),
                now
            ))
        
        self.conn.commit()
        logger.info(f"Stored {len(entities)} entities for file {file_id}")
    
    def store_relationships(self, file_id: str, relationships: List[Relationship]):
        """Store extracted relationships"""
        import json
        
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        for rel in relationships:
            cursor.execute("""
                INSERT OR REPLACE INTO relationships (
                    relationship_id, file_id, relationship_type,
                    source_entity_id, target_entity_id, confidence,
                    properties, created_ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rel.relationship_id,
                file_id,
                rel.relationship_type,
                rel.source_entity_id,
                rel.target_entity_id,
                rel.confidence,
                json.dumps(rel.properties),
                now
            ))
        
        self.conn.commit()
        logger.info(f"Stored {len(relationships)} relationships for file {file_id}")
    
    def update_lifecycle_state(self, file_id: str, new_state: LifecycleState):
        """Update file lifecycle state"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        cursor.execute("""
            UPDATE files
            SET lifecycle_state = ?, last_modified_ts = ?
            WHERE file_id = ?
        """, (new_state.value, now, file_id))
        
        self.conn.commit()
        
        self.log_event(file_id, "state_transition", {
            "new_state": new_state.value,
            "timestamp": now
        })
    
    def update_file_path(self, file_id: str, new_path: Path):
        """Update file current path"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        cursor.execute("""
            UPDATE files
            SET current_path = ?, last_modified_ts = ?
            WHERE file_id = ?
        """, (str(new_path), now, file_id))
        
        self.conn.commit()
        
        self.log_event(file_id, "path_change", {
            "new_path": str(new_path),
            "timestamp": now
        })
    
    def log_event(self, file_id: str, event_type: str, event_data: Dict[str, Any]):
        """Log an event"""
        import json
        import uuid
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO events (event_id, file_id, event_type, event_data, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            file_id,
            event_type,
            json.dumps(event_data),
            datetime.now().isoformat()
        ))
        self.conn.commit()
    
    def log_violation(self, violation_data: Dict[str, Any]):
        """Log a governance violation"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO violations (
                violation_id, file_id, violation_type, attempted_action,
                lifecycle_state, timestamp, blocked, user
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            violation_data['violation_id'],
            violation_data.get('file_id'),
            violation_data['violation_type'],
            violation_data['attempted_action'],
            violation_data['lifecycle_state'],
            violation_data['timestamp'],
            1 if violation_data['blocked'] else 0,
            violation_data.get('user')
        ))
        self.conn.commit()
    
    def store_plan(self, plan_id: str, plan_data: Dict[str, Any]):
        """Store a batch organization plan"""
        import json
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO plans (plan_id, created_ts, status, plan_data)
            VALUES (?, ?, ?, ?)
        """, (plan_id, now, "CREATED", json.dumps(plan_data)))
        self.conn.commit()
    
    def update_plan_status(self, plan_id: str, status: str):
        """Update the status of a plan (APPLIED, CANCELLED)"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE plans
            SET status = ?, applied_ts = ?
            WHERE plan_id = ?
        """, (status, now, plan_id))
        self.conn.commit()
    
    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get a stored plan"""
        import json
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        result = dict(row)
        result['plan_data'] = json.loads(result['plan_data'])
        return result

    def list_plans(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List stored plans with basic metadata."""
        cursor = self.conn.cursor()
        if status:
            cursor.execute(
                "SELECT plan_id, created_ts, applied_ts, status, plan_data FROM plans WHERE status = ? ORDER BY created_ts DESC LIMIT ?",
                (status, limit)
            )
        else:
            cursor.execute(
                "SELECT plan_id, created_ts, applied_ts, status, plan_data FROM plans ORDER BY created_ts DESC LIMIT ?",
                (limit,)
            )
        rows = cursor.fetchall()
        results = []
        for row in rows:
            row_dict = dict(row)
            # Parse plan_data to get item count without returning full payload
            try:
                import json
                plan_data = json.loads(row_dict.get("plan_data", "{}"))
                item_count = len(plan_data.get("items", [])) if isinstance(plan_data, dict) else 0
            except Exception:
                item_count = 0
            results.append({
                "plan_id": row_dict.get("plan_id"),
                "created_ts": row_dict.get("created_ts"),
                "applied_ts": row_dict.get("applied_ts"),
                "status": row_dict.get("status"),
                "item_count": item_count
            })
        return results

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM files WHERE file_id = ?", (file_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_file_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Get file record by hash"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM files WHERE sha256_hash = ?", (file_hash,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_files_by_case(self, case_number: str) -> List[Dict[str, Any]]:
        """Get all files for a case"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM files WHERE case_number = ?", (case_number,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_entities(self, file_id: str) -> List[Dict[str, Any]]:
        """Get entities for a file"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM entities WHERE file_id = ?", (file_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def _row_to_file_record(self, row: Dict[str, Any]) -> FileRecord:
        """Convert database row to FileRecord"""
        return FileRecord(
            file_id=row['file_id'],
            sha256_hash=row['sha256_hash'],
            ingestion_ts=row['ingestion_ts'],
            first_seen_path=row['first_seen_path'],
            current_path=row['current_path'],
            lifecycle_state=row['lifecycle_state'],
            case_number=row.get('case_number'),
            confidence=row.get('confidence', 0.0),
            last_modified_ts=row.get('last_modified_ts')
        )
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Closed legal database connection")


__all__ = [
    'FileRecord',
    'LegalDatabase',
]
