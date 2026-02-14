"""
Log handlers for different output destinations.
"""

import asyncio
import sys  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import List, Optional, TextIO  # noqa: E402

from ..interfaces.logging import (  # noqa: E402
    LogCategory,
    LogFormatter,
    LogHandler,
    LogHandlerError,
    LogLevel,
    LogRecord,
)


class FileLogHandler(LogHandler):
    """Log handler for file output with rotation support."""

    def __init__(
        self,
        file_path: str,
        max_size: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        encoding: str = "utf-8",
    ):
        self.file_path = Path(file_path)
        self.max_size = max_size
        self.backup_count = backup_count
        self.encoding = encoding
        self.formatter: Optional[LogFormatter] = None
        self._lock = asyncio.Lock()

        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    async def emit(self, record: LogRecord) -> None:
        """Emit log record to file."""
        if not self.formatter:
            raise LogHandlerError("No formatter set for file handler")

        try:
            formatted_message = self.formatter.format(record)

            async with self._lock:
                # Check if rotation is needed
                if (
                    self.file_path.exists()
                    and self.file_path.stat().st_size >= self.max_size
                ):
                    await self._rotate_files()

                # Write to file
                with open(self.file_path, "a", encoding=self.encoding) as f:
                    f.write(formatted_message + "\n")
                    f.flush()

        except Exception as e:
            raise LogHandlerError(f"Failed to write to log file: {e}")

    def set_formatter(self, formatter: LogFormatter) -> None:
        """Set log formatter."""
        self.formatter = formatter

    async def _rotate_files(self) -> None:
        """Rotate log files when max size is reached."""
        try:
            # Remove oldest backup if it exists
            oldest_backup = self.file_path.with_suffix(
                f"{self.file_path.suffix}.{self.backup_count}"
            )
            if oldest_backup.exists():
                oldest_backup.unlink()

            # Rotate existing backups
            for i in range(self.backup_count - 1, 0, -1):
                old_backup = self.file_path.with_suffix(f"{self.file_path.suffix}.{i}")
                new_backup = self.file_path.with_suffix(
                    f"{self.file_path.suffix}.{i + 1}"
                )

                if old_backup.exists():
                    old_backup.rename(new_backup)

            # Move current file to backup.1
            if self.file_path.exists():
                backup_path = self.file_path.with_suffix(f"{self.file_path.suffix}.1")
                self.file_path.rename(backup_path)

        except Exception as e:
            raise LogHandlerError(f"Failed to rotate log files: {e}")


class ConsoleLogHandler(LogHandler):
    """Log handler for console output with color support."""

    def __init__(self, use_colors: bool = True, stream: Optional[TextIO] = None):
        self.use_colors = use_colors
        self.stream = stream or sys.stdout
        self.formatter: Optional[LogFormatter] = None
        self._lock = asyncio.Lock()

        # Color codes for different log levels
        self.colors = {
            "TRACE": "\033[37m",  # White
            "DEBUG": "\033[36m",  # Cyan
            "INFO": "\033[32m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[35m",  # Magenta
            "RESET": "\033[0m",  # Reset
        }

    async def emit(self, record: LogRecord) -> None:
        """Emit log record to console."""
        if not self.formatter:
            raise LogHandlerError("No formatter set for console handler")

        try:
            formatted_message = self.formatter.format(record)

            # Add colors if enabled and terminal supports it
            if (
                self.use_colors
                and hasattr(self.stream, "isatty")
                and self.stream.isatty()
            ):
                color = self.colors.get(record.level.name, "")
                reset = self.colors["RESET"]
                formatted_message = f"{color}{formatted_message}{reset}"

            async with self._lock:
                self.stream.write(formatted_message + "\n")
                self.stream.flush()

        except Exception as e:
            raise LogHandlerError(f"Failed to write to console: {e}")

    def set_formatter(self, formatter: LogFormatter) -> None:
        """Set log formatter."""
        self.formatter = formatter


class RemoteLogHandler(LogHandler):
    """Log handler for remote logging services."""

    def __init__(
        self,
        endpoint: str,
        api_key: Optional[str] = None,
        timeout: float = 5.0,
        batch_size: int = 10,
        flush_interval: float = 1.0,
    ):
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout = timeout
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.formatter: Optional[LogFormatter] = None

        # Batching support
        self._batch: List[LogRecord] = []
        self._lock = asyncio.Lock()
        self._last_flush = datetime.now()

        # Start background flush task
        self._flush_task = asyncio.create_task(self._background_flush())

    async def emit(self, record: LogRecord) -> None:
        """Emit log record to remote service."""
        if not self.formatter:
            raise LogHandlerError("No formatter set for remote handler")

        async with self._lock:
            self._batch.append(record)

            # Flush if batch is full
            if len(self._batch) >= self.batch_size:
                await self._flush_batch()

    def set_formatter(self, formatter: LogFormatter) -> None:
        """Set log formatter."""
        self.formatter = formatter

    async def _flush_batch(self) -> None:
        """Flush current batch to remote service."""
        if not self._batch:
            return

        try:
            # Format all records in batch
            formatted_records = []
            for record in self._batch:
                formatted_message = self.formatter.format(record)
                formatted_records.append(formatted_message)

            # Send to remote service
            import aiohttp  # noqa: E402

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            payload = {
                "timestamp": datetime.now().isoformat(),
                "source": "legal-ai-platform",
                "records": formatted_records,
            }

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                async with session.post(
                    self.endpoint, json=payload, headers=headers
                ) as response:
                    if response.status >= 400:
                        raise LogHandlerError(
                            f"Remote logging failed with status {response.status}"
                        )

            # Clear batch after successful send
            self._batch.clear()
            self._last_flush = datetime.now()

        except Exception as e:
            # Don't raise exception to avoid breaking application
            # Log to stderr as fallback
            print(f"Failed to send logs to remote service: {e}", file=sys.stderr)

    async def _background_flush(self) -> None:
        """Background task to flush logs periodically."""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)

                async with self._lock:
                    if (
                        self._batch
                        and (datetime.now() - self._last_flush).total_seconds()
                        >= self.flush_interval
                    ):
                        await self._flush_batch()

            except asyncio.CancelledError:
                # Flush remaining logs before shutdown
                async with self._lock:
                    if self._batch:
                        await self._flush_batch()
                break
            except Exception as e:
                print(f"Error in background log flush: {e}", file=sys.stderr)

    async def close(self) -> None:
        """Close handler and flush remaining logs."""
        self._flush_task.cancel()

        try:
            await self._flush_task
        except asyncio.CancelledError:
            pass

        async with self._lock:
            if self._batch:
                await self._flush_batch()


class MemoryLogHandler(LogHandler):
    """Log handler that stores logs in memory for testing or debugging."""

    def __init__(self, max_records: int = 1000):
        self.max_records = max_records
        self.formatter: Optional[LogFormatter] = None
        self._records: List[LogRecord] = []
        self._lock = asyncio.Lock()

    async def emit(self, record: LogRecord) -> None:
        """Store log record in memory."""
        async with self._lock:
            self._records.append(record)

            # Remove oldest records if limit exceeded
            if len(self._records) > self.max_records:
                self._records = self._records[-self.max_records :]

    def set_formatter(self, formatter: LogFormatter) -> None:
        """Set log formatter."""
        self.formatter = formatter

    def get_records(self) -> list:
        """Get all stored log records."""
        return self._records.copy()

    def clear(self) -> None:
        """Clear all stored records."""
        self._records.clear()

    def get_records_by_level(self, level: LogLevel) -> List[LogRecord]:
        """Get records filtered by log level."""
        return [record for record in self._records if record.level == level]

    def get_records_by_category(self, category: LogCategory) -> List[LogRecord]:
        """Get records filtered by category."""
        return [record for record in self._records if record.category == category]
