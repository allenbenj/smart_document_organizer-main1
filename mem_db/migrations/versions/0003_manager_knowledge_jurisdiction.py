VERSION = 3
NAME = "manager_knowledge_jurisdiction"


def _is_expected_duplicate_column_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "duplicate column name" in msg or "no such table" in msg


def up(conn):
    try:
        conn.execute("ALTER TABLE manager_knowledge ADD COLUMN jurisdiction TEXT")
    except Exception as e:
        if _is_expected_duplicate_column_error(e):
            return
        raise
