-- ============================================================================
-- FILE INDEX DATABASE SCHEMA
-- Database for tracking and understanding application source files
-- NOT for documents processed by the application
-- Combines capabilities from all tools/db components
-- ============================================================================

-- ============================================================================
-- CORE FILE TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    file_name TEXT NOT NULL,
    file_extension TEXT,
    relative_path TEXT NOT NULL,
    absolute_path TEXT NOT NULL,
    
    -- File metadata
    file_size INTEGER,
    lines_of_code INTEGER,
    created_at TIMESTAMP,
    modified_at TIMESTAMP,
    last_scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Content hash for change detection
    content_hash TEXT,
    hash_algorithm TEXT DEFAULT 'SHA256',
    
    -- File classification
    file_type TEXT, -- 'python', 'javascript', 'markdown', 'config', 'sql', etc.
    file_category TEXT, -- 'core', 'agent', 'gui', 'tool', 'test', 'config', 'doc'
    module_path TEXT, -- Python module path like 'agents.core.manager'
    
    -- Status tracking
    is_active BOOLEAN DEFAULT TRUE,
    is_deprecated BOOLEAN DEFAULT FALSE,
    is_test_file BOOLEAN DEFAULT FALSE,
    is_generated BOOLEAN DEFAULT FALSE,
    
    -- Quality indicators
    has_tests BOOLEAN DEFAULT FALSE,
    test_coverage REAL,
    
    UNIQUE(absolute_path)
);

CREATE INDEX IF NOT EXISTS idx_files_path ON files(file_path);
CREATE INDEX IF NOT EXISTS idx_files_ext ON files(file_extension);
CREATE INDEX IF NOT EXISTS idx_files_type ON files(file_type);
CREATE INDEX IF NOT EXISTS idx_files_category ON files(file_category);
CREATE INDEX IF NOT EXISTS idx_files_modified ON files(modified_at);

-- ============================================================================
-- AI ANALYSIS RESULTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS file_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    
    -- AI analysis results
    primary_purpose TEXT,
    key_functionality TEXT,
    main_classes TEXT, -- JSON array of class names
    main_functions TEXT, -- JSON array of function names
    dependencies TEXT, -- JSON array of imports/dependencies
    exports TEXT, -- JSON array of exported items
    
    -- Code metrics
    complexity_score REAL,
    maintainability_score REAL,
    documentation_score REAL,
    security_score REAL,
    
    -- AI metadata
    ai_model_used TEXT,
    analysis_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analysis_confidence REAL DEFAULT 1.0,
    analysis_notes TEXT,
    
    -- Raw AI response
    raw_ai_response TEXT,
    
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analysis_file_id ON file_analysis(file_id);
CREATE INDEX IF NOT EXISTS idx_analysis_timestamp ON file_analysis(analysis_timestamp);

-- ============================================================================
-- FILE RELATIONSHIPS (imports, dependencies, etc.)
-- ============================================================================

CREATE TABLE IF NOT EXISTS file_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id INTEGER NOT NULL,
    target_file_id INTEGER,
    relationship_type TEXT NOT NULL, -- 'imports', 'inherits', 'calls', 'uses', 'extends'
    relationship_details TEXT, -- Specific import/call details
    line_number INTEGER, -- Where the relationship occurs
    confidence REAL DEFAULT 1.0,
    detected_by TEXT, -- 'static_analysis', 'ai', 'manual'
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(source_file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY(target_file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_relationships_source ON file_relationships(source_file_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON file_relationships(target_file_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON file_relationships(relationship_type);

-- ============================================================================
-- FILE CHANGE HISTORY
-- ============================================================================

CREATE TABLE IF NOT EXISTS file_change_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    
    -- Change details
    change_type TEXT NOT NULL, -- 'created', 'modified', 'moved', 'deleted', 'renamed'
    old_path TEXT,
    new_path TEXT,
    old_hash TEXT,
    new_hash TEXT,
    
    -- Change metrics
    lines_added INTEGER DEFAULT 0,
    lines_removed INTEGER DEFAULT 0,
    lines_modified INTEGER DEFAULT 0,
    
    -- Git integration
    git_commit_hash TEXT,
    git_branch TEXT,
    git_author TEXT,
    git_message TEXT,
    
    -- Timestamps
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    committed_at TIMESTAMP,
    
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_history_file_id ON file_change_history(file_id);
CREATE INDEX IF NOT EXISTS idx_history_type ON file_change_history(change_type);
CREATE INDEX IF NOT EXISTS idx_history_date ON file_change_history(detected_at);

-- ============================================================================
-- FILE TAGS AND ANNOTATIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS file_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    tag_name TEXT NOT NULL,
    tag_category TEXT NOT NULL, -- 'type', 'status', 'priority', 'module', 'custom'
    tag_value TEXT,
    confidence REAL DEFAULT 1.0,
    created_by TEXT DEFAULT 'system', -- 'system', 'ai', 'user'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tags_file_id ON file_tags(file_id);
CREATE INDEX IF NOT EXISTS idx_tags_category ON file_tags(tag_category);
CREATE INDEX IF NOT EXISTS idx_tags_name ON file_tags(tag_name);

-- Predefined tag definitions
CREATE TABLE IF NOT EXISTS tag_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    tag_name TEXT NOT NULL,
    description TEXT,
    color_hex TEXT DEFAULT '#6B7280',
    auto_assign_pattern TEXT, -- Regex pattern for auto-assignment
    UNIQUE(category, tag_name)
);

-- Insert default tags
INSERT OR IGNORE INTO tag_definitions (category, tag_name, description, color_hex, auto_assign_pattern) VALUES
-- Type tags
('type', 'agent', 'AI agent implementation', '#3B82F6', '.*agent.*\.py$'),
('type', 'gui', 'GUI/interface file', '#8B5CF6', '.*gui.*\.py$'),
('type', 'core', 'Core business logic', '#EF4444', '.*core.*\.py$'),
('type', 'utility', 'Utility/helper functions', '#6B7280', '.*util.*\.py$|.*helper.*\.py$'),
('type', 'test', 'Test file', '#10B981', '.*test.*\.py$|.*_test\.py$'),
('type', 'config', 'Configuration file', '#EC4899', '.*config.*\.(py|json|yaml|toml)$'),
('type', 'database', 'Database related', '#0891B2', '.*database.*\.py$|.*db.*\.py$'),
('type', 'api', 'API/endpoint file', '#06B6D4', '.*api.*\.py$|.*route.*\.py$'),

-- Status tags
('status', 'active', 'Actively maintained', '#059669', NULL),
('status', 'deprecated', 'Deprecated/legacy', '#6B7280', NULL),
('status', 'experimental', 'Experimental feature', '#F59E0B', NULL),
('status', 'needs_review', 'Needs code review', '#DC2626', NULL),
('status', 'production_ready', 'Production ready', '#10B981', NULL),

-- Priority tags
('priority', 'critical', 'Critical component', '#DC2626', NULL),
('priority', 'high', 'High priority', '#EA580C', NULL),
('priority', 'medium', 'Medium priority', '#D97706', NULL),
('priority', 'low', 'Low priority', '#65A30D', NULL);

-- ============================================================================
-- FILE ISSUES AND CONCERNS
-- ============================================================================

CREATE TABLE IF NOT EXISTS file_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    issue_type TEXT NOT NULL, -- 'bug', 'security', 'performance', 'quality', 'documentation'
    severity TEXT NOT NULL, -- 'critical', 'high', 'medium', 'low'
    title TEXT NOT NULL,
    description TEXT,
    location TEXT, -- Line number or function name
    
    -- Detection
    detected_by TEXT, -- 'ai', 'static_analysis', 'user', 'automated_scan'
    detection_confidence REAL DEFAULT 1.0,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Status
    status TEXT DEFAULT 'open', -- 'open', 'acknowledged', 'in_progress', 'resolved', 'wont_fix'
    assigned_to TEXT,
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_issues_file_id ON file_issues(file_id);
CREATE INDEX IF NOT EXISTS idx_issues_type ON file_issues(issue_type);
CREATE INDEX IF NOT EXISTS idx_issues_severity ON file_issues(severity);
CREATE INDEX IF NOT EXISTS idx_issues_status ON file_issues(status);

-- ============================================================================
-- CODE ENTITIES (classes, functions, etc.)
-- ============================================================================

CREATE TABLE IF NOT EXISTS code_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL, -- 'class', 'function', 'method', 'variable', 'constant'
    entity_name TEXT NOT NULL,
    full_name TEXT, -- Fully qualified name
    
    -- Location
    line_start INTEGER,
    line_end INTEGER,
    parent_entity_id INTEGER, -- For methods within classes
    
    -- Documentation
    docstring TEXT,
    has_documentation BOOLEAN DEFAULT FALSE,
    
    -- Signature
    signature TEXT,
    parameters TEXT, -- JSON array
    return_type TEXT,
    
    -- Metrics
    complexity INTEGER,
    lines_of_code INTEGER,
    
    -- Metadata
    is_public BOOLEAN DEFAULT TRUE,
    is_async BOOLEAN DEFAULT FALSE,
    is_generator BOOLEAN DEFAULT FALSE,
    decorators TEXT, -- JSON array of decorator names
    
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY(parent_entity_id) REFERENCES code_entities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entities_file_id ON code_entities(file_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON code_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON code_entities(entity_name);
CREATE INDEX IF NOT EXISTS idx_entities_parent ON code_entities(parent_entity_id);

-- ============================================================================
-- FILE GROUPS AND MODULES
-- ============================================================================

CREATE TABLE IF NOT EXISTS file_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT NOT NULL UNIQUE,
    group_type TEXT, -- 'module', 'feature', 'component', 'layer'
    description TEXT,
    parent_group_id INTEGER,
    path_pattern TEXT, -- Regex pattern for auto-grouping
    
    FOREIGN KEY(parent_group_id) REFERENCES file_groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS file_group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(group_id) REFERENCES file_groups(id) ON DELETE CASCADE,
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE,
    UNIQUE(group_id, file_id)
);

-- Insert default groups
INSERT OR IGNORE INTO file_groups (group_name, group_type, description, path_pattern) VALUES
('agents', 'module', 'AI agent implementations', '^agents/'),
('gui', 'module', 'GUI and interface files', '^gui/'),
('core', 'module', 'Core business logic', '^core/'),
('tools', 'module', 'Development tools', '^tools/'),
('config', 'module', 'Configuration files', '^config/'),
('databases', 'module', 'Database files', '^databases/'),
('tests', 'module', 'Test files', '^tests/'),
('docs', 'module', 'Documentation', '^docs/'),
('utils', 'module', 'Utility functions', '^utils/'),
('services', 'module', 'Service layer', '^services/');

-- ============================================================================
-- SCAN HISTORY AND METADATA
-- ============================================================================

CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_type TEXT NOT NULL, -- 'full', 'incremental', 'targeted'
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds REAL,
    
    -- Scan results
    files_scanned INTEGER DEFAULT 0,
    files_added INTEGER DEFAULT 0,
    files_updated INTEGER DEFAULT 0,
    files_removed INTEGER DEFAULT 0,
    files_analyzed INTEGER DEFAULT 0,
    
    -- Status
    status TEXT DEFAULT 'running', -- 'running', 'completed', 'failed', 'cancelled'
    error_message TEXT,
    
    -- Configuration
    scan_config TEXT, -- JSON with scan configuration
    ai_model_used TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_history_date ON scan_history(started_at);

-- ============================================================================
-- KNOWLEDGE GRAPH FOR CODE UNDERSTANDING
-- ============================================================================

CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL UNIQUE,
    node_type TEXT NOT NULL, -- 'file', 'class', 'function', 'concept', 'pattern'
    label TEXT NOT NULL,
    description TEXT,
    
    -- Links to other tables
    file_id INTEGER,
    entity_id INTEGER,
    
    -- Embedding for semantic search
    embedding_vector BLOB,
    
    -- Metadata
    properties TEXT, -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY(entity_id) REFERENCES code_entities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS knowledge_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    edge_id TEXT NOT NULL UNIQUE,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    edge_type TEXT NOT NULL, -- 'imports', 'calls', 'implements', 'uses', 'similar_to'
    weight REAL DEFAULT 1.0,
    confidence REAL DEFAULT 1.0,
    
    -- Metadata
    properties TEXT, -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(source_node_id) REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE,
    FOREIGN KEY(target_node_id) REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_type ON knowledge_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_file ON knowledge_nodes(file_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_edges_source ON knowledge_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_edges_target ON knowledge_edges(target_node_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_edges_type ON knowledge_edges(edge_type);

-- ============================================================================
-- SYSTEM CONFIGURATION AND LOGS
-- ============================================================================

CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    value_type TEXT, -- 'string', 'int', 'float', 'bool', 'json'
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default configuration
INSERT OR IGNORE INTO system_config (key, value, value_type, description) VALUES
('db_version', '1.0.0', 'string', 'Database schema version'),
('auto_scan_enabled', 'true', 'bool', 'Enable automatic file scanning'),
('scan_interval_minutes', '60', 'int', 'Minutes between automatic scans'),
('ai_analysis_enabled', 'true', 'bool', 'Enable AI analysis of files'),
('default_ai_model', 'ollama', 'string', 'Default AI model for analysis'),
('max_file_size_kb', '1024', 'int', 'Maximum file size to analyze in KB');

CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL, -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    category TEXT NOT NULL, -- 'scan', 'analysis', 'database', 'system'
    message TEXT NOT NULL,
    details TEXT, -- JSON with additional details
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);
CREATE INDEX IF NOT EXISTS idx_system_logs_category ON system_logs(category);
CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON system_logs(timestamp);

-- ============================================================================
-- USEFUL VIEWS FOR QUERIES
-- ============================================================================

-- Complete file information view
CREATE VIEW IF NOT EXISTS v_files_complete AS
SELECT 
    f.id,
    f.file_path,
    f.file_name,
    f.file_extension,
    f.file_type,
    f.file_category,
    f.lines_of_code,
    f.modified_at,
    f.is_active,
    fa.primary_purpose,
    fa.complexity_score,
    fa.maintainability_score,
    COUNT(DISTINCT fi.id) as issue_count,
    COUNT(DISTINCT ft.id) as tag_count,
    GROUP_CONCAT(DISTINCT ft.tag_name) as tags,
    MAX(fa.analysis_timestamp) as last_analyzed
FROM files f
LEFT JOIN file_analysis fa ON f.id = fa.file_id
LEFT JOIN file_issues fi ON f.id = fi.file_id AND fi.status = 'open'
LEFT JOIN file_tags ft ON f.id = ft.file_id
GROUP BY f.id;

-- File relationships view
CREATE VIEW IF NOT EXISTS v_file_dependencies AS
SELECT 
    f1.file_path as source_file,
    f2.file_path as target_file,
    fr.relationship_type,
    fr.relationship_details,
    fr.confidence
FROM file_relationships fr
JOIN files f1 ON fr.source_file_id = f1.id
LEFT JOIN files f2 ON fr.target_file_id = f2.id
WHERE f1.is_active = TRUE;

-- File statistics view
CREATE VIEW IF NOT EXISTS v_file_stats AS
SELECT 
    file_type,
    file_category,
    COUNT(*) as file_count,
    SUM(lines_of_code) as total_lines,
    AVG(lines_of_code) as avg_lines,
    COUNT(CASE WHEN is_test_file THEN 1 END) as test_files,
    COUNT(CASE WHEN is_deprecated THEN 1 END) as deprecated_files
FROM files
WHERE is_active = TRUE
GROUP BY file_type, file_category;

-- Issue summary view
CREATE VIEW IF NOT EXISTS v_issue_summary AS
SELECT 
    f.file_path,
    fi.issue_type,
    fi.severity,
    COUNT(*) as issue_count
FROM file_issues fi
JOIN files f ON fi.file_id = f.id
WHERE fi.status = 'open'
GROUP BY f.file_path, fi.issue_type, fi.severity;

-- ============================================================================
-- TRIGGERS FOR AUTOMATION
-- ============================================================================

-- Auto-tag files based on patterns when inserted
CREATE TRIGGER IF NOT EXISTS auto_tag_files_on_insert
AFTER INSERT ON files
BEGIN
    -- Tag based on tag definitions with auto_assign_pattern
    INSERT INTO file_tags (file_id, tag_name, tag_category, created_by)
    SELECT 
        NEW.id,
        td.tag_name,
        td.category,
        'auto_trigger'
    FROM tag_definitions td
    WHERE td.auto_assign_pattern IS NOT NULL
    AND NEW.file_path REGEXP td.auto_assign_pattern;
END;

-- Update file modification timestamp
CREATE TRIGGER IF NOT EXISTS update_file_timestamp
AFTER UPDATE ON files
BEGIN
    UPDATE files 
    SET last_scanned_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- Log file changes
CREATE TRIGGER IF NOT EXISTS log_file_changes
AFTER UPDATE ON files
WHEN OLD.content_hash != NEW.content_hash
BEGIN
    INSERT INTO file_change_history (
        file_id, file_path, change_type, 
        old_hash, new_hash, detected_at
    )
    VALUES (
        NEW.id, NEW.file_path, 'modified',
        OLD.content_hash, NEW.content_hash, CURRENT_TIMESTAMP
    );
END;

-- ============================================================================
-- PERFORMANCE OPTIMIZATION
-- ============================================================================

-- Full-text search support for file content
CREATE VIRTUAL TABLE IF NOT EXISTS file_search USING fts5(
    file_path,
    file_name,
    primary_purpose,
    key_functionality,
    content='file_analysis',
    content_rowid='id'
);

-- Populate FTS index
CREATE TRIGGER IF NOT EXISTS file_search_insert
AFTER INSERT ON file_analysis
BEGIN
    INSERT INTO file_search(rowid, file_path, file_name, primary_purpose, key_functionality)
    SELECT NEW.id, f.file_path, f.file_name, NEW.primary_purpose, NEW.key_functionality
    FROM files f WHERE f.id = NEW.file_id;
END;

-- ============================================================================
-- INITIALIZATION COMPLETE
-- ============================================================================

-- Record database initialization
INSERT OR IGNORE INTO system_logs (level, category, message, details)
VALUES (
    'INFO',
    'system',
    'File index database schema initialized',
    json_object(
        'version', '1.0.0',
        'initialized_at', datetime('now'),
        'purpose', 'Application file tracking and analysis'
    )
);

VACUUM;
ANALYZE;
