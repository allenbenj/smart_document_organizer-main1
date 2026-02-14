# agent_nodes.py
import hashlib
import json  # noqa: E402
import os  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any, Dict, List, Optional, Tuple, TypedDict  # noqa: E402

# --- Dependency Checks & Setup ---
try:
    from importlib.metadata import version  # noqa: E402

    import openai  # Use the standard OpenAI library  # noqa: E402

    openai_version = version("openai")
    assert int(openai_version.split(".")[0]) >= 1  # Check major version >= 1
    OPENAI_AVAILABLE = True
except (ImportError, AssertionError, Exception) as e:  # Catch specific/general errors
    openai = None  # Ensure openai is None if import fails
    OPENAI_AVAILABLE = False
    print(
        f"CRITICAL: openai package >= 1.0.0 is MISSING or failed version check! Error: {e}"
    )

    class OpenAIPlaceholder:
        class OpenAI:
            def __init__(self, **kwargs):
                print("ERROR: OpenAI placeholder initialized.")

            class Chat:
                class Completions:
                    @staticmethod
                    def create(*args, **kwargs):
                        raise NotImplementedError("openai not installed")

                completions = Completions()

            chat = Chat()

        APIError = Exception
        PermissionDeniedError = Exception
        RateLimitError = Exception

    openai = OpenAIPlaceholder()

from agents.extractors.document_utils import extract_document_text  # noqa: E402
from log_setup import logger  # noqa: E402

# Assuming config.py will be created or these are placeholders
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.example.xai")  # Placeholder
API_KEY_ENV_VAR = "XAI_API_KEY"  # Placeholder
OUTPUT_EXCERPT_LENGTH = 500  # Placeholder
OUTPUT_CATEGORY_MAX_LENGTH = 50  # Placeholder


# --- State Definition ---
class WorkflowState(TypedDict):
    file_path: str
    output_dir: str
    options: Dict[str, str]
    extracted_text: Optional[str]
    text_hash: Optional[str]
    is_duplicate: bool
    corrected_text: Optional[str]
    entities: Optional[str]
    structured_entities: Optional[Dict]
    analysis: Optional[str]
    summary: Optional[str]
    action_evidence_linkages: Optional[List[Dict]]
    category_dir: Optional[str]
    output_filename: Optional[str]
    final_output_path: Optional[str]
    error_message: Optional[str]


class AgentNodes:
    def __init__(self, model_name: str):
        self.xai_model_name = model_name
        self.openai_client: Optional[openai.OpenAI] = None
        if not OPENAI_AVAILABLE:
            logger.error("Cannot initialize AgentNodes: openai library not available.")
        else:
            self._get_openai_client()  # Initialize client on creation
        logger.info(f"AgentNodes initialized to use model: {self.xai_model_name}")

    def _get_openai_client(self) -> Optional[openai.OpenAI]:
        if not OPENAI_AVAILABLE:
            return None
        if self.openai_client is not None:
            return self.openai_client
        api_key = os.getenv(API_KEY_ENV_VAR)
        if not api_key:
            logger.error(
                f"{API_KEY_ENV_VAR} not found. Please set the environment variable."
            )
            return None
        if not XAI_BASE_URL:
            logger.error("XAI_BASE_URL not configured.")
            return None
        try:
            logger.info(
                f"Initializing OpenAI client for xAI (Base URL: {XAI_BASE_URL})..."
            )
            self.openai_client = openai.OpenAI(
                base_url=XAI_BASE_URL, api_key=api_key, timeout=60.0
            )
            logger.info("OpenAI client for xAI initialized.")
            return self.openai_client
        except Exception as e:
            logger.exception(f"Failed client init: {e}")
            self.openai_client = None
            return None

    def _call_xai(
        self, prompt: str, node_name: str
    ) -> Tuple[Optional[str], Optional[str]]:
        client = self._get_openai_client()
        if not client:
            return None, f"{node_name}: OpenAI client unavailable or not initialized."
        messages = [{"role": "user", "content": prompt}]
        try:
            logger.info(
                f"Node {node_name}: Sending request to {self.xai_model_name}..."
            )
            response = client.chat.completions.create(
                model=self.xai_model_name,
                messages=messages,
                temperature=0,
                stream=False,
            )
            if response.choices:
                content = response.choices[0].message.content
                logger.info(f"Node {node_name}: Response received.")
                return content.strip() if content else "", None
            else:
                logger.error(f"Node {node_name}: Response missing choices: {response}")
                return None, "API response missing choices"
        except openai.PermissionDeniedError as e:
            error_msg = (
                f"{node_name} API Permission Error: {getattr(e, 'message', str(e))}"
            )
            logger.error(error_msg)
            return None, error_msg
        except openai.RateLimitError as e:
            error_msg = (
                f"{node_name} API Rate Limit Error: {getattr(e, 'message', str(e))}"
            )
            logger.error(error_msg)
            return None, error_msg
        except openai.APIError as e:
            error_msg = f"{node_name} API Error ({getattr(e, 'status_code', 'N/A')}): {getattr(e, 'message', str(e))}"
            logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"{node_name} General Error: {e}"
            logger.exception(error_msg)
            return None, error_msg

    def extract_entities_direct(self, text_content: str) -> Optional[Dict[str, Any]]:
        """Directly extracts entities from text content, returning a structured dictionary."""
        node_name = "DirectEntityExtractor"
        if not text_content:
            logger.warning(f"{node_name}: Skipping due to empty content.")
            return None

        prompt = (
            'Extract key entities from the following text. Format the output as a JSON object with keys like "people", "organizations", "locations", "dates", "legal_terms", "monetary_values", and "metadata_doc_type". '
            'For "people", provide a list of dictionaries, each with "name" and a list of "mentions". Each mention should include "action_phrase" and "context_sentence".'
            f"\n\nText:\n```\n{text_content}\n```"
        )

        entities_text, error = self._call_xai(prompt, node_name)

        if error:
            logger.error(f"{node_name}: Error calling XAI: {error}")
            return None
        if not entities_text:
            logger.warning(f"{node_name}: No entities text returned from XAI.")
            return None

        try:
            structured_entities = json.loads(entities_text)
            logger.info(f"{node_name}: Successfully parsed structured entities.")
            return structured_entities
        except json.JSONDecodeError as json_err:
            logger.warning(
                f"{node_name}: Could not parse entities as JSON: {json_err}. Raw text: {entities_text}"
            )
            return None

    def run_tool(self, tool_name: str, **kwargs) -> Any:
        """Runs a specified tool. For 'Contradiction Check', it uses the MCP engine if available."""
        logger.info(
            f"AgentNodes: run_tool called for 	'{tool_name}	' with arguments: {kwargs}"
        )
        if tool_name == "Contradiction Check":
            # Check if this instance has an MCP engine (e.g., if it's an MCPEnhancedAgent)
            if hasattr(self, "mcp") and self.mcp is not None:
                topic = kwargs.get("topic")
                new_statementtext = kwargs.get("new_statement_text")  # noqa: F841
                new_speaker = kwargs.get("new_speaker")
                new_source_file = kwargs.get("new_source_file")

                if not topic or not new_statement_text:  # noqa: F821
                    error_msg = "Contradiction Check tool requires 'topic' and 'new_statement_text' arguments."
                    logger.error(error_msg)
                    return {
                        "error": error_msg,
                        "contradictions": [],
                    }  # Return a list for contradictions key

                try:
                    # Assuming self.mcp is an instance of ModelContextProtocol from mcp_engine
                    # and has a check_contradiction method.
                    contradictions = self.mcp.check_contradiction(
                        topic=topic,
                        new_statement_text=new_statement_text,  # noqa: F821
                        new_speaker=new_speaker,
                        new_source_file=new_source_file,
                        similarity_threshold=kwargs.get(
                            "similarity_threshold"
                        ),  # Pass it through
                    )
                    return contradictions  # Expected to be List[Dict[str, Any]]
                except Exception as e:
                    error_msg = f"Error during MCP contradiction check: {e}"
                    logger.exception(error_msg)
                    return {"error": error_msg, "contradictions": []}
            else:
                error_msg = "Contradiction Check tool cannot be run: MCP engine not available on this agent instance."
                logger.error(error_msg)
                # Return a structure consistent with expected output, even for errors
                return {"error": error_msg, "contradictions": []}
        elif tool_name == "Violation Detection":
            logger.warning(f"Tool 	'{tool_name}	' is a placeholder.")
            return "Violation Detection Complete: No violations found (Placeholder)"
        elif tool_name == "Strategy Generation":
            logger.warning(f"Tool 	'{tool_name}	' is a placeholder.")
            return "Strategy Generation Complete: Strategy X recommended (Placeholder)"
        elif tool_name == "Case Narrative Generation":
            logger.warning(f"Tool 	'{tool_name}	' is a placeholder.")
            return (
                "Case Narrative Generation Complete: Narrative generated (Placeholder)"
            )
        else:
            logger.warning(
                f"Tool 	'{tool_name}	' not implemented in AgentNodes.run_tool."
            )
            return None

    def extract_text(self, state: WorkflowState) -> WorkflowState:  # noqa: C901
        logger.info(f"Node Extract Text running for: {state['file_path']}")
        text, error = extract_document_text(state["file_path"])
        state["extracted_text"] = text
        state["error_message"] = error
        state["text_hash"] = (
            hashlib.md5(text.encode()).hexdigest() if text and not error else None
        )
        return state

    def proofread(self, state: WorkflowState) -> WorkflowState:
        node_name = "Proofreader"
        text = state.get("extracted_text", "")
        if state.get("error_message") or not text:
            logger.warning(f"{node_name}: Skipping.")
            state["corrected_text"] = text
            return state
        logger.info(f"Node: {node_name} running for: {state['file_path']}")
        mode = state["options"].get("correction_mode", "full")
        base_prompt = (
            "Correct spelling, grammar, punctuation, terminology, ambiguities."
        )
        tone_prompt = " Ensure professional legal tone."
        prompt = (
            f"{base_prompt}{tone_prompt}\n\nText:\n```\n{text}\n```"
            if mode == "full"
            else f"Correct {mode}.{tone_prompt}\n\nText:\n```\n{text}\n```"
        )
        corrected_text, error = self._call_xai(prompt, node_name)
        if error:
            state["error_message"] = error
            state["corrected_text"] = text
        else:
            state["corrected_text"] = corrected_text
        return state

    def extract_entities(self, state: WorkflowState) -> WorkflowState:
        node_name = "EntityExtractor"
        text = state.get("corrected_text", "")
        if state.get("error_message") or not text:
            logger.warning(f"{node_name}: Skipping.")
            state["entities"] = "[Skipped]"
            state["structured_entities"] = None
            return state
        logger.info(f"Node: {node_name} running for: {state['file_path']}")
        prompt = (
            'Extract key entities from the following text. Format the output as a JSON object with keys like "people", "organizations", "locations", "dates", "legal_terms", "monetary_values", and "metadata_doc_type". '
            'For "people", provide a list of dictionaries, each with "name" and a list of "mentions". Each mention should include "action_phrase" and "context_sentence".'
            f"\n\nText:\n```\n{text}\n```"  # Using {text} which is derived from state['corrected_text']
        )
        entities_text, error = self._call_xai(prompt, node_name)
        state["entities"] = entities_text
        state["structured_entities"] = None
        if error:
            state["error_message"] = error
            state["entities"] = "[API Error]"
        elif entities_text:
            try:
                state["structured_entities"] = json.loads(entities_text)
                logger.info("Parsed structured entities.")
            except json.JSONDecodeError as json_err:
                logger.warning(f"Could not parse entities as JSON: {json_err}")
        return state

    def analyze(self, state: WorkflowState) -> WorkflowState:
        node_name = "Analyzer"
        text = state.get("corrected_text", "")
        if state.get("error_message") or not text:
            logger.warning(f"{node_name}: Skipping.")
            state["analysis"] = "[Skipped]"
            return state
        logger.info(f"Node: {node_name} running for: {state['file_path']}")
        prompt = (
            "Analyze doc: 1. Key themes/topics. 2. Legal issues/risks/arguments. "
            f"3. Sentiment/tone (neutral, cooperative, aggressive, etc.). 4. Purpose/objective.\n\nDoc:\n```\n{text}\n```"
        )
        analysis, error = self._call_xai(prompt, node_name)
        if error:
            state["error_message"] = error
            state["analysis"] = "[API Error]"
        else:
            state["analysis"] = analysis
        return state

    def summarize(self, state: WorkflowState) -> WorkflowState:
        node_name = "Summarizer"
        text = state.get("corrected_text", "")
        if state.get("error_message") or not text:
            logger.warning(f"{node_name}: Skipping.")
            state["summary"] = "[Skipped]"
            return state
        logger.info(f"Node: {node_name} running for: {state['file_path']}")
        length = state["options"].get("summary_length", "medium")  # noqa: F841
        focus = state["options"].get("summary_focus", "general")  # noqa: F841
        analysis_context = state.get("analysis", "[Analysis unavailable]")  # noqa: F841
        prompt = """Analysis Context:
---
{analysis_context}
---
Summary Requirements:
- Length:
{length}
.
- Focus:
{focus}
.
- Format: Clear points/paragraphs.

Main Document:
```
{text}
```"""
        summary, error = self._call_xai(prompt, node_name)
        if error:
            state["error_message"] = error
            state["summary"] = "[API Error]"
        else:
            state["summary"] = summary
        return state

    def categorize(self, state: WorkflowState) -> WorkflowState:
        node_name = "Categorizer"
        if state.get("error_message") or state.get("is_duplicate"):
            logger.warning(f"{node_name}: Skipping.")
            return state
        logger.info(f"{node_name}: Determining category for: {state['file_path']}")
        output_dir = state["output_dir"]
        structured_entities = state.get("structured_entities")
        file_path = state["file_path"]
        category = "Uncategorized"
        doc_type_str: Optional[str] = None
        if isinstance(structured_entities, dict):
            potential_doc_type = structured_entities.get("metadata_doc_type")
            if isinstance(potential_doc_type, str):
                doc_type_str = potential_doc_type
            else:
                logger.warning(
                    f"{node_name}: 	'metadata_doc_type	' not a string: {potential_doc_type}. Using 	'Uncategorized	'."
                )
        else:
            logger.warning(
                f"{node_name}: No structured entities found. Using 	'Uncategorized	'."
            )
        if doc_type_str:
            logger.info(f"{node_name}: Using Document Type: 	'{doc_type_str}	'")
            # Corrected line 237: replace('"""', '"') changed to replace('"', '')
            sanitized_type = (
                doc_type_str.replace("**", "")
                .replace("*", "")
                .replace("`", "")
                .replace(" ", "")
                .replace("'", "")
            )
            sanitized_type = (
                sanitized_type.replace(" ", "_")
                .replace("/", "_")
                .replace("\\", "_")
                .replace(":", "_")
            )
            sanitized_type = "".join(
                c for c in sanitized_type if c.isalnum() or c in ("_", "-")
            )
            sanitized_type = sanitized_type.strip("_-")
            sanitized_type = sanitized_type[:OUTPUT_CATEGORY_MAX_LENGTH]
            if sanitized_type:
                category = sanitized_type
            else:
                logger.warning(
                    f"{node_name}: Doc type 	'{doc_type_str}	' sanitized empty. Using 	'Uncategorized	'."
                )
        else:
            logger.warning(
                f"{node_name}: No valid document type string. Using 	'Uncategorized	'."
            )
        category_dir = os.path.join(output_dir, category)
        state["category_dir"] = category_dir
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        state["output_filename"] = f"{base_name}_{timestamp}_processed.txt"
        state["final_output_path"] = os.path.join(
            category_dir, state["output_filename"]
        )
        logger.info(
            f"{node_name}: Determined output path: {state['final_output_path']}"
        )
        return state

    def save_output(self, state: WorkflowState) -> WorkflowState:
        node_name = "SaveOutput"
        if state.get("error_message") or state.get("is_duplicate"):
            logger.warning(f"{node_name}: Skipping save.")
            return state
        final_output_path = state.get("final_output_path")
        if not final_output_path:
            logger.error(f"{node_name}: Output path missing.")
            state["error_message"] = "Save error: Path missing."
            return state
        category_dir = state.get("category_dir")
        logger.info(f"{node_name}: Saving to: {final_output_path}")
        try:
            if category_dir:
                os.makedirs(category_dir, exist_ok=True)
            else:
                logger.error(f"{node_name}: Category dir missing.")
                state["error_message"] = "Save error: Category dir missing."
                return state
            output_content = (
                f"--- Original File: {state.get('file_path', 'N/A')} ---\n\n"
            )
            output_content += f"--- Entities and Metadata ---\n{state.get('entities', '[Not Extracted]')}\n\n"
            output_content += (
                f"--- Analysis ---\n{state.get('analysis', '[Not Analyzed]')}\n\n"
            )
            output_content += f"--- Summary ({state['options'].get('summary_length','N/A')} / {state['options'].get('summary_focus','N/A')}) ---\n{state.get('summary', '[Not Summarized]')}\n\n"
            output_content += f"--- Corrected Text (Excerpt) ---\n{state.get('corrected_text', '[Not Corrected]')[:OUTPUT_EXCERPT_LENGTH]}\n... (full text in memory)"
            with open(final_output_path, "w", encoding="utf-8") as f:
                f.write(output_content)
            logger.info(
                f"{node_name}: Successfully saved output to {final_output_path}"
            )
        except Exception as e:
            logger.exception(
                f"{node_name}: Error saving output to {final_output_path}: {e}"
            )
            state["error_message"] = f"Save error: {e}"
        return state
