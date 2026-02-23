"""
Enhanced Database Schema - Comprehensive storage for all file organization features

This module adds extensive database tables for:
- Content caching and hashing
- Duplicate detection
- Content similarity and clustering
- Topic modeling and embeddings
- Quality validation
- User feedback tracking
- Temporal organization
- Cross-references and citations
- Multi-modal support (images, videos, audio)
- Performance tracking
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class EnhancedDatabaseSchema:
    """
    Comprehensive database schema for advanced file organization.
    
    This extends the existing legal_db and learning_engine databases with:
    - Content extraction caching
    - Duplicate detection and deduplication
    - Document similarity and clustering
    - Topic modeling and classification
    - Quality metrics and validation
    - User feedback and corrections
    - Temporal lifecycle tracking
    - Cross-reference and citation graphs
    - Multi-modal content support
    """
    
    def __init__(self, db_path: Path):
        """Initialize enhanced database schema"""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        self._initialize_enhanced_schema()
    
    def _initialize_enhanced_schema(self):
        """Create all enhanced database tables"""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # ==================== BASIC FILES TABLE ====================
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
        
        # ==================== CONTENT EXTRACTION & CACHING ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content_cache (
                file_id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                content_hash TEXT,
                extracted_text TEXT,
                extraction_method TEXT,
                extraction_timestamp TEXT NOT NULL,
                extraction_duration_ms INTEGER,
                char_count INTEGER,
                word_count INTEGER,
                language TEXT,
                encoding TEXT,
                metadata TEXT,  -- JSON with additional metadata
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        # ==================== DUPLICATE DETECTION ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duplicates (
                duplicate_id TEXT PRIMARY KEY,
                file_id_1 TEXT NOT NULL,
                file_id_2 TEXT NOT NULL,
                similarity_type TEXT NOT NULL,  -- exact, content, perceptual, semantic
                similarity_score REAL NOT NULL,
                hash_type TEXT,  -- md5, sha256, perceptual, content
                hash_value TEXT,
                detected_timestamp TEXT NOT NULL,
                resolution_status TEXT DEFAULT 'unresolved',  -- unresolved, merged, kept_both, deleted
                resolution_timestamp TEXT,
                resolution_action TEXT,
                FOREIGN KEY (file_id_1) REFERENCES files(file_id),
                FOREIGN KEY (file_id_2) REFERENCES files(file_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_hashes (
                file_id TEXT PRIMARY KEY,
                md5_hash TEXT,
                sha256_hash TEXT,
                content_hash TEXT,
                perceptual_hash TEXT,  -- For images
                semantic_hash TEXT,  -- For text similarity
                hash_updated_timestamp TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        # ==================== CONTENT SIMILARITY & EMBEDDINGS ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_embeddings (
                embedding_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding_vector BLOB,  -- Serialized numpy array or JSON
                embedding_dimension INTEGER,
                created_timestamp TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS similarity_clusters (
                cluster_id TEXT PRIMARY KEY,
                cluster_name TEXT,
                cluster_type TEXT,  -- semantic, topic, entity_based
                centroid_embedding BLOB,
                file_count INTEGER DEFAULT 0,
                avg_similarity REAL,
                created_timestamp TEXT NOT NULL,
                updated_timestamp TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cluster_members (
                membership_id TEXT PRIMARY KEY,
                cluster_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                similarity_score REAL,
                distance_to_centroid REAL,
                added_timestamp TEXT NOT NULL,
                FOREIGN KEY (cluster_id) REFERENCES similarity_clusters(cluster_id),
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        # ==================== TOPIC MODELING ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                topic_id TEXT PRIMARY KEY,
                topic_name TEXT NOT NULL,
                topic_keywords TEXT,  -- JSON array
                topic_description TEXT,
                document_count INTEGER DEFAULT 0,
                created_timestamp TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_topics (
                doc_topic_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                topic_id TEXT NOT NULL,
                relevance_score REAL NOT NULL,
                extraction_method TEXT,
                created_timestamp TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(file_id),
                FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
            )
        """)
        
        # ==================== QUALITY VALIDATION ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_metrics (
                metric_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                organization_quality_score REAL,
                content_quality_score REAL,
                naming_quality_score REAL,
                metadata_completeness_score REAL,
                validation_issues TEXT,  -- JSON array of issues
                validated_timestamp TEXT NOT NULL,
                validator_version TEXT,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS misclassifications (
                misclass_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                expected_location TEXT,
                actual_location TEXT,
                expected_type TEXT,
                actual_type TEXT,
                confidence_score REAL,
                detected_timestamp TEXT NOT NULL,
                corrected BOOLEAN DEFAULT FALSE,
                correction_timestamp TEXT,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validation_rules (
                rule_id TEXT PRIMARY KEY,
                rule_name TEXT NOT NULL,
                rule_type TEXT NOT NULL,  -- naming, location, metadata, content
                rule_pattern TEXT,
                rule_logic TEXT,  -- JSON with validation logic
                severity TEXT DEFAULT 'warning',  -- info, warning, error
                enabled BOOLEAN DEFAULT TRUE,
                created_timestamp TEXT NOT NULL,
                updated_timestamp TEXT
            )
        """)
        
        # ==================== USER FEEDBACK & LEARNING ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_corrections (
                correction_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                correction_type TEXT NOT NULL,  -- move, rename, classify, tag
                original_value TEXT,
                corrected_value TEXT,
                system_confidence REAL,
                user_id TEXT,
                correction_timestamp TEXT NOT NULL,
                applied BOOLEAN DEFAULT TRUE,
                feedback_notes TEXT,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                preference_id TEXT PRIMARY KEY,
                user_id TEXT,
                preference_type TEXT NOT NULL,  -- folder_structure, naming_pattern, organization_style
                preference_key TEXT NOT NULL,
                preference_value TEXT,  -- JSON for complex preferences
                strength REAL DEFAULT 1.0,
                learned_from_corrections INTEGER DEFAULT 0,
                created_timestamp TEXT NOT NULL,
                updated_timestamp TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_analytics (
                analytics_id TEXT PRIMARY KEY,
                time_period TEXT,  -- day, week, month
                correction_count INTEGER DEFAULT 0,
                correction_types TEXT,  -- JSON with breakdown
                most_corrected_patterns TEXT,  -- JSON array
                accuracy_improvement REAL,
                created_timestamp TEXT NOT NULL
            )
        """)
        
        # ==================== TEMPORAL ORGANIZATION ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_lifecycle (
                lifecycle_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                lifecycle_stage TEXT NOT NULL,  -- draft, active, review, archived
                stage_entered_timestamp TEXT NOT NULL,
                stage_exited_timestamp TEXT,
                expected_duration_days INTEGER,
                is_current BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_deadlines (
                deadline_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                deadline_type TEXT NOT NULL,  -- filing, response, review
                deadline_date TEXT NOT NULL,
                reminder_sent BOOLEAN DEFAULT FALSE,
                completed BOOLEAN DEFAULT FALSE,
                completion_timestamp TEXT,
                notes TEXT,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS archival_candidates (
                candidate_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                last_accessed_timestamp TEXT,
                last_modified_timestamp TEXT,
                age_days INTEGER,
                archival_score REAL,
                archival_reason TEXT,
                recommended_action TEXT,  -- archive, delete, keep
                reviewed BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        # ==================== CROSS-REFERENCES & CITATIONS ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_references (
                reference_id TEXT PRIMARY KEY,
                source_file_id TEXT NOT NULL,
                target_file_id TEXT,
                reference_type TEXT NOT NULL,  -- citation, attachment, thread, related
                reference_text TEXT,
                confidence REAL,
                extraction_method TEXT,
                created_timestamp TEXT NOT NULL,
                FOREIGN KEY (source_file_id) REFERENCES files(file_id),
                FOREIGN KEY (target_file_id) REFERENCES files(file_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_threads (
                thread_id TEXT PRIMARY KEY,
                thread_name TEXT,
                thread_type TEXT,  -- conversation, case_progression, project
                root_file_id TEXT,
                file_count INTEGER DEFAULT 0,
                start_timestamp TEXT,
                end_timestamp TEXT,
                FOREIGN KEY (root_file_id) REFERENCES files(file_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS thread_members (
                membership_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                sequence_number INTEGER,
                added_timestamp TEXT NOT NULL,
                FOREIGN KEY (thread_id) REFERENCES document_threads(thread_id),
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        # ==================== RELATIONSHIP-BASED GROUPING ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS case_bundles (
                bundle_id TEXT PRIMARY KEY,
                case_number TEXT NOT NULL,
                bundle_name TEXT,
                file_count INTEGER DEFAULT 0,
                bundle_type TEXT,  -- pleadings, discovery, correspondence
                created_timestamp TEXT NOT NULL,
                updated_timestamp TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bundle_members (
                membership_id TEXT PRIMARY KEY,
                bundle_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                role_in_bundle TEXT,
                added_timestamp TEXT NOT NULL,
                FOREIGN KEY (bundle_id) REFERENCES case_bundles(bundle_id),
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS party_associations (
                association_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                party_name TEXT NOT NULL,
                party_role TEXT,  -- plaintiff, defendant, witness
                association_strength REAL,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        # ==================== MULTI-MODAL CONTENT ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS image_metadata (
                image_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                format TEXT,
                color_mode TEXT,
                dpi INTEGER,
                exif_data TEXT,  -- JSON
                ocr_text TEXT,
                detected_objects TEXT,  -- JSON array
                face_count INTEGER,
                perceptual_hash TEXT,
                created_timestamp TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_metadata (
                video_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                duration_seconds REAL,
                width INTEGER,
                height INTEGER,
                codec TEXT,
                bitrate INTEGER,
                fps REAL,
                has_audio BOOLEAN,
                transcript TEXT,
                key_frames TEXT,  -- JSON array of timestamps
                created_timestamp TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audio_metadata (
                audio_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                duration_seconds REAL,
                sample_rate INTEGER,
                bitrate INTEGER,
                channels INTEGER,
                codec TEXT,
                transcript TEXT,
                speaker_count INTEGER,
                language TEXT,
                created_timestamp TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        # ==================== ADVANCED PATTERN RECOGNITION ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ml_pattern_models (
                model_id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                model_type TEXT NOT NULL,  -- classifier, extractor, clusterer
                model_artifact BLOB,  -- Serialized model
                training_examples INTEGER,
                accuracy_score REAL,
                features_used TEXT,  -- JSON
                created_timestamp TEXT NOT NULL,
                last_updated_timestamp TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pattern_examples (
                example_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                example_text TEXT NOT NULL,
                extracted_value TEXT,
                is_positive BOOLEAN DEFAULT TRUE,
                confidence REAL,
                used_for_training BOOLEAN DEFAULT FALSE,
                created_timestamp TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extraction_failures (
                failure_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                extraction_type TEXT NOT NULL,
                error_message TEXT,
                attempted_patterns TEXT,  -- JSON
                file_snippet TEXT,
                failure_timestamp TEXT NOT NULL,
                resolved BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        # ==================== PERFORMANCE TRACKING ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                metric_id TEXT PRIMARY KEY,
                operation_type TEXT NOT NULL,  -- scan, extract, organize, analyze
                operation_count INTEGER,
                total_duration_ms INTEGER,
                avg_duration_ms REAL,
                files_processed INTEGER,
                errors_count INTEGER,
                timestamp TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incremental_scan_state (
                scan_id TEXT PRIMARY KEY,
                root_path TEXT NOT NULL,
                last_scan_timestamp TEXT NOT NULL,
                files_scanned INTEGER,
                files_changed INTEGER,
                files_added INTEGER,
                files_removed INTEGER,
                scan_duration_ms INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_change_log (
                change_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                change_type TEXT NOT NULL,  -- added, modified, removed, moved
                old_path TEXT,
                new_path TEXT,
                old_hash TEXT,
                new_hash TEXT,
                detected_timestamp TEXT NOT NULL,
                processed BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        
        # ==================== ADAPTIVE HIERARCHY & STRUCTURE ====================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folder_hierarchies (
                hierarchy_id TEXT PRIMARY KEY,
                hierarchy_name TEXT NOT NULL,
                root_path TEXT NOT NULL,
                hierarchy_pattern TEXT,  -- JSON describing structure
                document_types TEXT,  -- JSON array of doc types
                usage_count INTEGER DEFAULT 0,
                success_rate REAL,
                user_satisfaction REAL,
                created_timestamp TEXT NOT NULL,
                updated_timestamp TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folder_purpose (
                folder_id TEXT PRIMARY KEY,
                folder_path TEXT NOT NULL,
                purpose_description TEXT,
                expected_content_types TEXT,  -- JSON
                naming_pattern TEXT,
                auto_generated BOOLEAN DEFAULT FALSE,
                created_timestamp TEXT NOT NULL
            )
        """)
        
        # ==================== COMPREHENSIVE INDEXES ====================
        # Content cache indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_cache_hash ON content_cache(file_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_cache_content_hash ON content_cache(content_hash)")
        
        # Duplicate detection indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duplicates_file1 ON duplicates(file_id_1)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duplicates_file2 ON duplicates(file_id_2)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duplicates_status ON duplicates(resolution_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_hashes_content ON file_hashes(content_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_hashes_sha256 ON file_hashes(sha256_hash)")
        
        # Embedding and clustering indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_file ON document_embeddings(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cluster_members_cluster ON cluster_members(cluster_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cluster_members_file ON cluster_members(file_id)")
        
        # Topic modeling indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_topics_file ON document_topics(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_topics_topic ON document_topics(topic_id)")
        
        # Quality validation indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_metrics_file ON quality_metrics(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_misclass_file ON misclassifications(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_misclass_corrected ON misclassifications(corrected)")
        
        # User feedback indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_corrections_file ON user_corrections(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_corrections_type ON user_corrections(correction_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_corrections_timestamp ON user_corrections(correction_timestamp)")
        
        # Temporal organization indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lifecycle_file ON document_lifecycle(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lifecycle_stage ON document_lifecycle(lifecycle_stage)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_deadlines_file ON document_deadlines(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_deadlines_date ON document_deadlines(deadline_date)")
        
        # Cross-reference indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_references_source ON document_references(source_file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_references_target ON document_references(target_file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thread_members_thread ON thread_members(thread_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thread_members_file ON thread_members(file_id)")
        
        # Relationship grouping indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundle_members_bundle ON bundle_members(bundle_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundle_members_file ON bundle_members(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_party_assoc_file ON party_associations(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_party_assoc_name ON party_associations(party_name)")
        
        # Multi-modal indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_meta_file ON image_metadata(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_meta_file ON video_metadata(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audio_meta_file ON audio_metadata(file_id)")
        
        # Performance tracking indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_metrics_type ON performance_metrics(operation_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_metrics_timestamp ON performance_metrics(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_change_log_file ON file_change_log(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_change_log_processed ON file_change_log(processed)")
        
        self.conn.commit()
        logger.info(f"Enhanced database schema initialized at {self.db_path}")
    
    def add_to_existing_db(self, existing_conn: sqlite3.Connection):
        """
        Add enhanced tables to an existing database connection.
        
        This allows integrating enhanced schema into legal_db or learning_engine.
        """
        # Get existing cursor
        cursor = existing_conn.cursor()
        
        # Check which tables already exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}
        
        logger.info(f"Found {len(existing_tables)} existing tables")
        
        # Re-run initialization script, CREATE IF NOT EXISTS handles conflicts
        self.conn = existing_conn
        self._initialize_enhanced_schema()
        
        logger.info("Enhanced schema added to existing database")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Closed enhanced database connection")


__all__ = [
    'EnhancedDatabaseSchema',
]
