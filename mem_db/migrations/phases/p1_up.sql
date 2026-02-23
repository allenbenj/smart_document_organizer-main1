CREATE TABLE IF NOT EXISTS canonical_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    source_uri TEXT,
    mime_type TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artifact_id, sha256)
);

CREATE TABLE IF NOT EXISTS canonical_artifact_blobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_row_id INTEGER NOT NULL,
    blob_locator TEXT NOT NULL,
    content_size_bytes INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (artifact_row_id) REFERENCES canonical_artifacts(id)
);

CREATE TABLE IF NOT EXISTS canonical_artifact_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_row_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_data_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (artifact_row_id) REFERENCES canonical_artifacts(id)
);

CREATE TRIGGER IF NOT EXISTS prevent_canonical_artifacts_update
BEFORE UPDATE ON canonical_artifacts
BEGIN
    SELECT RAISE(ABORT, 'Mutation of canonical artifacts is forbidden.');
END;

CREATE TRIGGER IF NOT EXISTS prevent_canonical_artifacts_delete
BEFORE DELETE ON canonical_artifacts
BEGIN
    SELECT RAISE(ABORT, 'Deletion of canonical artifacts is forbidden.');
END;
