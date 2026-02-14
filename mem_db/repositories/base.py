from __future__ import annotations

import sqlite3
import time
from typing import Any, Callable, ContextManager, TypeVar

T = TypeVar("T")


class BaseRepository:
    def __init__(self, connection_factory: Callable[[], ContextManager[Any]]):
        self._connection_factory = connection_factory

    def connection(self) -> ContextManager[Any]:
        return self._connection_factory()

    def write_with_retry(
        self,
        fn: Callable[[Any], T],
        *,
        max_attempts: int = 5,
        base_delay_seconds: float = 0.02,
        max_delay_seconds: float = 0.25,
    ) -> T:
        """Run a write transaction with bounded retry for transient SQLite locks."""
        attempt = 0
        while True:
            try:
                with self.connection() as conn:
                    out = fn(conn)
                    conn.commit()
                    return out
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if "database is locked" not in msg and "database table is locked" not in msg:
                    raise
                attempt += 1
                if attempt >= max_attempts:
                    raise
                delay = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
                time.sleep(delay)
