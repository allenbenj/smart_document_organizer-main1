import asyncio
from dataclasses import dataclass  # noqa: E402
from typing import Any, Dict, List  # noqa: E402


@dataclass
class AgentMessage:
    topic: str
    sender: str
    payload: Dict[str, Any]


class MessageBus:
    """Simple in-memory pub/sub message bus for inter-agent messaging."""

    def __init__(self) -> None:
        self._topics: Dict[str, asyncio.Queue] = {}

    def _get_queue(self, topic: str) -> asyncio.Queue:
        if topic not in self._topics:
            self._topics[topic] = asyncio.Queue()
        return self._topics[topic]

    async def publish(self, topic: str, sender: str, payload: Dict[str, Any]) -> None:
        msg = AgentMessage(topic=topic, sender=sender, payload=payload)
        await self._get_queue(topic).put(msg)

    async def drain(self, topic: str, max_items: int = 100) -> List[AgentMessage]:
        q = self._get_queue(topic)
        msgs: List[AgentMessage] = []
        for _ in range(max_items):
            try:
                msgs.append(q.get_nowait())
            except asyncio.QueueEmpty:
                break
        return msgs
