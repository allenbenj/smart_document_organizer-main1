import sqlite3
import os

def examine_database(db_path):
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found")
        return

    print(f"\n=== Examining {db_path} ===")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

    print(f"Tables ({len(tables)}):")
    for table in tables:
        table_name = table[0]
        print(f"  {table_name}")

        # Get row count
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"    Rows: {count}")
        except:
            print("    Rows: Error counting")

        # Get columns
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            print(f"    Columns: {len(columns)}")
            for col in columns[:5]:  # Show first 5 columns
                print(f"      {col[1]} ({col[2]})")
            if len(columns) > 5:
                print(f"      ... and {len(columns) - 5} more")
        except:
            print("    Columns: Error getting info")

    conn.close()

# Examine both databases
examine_database("legal.db")
examine_database("scan_index.db")