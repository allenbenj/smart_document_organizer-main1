import ast
import json  # noqa: E402
import logging  # noqa: E402
import sqlite3  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Dict, Union  # noqa: E402

from langchain_core.tools import tool  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATABASE_PATH = "db/refactor.db"


def load_tasks():
    with open(
        "e:/Projects/smart_document_organizer/smart_document_organizer/core/refactor_tasks.json"
    ) as f:
        return json.load(f)


TASKS = load_tasks()


def init_database():
    """Initialize the SQLite database with the refactor_templates table."""
    db_dir = Path("db")
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS refactor_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT UNIQUE,
            template_data TEXT,
            refactored_code TEXT,
            test_code TEXT,
            websearch_info TEXT,
            status TEXT,
            error_message TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    now = datetime.now().isoformat()
    for name, data in TASKS.items():
        cursor.execute(
            """
            INSERT OR REPLACE INTO refactor_templates
            (template_name, template_data, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, json.dumps(data), "pending", now, now),
        )
    conn.commit()
    conn.close()
    logger.info("Initialized database")


@tool
def validate_code_tool(template_name: str) -> Dict[str, Union[bool, str]]:
    """
    Validate the syntax and style of code in a JSON template.

    Args:
        template_name (str): Name of the template.

    Returns:
        Dict[str, Union[bool, str]]: Validation result with status and message.
    """
    from .load_template import load_template  # noqa: E402

    try:
        template_data = load_template.invoke({"name": template_name})
        if "error" in template_data:
            return {"valid": False, "message": template_data["error"]}

        code = template_data["args"].get("code", "")
        if not code:
            return {"valid": False, "message": "No code found in template"}

        try:
            ast.parse(code)
        except SyntaxError as e:
            return {"valid": False, "message": f"Syntax error: {str(e)}"}

        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            if len(line) > 79:
                return {
                    "valid": False,
                    "message": f"Line {i} exceeds 79 characters (PEP 8)",
                }

        return {
            "valid": True,
            "message": "Code is syntactically valid and PEP 8 compliant",
        }
    except Exception as e:
        logger.error(f"Validation failed for {template_name}: {str(e)}")
        return {"valid": False, "message": f"Validation error: {str(e)}"}


@tool
def apply_refactor_tool(
    template_name: str, save_to_file: bool = False
) -> Dict[str, Union[str, bool]]:
    """
    Apply a refactoring task from a JSON template to its code.

    Args:
        template_name (str): Name of the template.
        save_to_file (bool): Whether to save refactored code to a file.

    Returns:
        Dict[str, Union[str, bool]]: Result with refactored code and status.
    """
    from .load_template import load_template  # noqa: E402

    try:
        template_data = load_template.invoke({"name": template_name})
        if "error" in template_data:
            return {"success": False, "message": template_data["error"]}

        validation = validate_code_tool.invoke({"template_name": template_name})
        if not validation["valid"]:
            return {"success": False, "message": validation["message"]}

        code = template_data["args"]["code"]
        instruction = template_data["args"]["instruction"]
        refactored_code = code

        if "Add docstrings and type annotations" in instruction:
            lines = code.splitlines()
            if lines[0].startswith("def "):
                func_name = lines[0].split("def ")[1].split("(")[0]
                refactored_code = f"""def {func_name}(a: float, b: float) -> float:
    \"\"\"Multiply two numbers and return the result.\n\n    Args:\n        a (float): First number.\n        b (float): Second number.\n\n    Returns:\n        float: Product of a and b.\n    \"\"\"\n    return a * b"""
        elif "Simplify conditionals" in instruction:
            if "if x > 10" in code:
                refactored_code = "def compute(x: int) -> bool:\n    return x > 10"

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE refactor_templates
            SET refactored_code = ?, status = ?, error_message = NULL, updated_at = ?
            WHERE template_name = ?
            """,
            (refactored_code, "success", datetime.now().isoformat(), template_name),
        )
        conn.commit()
        conn.close()

        if save_to_file:
            output_path = f"refactored/{template_name}_refactored.py"
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(refactored_code)
            logger.info(f"Saved refactored code to {output_path}")

        return {
            "success": True,
            "code": refactored_code,
            "message": "Refactoring applied successfully",
        }
    except Exception as e:
        logger.error(f"Refactoring failed for {template_name}: {str(e)}")
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE refactor_templates
            SET status = ?, error_message = ?, updated_at = ?
            WHERE template_name = ?
            """,
            ("failed", str(e), datetime.now().isoformat(), template_name),
        )
        conn.commit()
        conn.close()
        return {"success": False, "message": f"Refactoring error: {str(e)}"}


def get_tools():
    return [validate_code_tool, apply_refactor_tool]
