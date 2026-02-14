import hashlib
import logging  # noqa: E402
import os  # noqa: E402
from datetime import datetime  # noqa: E402
from multiprocessing import Pool, cpu_count  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Tuple  # noqa: E402

# Setup basic logging for this module
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class FileScanner:
    """
    Scans a specified project directory, collects metadata for all files,
    and calculates content hashes. Designed to be robust and efficient.
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        if not self.project_root.is_dir():
            raise ValueError(f"Project root is not a valid directory: {project_root}")
        logging.info(f"FileScanner initialized for project root: {self.project_root}")

        # Define file types to ignore (case-insensitive extensions)
        self.ignore_extensions = {
            ".pyc",
            ".pyo",
            ".pyd",
            ".bak",
            ".tmp",
            ".log",
            ".DS_Store",
            ".git",
            ".svn",
            ".vscode",
            ".idea",
            ".env",
            ".venv",
            ".zip",
            ".tar",
            ".gz",
            ".rar",
            ".7z",
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".jpg",
            ".jpeg",
            ".png",
            ".gi",
            ".bmp",
            ".ti",
            ".ico",
            ".mp3",
            ".wav",
            ".ogg",
            ".mp4",
            ".avi",
            ".mov",
            ".flv",
            ".pd",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".sqlite",
            ".db",
            ".sqlite3",  # Added database files to ignore list
        }
        # Define directories to ignore (case-insensitive names)
        self.ignore_directories = {
            "__pycache__",
            ".git",
            ".svn",
            ".vscode",
            ".idea",
            "node_modules",
            "venv",
            "env",
            "logs",
            "reports",
            "build",
            "dist",
            "output",
            "__MACOSX",
            "databases",
            "data",
            "temp",
            "tmp",
            "organized_docs",  # Added common data/output folders
        }

    @staticmethod
    def _calculate_file_hash_static(file_path: Path) -> Tuple[str, str]:
        """
        Calculates the SHA256 hash of a file's content.
        This is a static method to be compatible with multiprocessing.
        """
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):  # Read in 8KB chunks
                    hasher.update(chunk)
            return str(file_path), hasher.hexdigest()
        except Exception as e:
            logging.error(f"Error hashing file {file_path}: {e}")
            return str(file_path), "ERROR_HASHING"

    def scan_file_system(self) -> List[Dict[str, Any]]:  # noqa: C901
        """
        Scans the project root directory, collects file metadata,
        and uses multiprocessing for efficient hashing.
        """
        all_files_metadata = []
        files_to_hash = []

        for root, dirs, files in os.walk(self.project_root, topdown=True):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if d.lower() not in self.ignore_directories]

            for file_name in files:
                file_path = Path(root) / file_name
                file_extension = file_path.suffix.lower()

                if file_extension in self.ignore_extensions:
                    continue

                try:
                    file_size = file_path.stat().st_size
                    modified_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    relative_path = file_path.relative_to(self.project_root)

                    # For content, we might read small files directly or defer for AI analysis
                    content = None
                    if (
                        file_size < 1024 * 1024 * 5
                    ):  # Read content for files smaller than 5MB
                        try:
                            with open(
                                file_path, "r", encoding="utf-8", errors="ignore"
                            ) as f:
                                content = f.read()
                        except Exception as e:
                            logging.warning(
                                f"Could not read content of {file_path}: {e}"
                            )
                            content = None  # Ensure content is None if read fails

                    file_info = {
                        "file_path": str(file_path),
                        "relative_path": str(relative_path),
                        "file_name": file_name,
                        "file_extension": file_extension,
                        "file_size": file_size,
                        "modified_time": modified_time.isoformat(),
                        "content": content,
                        "content_hash": None,  # Will be filled by multiprocessing
                    }
                    all_files_metadata.append(file_info)
                    files_to_hash.append(file_path)  # Add only the path for hashing

                except Exception as e:
                    logging.error(f"Error processing file {file_path}: {e}")
                    continue

        # Use multiprocessing for hashing
        if files_to_hash:
            num_processes = max(1, cpu_count() - 1)  # Leave one core free
            logging.info(
                f"Starting multiprocessing pool with {num_processes} processes for hashing."
            )
            with Pool(processes=num_processes) as pool:
                hash_results = pool.map(
                    FileScanner._calculate_file_hash_static, files_to_hash
                )

            # Map hashes back to the metadata
            hash_map = {path: h for path, h in hash_results}
            for file_info in all_files_metadata:
                file_info["content_hash"] = hash_map.get(
                    file_info["file_path"], "ERROR_HASHING"
                )

        logging.info(f"Finished scanning. Discovered {len(all_files_metadata)} files.")
        return all_files_metadata
