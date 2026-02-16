#!/usr/bin/env python3
"""
Enhance Database Schema - Add missing tables from original schema
"""

import sqlite3
from datetime import datetime

def enhance_database():
    """Add missing tables to match original schema"""
    db_path = '/mnt/e/Coding_Project/project_tools/data/file_tracker_new.db'
    
    print("🔧 Enhancing database schema to match original...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Add missing tables from original schema
    
    # 1. document_topics (for topic modeling)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS document_topics (
        document_id INTEGER,
        topic_id INTEGER,
        probability REAL,
        FOREIGN KEY (document_id) REFERENCES files(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    )
    """)
    
    # 2. topics (referenced by document_topics)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_name TEXT NOT NULL,
        description TEXT,
        keywords TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 3. file_operations (track file operations)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS file_operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL,
        operation_type TEXT,
        notes TEXT,
        timestamp REAL DEFAULT (julianday('now'))
    )
    """)
    
    # 4. Enhance existing file_analysis table with missing columns
    try:
        cursor.execute("ALTER TABLE file_analysis ADD COLUMN key_functionality TEXT")
        print(" Added key_functionality column")
    except:
        pass  # Column already exists
    
    # 5. Add indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON files(file_path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_path ON file_analysis(file_path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_topics_name ON topics(topic_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_topics ON document_topics(document_id, topic_id)")
    
    # 6. Add some sample topics to get started
    sample_topics = [
        ('Configuration', 'Configuration and setup files', 'config,setup,json,yaml'),
        ('Documentation', 'Documentation and README files', 'readme,docs,guide,manual'),
        ('Testing', 'Test files and testing utilities', 'test,spec,mock,jest'),
        ('Development', 'Development tools and workflows', 'dev,build,workflow,tools'),
        ('AI/ML', 'Artificial Intelligence and Machine Learning', 'ai,ml,model,agent'),
        ('Database', 'Database related files', 'db,sql,schema,migration'),
        ('API', 'API and web service files', 'api,rest,endpoint,service'),
        ('UI/Frontend', 'User interface and frontend', 'ui,frontend,react,html,css'),
        ('Backend', 'Backend and server code', 'backend,server,controller,service'),
        ('Utilities', 'Utility and helper functions', 'util,helper,common,shared')
    ]
    
    for topic_name, description, keywords in sample_topics:
        cursor.execute("""
        INSERT OR IGNORE INTO topics (topic_name, description, keywords)
        VALUES (?, ?, ?)
        """, (topic_name, description, keywords))
    
    conn.commit()
    
    # Show current schema
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"\n Enhanced Database Schema:")
    print(f"Total Tables: {len(tables)}")
    for table in tables:
        print(f"   {table[0]}")
    
    # Show sample stats
    cursor.execute("SELECT COUNT(*) FROM files")
    total_files = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM file_analysis")
    analyzed_files = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM topics")
    total_topics = cursor.fetchone()[0]
    
    print(f"\n📈 Current Stats:")
    print(f"   Total Files: {total_files:,}")
    print(f"   Analyzed Files: {analyzed_files:,}")
    print(f"  ️ Topics Available: {total_topics}")
    print(f"   Analysis Progress: {(analyzed_files/total_files*100):.1f}%")
    
    conn.close()
    print(f"\n Database schema enhanced successfully!")

if __name__ == "__main__":
    enhance_database()