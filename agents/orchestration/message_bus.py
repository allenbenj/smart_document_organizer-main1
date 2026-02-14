from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class BusMessage:
    topic: str
    sender: str
    payload: Dict[str, Any]
    created_at: str


class MessageBus:
    """In-memory async message bus used by pipeline orchestration."""

    def __init__(self) -> None:
        self._queues: Dict[str, List[BusMessage]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, topic: str, *, sender: str, payload: Dict[str, Any]) -> None:
        msg = BusMessage(
            topic=str(topic),
            sender=str(sender),
            payload=dict(payload or {}),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        async with self._lock:
            self._queues.setdefault(msg.topic, []).append(msg)

    async def drain(self, topic: str) -> List[BusMessage]:
        key = str(topic)
        async with self._lock:
            items = list(self._queues.get(key, []))
            self._queues[key] = []
            return items
