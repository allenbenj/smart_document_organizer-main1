import os
import sqlite3  # noqa: E402
from pathlib import Path

# Updated to point to production databases
DB_PATHS = [
    Path("mem_db/data/documents.db"),
    Path("databases/unified_memory.db"),
    Path("mem_db/data/memory_proposals.db")
]

def inspect_db(path):
    print(f"\n--- Inspecting: {path} ---")
    if not path.exists():
        print(f"Error: Database file does not exist at {path}")
        return

    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        
        # List tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables found: {len(tables)}")
        for t in tables:
            print(f"  - {t[0]}")
            
        conn.close()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    print("For a full GUI experience, run 'python Launch_DB_Monitor.py'")
    for p in DB_PATHS:
        inspect_db(p)
