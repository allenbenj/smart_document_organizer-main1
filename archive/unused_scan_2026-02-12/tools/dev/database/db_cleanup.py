import hashlib
import os  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

# Add the project root and utils directory to the Python path
project_root = "/mnt/e/Coding_Project"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "utils"))

from enhanced_db_client import EnhancedDBClient  # noqa: E402


class DatabaseCleanup:
    def __init__(self, dry_run=True):
        self.db_client = EnhancedDBClient()
        self.dry_run = dry_run
        print(f"--- Database Cleanup Initialized (Dry Run: {self.dry_run}) ---")

    def run_cleanup(self):
        """
        Runs all cleanup tasks and prints a summary.
        """
        print("\n--- Starting Database Cleanup ---")

        all_files = self._get_all_files_from_db()

        self._purge_ghost_records(all_files)
        self._re_index_modified_files(all_files)
        self._deduplicate_files()

        print("\n--- Cleanup Complete ---")

    def _get_all_files_from_db(self) -> list[dict]:
        """Fetches all file records from the database."""
        conn = self.db_client.conn
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_path, content_hash FROM files")
        return [dict(row) for row in cursor.fetchall()]

    def _purge_ghost_records(self, all_files: list[dict]):
        """Deletes records from the DB that point to non-existent files."""
        print("\n--- 1. Purging 'ghost' records... ---")
        ghost_count = 0
        for file_record in all_files:
            if not Path(file_record["file_path"]).exists():
                ghost_count += 1
                print(f"  - Deleting record for: {file_record['file_path']}")
                if not self.dry_run:
                    self.db_client.delete_file_record(file_record["file_path"])
        print(f"  -> Found and purged {ghost_count} ghost records.")

    def _re_index_modified_files(self, all_files: list[dict]):
        """Updates the hash for files that have been modified."""
        print("\n--- 2. Re-indexing modified files... ---")
        modified_count = 0
        for file_record in all_files:
            path = Path(file_record["file_path"])
            if path.exists():
                try:
                    current_hash = self._get_file_hash(path)
                    if current_hash != file_record["content_hash"]:
                        modified_count += 1
                        print(f"  - Updating hash for: {file_record['file_path']}")
                        if not self.dry_run:
                            self.db_client.update_file_hash(
                                file_record["file_path"], current_hash
                            )
                except Exception as e:
                    print(f"  [!] Could not hash {path}: {e}")
        print(f"  -> Found and re-indexed {modified_count} modified files.")

    def _deduplicate_files(self):
        """Finds and archives duplicate files."""
        print("\n--- 3. De-duplicating files... ---")

        duplicates = self.db_client.get_duplicate_sets()
        dedup_count = 0

        for content_hash, file_paths_str in duplicates.items():
            file_paths = file_paths_str.split("; ")

            # Simple strategy: keep the one with the "cleanest" name
            file_paths.sort(key=lambda p: len(p))
            canonical_file = file_paths[0]
            print(f"\n  - Keeping: {canonical_file}")

            for duplicate_path in file_paths[1:]:
                dedup_count += 1
                print(f"    - Archiving: {duplicate_path}")
                if not self.dry_run:
                    self._archive_file(Path(duplicate_path))
                    self.db_client.delete_file_record(duplicate_path)

        print(f"  -> Archived {dedup_count} duplicate files.")

    def _archive_file(self, file_path: Path):
        """Moves a file to the archive directory."""
        archive_path = Path("/mnt/e/Coding_Project/_project_archive/")
        if file_path.exists():
            try:
                shutil.move(file_path, archive_path / file_path.name)
            except Exception as e:
                print(f"    [!] Could not archive {file_path}: {e}")

    def _get_file_hash(self, file_path: Path) -> str:
        """Calculates the SHA256 hash of a file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()


def main():
    dry_run = "--execute" not in sys.argv
    cleanup = DatabaseCleanup(dry_run=dry_run)
    cleanup.run_cleanup()


if __name__ == "__main__":
    main()
