CREATE TABLE IF NOT EXISTS aedis_provenance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_artifact_row_id INTEGER NOT NULL,
    source_sha256 TEXT NOT NULL,
    extractor_id TEXT NOT NULL,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (source_artifact_row_id) REFERENCES canonical_artifacts(id)
);

CREATE TABLE IF NOT EXISTS aedis_evidence_spans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provenance_id INTEGER NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    quote TEXT,
    FOREIGN KEY (provenance_id) REFERENCES aedis_provenance_records(id)
);

CREATE TABLE IF NOT EXISTS aedis_artifact_provenance_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provenance_id INTEGER NOT NULL,
    target_type TEXT NOT NULL, -- e.g., 'analysis', 'organization_proposal'
    target_id TEXT NOT NULL,
    FOREIGN KEY (provenance_id) REFERENCES aedis_provenance_records(id)
);

CREATE INDEX IF NOT EXISTS idx_provenance_source ON aedis_provenance_records(source_artifact_row_id);
CREATE INDEX IF NOT EXISTS idx_evidence_offsets ON aedis_evidence_spans(start_char, end_char);
