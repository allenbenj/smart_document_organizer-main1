CREATE TABLE IF NOT EXISTS ontology_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ontology_type TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL,
    schema_json TEXT,
    lineage_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ontology_type, version)
);

CREATE TABLE IF NOT EXISTS ontology_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ontology_id INTEGER NOT NULL,
    term_id TEXT NOT NULL,
    label TEXT NOT NULL,
    attributes_json TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    UNIQUE(ontology_id, term_id),
    FOREIGN KEY (ontology_id) REFERENCES ontology_registry(id)
);

CREATE TABLE IF NOT EXISTS ontology_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ontology_id INTEGER NOT NULL,
    from_term TEXT NOT NULL,
    to_term TEXT NOT NULL,
    rel_type TEXT NOT NULL,
    properties_json TEXT,
    FOREIGN KEY (ontology_id) REFERENCES ontology_registry(id)
);
