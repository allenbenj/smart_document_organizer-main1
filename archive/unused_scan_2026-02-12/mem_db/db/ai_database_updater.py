import logging
import os  # noqa: E402
import sqlite3  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any, Dict, List, Optional, Tuple  # noqa: E402

from core.ai_analyzer import AIAnalyzer  # noqa: E402
from core.ai_client import AIClient  # noqa: E402

# Import the new centralized core modules
from core.database_config import DatabaseConfig  # noqa: E402

# Setup basic logging for this module
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class AIDatabaseUpdater:
    """
    Uses AI to analyze and update file information in the file_tracker database.
    This class now integrates with the centralized DatabaseConfig, AIClient, and AIAnalyzer.
    """

    def __init__(
        self, db_config: DatabaseConfig, ai_client: AIClient, ai_analyzer: AIAnalyzer
    ):
        """
        Initializes the AIDatabaseUpdater with instances of core components.

        Args:
            db_config (DatabaseConfig): Centralized database configuration.
            ai_client (AIClient): Centralized AI model client.
            ai_analyzer (AIAnalyzer): Centralized AI content analyzer.
        """
        self.db_config = db_config
        self.ai_client = ai_client
        self.ai_analyzer = ai_analyzer
        self.file_tracker_db_path = self.db_config.get_db_path("file_tracker")

        if not self.file_tracker_db_path:
            logging.error("File tracker database path not configured. Exiting.")
            raise ValueError("File tracker database path is not configured.")

        logging.info("AIDatabaseUpdater initialized.")

    def get_unanalyzed_files(self, limit: int = 50) -> List[Tuple[int, str, str]]:
        """
        Retrieves files from the 'files' table that have not yet been analyzed
        (i.e., no corresponding entry in 'file_analysis' table).

        Args:
            limit (int): The maximum number of unanalyzed files to retrieve.

        Returns:
            List[Tuple[int, str, str]]: A list of tuples, each containing
                                        (file_id, file_path, content).
        """
        conn = self.db_config.get_connection("file_tracker", read_only=True)
        if not conn:
            logging.error(
                "Failed to connect to file_tracker database to get unanalyzed files."
            )
            return []

        cursor = conn.cursor()
        query = """
        SELECT f.id, f.file_path, f.content
        FROM files f
        LEFT JOIN file_analysis fa ON f.file_path = fa.file_path
        WHERE fa.file_path IS NULL
        AND f.content IS NOT NULL
        AND length(f.content) > 10 -- Ensure content is not empty or too short
        AND f.file_extension IN ('.py', '.js', '.md', '.txt', '.json', '.yaml', '.yml', '.sql', '.sh', '.html', '.css')
        LIMIT ?
        """
        try:
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            logging.info(f"Retrieved {len(results)} unanalyzed files.")
            return results
        except sqlite3.Error as e:
            logging.error(f"Error retrieving unanalyzed files: {e}")
            return []
        finally:
            conn.close()

    def save_analysis(self, file_path: str, analysis: Dict[str, Any]):
        """
        Saves the structured AI analysis result to the file_analysis table.
        This method is similar to the one in AIFileSystemBuilder, but kept here
        for the specific context of updating existing files.

        Args:
            file_path (str): The path of the analyzed file.
            analysis (Dict[str, Any]): The structured analysis data.
        """
        conn = self.db_config.get_connection("file_tracker", read_only=False)
        if not conn:
            logging.error(
                "Failed to connect to file_tracker database to save analysis."
            )
            return

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
            INSERT OR REPLACE INTO file_analysis
            (file_path, file_name, file_type, programming_language, primary_purpose,
             key_functionality, dependencies, complexity_score, analysis_timestamp,
             analysis_notes, ai_model_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    file_path,
                    os.path.basename(file_path),
                    analysis.get("file_type", "unknown"),
                    analysis.get("programming_language", "unknown"),
                    analysis.get("primary_purpose", "Unknown"),
                    analysis.get("key_functionality", ""),
                    analysis.get("dependencies", ""),
                    analysis.get("complexity_score", 0),
                    datetime.now().timestamp(),
                    analysis.get("analysis_notes", ""),
                    analysis.get("ai_model_used", "unknown"),
                ),
            )
            conn.commit()
            logging.info(f"Analysis saved for {file_path}")
        except sqlite3.Error as e:
            logging.error(f"Error saving analysis for {file_path} to database: {e}")
            conn.rollback()
        finally:
            conn.close()

    def update_file_status(self, file_id: int, status: str = "analyzed"):
        """
        Updates the status of a file in the 'files' table.

        Args:
            file_id (int): The ID of the file to update.
            status (str): The new status (e.g., 'analyzed', 'error').
        """
        conn = self.db_config.get_connection("file_tracker", read_only=False)
        if not conn:
            logging.error(
                f"Failed to connect to file_tracker to update status for file_id {file_id}."
            )
            return

        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE files SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, file_id),
            )
            conn.commit()
            logging.info(f"Updated status for file_id {file_id} to '{status}'.")
        except sqlite3.Error as e:
            logging.error(f"Error updating status for file_id {file_id}: {e}")
        finally:
            conn.close()

    def run_analysis_batch(
        self, batch_size: int = 20, model_preference: str = "ollama"
    ) -> int:
        """
        Runs AI analysis on a batch of unanalyzed files.

        Args:
            batch_size (int): The number of files to process in this batch.
            model_preference (str): Preferred AI model to use ('ollama' or 'deepseek').

        Returns:
            int: The number of files successfully analyzed in this batch.
        """
        print(f"\n--- Running AI Analysis Batch (batch size: {batch_size}) ---")
        files = self.get_unanalyzed_files(batch_size)

        if not files:
            print("No unanalyzed files found to process in this batch!")
            return 0

        print(f"Analyzing {len(files)} files...")
        analyzed_count = 0

        for file_id, file_path, content in files:
            if not content or content.strip() == "":
                print(f"  Skipping empty file: {os.path.basename(file_path)}")
                self.update_file_status(file_id, "skipped_empty")
                continue

            print(f" Analyzing: {os.path.basename(file_path)}")

            try:
                # Delegate analysis to AIAnalyzer
                analysis = self.ai_analyzer.analyze_file_content(
                    file_path, content, model_preference
                )

                if analysis:
                    self.save_analysis(file_path, analysis)
                    self.update_file_status(file_id, "analyzed")
                    analyzed_count += 1
                    print(
                        f" Successfully analyzed: {os.path.basename(file_path)} (Purpose: {analysis.get('primary_purpose', 'N/A')})"
                    )
                else:
                    self.update_file_status(file_id, "analysis_failed")
                    print(
                        f" AI analysis failed for {os.path.basename(file_path)}. See logs for details."
                    )

            except Exception as e:
                logging.error(f"Error processing file {file_path} in batch: {e}")
                self.update_file_status(file_id, "error_during_analysis")
                print(f" Error analyzing {os.path.basename(file_path)}: {e}")

        print(f"🎉 Completed analysis of {analyzed_count} files in this batch!")
        return analyzed_count

    def generate_summary_report(
        self, model_preference: str = "deepseek"
    ) -> Optional[str]:
        """
        Generates a comprehensive summary report of file analysis using an AI model.

        Args:
            model_preference (str): Preferred AI model to use ('ollama' or 'deepseek').

        Returns:
            Optional[str]: The path to the generated markdown report file, or None if failed.
        """
        conn = self.db_config.get_connection("file_tracker", read_only=True)
        if not conn:
            print("Failed to connect to file_tracker database for summary report.")
            return None

        cursor = conn.cursor()
        summary_data = []
        try:
            # Get analysis summary
            cursor.execute("""
            SELECT file_type, COUNT(*) as count,
                   GROUP_CONCAT(primary_purpose, '; ') as purposes
            FROM file_analysis
            GROUP BY file_type
            ORDER BY count DESC
            """)
            summary_data = cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error querying database for summary report: {e}")
            print(f"Error querying database for summary report: {e}")
            return None
        finally:
            conn.close()

        if not summary_data:
            print("No analysis data available to generate a summary report.")
            return None

        # Create summary prompt for AI
        file_type_breakdown = chr(10).join(  # noqa: F841
            [
                f"{ftype}: {count} files - {purposes[:200]}..."
                for ftype, count, purposes in summary_data
            ]
        )

        prompt = """
Analyze this file analysis summary and create a comprehensive report:

FILE TYPE BREAKDOWN:
{file_type_breakdown}

Please provide:
1. Overall system architecture insights
2. File type distribution analysis
3. Key components and their roles
4. Dependency patterns
5. Recommendations for organization

Make it professional and actionable.
"""
        print(f"Generating summary report with {model_preference.capitalize()}...")
        report_content = None
        if model_preference == "deepseek":
            report_content = self.ai_client.call_deepseek(prompt, max_tokens=2000)
        else:  # Default to Ollama
            report_content = self.ai_client.call_ollama(
                prompt, model="phi3:mini", max_tokens=2000
            )

        if not report_content:
            print(
                f"Failed to get response from {model_preference.capitalize()} for summary report."
            )
            return None

        # Save report
        timestamp = datetime.now().isoformat()
        report_file_name = f"file_analysis_report_{timestamp.replace(':', '-')}.md"
        output_dir = self.db_config.project_root / "reports"
        output_dir.mkdir(exist_ok=True)  # Ensure reports directory exists
        report_file_path = output_dir / report_file_name

        try:
            with open(report_file_path, "w", encoding="utf-8") as f:
                f.write("# File Analysis Report\n")
                f.write(
                    f"*Generated by {model_preference.capitalize()} AI on {timestamp}*\n\n"
                )
                f.write(report_content)
            print(f"📄 Report saved to: {report_file_path}")
            return str(report_file_path)
        except Exception as e:
            logging.error(f"Error saving summary report: {e}")
            print(f"Error saving summary report: {e}")
            return None


# Example usage (for testing this module directly)
if __name__ == "__main__":
    print("--- Testing AIDatabaseUpdater ---")

    # Initialize core components
    db_config = DatabaseConfig()
    ai_client = AIClient()
    ai_analyzer = AIAnalyzer(ai_client)

    updater = AIDatabaseUpdater(db_config, ai_client, ai_analyzer)

    # Note: For this to work effectively, file_tracker_new.db needs to exist
    # and have some files cataloged (e.g., by running AIFileSystemBuilder first).

    # Run analysis batch
    analyzed_count = updater.run_analysis_batch(
        batch_size=10, model_preference="ollama"
    )

    if analyzed_count > 0:
        # Generate summary report (can use DeepSeek or Ollama)
        report_file = updater.generate_summary_report(model_preference="deepseek")
        if report_file:
            print(f"Analysis complete! Summary report: {report_file}")
        else:
            print("Failed to generate summary report.")
    else:
        print("No files analyzed in this run, skipping summary report generation.")
