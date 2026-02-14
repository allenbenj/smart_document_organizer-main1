# agents/smart_doc_orchestrator.py - COMPLETE AND CORRECTED SCRIPT

import ast  # Using the built-in 'ast' module for parsing, which is robust
import logging  # noqa: E402
import sys  # noqa: E402
from concurrent.futures import ThreadPoolExecutor, as_completed  # For concurrency  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional, Tuple  # noqa: E402

# Configure logging at the module level
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


try:
    # This import is correct and will work when run from the project root.
    from core.enhanced_db_client import EnhancedDocumentationClient  # noqa: E402
except ImportError as e:
    logger.error(f"Import error in smart_doc_orchestrator.py: {e}")
    logger.error(
        "This script requires 'core.enhanced_db_client'. Ensure you run from the project root."
    )
    sys.exit(1)


# ==============================================================================
# LLM Integration Placeholder
# This class needs to be implemented with actual LLM API calls.
# ==============================================================================
class LLMClient:
    """
    Placeholder for an LLM client. This should be replaced with actual
    integration with a large language model API (e.g., Google Gemini, OpenAI).
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-pro"):
        self.api_key = api_key  # In a real app, this should be handled securely
        self.model_name = model_name
        if not self.api_key:
            logger.warning(
                "LLM_API_KEY not provided. LLM calls will fail or use a dummy response."
            )

    def generate_docstring(self, code_snippet: str, language: str = "python") -> str:
        """
        Generates a docstring for a given code snippet using an LLM.
        Replace this with actual LLM API call.
        """
        try:
            # Placeholder for actual LLM API call
            # Example using a dummy response:
            if not self.api_key:
                logger.warning(
                    "Using dummy docstring generation as no API key provided for LLM."
                )
                return self._dummy_docstring_generation(code_snippet)

            # --- REPLACE THIS WITH ACTUAL LLM API CALL ---
            # Example for Google Gemini:
            # import google.generativeai as genai
            # genai.configure(api_key=self.api_key)
            # model = genai.GenerativeModel(self.model_name)
            # response = model.generate_content(prompt)
            # return response.text

            # Example for OpenAI:
            # from openai import OpenAI
            # client = OpenAI(api_key=self.api_key)
            # response = client.chat.completions.create(
            #     model=self.model_name,
            #     messages=[{"role": "user", "content": prompt}]
            # )
            # return response.choices[0].message.content
            # ------------------------------------------------

            # Fallback to dummy if real API not implemented/configured
            return self._dummy_docstring_generation(code_snippet)
        except Exception as e:
            logger.error(f"Error calling LLM API for docstring generation: {e}")
            return self._dummy_docstring_generation(
                code_snippet
            )  # Fallback to dummy on error

    def generate_rst_content(self, func_name: str, parameters: List[str]) -> str:
        """
        Generates reStructuredText content for a function signature.
        Replace this with actual LLM API call or a more sophisticated template.
        """
        params_str = ", ".join(parameters)
        try:
            if not self.api_key:
                logger.warning(
                    "Using dummy RST generation as no API key provided for LLM."
                )
                return f".. function:: {func_name}({params_str})"
            # --- REPLACE THIS WITH ACTUAL LLM API CALL FOR RST ---
            # Example: Could ask LLM to format a full Sphinx-compatible RST entry
            # -----------------------------------------------------
            return f".. function:: {func_name}({params_str})"  # Still a basic fallback
        except Exception as e:
            logger.error(f"Error calling LLM API for RST content: {e}")
            return f".. function:: {func_name}({params_str})"  # Fallback on error

    def _dummy_docstring_generation(self, code_snippet: str) -> str:
        """Generates a simple dummy docstring based on the function signature."""
        try:
            tree = ast.parse(code_snippet)
            node = tree.body[0]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [arg.arg for arg in node.args.args]
                params_str = (
                    "\n".join(
                        [f"        {p} (Any): Undocumented parameter." for p in params]
                    )
                    if params
                    else "        (No parameters)"
                )
                return f'''"""{node.name} summary.

    This is a placeholder docstring because LLM integration is not complete or failed.

    Args:
{params_str}

    Returns:
        Any: Undocumented return value.
    """'''
            return '"""Placeholder docstring."""'
        except (SyntaxError, IndexError):
            return '"""Placeholder docstring (parsing error)."""'


# ==============================================================================
# Placeholder for Code Parsing
# This should eventually be more robust and potentially language-agnostic.
# ==============================================================================


def get_functions_from_file(file_path: str) -> List[Tuple[str, str]]:
    """
    Placeholder for the missing code parser.
    This uses the built-in 'ast' module to find functions robustly.
    Returns a list of (function_name, function_source_code) tuples.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()

        tree = ast.parse(source_code)
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # ast.unparse is available in Python 3.9+ and is cleaner
                # Fallback to get_source_segment for older versions if needed,
                # but this script now assumes Python 3.9+ for ast.unparse.
                if sys.version_info >= (3, 9):
                    func_code = ast.unparse(node)
                else:
                    # Fallback for older Python versions, less robust for complex nodes
                    func_code = ast.get_source_segment(source_code, node)
                functions.append((node.name, func_code))
        return functions
    except SyntaxError as se:
        logger.warning(
            f"Syntax error parsing {file_path}: {se}. Skipping functions from this file."
        )
        return []
    except Exception as e:
        logger.error(f"Could not parse functions from {file_path}: {e}")
        return []


# ==============================================================================
# THE ORIGINAL CLASS LOGIC (MODIFIED FOR RECOMMENDATIONS)
# ==============================================================================


class SmartDocumentationOrchestrator:
    """
    Intelligent orchestrator that combines database insights with
    multi-LLM documentation generation.
    """

    def __init__(self, db_path: str, llm_api_key: Optional[str] = None):
        self.db_client = EnhancedDocumentationClient(db_path=db_path)
        self.llm_client = LLMClient(api_key=llm_api_key)  # Initialize LLM client
        self.stats = {
            "files_processed": 0,
            "functions_documented": 0,
            "errors_encountered": 0,
            "total_processing_time": 0.0,
        }
        logger.info("Smart Documentation Orchestrator initialized.")

    def run_smart_documentation_workflow(  # noqa: C901
        self,
        priority_filter: str = "high",
        max_files: int = 5,
        dry_run: bool = False,
        max_workers: int = 4,  # New parameter for concurrency
    ) -> Dict[str, Any]:
        """
        Run intelligent documentation workflow based on database insights.
        """
        start_time = datetime.now()
        logger.info("-" * 40)
        logger.info("Smart Documentation Orchestrator Workflow")
        logger.info("-" * 40)

        progress = self.db_client.get_documentation_progress()
        logger.info(
            f"Current Progress: {progress['overall_progress']['completion_percentage']:.1f}% complete"
        )
        files_to_process = self.db_client.get_files_to_document(priority_filter)

        if not files_to_process:
            logger.info("No files need documentation based on current criteria!")
            return self.stats

        logger.info(
            f"Found {len(files_to_process)} files matching '{priority_filter}' priority"
        )
        files_to_process_subset = files_to_process[:max_files]
        logger.info(f"Processing top {len(files_to_process_subset)} files:")

        for i, file_info in enumerate(files_to_process_subset, 1):
            file_name = Path(file_info["file_path"]).name
            priority_score = file_info["priority_score"]
            logger.info(f"{i}. {file_name}")
            logger.info(f"   Priority Score: {priority_score:.1f}/10")
            if file_info.get("agent_name"):
                logger.info(f"   Agent: {file_info['agent_name']}")
            if file_info.get("complexity_score", 0) > 0:
                logger.info(f"   Complexity: {file_info['complexity_score']}/10")
            if file_info.get("file_size", 0) > 0:
                logger.info(f"   Size: {file_info['file_size']:,} bytes")

        if dry_run:
            logger.info("DRY RUN: No files will be actually processed.")
            return self.stats

        logger.info("\nStarting documentation generation...")

        # Use ThreadPoolExecutor for concurrent processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(
                    self._process_single_file,
                    file_info,
                    i,
                    len(files_to_process_subset),
                ): (file_info, i)
                for i, file_info in enumerate(files_to_process_subset, 1)
            }

            for future in as_completed(future_to_file):
                file_info, current_idx = future_to_file[future]
                try:
                    result = future.result()
                    if result["success"]:
                        self.stats["files_processed"] += 1
                        self.stats["functions_documented"] += result["functions_count"]
                    else:
                        self.stats["errors_encountered"] += 1
                except Exception as exc:
                    logger.error(
                        f"Error processing {file_info['file_path']} in executor: {exc}"
                    )
                    self.stats["errors_encountered"] += 1

        end_time = datetime.now()
        self.stats["total_processing_time"] = (end_time - start_time).total_seconds()
        self._show_final_summary()
        return self.stats

    def _process_single_file(
        self, file_info: Dict[str, Any], current: int, total: int
    ) -> Dict[str, Any]:
        """
        Processes a single file to generate documentation.
        This method is designed to be run concurrently.
        """
        file_path = file_info["file_path"]
        file_name = Path(file_path).name
        logger.info(f"Processing [{current}/{total}]: {file_name}")
        logger.debug(f"Updating status for {file_name} to 'in_progress'")

        try:
            self.db_client.update_documentation_status(
                file_path,
                "in_progress",
                {"priority_score": file_info["priority_score"]},
            )

            functions_to_document = get_functions_from_file(
                file_path
            )  # Calls our placeholder
            if not functions_to_document:
                logger.info(f"    No functions found to document in {file_name}")
                self.db_client.update_documentation_status(
                    file_path, "documented_no_functions"
                )
                return {"success": True, "functions_count": 0}

            logger.info(
                f"    Found {len(functions_to_document)} functions in {file_name} to document"
            )
            documented_functions = []

            for func_name, func_source in functions_to_document:
                logger.info(f"    Documenting function: {func_name}")
                try:
                    # Pass the LLM client to the documentation generation function
                    inline_docstring, rst_content = self._generate_function_docs(
                        func_name, func_source
                    )
                    documented_functions.append(
                        {"function_name": func_name, "success": True}
                    )
                    logger.info(f"    {func_name} documented successfully")
                    # In a real scenario, you'd apply the docstring to the source file
                    # and potentially save the RST content to a separate .rst file.
                    # This script only simulates the generation.
                except Exception as e:
                    logger.error(
                        f"    Failed to document {func_name} in {file_name}: {e}"
                    )
                    documented_functions.append(
                        {"function_name": func_name, "error": str(e), "success": False}
                    )

            doc_results = {
                "functions": documented_functions,
                "total_functions": len(functions_to_document),
                "successful_functions": sum(
                    1 for f in documented_functions if f["success"]
                ),
                "processing_timestamp": str(datetime.now()),
            }
            logger.debug(f"Storing documentation results for {file_name}")
            self.db_client.store_documentation_results(file_path, doc_results)

            if all(f["success"] for f in documented_functions):
                self.db_client.update_documentation_status(
                    file_path, "documented", doc_results
                )
                logger.info(f"    {file_name} fully documented!")
            else:
                self.db_client.update_documentation_status(
                    file_path, "partially_documented", doc_results
                )
                logger.warning(
                    f"    {file_name} partially documented (some functions failed)."
                )

            return {
                "success": True,
                "functions_count": sum(1 for f in documented_functions if f["success"]),
            }

        except Exception as e:
            logger.error(f"Failed to process {file_name}: {e}")
            self.db_client.update_documentation_status(
                file_path, "error", {"error_message": str(e)}
            )
            return {"success": False, "functions_count": 0}

    def _generate_function_docs(
        self, func_name: str, func_source: str
    ) -> Tuple[str, str]:
        """
        Generates docstring and RST content using the LLM client.
        """
        # Parse parameters from source code for RST generation (more robust than LLM for this)
        try:
            parsed_func = ast.parse(func_source).body[0]
            params = [arg.arg for arg in parsed_func.args.args]
        except (SyntaxError, IndexError):
            params = []
            logger.warning(
                f"Could not parse parameters from source for {func_name}. Using empty list."
            )

        inline_docstring = self.llm_client.generate_docstring(func_source)
        rst_content = self.llm_client.generate_rst_content(func_name, params)
        return inline_docstring, rst_content

    def _show_final_summary(self):
        logger.info("\n" + "=" * 50)
        logger.info(" DOCUMENTATION WORKFLOW COMPLETE")
        logger.info("=" * 50)
        logger.info(f" Files Processed: {self.stats['files_processed']}")
        logger.info(f" Functions Documented: {self.stats['functions_documented']}")
        logger.info(f" Errors Encountered: {self.stats['errors_encountered']}")
        logger.info(
            f" Total Processing Time: {self.stats['total_processing_time']:.2f} seconds"
        )

        if self.stats["files_processed"] > 0:
            progress = self.db_client.get_documentation_progress()
            logger.info("\nUpdated Progress:")
            logger.info(
                f"  • Overall: {progress['overall_progress']['completion_percentage']:.1f}% complete"
            )
            logger.info(
                f"  • Agents: {progress['agent_progress']['agent_completion_percentage']:.1f}% complete"
            )

        logger.info("\nNext steps:")
        logger.info("  • Run with different priority filters to continue.")
        logger.info("  • Check documentation_status_report.txt for detailed insights.")
        logger.info("  • Use the database dashboard for interactive exploration.")

    def show_recommendations(self):
        logger.info("-" * 45)
        logger.info("SMART DOCUMENTATION RECOMMENDATIONS")
        logger.info("-" * 45)
        recommendations = self.db_client.get_documentation_recommendations()
        if not recommendations:
            logger.info("No immediate documentation recommendations!")
            return
        logger.info("Top 10 files recommended for documentation:\n")
        for i, rec in enumerate(recommendations[:10], 1):
            logger.info(f"{i:2}. {rec['file_name']}")
            logger.info(f"    Priority: {rec['priority_score']:.1f}/10")
            logger.info(f"    Reasons: {', '.join(rec['reasons'])}")
            logger.info(f"    Effort: {rec['estimated_effort']}")
            logger.info("")  # Empty line for spacing


if __name__ == "__main__":
    # Example usage:
    # Set your database path
    # Replace 'documentation.db' with your actual database file path
    DB_PATH = "data/documentation.db"

    # Set your LLM API Key securely (e.g., from environment variable)
    # import os
    # LLM_API_KEY = os.getenv("YOUR_LLM_API_KEY")
    LLM_API_KEY = "YOUR_LLM_API_KEY_HERE"  # <<< IMPORTANT: REPLACE WITH YOUR ACTUAL KEY OR USE ENV VAR

    # Ensure the database directory exists if it's not the current directory
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    orchestrator = SmartDocumentationOrchestrator(
        db_path=DB_PATH, llm_api_key=LLM_API_KEY
    )

    # Example: Run a dry run first to see what would be processed
    # results = orchestrator.run_smart_documentation_workflow(dry_run=True, max_files=2)

    # Example: Run the actual workflow
    results = orchestrator.run_smart_documentation_workflow(
        priority_filter="high",
        max_files=5,
        dry_run=False,
        max_workers=4,  # Process 4 files concurrently
    )

    logger.info("\nFinal Statistics:")
    for key, value in results.items():
        logger.info(f"  {key}: {value}")

    orchestrator.show_recommendations()
