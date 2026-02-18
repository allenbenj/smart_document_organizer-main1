"""
Agent Service
=============
Handles agent task dispatch, coordination, and management.
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

_WIN_DRIVE_RE = re.compile(r"^([A-Za-z]):[\\/](.*)$")


def _normalize_path_for_runtime(path_str: str) -> str:
    """Normalize incoming file paths for the current runtime OS.

    - Windows runtime: keep Windows paths as Windows paths.
    - POSIX/WSL runtime: map `C:\\...` -> `/mnt/c/...`.
    """
    s = str(path_str).strip().strip('"').strip("'")
    m = _WIN_DRIVE_RE.match(s)
    if m:
        if os.name == "nt":
            return s
        drive = m.group(1).lower()
        rest = m.group(2).replace("\\", "/").lstrip("/")
        return f"/mnt/{drive}/{rest}"
    return str(Path(s).expanduser())


class AgentService:
    """
    Central service for interacting with the Agent system.
    Abstracts the complexity of agent instantiation, task routing, and result handling.
    """

    def __init__(self, agent_manager):
        """
        Initialize with a specific agent manager (ProductionAgentManager).
        """
        self.agent_manager = agent_manager

    async def get_available_agents(self) -> List[str]:
        """
        Get list of active/available agent types.
        """
        try:
            # Inspection of the manager to find available agents
            if hasattr(self.agent_manager, "agents"):
                # Return the string value of the agent type (e.g., "document_processor")
                # keys are AgentType enums, so use .value
                return [k.value for k in self.agent_manager.agents.keys()]

            # Fallback if the manager exposes them differently
            # This logic mimics the route's current discovery logic or delegated call
            return []
        except Exception as e:
            logger.error(f"Error getting available agents: {e}")
            return []

    async def dispatch_task(self, task_type: str, payload: Dict[str, Any]) -> Any:
        """
        Dispatch a task to the appropriate agent.

        Args:
            task_type: logical name of the task (e.g., 'document_processing', 'legal_analysis')
            payload: Input data for the task

        Returns:
            Result object/dict from the agent
        """
        logger.info(
            "Dispatching task %s via manager=%s (%s)",
            task_type,
            type(self.agent_manager).__name__,
            type(self.agent_manager).__module__,
        )

        # Ensure agent manager is initialized if it has agents and initialize method
        if (
            hasattr(self.agent_manager, "initialize")
            and hasattr(self.agent_manager, "agents")
            and not getattr(self.agent_manager, "agents", {})
        ):
            logger.info("Initializing agent manager before dispatch")
            await self.agent_manager.initialize()
            logger.info(
                "Agent manager initialized, agents available: %s",
                list(getattr(self.agent_manager, "agents", {}).keys()),
            )

        try:
            # Map task types to manager methods
            # This is a temporary adapter logic until we unify the agent interface (AG-3)

            if task_type == "process_document":
                file_path = payload.get("file_path")
                if not file_path:
                    raise ValueError("file_path required for process_document")

                normalized_path = _normalize_path_for_runtime(file_path)
                exists = Path(normalized_path).exists()
                logger.info(
                    "process_document path raw=%r normalized=%r exists=%s",
                    file_path,
                    normalized_path,
                    exists,
                )
                if not exists:
                    raise ValueError(
                        f"file_path not found: {file_path} -> {normalized_path}"
                    )

                # Direct document processing without agent dependency

                import time

                start_time = time.time()
                logger.info(
                    "Starting direct document processing for %s", normalized_path
                )
                try:
                    path = Path(normalized_path)
                    if path.suffix.lower() == ".txt":
                        logger.info("Processing .txt file")
                        with open(normalized_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        processing_time = time.time() - start_time
                        logger.info(
                            "Successfully processed .txt file in %.2f seconds",
                            processing_time,
                        )
                        result = {
                            "success": True,
                            "data": {
                                "content": content,
                                "metadata": {"file_type": "txt"},
                            },
                            "error": None,
                            "agent_type": "document_processor",
                            "processing_time": processing_time,
                            "metadata": {},
                        }
                    else:
                        logger.warning("Unsupported file type: %s", path.suffix)
                        result = {
                            "success": False,
                            "data": {},
                            "error": "Unsupported file type",
                            "agent_type": "document_processor",
                            "processing_time": time.time() - start_time,
                            "metadata": {},
                        }
                except Exception as e:
                    logger.error("Error during direct processing: %s", e)
                    result = {
                        "success": False,
                        "data": {},
                        "error": str(e),
                        "agent_type": "document_processor",
                        "processing_time": time.time() - start_time,
                        "metadata": {},
                    }
                return result

            elif task_type == "extract_entities":
                text = payload.get("text")
                if not text:
                    raise ValueError("text required for extract_entities")
                return await self.agent_manager.extract_entities(text)

            elif task_type == "analyze_legal":
                text = payload.get("text")
                context = payload.get("context") or {}
                # Call the correct method on the manager
                if hasattr(self.agent_manager, "analyze_legal_reasoning"):
                    return await self.agent_manager.analyze_legal_reasoning(
                        text, **context
                    )
                # Fallback purely for safety if mixing manager types
                elif hasattr(self.agent_manager, "analyze_legal_text"):
                    return await self.agent_manager.analyze_legal_text(text, context)
                else:
                    raise ValueError(
                        "Legal analysis not supported by this agent manager"
                    )

            elif task_type == "analyze_irac":
                text = payload.get("text")
                options = payload.get("options") or {}
                if hasattr(self.agent_manager, "analyze_irac"):
                    return await self.agent_manager.analyze_irac(text, **options)
                raise ValueError("IRAC analysis not supported")

            elif task_type == "analyze_toulmin":
                text = payload.get("text")
                options = payload.get("options") or {}
                if hasattr(self.agent_manager, "analyze_toulmin"):
                    return await self.agent_manager.analyze_toulmin(text, **options)
                raise ValueError("Toulmin analysis not supported")

            elif task_type == "submit_feedback":
                # Direct method mapping
                if hasattr(self.agent_manager, "submit_feedback"):
                    return await self.agent_manager.submit_feedback(**payload)
                raise ValueError("Feedback submission not supported")

            elif task_type == "analyze_semantic":
                text = payload.get("text")
                options = payload.get("options") or {}
                # Some managers might expose this differently or via generic execute
                if hasattr(self.agent_manager, "analyze_semantic"):
                    return await self.agent_manager.analyze_semantic(text, **options)
                # Fallback to execute_task if available
                if hasattr(self.agent_manager, "execute_task"):
                    return await self.agent_manager.execute_task(
                        "semantic_analysis", payload
                    )
                raise ValueError("Semantic analysis not supported")

            elif task_type == "analyze_contradictions":
                text = payload.get("text")
                options = payload.get("options") or {}
                if hasattr(self.agent_manager, "analyze_contradictions"):
                    return await self.agent_manager.analyze_contradictions(
                        text, **options
                    )
                raise ValueError("Contradiction analysis not supported")

            elif task_type == "analyze_violations":
                text = payload.get("text")
                options = payload.get("options") or {}
                if hasattr(self.agent_manager, "analyze_violations"):
                    return await self.agent_manager.analyze_violations(text, **options)
                raise ValueError("Violation analysis not supported")

            elif task_type == "analyze_contract":
                text = payload.get("text")
                options = payload.get("options") or {}
                if hasattr(self.agent_manager, "analyze_contract"):
                    return await self.agent_manager.analyze_contract(text, **options)
                raise ValueError("Contract analysis not supported")

            elif task_type == "check_compliance":
                text = payload.get("text")
                options = payload.get("options") or {}
                if hasattr(self.agent_manager, "check_compliance"):
                    return await self.agent_manager.check_compliance(text, **options)
                raise ValueError("Compliance checking not supported")

            elif task_type == "embed_texts":
                texts = payload.get("texts", [])
                options = payload.get("options") or {}
                if hasattr(self.agent_manager, "embed_texts"):
                    return await self.agent_manager.embed_texts(texts, **options)
                raise ValueError("Embedding not supported")

            elif task_type == "classify_text":
                text = payload.get("text")
                options = payload.get("options") or {}
                if hasattr(self.agent_manager, "classify_text"):
                    return await self.agent_manager.classify_text(text, **options)
                raise ValueError("Classification not supported")

            elif task_type == "orchestrate_task":
                text = payload.get("text")
                options = payload.get("options") or {}
                if hasattr(self.agent_manager, "orchestrate"):
                    return await self.agent_manager.orchestrate(text, **options)
                raise ValueError("Orchestration not supported")

            else:
                # Generic fallback if manager supports generic execution
                if hasattr(self.agent_manager, "execute_task"):
                    return await self.agent_manager.execute_task(task_type, payload)
                else:
                    raise ValueError(f"Unknown task type: {task_type}")

        except Exception as e:
            logger.error(f"Task dispatch failed for {task_type}: {e}")
            # unify return structure?
            return {"success": False, "error": str(e), "task_type": task_type}

    async def get_agent_status(self) -> Dict[str, Any]:
        """
        Get health and status of active agents.
        """
        status = {
            "manager_type": type(self.agent_manager).__name__,
            "agents": {},
            "healthy": True,
        }

        # If manager has status method
        if hasattr(self.agent_manager, "get_system_health"):
            return await self.agent_manager.get_system_health()
        elif hasattr(self.agent_manager, "get_status"):
            return await self.agent_manager.get_status()

        return status
