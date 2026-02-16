# database_schema.py

import logging

class DatabaseSchema:
    """Handles database table creation and schema verification."""

    def __init__(self):
        self.table_name = 'files'
        self.columns = [
            'id INTEGER PRIMARY KEY AUTOINCREMENT',
            'filename TEXT',
            'filepath TEXT',
            'content TEXT',
            'metadata TEXT',
            'processed_content TEXT',
            'entities_with_links TEXT',
            'document_type TEXT',
            'features BLOB',
            'cluster_label INTEGER',
            'topics TEXT'
        ]

    def create_table(self, conn):
        """Create the 'files' table if it does not exist."""
        cursor = conn.cursor()
        create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                {', '.join(self.columns)}
            )
        """
        cursor.execute(create_table_sql)
        conn.commit()
        logging.debug(f"Created table '{self.table_name}' if not exists.")

    def ensure_columns(self, conn):
        """Ensure all required columns exist in the 'files' table."""
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({self.table_name});")
        existing_columns = [info[1] for info in cursor.fetchall()]

        for column_def in self.columns:
            column_name = column_def.split()[0]
            if column_name not in existing_columns:
                cursor.execute(f"ALTER TABLE {self.table_name} ADD COLUMN {colu\
mn_def};")
                logging.info(f"Added missing column '{column_name}' to '{self.t\
able_name}' table.")

        conn.commit()
        logging.debug(f"Ensured all columns exist in '{self.table_name}' table.\
")
