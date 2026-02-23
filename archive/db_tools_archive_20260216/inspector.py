#!/usr/bin/env python3
"""Check what's in our databases"""
import sqlite3
import os
from pathlib import Path

# Go up from tools/db/ to project root
project_root = Path(__file__).parent.parent.parent
databases = {
    'unified_memory': project_root / 'databases' / 'unified_memory.db',
    'documents': project_root / 'mem_db' / 'data' / 'documents.db',
    'memory_proposals': project_root / 'mem_db' / 'data' / 'memory_proposals.db',
}

for name, db_path in databases.items():
    print(f"\n{'='*60}")
    print(f"DATABASE: {name}")
    print(f"Path: {db_path}")
    print(f"{'='*60}")
    
    if not db_path.exists():
        print("  ❌ NOT FOUND")
        continue
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        print(f"\n📁 Tables ({len(tables)}):")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  • {table_name}: {count} rows")
        
        conn.close()
    except Exception as e:
        print(f"  ❌ Error: {e}")

print(f"\n{'='*60}")
print("Database check complete")
print(f"{'='*60}\n")
