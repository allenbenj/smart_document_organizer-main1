import json
import sqlite3  # noqa: E402
from typing import Dict, Union  # noqa: E402

from langchain_core.tools import tool  # noqa: E402

DATABASE_PATH = "db/refactor.db"


@tool
def load_template(name: str) -> Dict[str, Union[str, dict]]:
    """
    Load a saved MCP call template by name from the database.
    Returns a dict with keys 'tool' and 'args' for use in refactoring.

    Args:
        name (str): Name of the template (e.g., 'add_docstrings').

    Returns:
        Dict[str, Union[str, dict]]: Template data or error message.
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT template_data FROM refactor_templates WHERE template_name = ?",
            (name,),
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            return {"error": f"Template '{name}' not found in database"}

        data = json.loads(result[0])
        if "tool" not in data or "args" not in data:
            return {"error": "Invalid template format; must contain 'tool' and 'args'"}
        return data
    except Exception as e:
        return {"error": f"Failed to load template: {str(e)}"}


def get_tools():
    return [load_template]
