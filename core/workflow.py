import logging
from typing import Dict, TypedDict, Union  # noqa: E402

from langgraph.graph import END, StateGraph  # noqa: E402

from .load_template import load_template  # noqa: E402
from .refactor_tools import apply_refactor_tool, validate_code_tool  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATABASE_PATH = "db/refactor.db"


class RefactorState(TypedDict):
    template_name: str
    template_data: Dict[str, Union[str, dict]]
    validation_result: Dict[str, Union[bool, str]]
    refactor_result: Dict[str, Union[str, bool]]


def load_node(state: RefactorState) -> RefactorState:
    state["template_data"] = load_template.invoke({"name": state["template_name"]})
    return state


def validate_node(state: RefactorState) -> RefactorState:
    state["validation_result"] = validate_code_tool.invoke(
        {"template_name": state["template_name"]}
    )
    return state


def refactor_node(state: RefactorState) -> RefactorState:
    if state["validation_result"].get("valid", False):
        state["refactor_result"] = apply_refactor_tool.invoke(
            {"template_name": state["template_name"], "save_to_file": True}
        )
    else:
        state["refactor_result"] = {
            "success": False,
            "message": "Validation failed, skipping refactoring",
        }
    return state


def create_workflow():
    workflow = StateGraph(RefactorState)
    workflow.add_node("load", load_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("refactor", refactor_node)
    workflow.set_entry_point("load")
    workflow.add_edge("load", "validate")
    workflow.add_edge("validate", "refactor")
    workflow.add_edge("refactor", END)
    return workflow.compile()


def run_workflow(template_name: str):
    workflow = create_workflow()
    initial_state = RefactorState(template_name=template_name)
    result = workflow.invoke(initial_state)
    logger.info(f"Workflow result for {template_name}: {result['refactor_result']}")
    return result
