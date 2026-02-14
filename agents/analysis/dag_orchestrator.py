import asyncio
from typing import Any, Dict  # noqa: E402


class DagOrchestrator:
    """Lightweight async DAG orchestrator for text analysis.

    Runs entity extraction and semantic analysis in parallel, then runs
    violations review. Can be extended with additional nodes (e.g., IRAC,
    contradiction analysis) using the same pattern.
    """

    def __init__(self, manager: Any):
        self.manager = manager

    async def run(
        self, text: str, options: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        opts = options or {}
        # Parallel nodes
        ent_task = asyncio.create_task(self.manager.extract_entities(text, **opts))
        sem_task = asyncio.create_task(self.manager.analyze_semantic(text, **opts))
        # Wait for parallel
        ent_res, sem_res = await asyncio.gather(ent_task, sem_task)
        # Downstream node
        vio_res = await self.manager.analyze_violations(text, **opts)

        return {
            "entities": (ent_res.data if getattr(ent_res, "success", False) else {}),
            "semantic": (sem_res.data if getattr(sem_res, "success", False) else {}),
            "violations": (vio_res.data if getattr(vio_res, "success", False) else {}),
        }
