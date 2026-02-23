import sqlite3
import os
import hashlib
from pathlib import Path
from datetime import datetime

def calculate_sha256(file_path):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except:
        return None

def index_all_files():
    """Index all remaining files in Organization_Folder into legal.db"""

    conn = sqlite3.connect('legal.db')
    cursor = conn.cursor()

    # Get already indexed files
    cursor.execute("SELECT current_path FROM files")
    indexed_files = {row[0] for row in cursor.fetchall()}

    print(f"Already indexed: {len(indexed_files)} files")

    # Scan all files
    root_path = Path('E:\\Organization_Folder')
    all_files = []

    print("\nScanning Organization_Folder for all files...")
    for file_path in root_path.rglob('*'):
        if file_path.is_file():
            # Skip database files themselves
            if file_path.suffix.lower() in ['.db', '.sqlite', '.sqlite3']:
                continue
            all_files.append(file_path)

    print(f"Found {len(all_files)} total files")

    # Filter out already indexed
    new_files = [f for f in all_files if str(f) not in indexed_files]
    print(f"New files to index: {len(new_files)}")

    if not new_files:
        print("All files are already indexed!")
        conn.close()
        return

    # Add new files to database
    added_count = 0
    for file_path in new_files:
        try:
            # Calculate hash
            file_hash = calculate_sha256(file_path)
            if not file_hash:
                continue

            # Get file info
            file_stat = file_path.stat()
            file_id = f"{file_hash[:8]}-{added_count}"

            # Insert into database
            cursor.execute("""
                INSERT INTO files (
                    file_id,
                    sha256_hash,
                    ingestion_ts,
                    first_seen_path,
                    current_path,
                    lifecycle_state,
                    last_modified_ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file_id,
                file_hash,
                datetime.now().isoformat(),
                str(file_path),
                str(file_path),
                'ACTIVE',
                datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            ))

            # Add ingestion event
            cursor.execute("""
                INSERT INTO events (
                    event_id,
                    file_id,
                    event_type,
                    event_data,
                    timestamp
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                f"evt-{file_id}",
                file_id,
                'ingestion',
                f'{{"path": "{str(file_path)}", "size": {file_stat.st_size}}}',
                datetime.now().isoformat()
            ))

            added_count += 1

            if added_count % 100 == 0:
                conn.commit()
                print(f"  Indexed {added_count} files...")

        except Exception as e:
            print(f"  Error indexing {file_path}: {e}")
            continue

    conn.commit()
    print(f"\nSuccessfully indexed {added_count} new files into legal.db")

    # Show summary
    cursor.execute("SELECT COUNT(*) FROM files")
    total = cursor.fetchone()[0]
    print(f"Total files now in legal.db: {total}")

    conn.close()

if __name__ == '__main__':
    index_all_files()
