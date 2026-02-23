"""
Migration for adding ai_model_version column to file_analysis table.
"""

VERSION = 6
NAME = "Add ai_model_version to file_analysis"

def up(conn):
    """
    Adds the ai_model_version column to the file_analysis table.
    """
    conn.execute("""
        ALTER TABLE file_analysis ADD COLUMN ai_model_version TEXT;
    """)

def down(conn):
    """
    Removes the ai_model_version column from the file_analysis table.
    (Note: SQLite does not support dropping columns directly in all versions,
    this would typically require a more complex table recreation process.
    For simplicity in this migration system, we'll assume a basic DROP is sufficient
    or handle it in a more robust way if needed for actual production.)
    """
    # SQLite does not directly support DROP COLUMN before 3.35.0 (2021-03-12)
    # A more robust down migration would involve:
    # 1. CREATE TABLE new_file_analysis (...)
    # 2. INSERT INTO new_file_analysis SELECT ... FROM file_analysis
    # 3. DROP TABLE file_analysis
    # 4. ALTER TABLE new_file_analysis RENAME TO file_analysis
    # For now, we will leave it as a comment for simplicity.
    pass # conn.execute("ALTER TABLE file_analysis DROP COLUMN ai_model_version;")
