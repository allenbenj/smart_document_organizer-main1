import sqlite3
import os

def clean_database_references():
    """Remove database records for files that no longer exist"""

    # Clean legal.db
    if os.path.exists('legal.db'):
        print('=== CLEANING LEGAL.DB ===')
        conn = sqlite3.connect('legal.db')
        cursor = conn.cursor()

        # Get all file records
        cursor.execute("SELECT file_id, current_path FROM files")
        files = cursor.fetchall()

        removed_count = 0
        for file_id, current_path in files:
            if current_path and not os.path.exists(current_path):
                # Remove file record
                cursor.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
                # Remove related entities
                cursor.execute("DELETE FROM entities WHERE file_id = ?", (file_id,))
                # Remove related events
                cursor.execute("DELETE FROM events WHERE file_id = ?", (file_id,))
                # Remove other related records that have file_id
                cursor.execute("DELETE FROM citations WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM violations WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM content_cache WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM duplicates WHERE file_id_1 = ? OR file_id_2 = ?", (file_id, file_id))
                cursor.execute("DELETE FROM file_hashes WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM document_embeddings WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM cluster_members WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM document_topics WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM quality_metrics WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM misclassifications WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM user_corrections WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM document_lifecycle WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM document_deadlines WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM archival_candidates WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM document_references WHERE source_file_id = ? OR target_file_id = ?", (file_id, file_id))
                cursor.execute("DELETE FROM image_metadata WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM video_metadata WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM audio_metadata WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM extraction_failures WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM file_change_log WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM thread_members WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM bundle_members WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM party_associations WHERE file_id = ?", (file_id,))

                removed_count += 1
                if removed_count % 10 == 0:
                    print(f"  Removed {removed_count} file records...")

        conn.commit()
        print(f"Removed {removed_count} file records from legal.db")
        conn.close()

    # Clean scan_index.db
    if os.path.exists('scan_index.db'):
        print('\n=== CLEANING SCAN_INDEX.DB ===')
        conn = sqlite3.connect('scan_index.db')
        cursor = conn.cursor()

        # Get all file records
        cursor.execute("SELECT path FROM file_index")
        files = cursor.fetchall()

        removed_count = 0
        for (path,) in files:
            if not os.path.exists(path):
                cursor.execute("DELETE FROM file_index WHERE path = ?", (path,))
                removed_count += 1
                if removed_count % 1000 == 0:
                    print(f"  Removed {removed_count} file records...")

        conn.commit()
        print(f"Removed {removed_count} file records from scan_index.db")
        conn.close()

    print('\n=== CLEANUP COMPLETE ===')

if __name__ == '__main__':
    clean_database_references()