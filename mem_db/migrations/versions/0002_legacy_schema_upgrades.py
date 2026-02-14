VERSION = 2
NAME = "legacy_schema_upgrades"


_STATEMENTS = [
    "ALTER TABLE files_index ADD COLUMN mime_source TEXT",
    "ALTER TABLE files_index ADD COLUMN sha256 TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN ontology_entity_id TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN framework_type TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN components_json TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN legal_use_cases_json TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN preferred_perspective TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN is_canonical INTEGER DEFAULT 0",
    "ALTER TABLE manager_knowledge ADD COLUMN issue_category TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN severity TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN impact_description TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN root_cause_json TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN fix_status TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN resolution_evidence TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN resolution_date TIMESTAMP",
    "ALTER TABLE manager_knowledge ADD COLUMN next_review_date TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN related_frameworks_json TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN aliases_json TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN description TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN attributes_json TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN relations_json TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN sources_json TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN verified INTEGER DEFAULT 0",
    "ALTER TABLE manager_knowledge ADD COLUMN verified_by TEXT",
    "ALTER TABLE manager_knowledge ADD COLUMN user_notes TEXT",
]


def _is_expected_duplicate_column_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "duplicate column name" in msg or "no such table" in msg


def up(conn):
    for stmt in _STATEMENTS:
        try:
            conn.execute(stmt)
        except Exception as e:
            if _is_expected_duplicate_column_error(e):
                continue
            raise
