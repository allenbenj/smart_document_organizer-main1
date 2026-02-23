VERSION = 4
NAME = "learning_path_storage"


def up(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS aedis_learning_paths (
            path_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            objective_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            ontology_version INTEGER NOT NULL DEFAULT 1,
            heuristic_snapshot_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS aedis_learning_path_steps (
            path_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            title TEXT NOT NULL,
            instruction TEXT NOT NULL,
            objective_id TEXT NOT NULL,
            heuristic_ids_json TEXT,
            evidence_spans_json TEXT,
            difficulty INTEGER NOT NULL DEFAULT 1,
            completed INTEGER NOT NULL DEFAULT 0,
            step_order INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (path_id, step_id),
            FOREIGN KEY (path_id) REFERENCES aedis_learning_paths(path_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_learning_path_steps_path_order ON aedis_learning_path_steps(path_id, step_order)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_learning_path_steps_path_completed ON aedis_learning_path_steps(path_id, completed)"
    )
