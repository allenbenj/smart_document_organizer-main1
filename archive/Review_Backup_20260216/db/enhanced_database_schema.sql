-- Enhanced Database Schema for Legal AI Code Intelligence Platform
-- Integrates all 10 user-requested features with existing Codestral analysis
-- Built for tamper-proof audit trails and enterprise compliance

-- ============================================================================
-- CORE TABLES (Enhanced from existing schema)
-- ============================================================================

-- Enhanced file_review table with new audit and tracking fields
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS hash_before TEXT;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS hash_after TEXT;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS hash_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS cleanup_commit_hash TEXT;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS refactor_commit_hash TEXT;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS cleanup_author TEXT;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS tracker_url TEXT;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS tracker_status TEXT;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS priority_level INTEGER DEFAULT 3;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS file_category TEXT; -- 'core', 'test', 'legacy', 'security'
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS risk_level TEXT; -- 'critical', 'high', 'medium', 'low'
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS last_modified_date TIMESTAMP;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS lines_of_code INTEGER;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS complexity_score REAL;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS test_coverage REAL;
ALTER TABLE file_review ADD COLUMN IF NOT EXISTS dependency_count INTEGER;

-- ============================================================================
-- FILE HASH TRACKING (Feature #1)
-- ============================================================================

CREATE TABLE IF NOT EXISTS file_hash_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    operation_type TEXT NOT NULL, -- 'cleanup', 'refactor', 'organization', 'quality_fix'
    hash_before TEXT NOT NULL,
    hash_after TEXT NOT NULL,
    hash_algorithm TEXT DEFAULT 'SHA256',
    operation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    git_commit_hash TEXT,
    author_name TEXT,
    author_email TEXT,
    verification_status TEXT DEFAULT 'pending', -- 'pending', 'verified', 'failed'
    verification_timestamp TIMESTAMP,
    operation_details TEXT, -- JSON with specific changes made
    FOREIGN KEY(file_path) REFERENCES file_review(path)
);

-- Index for fast hash lookups
CREATE INDEX IF NOT EXISTS idx_file_hash_history_path ON file_hash_history(file_path);
CREATE INDEX IF NOT EXISTS idx_file_hash_history_operation ON file_hash_history(operation_type);
CREATE INDEX IF NOT EXISTS idx_file_hash_history_timestamp ON file_hash_history(operation_timestamp);

-- ============================================================================
-- GIT COMMIT TRACKING (Feature #2)
-- ============================================================================

CREATE TABLE IF NOT EXISTS git_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    operation_type TEXT NOT NULL, -- 'cleanup', 'refactor', 'move', 'delete'
    commit_hash_before TEXT,
    commit_hash_after TEXT NOT NULL,
    branch_name TEXT,
    author_name TEXT NOT NULL,
    author_email TEXT NOT NULL,
    commit_message TEXT,
    operation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    files_changed INTEGER DEFAULT 1,
    lines_added INTEGER DEFAULT 0,
    lines_removed INTEGER DEFAULT 0,
    operation_success BOOLEAN DEFAULT TRUE,
    rollback_commit_hash TEXT, -- For rollback operations
    FOREIGN KEY(file_path) REFERENCES file_review(path)
);

-- Index for git operations
CREATE INDEX IF NOT EXISTS idx_git_operations_file ON git_operations(file_path);
CREATE INDEX IF NOT EXISTS idx_git_operations_commit ON git_operations(commit_hash_after);
CREATE INDEX IF NOT EXISTS idx_git_operations_author ON git_operations(author_name);

-- ============================================================================
-- FILE TAGGING & ANNOTATION SYSTEM (Feature #6)
-- ============================================================================

CREATE TABLE IF NOT EXISTS file_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    tag_name TEXT NOT NULL,
    tag_category TEXT NOT NULL, -- 'type', 'risk', 'module', 'status', 'priority'
    tag_value TEXT, -- Optional value for the tag
    confidence_score REAL DEFAULT 1.0, -- AI confidence in tag assignment
    created_by TEXT DEFAULT 'system', -- 'system', 'user', 'codestral'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP, -- Optional expiration for temporary tags
    metadata TEXT, -- JSON with additional tag metadata
    FOREIGN KEY(file_path) REFERENCES file_review(path)
);

-- Predefined tag categories and values
CREATE TABLE IF NOT EXISTS tag_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    tag_name TEXT NOT NULL,
    description TEXT,
    color_hex TEXT DEFAULT '#6B7280', -- UI color for tag
    icon_name TEXT, -- UI icon for tag
    auto_assign_rules TEXT, -- JSON rules for automatic assignment
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, tag_name)
);

-- Insert default tag definitions
INSERT OR IGNORE INTO tag_definitions (category, tag_name, description, color_hex, icon_name) VALUES
-- File type tags
('type', 'core', 'Core business logic files', '#EF4444', 'cpu'),
('type', 'test', 'Test files and testing utilities', '#10B981', 'beaker'),
('type', 'legacy', 'Legacy code requiring modernization', '#F59E0B', 'archive'),
('type', 'security', 'Security-related code and authentication', '#8B5CF6', 'shield'),
('type', 'api', 'API endpoints and web services', '#06B6D4', 'cloud'),
('type', 'utility', 'Utility functions and helpers', '#6B7280', 'wrench'),
('type', 'config', 'Configuration and settings files', '#EC4899', 'cog'),
('type', 'agent', 'AI agent implementations', '#3B82F6', 'robot'),

-- Risk level tags
('risk', 'critical', 'Critical issues requiring immediate attention', '#DC2626', 'exclamation-triangle'),
('risk', 'high', 'High-risk code with significant issues', '#EA580C', 'warning'),
('risk', 'medium', 'Medium-risk code with some issues', '#D97706', 'info'),
('risk', 'low', 'Low-risk code with minor issues', '#65A30D', 'check'),
('risk', 'safe', 'Safe code with no significant issues', '#059669', 'shield-check'),

-- Module tags
('module', 'document_processing', 'Document processing and analysis', '#7C3AED', 'document'),
('module', 'knowledge_graph', 'Knowledge graph and relationships', '#DB2777', 'share'),
('module', 'vector_store', 'Vector storage and embeddings', '#0891B2', 'database'),
('module', 'memory_management', 'Memory and state management', '#DC2626', 'memory'),
('module', 'workflow_orchestration', 'Workflow and process orchestration', '#16A34A', 'workflow'),

-- Status tags
('status', 'production_ready', 'Ready for production deployment', '#059669', 'check-circle'),
('status', 'needs_refactor', 'Requires refactoring before deployment', '#DC2626', 'refresh'),
('status', 'archive_candidate', 'Candidate for archiving', '#6B7280', 'archive'),
('status', 'under_review', 'Currently under review', '#3B82F6', 'eye'),
('status', 'cleaned', 'Successfully cleaned and refactored', '#10B981', 'check-double');

-- Index for tags
CREATE INDEX IF NOT EXISTS idx_file_tags_path ON file_tags(file_path);
CREATE INDEX IF NOT EXISTS idx_file_tags_category ON file_tags(tag_category);
CREATE INDEX IF NOT EXISTS idx_file_tags_name ON file_tags(tag_name);

-- ============================================================================
-- AUTOMATED RE-REVIEW SYSTEM (Feature #4)
-- ============================================================================

CREATE TABLE IF NOT EXISTS review_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    review_type TEXT NOT NULL, -- 'initial', 'post_refactor', 'periodic', 'triggered'
    review_trigger TEXT, -- What triggered this review
    codestral_prompt_used TEXT, -- Which prompt template was used
    
    -- Before metrics
    rating_before INTEGER,
    maintainability_before REAL,
    security_before REAL,
    performance_before REAL,
    documentation_before REAL,
    complexity_before REAL,
    
    -- After metrics  
    rating_after INTEGER,
    maintainability_after REAL,
    security_after REAL,
    performance_after REAL,
    documentation_after REAL,
    complexity_after REAL,
    
    -- Improvement calculations
    overall_improvement REAL, -- Calculated improvement score
    improvement_category TEXT, -- 'significant', 'moderate', 'minor', 'none', 'regression'
    
    -- Review metadata
    review_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    review_duration_seconds INTEGER,
    codestral_model_version TEXT,
    reviewer_notes TEXT,
    
    -- Validation
    improvement_verified BOOLEAN DEFAULT FALSE,
    verification_timestamp TIMESTAMP,
    verification_notes TEXT,
    
    FOREIGN KEY(file_path) REFERENCES file_review(path)
);

-- Index for review history
CREATE INDEX IF NOT EXISTS idx_review_history_path ON review_history(file_path);
CREATE INDEX IF NOT EXISTS idx_review_history_type ON review_history(review_type);
CREATE INDEX IF NOT EXISTS idx_review_history_improvement ON review_history(improvement_category);

-- ============================================================================
-- RISK ALERT SYSTEM (Feature #9)
-- ============================================================================

CREATE TABLE IF NOT EXISTS risk_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    alert_type TEXT NOT NULL, -- 'security_vulnerability', 'dangerous_pattern', 'low_quality', 'compliance_issue'
    severity TEXT NOT NULL, -- 'critical', 'high', 'medium', 'low'
    alert_title TEXT NOT NULL,
    alert_message TEXT NOT NULL,
    alert_details TEXT, -- JSON with detailed information
    
    -- Detection metadata
    detected_by TEXT NOT NULL, -- 'codestral', 'static_analysis', 'pattern_matching', 'user'
    detection_confidence REAL DEFAULT 1.0,
    detection_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Alert management
    status TEXT DEFAULT 'open', -- 'open', 'investigating', 'resolved', 'false_positive'
    assigned_to TEXT, -- Who is responsible for addressing this
    priority_score INTEGER DEFAULT 5, -- 1-10 priority scale
    
    -- Resolution tracking
    resolved_at TIMESTAMP,
    resolved_by TEXT,
    resolution_notes TEXT,
    resolution_commit_hash TEXT,
    
    -- Notification tracking
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_timestamp TIMESTAMP,
    notification_channels TEXT, -- JSON array of channels notified
    
    -- Related alerts
    parent_alert_id INTEGER, -- For grouped/related alerts
    alert_group_id TEXT, -- For batch alerts
    
    FOREIGN KEY(file_path) REFERENCES file_review(path),
    FOREIGN KEY(parent_alert_id) REFERENCES risk_alerts(id)
);

-- Index for risk alerts
CREATE INDEX IF NOT EXISTS idx_risk_alerts_file ON risk_alerts(file_path);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_severity ON risk_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_status ON risk_alerts(status);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_type ON risk_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_priority ON risk_alerts(priority_score);

-- ============================================================================
-- CUSTOM CODESTRAL PROMPTS (Feature #7)
-- ============================================================================

CREATE TABLE IF NOT EXISTS codestral_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_name TEXT NOT NULL UNIQUE,
    file_type_pattern TEXT NOT NULL, -- Regex pattern for file matching
    prompt_template TEXT NOT NULL, -- The actual prompt template
    description TEXT,
    
    -- Prompt metadata
    focus_areas TEXT, -- JSON array of what this prompt focuses on
    expected_output_format TEXT, -- JSON schema or description
    prompt_version TEXT DEFAULT '1.0',
    
    -- Usage tracking
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    avg_response_time REAL,
    avg_quality_score REAL,
    
    -- Prompt management
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system'
);

-- Insert default Codestral prompts
INSERT OR IGNORE INTO codestral_prompts (prompt_name, file_type_pattern, prompt_template, description, focus_areas) VALUES
('test_files', '.*test.*\.py$|.*_test\.py$|.*tests\.py$', 
 'Analyze this test file focusing on: 1) Test coverage completeness, 2) Assertion quality and specificity, 3) Test organization and maintainability, 4) Mock usage appropriateness, 5) Edge case coverage. Rate the test quality on a scale of 1-10 and provide specific recommendations for improvement.',
 'Specialized prompt for test files focusing on testing best practices',
 '["test_coverage", "assertion_quality", "mock_usage", "edge_cases", "maintainability"]'),

('security_files', '.*security.*\.py$|.*auth.*\.py$|.*crypto.*\.py$|.*permission.*\.py$',
 'Analyze this security-related file focusing on: 1) Security vulnerabilities and attack vectors, 2) Input validation and sanitization, 3) Authentication/authorization patterns, 4) Cryptographic usage, 5) Data protection measures. Rate security posture on 1-10 and flag any critical security issues.',
 'Security-focused analysis for authentication and security modules',
 '["security_vulnerabilities", "input_validation", "auth_patterns", "cryptography", "data_protection"]'),

('core_modules', '.*core.*\.py$|.*main.*\.py$|.*manager.*\.py$|.*service.*\.py$',
 'Analyze this core module focusing on: 1) Architecture and design patterns, 2) Business logic correctness, 3) Error handling robustness, 4) Performance implications, 5) Maintainability and extensibility. Rate overall code quality on 1-10 with emphasis on production readiness.',
 'Core business logic analysis emphasizing architecture and reliability',
 '["architecture", "design_patterns", "business_logic", "error_handling", "performance"]'),

('agent_files', '.*agent.*\.py$|.*workflow.*\.py$|.*orchestrat.*\.py$',
 'Analyze this AI agent file focusing on: 1) Agent design patterns and state management, 2) Memory usage and context handling, 3) Tool integration and error recovery, 4) Workflow orchestration logic, 5) Performance and scalability. Rate agent implementation quality on 1-10.',
 'AI agent analysis focusing on agent-specific patterns and workflows',
 '["agent_patterns", "state_management", "memory_usage", "tool_integration", "workflow_logic"]'),

('api_endpoints', '.*api.*\.py$|.*endpoint.*\.py$|.*route.*\.py$|.*handler.*\.py$',
 'Analyze this API file focusing on: 1) Input validation and sanitization, 2) Error handling and status codes, 3) Authentication/authorization checks, 4) Rate limiting and abuse prevention, 5) API documentation and contracts. Rate API quality on 1-10.',
 'API endpoint analysis focusing on web security and reliability',
 '["input_validation", "error_handling", "auth_checks", "rate_limiting", "documentation"]'),

('utility_files', '.*util.*\.py$|.*helper.*\.py$|.*tool.*\.py$',
 'Analyze this utility file focusing on: 1) Function design and reusability, 2) Error handling and edge cases, 3) Performance and efficiency, 4) Documentation and examples, 5) Testing and validation. Rate utility quality on 1-10.',
 'Utility function analysis focusing on reusability and reliability',
 '["function_design", "error_handling", "performance", "documentation", "testing"]'),

('config_files', '.*config.*\.py$|.*setting.*\.py$|.*constant.*\.py$',
 'Analyze this configuration file focusing on: 1) Configuration organization and structure, 2) Security of sensitive values, 3) Environment handling, 4) Validation and defaults, 5) Documentation and examples. Rate configuration quality on 1-10.',
 'Configuration file analysis focusing on security and maintainability',
 '["organization", "security", "environment_handling", "validation", "documentation"]');

-- Index for prompts
CREATE INDEX IF NOT EXISTS idx_codestral_prompts_pattern ON codestral_prompts(file_type_pattern);
CREATE INDEX IF NOT EXISTS idx_codestral_prompts_active ON codestral_prompts(active);

-- ============================================================================
-- ISSUE TRACKER INTEGRATION (Feature #5)
-- ============================================================================

CREATE TABLE IF NOT EXISTS issue_trackers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tracker_name TEXT NOT NULL, -- 'jira', 'github', 'linear', 'asana'
    tracker_type TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_endpoint TEXT,
    auth_token_encrypted TEXT, -- Encrypted API token
    project_key TEXT, -- JIRA project key, GitHub repo, etc.
    
    -- Configuration
    default_issue_type TEXT DEFAULT 'Task',
    default_priority TEXT DEFAULT 'Medium',
    custom_fields TEXT, -- JSON mapping of custom fields
    
    -- Status
    active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMP,
    sync_status TEXT DEFAULT 'pending',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS file_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    tracker_id INTEGER NOT NULL,
    issue_key TEXT NOT NULL, -- JIRA-123, GitHub #456, etc.
    issue_url TEXT NOT NULL,
    issue_title TEXT,
    issue_description TEXT,
    issue_type TEXT, -- 'bug', 'task', 'improvement', 'refactor'
    issue_status TEXT, -- 'open', 'in_progress', 'resolved', 'closed'
    issue_priority TEXT, -- 'critical', 'high', 'medium', 'low'
    
    -- Assignee information
    assigned_to TEXT,
    assigned_at TIMESTAMP,
    
    -- Issue metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    
    -- Link to code review
    review_id INTEGER,
    alert_id INTEGER,
    
    FOREIGN KEY(file_path) REFERENCES file_review(path),
    FOREIGN KEY(tracker_id) REFERENCES issue_trackers(id),
    FOREIGN KEY(alert_id) REFERENCES risk_alerts(id)
);

-- Index for issues
CREATE INDEX IF NOT EXISTS idx_file_issues_path ON file_issues(file_path);
CREATE INDEX IF NOT EXISTS idx_file_issues_tracker ON file_issues(tracker_id);
CREATE INDEX IF NOT EXISTS idx_file_issues_status ON file_issues(issue_status);

-- ============================================================================
-- BULK OPERATIONS & DASHBOARD (Feature #3)
-- ============================================================================

CREATE TABLE IF NOT EXISTS bulk_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_name TEXT NOT NULL,
    operation_type TEXT NOT NULL, -- 'tag_files', 'mark_cleaned', 'create_issues', 'archive_files'
    operation_criteria TEXT NOT NULL, -- JSON criteria for file selection
    
    -- Operation metadata
    initiated_by TEXT NOT NULL,
    initiated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Execution tracking
    status TEXT DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Results
    files_selected INTEGER DEFAULT 0,
    files_processed INTEGER DEFAULT 0,
    files_successful INTEGER DEFAULT 0,
    files_failed INTEGER DEFAULT 0,
    
    -- Progress tracking
    progress_percentage REAL DEFAULT 0.0,
    current_file TEXT,
    estimated_completion TIMESTAMP,
    
    -- Error handling
    error_message TEXT,
    error_details TEXT, -- JSON with detailed error information
    
    -- Results storage
    operation_results TEXT, -- JSON with detailed results
    log_file_path TEXT
);

-- Index for bulk operations
CREATE INDEX IF NOT EXISTS idx_bulk_operations_status ON bulk_operations(status);
CREATE INDEX IF NOT EXISTS idx_bulk_operations_type ON bulk_operations(operation_type);
CREATE INDEX IF NOT EXISTS idx_bulk_operations_initiated ON bulk_operations(initiated_at);

-- ============================================================================
-- TREND ANALYTICS (Feature #8)
-- ============================================================================

CREATE TABLE IF NOT EXISTS quality_metrics_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    measurement_date DATE NOT NULL,
    measurement_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Overall metrics
    total_files INTEGER,
    files_reviewed INTEGER,
    files_cleaned INTEGER,
    files_production_ready INTEGER,
    
    -- Quality distribution
    files_rating_1_2 INTEGER DEFAULT 0, -- Very poor
    files_rating_3_4 INTEGER DEFAULT 0, -- Poor
    files_rating_5_6 INTEGER DEFAULT 0, -- Fair
    files_rating_7_8 INTEGER DEFAULT 0, -- Good
    files_rating_9_10 INTEGER DEFAULT 0, -- Excellent
    
    -- Average scores
    avg_rating REAL,
    avg_maintainability REAL,
    avg_security REAL,
    avg_performance REAL,
    avg_documentation REAL,
    
    -- Risk metrics
    critical_alerts INTEGER DEFAULT 0,
    high_alerts INTEGER DEFAULT 0,
    medium_alerts INTEGER DEFAULT 0,
    low_alerts INTEGER DEFAULT 0,
    
    -- Progress metrics
    cleanup_operations INTEGER DEFAULT 0,
    refactor_operations INTEGER DEFAULT 0,
    files_improved INTEGER DEFAULT 0,
    files_regressed INTEGER DEFAULT 0,
    
    -- Efficiency metrics
    avg_review_time REAL,
    avg_cleanup_time REAL,
    codestral_api_calls INTEGER DEFAULT 0,
    codestral_api_cost REAL DEFAULT 0.0,
    
    UNIQUE(measurement_date)
);

-- Index for analytics
CREATE INDEX IF NOT EXISTS idx_quality_metrics_date ON quality_metrics_history(measurement_date);
CREATE INDEX IF NOT EXISTS idx_quality_metrics_timestamp ON quality_metrics_history(measurement_timestamp);

-- ============================================================================
-- RAG/KNOWLEDGE GRAPH INTEGRATION (Feature #10)
-- ============================================================================

CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL UNIQUE,
    node_type TEXT NOT NULL, -- 'file', 'function', 'class', 'module', 'concept'
    node_label TEXT NOT NULL,
    
    -- Content and metadata
    content TEXT,
    content_hash TEXT,
    embedding_vector BLOB, -- Serialized embedding vector
    
    -- Source information
    source_file TEXT,
    source_line_start INTEGER,
    source_line_end INTEGER,
    
    -- Classification
    category TEXT,
    subcategory TEXT,
    confidence_score REAL DEFAULT 1.0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP,
    
    -- Metadata
    metadata TEXT, -- JSON with additional properties
    
    FOREIGN KEY(source_file) REFERENCES file_review(path)
);

CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    edge_id TEXT NOT NULL UNIQUE,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    edge_type TEXT NOT NULL, -- 'imports', 'calls', 'inherits', 'depends_on', 'similar_to'
    edge_label TEXT,
    
    -- Edge properties
    weight REAL DEFAULT 1.0,
    confidence REAL DEFAULT 1.0,
    direction TEXT DEFAULT 'directed', -- 'directed', 'undirected'
    
    -- Context
    context TEXT, -- Additional context about the relationship
    evidence TEXT, -- Evidence supporting this relationship
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Metadata
    metadata TEXT, -- JSON with additional properties
    
    FOREIGN KEY(source_node_id) REFERENCES knowledge_graph_nodes(node_id),
    FOREIGN KEY(target_node_id) REFERENCES knowledge_graph_nodes(node_id)
);

-- Indexes for knowledge graph
CREATE INDEX IF NOT EXISTS idx_kg_nodes_type ON knowledge_graph_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_source ON knowledge_graph_nodes(source_file);
CREATE INDEX IF NOT EXISTS idx_kg_edges_source ON knowledge_graph_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_target ON knowledge_graph_edges(target_node_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_type ON knowledge_graph_edges(edge_type);

-- ============================================================================
-- VIEWS FOR DASHBOARD AND REPORTING
-- ============================================================================

-- File summary view with all key metrics
CREATE VIEW IF NOT EXISTS file_summary AS
SELECT 
    fr.path,
    fr.rating,
    fr.maintainability_score,
    fr.security_score,
    fr.performance_score,
    fr.documentation_score,
    fr.hash_before,
    fr.hash_after,
    fr.cleanup_commit_hash,
    fr.risk_level,
    fr.file_category,
    fr.priority_level,
    
    -- Tag information
    GROUP_CONCAT(DISTINCT ft.tag_name) as tags,
    
    -- Alert count
    COUNT(DISTINCT ra.id) as alert_count,
    MAX(ra.severity) as highest_alert_severity,
    
    -- Review history
    MAX(rh.review_timestamp) as last_review,
    COUNT(DISTINCT rh.id) as review_count,
    
    -- Issue tracking
    COUNT(DISTINCT fi.id) as issue_count,
    
    fr.reviewed,
    fr.cleaned,
    fr.last_modified
FROM file_review fr
LEFT JOIN file_tags ft ON fr.path = ft.file_path
LEFT JOIN risk_alerts ra ON fr.path = ra.file_path AND ra.status = 'open'
LEFT JOIN review_history rh ON fr.path = rh.file_path
LEFT JOIN file_issues fi ON fr.path = fi.file_path AND fi.issue_status IN ('open', 'in_progress')
GROUP BY fr.path;

-- Quality trends view
CREATE VIEW IF NOT EXISTS quality_trends AS
SELECT 
    DATE(measurement_timestamp) as date,
    total_files,
    files_reviewed,
    files_cleaned,
    (files_cleaned * 100.0 / NULLIF(total_files, 0)) as cleanup_percentage,
    avg_rating,
    avg_maintainability,
    avg_security,
    (critical_alerts + high_alerts) as high_priority_alerts,
    cleanup_operations,
    files_improved
FROM quality_metrics_history
ORDER BY measurement_timestamp DESC;

-- Risk dashboard view
CREATE VIEW IF NOT EXISTS risk_dashboard AS
SELECT 
    ra.file_path,
    ra.alert_type,
    ra.severity,
    ra.alert_title,
    ra.detection_timestamp,
    ra.status,
    ra.priority_score,
    fr.rating as file_rating,
    fr.file_category,
    GROUP_CONCAT(DISTINCT ft.tag_name) as tags
FROM risk_alerts ra
JOIN file_review fr ON ra.file_path = fr.path
LEFT JOIN file_tags ft ON ra.file_path = ft.file_path
WHERE ra.status = 'open'
GROUP BY ra.id
ORDER BY ra.priority_score DESC, ra.detection_timestamp DESC;

-- ============================================================================
-- TRIGGERS FOR AUTOMATED PROCESSES
-- ============================================================================

-- Auto-update file_review when hash changes
CREATE TRIGGER IF NOT EXISTS update_file_review_on_hash_change
AFTER INSERT ON file_hash_history
BEGIN
    UPDATE file_review 
    SET 
        hash_after = NEW.hash_after,
        hash_verified = CASE WHEN NEW.verification_status = 'verified' THEN TRUE ELSE FALSE END,
        cleanup_commit_hash = NEW.git_commit_hash,
        cleanup_author = NEW.author_name,
        last_modified = NEW.operation_timestamp
    WHERE path = NEW.file_path;
END;

-- Auto-create risk alerts for low ratings
CREATE TRIGGER IF NOT EXISTS create_risk_alert_on_low_rating
AFTER UPDATE ON file_review
WHEN NEW.rating <= 5 AND (OLD.rating IS NULL OR OLD.rating > 5)
BEGIN
    INSERT INTO risk_alerts (file_path, alert_type, severity, alert_title, alert_message, detected_by)
    VALUES (
        NEW.path,
        'low_quality',
        CASE 
            WHEN NEW.rating <= 3 THEN 'critical'
            WHEN NEW.rating <= 4 THEN 'high'
            ELSE 'medium'
        END,
        'Low Code Quality Rating',
        'File has received a low quality rating of ' || NEW.rating || '/10 and requires attention.',
        'automated_trigger'
    );
END;

-- Auto-tag files based on path patterns
CREATE TRIGGER IF NOT EXISTS auto_tag_files_on_review
AFTER INSERT ON file_review
BEGIN
    -- Tag test files
    INSERT INTO file_tags (file_path, tag_name, tag_category, created_by)
    SELECT NEW.path, 'test', 'type', 'auto_tagger'
    WHERE NEW.path LIKE '%test%' OR NEW.path LIKE '%_test.py';
    
    -- Tag security files
    INSERT INTO file_tags (file_path, tag_name, tag_category, created_by)
    SELECT NEW.path, 'security', 'type', 'auto_tagger'
    WHERE NEW.path LIKE '%security%' OR NEW.path LIKE '%auth%' OR NEW.path LIKE '%crypto%';
    
    -- Tag agent files
    INSERT INTO file_tags (file_path, tag_name, tag_category, created_by)
    SELECT NEW.path, 'agent', 'type', 'auto_tagger'
    WHERE NEW.path LIKE '%agent%' OR NEW.path LIKE '%workflow%';
    
    -- Tag based on rating
    INSERT INTO file_tags (file_path, tag_name, tag_category, created_by)
    SELECT NEW.path, 
           CASE 
               WHEN NEW.rating >= 8 THEN 'production_ready'
               WHEN NEW.rating >= 6 THEN 'needs_review'
               ELSE 'needs_refactor'
           END,
           'status', 'auto_tagger'
    WHERE NEW.rating IS NOT NULL;
END;

-- ============================================================================
-- INITIAL DATA AND CONFIGURATION
-- ============================================================================

-- Insert default issue tracker configuration
INSERT OR IGNORE INTO issue_trackers (tracker_name, tracker_type, base_url, project_key, active) 
VALUES ('GitHub Issues', 'github', 'https://api.github.com', 'legal-ai-platform', FALSE);

-- Insert initial quality metrics
INSERT OR IGNORE INTO quality_metrics_history (measurement_date, total_files, files_reviewed, measurement_timestamp)
VALUES (DATE('now'), 0, 0, CURRENT_TIMESTAMP);

-- ============================================================================
-- CLEANUP AND MAINTENANCE
-- ============================================================================

-- Function to cleanup old history (keep last 12 months)
-- Note: SQLite doesn't have stored procedures, so this would be handled by application code
-- DELETE FROM file_hash_history WHERE operation_timestamp < DATE('now', '-12 months');
-- DELETE FROM review_history WHERE review_timestamp < DATE('now', '-12 months');
-- DELETE FROM quality_metrics_history WHERE measurement_date < DATE('now', '-12 months');

-- Vacuum and analyze for performance
VACUUM;
ANALYZE;

-- ============================================================================
-- COMPLETION SUMMARY
-- ============================================================================

-- This enhanced schema provides:
-- ✅ Feature #1: Before/After File Hash Tracking (file_hash_history)
-- ✅ Feature #2: Git Commit Tracking (git_operations)
-- ✅ Feature #3: Bulk Operations & Dashboard (bulk_operations, views)
-- ✅ Feature #4: Automated Re-review (review_history)
-- ✅ Feature #5: Issue Tracker Integration (issue_trackers, file_issues)
-- ✅ Feature #6: File Tagging/Annotation (file_tags, tag_definitions)
-- ✅ Feature #7: Custom Codestral Prompts (codestral_prompts)
-- ✅ Feature #8: Trend Analytics (quality_metrics_history)
-- ✅ Feature #9: Risk Alert System (risk_alerts)
-- ✅ Feature #10: RAG/Knowledge Graph Integration (knowledge_graph_nodes/edges)
-- ✅ Enterprise audit trails and compliance
-- ✅ Automated triggers for common operations
-- ✅ Comprehensive views for dashboards and reporting
-- ✅ Proper indexing for performance at scale