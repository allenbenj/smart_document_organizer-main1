#!/usr/bin/env python3
"""Log tools folder cleanup to database"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('mem_db/data/documents.db')
cursor = conn.cursor()

# Log the cleanup action
cursor.execute('''
    INSERT INTO organization_actions 
    (action_type, target_path, old_value, new_value, confidence, reasoning, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?)
''', (
    'cleanup',
    'tools/',
    'Mixed files: 20 files including duplicates and empty files',
    'Organized: 12 core tools + 3 specialized subdirectories',
    0.95,
    'Deleted: database.py (empty), check_state.py, organize_final_products.py. Moved database inspectors to tools/db/. Result: Clean structure with analyzer, metadata, ai_organizer, fs_builder, workflow_watch, run_app as core utilities.',
    datetime.now().isoformat()
))

conn.commit()
print('✓ Logged tools folder cleanup to organization_actions table')

# Verify the entry
cursor.execute('SELECT * FROM organization_actions ORDER BY id DESC LIMIT 1')
row = cursor.fetchone()
print(f'✓ Entry ID: {row[0]} | Type: {row[1]} | Target: {row[2]}')

conn.close()
