"""
Migration for creating the memory_code_links table.
"""

VERSION = 5
NAME = "Create memory_code_links table"

def up(conn):
    """
    Creates the memory_code_links table.
    """
    conn.execute("""
        CREATE TABLE memory_code_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_record_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            confidence REAL DEFAULT 1.0,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(memory_record_id) REFERENCES memory_records(record_id) ON DELETE CASCADE,
            UNIQUE(memory_record_id, file_path, relation_type)
        )
    """)
    conn.execute("CREATE INDEX idx_memory_code_links_memory_record_id ON memory_code_links(memory_record_id)")
    conn.execute("CREATE INDEX idx_memory_code_links_file_path ON memory_code_links(file_path)")

def down(conn):
    """
    Removes the memory_code_links table.
    """
    conn.execute("DROP TABLE IF EXISTS memory_code_links")
