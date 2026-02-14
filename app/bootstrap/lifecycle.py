from __future__ import annotations

import asyncio
import os
from typing import Any


async def taskmaster_scheduler_loop(*, logger: Any) -> None:
    """Run due TaskMaster schedules periodically with bounded per-tick throughput."""
    from mem_db.database import get_database_manager
    from services.taskmaster_service import TaskMasterService

    interval = int(os.getenv("TASKMASTER_SCHEDULER_INTERVAL_SECONDS", "60"))
    max_due = int(os.getenv("TASKMASTER_SCHEDULER_MAX_DUE_PER_TICK", "2"))
    while True:
        try:
            db = get_database_manager()
            svc = TaskMasterService(db)
            svc.run_due_schedules(max_due=max_due)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("TaskMaster scheduler tick failed: %s", e)
        await asyncio.sleep(max(10, interval))
