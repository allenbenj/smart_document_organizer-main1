"""
Database Inspector - Quickly inspect all SQLite databases in the project
"""
import sqlite3
import os
from pathlib import Path


def inspect_database(db_path: str, db_name: str):
    """Inspect a SQLite database and print its structure."""
    if not os.path.exists(db_path):
        print(f'\n⚠ {db_name} - NOT FOUND at {db_path}')
        return
        
    size_kb = os.path.getsize(db_path) / 1024
    print(f'\n📁 {db_name}')
    print(f'   Path: {db_path}')
    print(f'   Size: {size_kb:.1f} KB')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        if tables:
            print(f'   Tables:')
            for (table_name,) in tables:
                # Get row count
                cursor.execute(f'SELECT COUNT(*) FROM [{table_name}]')
                count = cursor.fetchone()[0]
                
                # Get column info
                cursor.execute(f'PRAGMA table_info([{table_name}])')
                columns = cursor.fetchall()
                col_names = [col[1] for col in columns[:5]]  # First 5 columns
                col_str = ', '.join(col_names)
                if len(columns) > 5:
                    col_str += f', ... ({len(columns)} total)'
                
                print(f'     - {table_name}: {count} rows')
                print(f'       Columns: {col_str}')
                
                # Show sample data if rows exist
                if count > 0 and count <= 5:
                    cursor.execute(f'SELECT * FROM [{table_name}] LIMIT 3')
                    rows = cursor.fetchall()
                    if rows:
                        print(f'       Sample: {rows[0][:3]}...')
        else:
            print('     (No tables found)')
            
        conn.close()
    except Exception as e:
        print(f'     Error: {e}')


if __name__ == '__main__':
    print('\n' + '='*80)
    print('📊 SQLITE DATABASE INSPECTION - Smart Document Organizer')
    print('='*80)
    
    databases = [
        ('mem_db/data/documents.db', 'Documents Database (Main document storage)'),
        ('mem_db/data/memory_proposals.db', 'Memory Proposals (AI organization proposals)'),
        ('databases/unified_memory.db', 'Unified Memory (Centralized memory system)'),
        ('databases/todo.db', 'Todo Database (Task tracking)'),
        ('agents/legal/organizer.db', 'Legal Organizer (Legal document organization)'),
        ('analysis_results.db', 'Analysis Results (Code analysis from database.py)'),
    ]
    
    for db_path, db_name in databases:
        inspect_database(db_path, db_name)
    
    print('\n' + '='*80)
    print('\n💡 TIP: Use database.py DatabaseManager to create analysis_results.db')
    print('   Example: python -c "from database import DatabaseManager; db = DatabaseManager(); db.add_project(\'test\', \'desc\', \'.\')"\n')
