import asyncio
import json  # noqa: E402
import logging  # noqa: E402
import multiprocessing  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import sqlite3  # noqa: E402
import time  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402
from watchdog.events import FileSystemEventHandler  # noqa: E402
from watchdog.observers import Observer  # noqa: E402

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# --- Configuration Loader ---
class Config:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r") as f:
            self.config_data = yaml.safe_load(f)

        system_config = self.config_data.get("system", {})
        self.WATCH_DIR = Path(system_config.get("watch_directory", "watch"))
        self.OUTPUT_DIR = Path(system_config.get("output_directory", "organized"))
        self.PROCESSING_DIR = Path(
            system_config.get("processing_directory", "processing")
        )
        self.LOG_DIR = Path(system_config.get("log_directory", "logs"))
        self.BACKUP_DIR = Path(system_config.get("backup_directory", "backup"))
        self.METRICS_FILE = Path(
            system_config.get("metrics_file", "system_metrics.json")
        )

        keep_alive_config = self.config_data.get("keep_alive", {})
        self.HEARTBEAT_FILE = Path(
            keep_alive_config.get("heartbeat_file", "system_heartbeat.json")
        )
        self.KEEP_ALIVE_INTERVAL = keep_alive_config.get("interval_seconds", 10)

        processing_config = self.config_data.get("processing", {})
        self.MAX_WORKERS = processing_config.get(
            "max_workers", multiprocessing.cpu_count()
        )

        # Create directories if they don't exist
        for d in [
            self.WATCH_DIR,
            self.OUTPUT_DIR,
            self.PROCESSING_DIR,
            self.LOG_DIR,
            self.BACKUP_DIR,
        ]:
            d.mkdir(parents=True, exist_ok=True)

        logger.info("⚙️ Configuration loaded successfully.")


# --- Metrics Collection ---
class MetricsManager:
    def __init__(self, metrics_file):
        self.metrics_file = metrics_file
        self.stats = self.load_metrics()

    def load_metrics(self):
        try:
            with open(self.metrics_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "total_files_processed": 0,
                "successful_organizations": 0,
                "failed_organizations": 0,
                "time_metrics": {},
            }

    def save_metrics(self):
        try:
            with open(self.metrics_file, "w") as f:
                json.dump(self.stats, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")

    def update_metrics(self, category, processing_time):
        self.stats["total_files_processed"] += 1
        if category and category not in ["Unreadable", "Processing_Error"]:
            self.stats["successful_organizations"] += 1
        else:
            self.stats["failed_organizations"] += 1

        category = category or "Unknown_Error"  # Handle None case
        if category not in self.stats["time_metrics"]:
            self.stats["time_metrics"][category] = {"total_time": 0, "count": 0}

        self.stats["time_metrics"][category]["total_time"] += processing_time
        self.stats["time_metrics"][category]["count"] += 1
        self.save_metrics()

    def get_summary(self):
        summary = "\n📊 System Metrics Summary\n" + "=" * 30 + "\n"
        summary += f"Total Files Processed: {self.stats['total_files_processed']}\n"
        summary += (
            f"Successful Organizations: {self.stats['successful_organizations']}\n"
        )
        summary += f"Failed Organizations: {self.stats['failed_organizations']}\n"
        summary += "Average Processing Time per Category:\n"
        for cat, data in self.stats["time_metrics"].items():
            avg_time = data["total_time"] / data["count"] if data["count"] > 0 else 0
            summary += f" - {cat}: {avg_time:.4f} seconds ({data['count']} files)\n"
        return summary


# --- SQLite Memory Bank Manager ---
class MemoryBank:
    def __init__(self, db_path="organizer.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._setup_db()

    def _setup_db(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS classification_history (
                filename TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                last_updated TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def save_classification(self, filename, category):
        try:
            self.cursor.execute(
                """
                INSERT OR REPLACE INTO classification_history
                (filename, category, last_updated)
                VALUES (?, ?, ?)
            """,
                (filename, category, datetime.now().isoformat()),
            )
            self.conn.commit()
            logger.info(f"💾 Saved classification for '{filename}' as '{category}'.")
        except sqlite3.Error as e:
            logger.error(f"SQLite error when saving classification: {e}")

    def get_classification(self, filename):
        try:
            self.cursor.execute(
                "SELECT category FROM classification_history WHERE filename = ?",
                (filename,),
            )
            result = self.cursor.fetchone()
            if result:
                logger.debug(
                    f"🧠 Found classification for '{filename}' in memory: '{result[0]}'"
                )
                return result[0]
            return None
        except sqlite3.Error as e:
            logger.error(f"SQLite error when getting classification: {e}")
            return None

    def close(self):
        self.conn.close()


# --- Document Processing and Classification Engine ---
class DocumentProcessor:
    def __init__(self, memory_bank):
        self.memory_bank = memory_bank

    def extract_text(self, file_path):  # noqa: C901
        try:
            import pypdf  # noqa: E402

            if file_path.suffix.lower() == ".pd":
                text = ""
                with open(file_path, "rb") as file:
                    pdf_reader = pypdf.PdfReader(file)
                    for page in pdf_reader.pages:
                        text += page.extract_text() or ""
                        if len(text) > 10000:
                            break
                return text.strip()
            elif file_path.suffix.lower() in [".docx", ".xlsx"]:
                logger.warning(f"DOCX/XLSX processing not implemented: {file_path}")
                return ""
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read(10000)
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return None

    def get_legal_document_type(self, text, filename):
        # FIX: Check if memory_bank exists before using it. This allows
        # this class to be used in worker processes without a DB connection.
        if self.memory_bank:
            classification = self.memory_bank.get_classification(filename)
            if classification:
                return classification

        text_lower = text.lower() if text else ""
        if not text_lower:
            return "Unclassified/Empty_File"

        if any(
            word in text_lower
            for word in ["motion to", "plainti", "defendant", "court order"]
        ):
            return "Court_Documents/Motions"
        elif any(
            word in text_lower
            for word in ["agreement", "contract", "terms and conditions"]
        ):
            return "Agreements/General"
        elif any(word in text_lower for word in ["invoice", "financial statement"]):
            return "Financial/Invoices"

        return "Miscellaneous"


# --- File Organizer Class ---
class LegalOrganizer:
    def __init__(self, config):
        self.config = config

    def _generate_intelligent_filename(self, text, original_name):
        case_no_match = re.search(r"(case no\.?|docket no\.?)\s*([\w-]+)", text, re.I)
        parties_match = re.search(r"(plaintiff)\s+v\.\s+(defendant)", text, re.I)

        if case_no_match and parties_match:
            case_no = case_no_match.group(2).replace("/", "_")
            plaintiff = parties_match.group(1)
            defendant = parties_match.group(2)
            base_name = f"{case_no}_{plaintiff}_v_{defendant}"
            return f"{base_name}{Path(original_name).suffix}"

        return original_name

    def move_file(self, source_path, category):
        try:
            text_content = ""
            with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
                text_content = f.read(10000)

            new_name = self._generate_intelligent_filename(
                text_content, source_path.name
            )
            target_dir = self.config.OUTPUT_DIR / category
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / new_name

            counter = 1
            original_stem = Path(new_name).stem
            original_suffix = Path(new_name).suffix
            while target_path.exists():
                unique_name = f"{original_stem}_{counter}{original_suffix}"
                target_path = target_dir / unique_name
                counter += 1

            shutil.move(str(source_path), str(target_path))
            logger.info(f"✅ Moved '{source_path.name}' to '{target_path}'.")
            return target_path
        except Exception as e:
            logger.error(f"❌ Failed to move file {source_path}: {e}")
            return None


# --- WORKER FUNCTION FOR MULTIPROCESSING ---
# FIX: This function MUST be at the top level (not inside a class) for multiprocessing to work.
# It is designed to be self-contained and avoids using un-pickleable objects from the main process.
def process_file_worker(args):
    """Worker function for parallel processing that is self-contained."""
    file_path, config_data = args
    start_time = time.time()

    # A lightweight object to hold config paths, created from serializable dict
    class WorkerConfig:
        def __init__(self, data):
            system_config = data.get("system", {})
            self.PROCESSING_DIR = Path(
                system_config.get("processing_directory", "processing")
            )
            self.OUTPUT_DIR = Path(system_config.get("output_directory", "organized"))

    try:
        config = WorkerConfig(config_data)
        organizer = LegalOrganizer(config)
        # Create a processor without a database connection.
        processor = DocumentProcessor(memory_bank=None)

        processing_path = config.PROCESSING_DIR / file_path.name
        if not file_path.exists():
            return None  # File was likely grabbed by another process
        shutil.move(str(file_path), str(processing_path))

        text_content = processor.extract_text(processing_path)
        category = processor.get_legal_document_type(text_content, processing_path.name)

        organizer.move_file(processing_path, category)
        end_time = time.time()

        # Return results to the main process for DB/metrics updates
        return (file_path.name, category, end_time - start_time)
    except Exception as e:
        print(
            f"[WORKER ERROR] Failed to process {file_path.name}: {e}"
        )  # Use print as logger may not be configured in child process
        end_time = time.time()
        return (file_path.name, "Processing_Error", end_time - start_time)


# --- Continuous Document Organizer - The Main Engine ---
class ContinuousDocumentOrganizer:
    def __init__(self, config, memory_bank, metrics_manager):
        self.config = config
        self.memory_bank = memory_bank
        self.metrics_manager = metrics_manager
        self.processor = DocumentProcessor(self.memory_bank)
        self.organizer = LegalOrganizer(config)
        self.running = False

    async def _send_keep_alive(self):
        while self.running:
            try:
                heartbeat_data = {
                    "timestamp": datetime.now().isoformat(),
                    "status": "active",
                    "processed_files": self.metrics_manager.stats.get(
                        "total_files_processed", 0
                    ),
                }
                with open(self.config.HEARTBEAT_FILE, "w") as f:
                    json.dump(heartbeat_data, f)
                logger.debug("❤️ Heartbeat sent.")
                await asyncio.sleep(self.config.KEEP_ALIVE_INTERVAL)
            except Exception as e:
                logger.error(f"Error sending keep-alive heartbeat: {e}")
                await asyncio.sleep(self.config.KEEP_ALIVE_INTERVAL)

    def process_single_file(self, file_path: Path):
        """Processes a single file. Used by the watchdog handler in the main thread."""
        logger.info(f"Processing new file: {file_path.name}")
        start_time = time.time()
        category = "Processing_Error"
        try:
            processing_path = self.config.PROCESSING_DIR / file_path.name
            shutil.move(str(file_path), str(processing_path))

            text_content = self.processor.extract_text(processing_path)
            category = self.processor.get_legal_document_type(
                text_content, processing_path.name
            )

            self.organizer.move_file(processing_path, category)
            self.memory_bank.save_classification(file_path.name, category)
        except Exception as e:
            logger.error(f"❌ Error processing {file_path}: {e}")
        finally:
            end_time = time.time()
            self.metrics_manager.update_metrics(category, end_time - start_time)

    async def start_watching(self):
        self.running = True
        logger.info("🚀 Starting continuous document organizer...")

        class FileHandler(FileSystemEventHandler):
            def __init__(self, parent_organizer):
                self.parent = parent_organizer

            def on_created(self, event):
                if not event.is_directory:
                    logger.info(f"✨ New file detected: {event.src_path}")
                    # Call the single file processor, which runs in the main thread
                    self.parent.process_single_file(Path(event.src_path))

        event_handler = FileHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(self.config.WATCH_DIR), recursive=False)
        observer.start()
        logger.info(f"🔍 Watching for new files in: {self.config.WATCH_DIR}")

        try:
            await self._send_keep_alive()
        except asyncio.CancelledError:
            logger.info("Service shutting down.")
        finally:
            observer.stop()
            observer.join()
            self.running = False


# FIX: The entire __main__ block has been restructured for clarity, correct logic flow,
# and proper exception handling.
if __name__ == "__main__":
    # For Windows compatibility with multiprocessing
    multiprocessing.freeze_support()

    memory_bank = None  # Define here to ensure it's accessible in the `finally` block
    try:
        # --- 1. Initialization ---
        config = Config()
        memory_bank = MemoryBank()
        metrics_manager = MetricsManager(config.METRICS_FILE)

        # --- 2. Process existing files on startup using multiprocessing ---
        files_to_process = [f for f in config.WATCH_DIR.glob("*") if f.is_file()]
        if files_to_process:
            logger.info(
                f"Found {len(files_to_process)} existing files. Processing in parallel..."
            )

            # Prepare arguments for the worker function (file path and serializable config data)
            worker_args = [(f, config.config_data) for f in files_to_process]

            with multiprocessing.Pool(processes=config.MAX_WORKERS) as pool:
                results = pool.map(process_file_worker, worker_args)

            # Process results in the main thread to update database and metrics
            for result in results:
                if result is None:
                    continue
                filename, category, proc_time = result
                logger.info(
                    f"Startup result for '{filename}': Category='{category}', Time={proc_time:.2f}s"
                )
                if category and category != "Processing_Error":
                    memory_bank.save_classification(filename, category)
                metrics_manager.update_metrics(category, proc_time)
            logger.info("Startup scan complete.")

        # --- 3. Start the continuous monitoring service ---
        # This object uses the already-updated memory_bank and metrics
        organizer_system = ContinuousDocumentOrganizer(
            config, memory_bank, metrics_manager
        )
        asyncio.run(organizer_system.start_watching())

    except KeyboardInterrupt:
        logger.info("\n🛑 Ctrl+C detected. Shutting down gracefully...")

    except Exception as e:
        logger.critical(f"An unexpected critical error occurred: {e}", exc_info=True)

    finally:
        # This block will run whether the script exits cleanly or with an error
        if "metrics_manager" in locals():
            print(metrics_manager.get_summary())
        if memory_bank is not None:
            memory_bank.close()
            logger.info("💾 Memory bank connection closed.")
        logger.info("System shutdown complete.")
