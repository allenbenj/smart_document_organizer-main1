# Diagnostics runtime engine for patch logging and loop-detection

import json
import os  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from typing import Any, Dict, Optional  # noqa: E402


class DiagnosticsEngine:
    """
    Lightweight runtime diagnostics engine to support patch logging
    and loop-detection for automatic editing workflows.

    Behavior:
    - Logs per-run diagnostic entries to a runtime log file.
    - Tracks patch fingerprints to detect repeated edits within a session.
    - Provides a simple API to emit run events and query current state.
    """

    def __init__(
        self,
        log_dir: Optional[str] = None,
        log_filename: str = "diagnostics_runtime.log",
        max_edits_per_session: int = 3,
    ):
        # Determine log directory (default to .kilocode/diagnostics in the workspace)
        self.log_dir = log_dir or self._default_log_dir()
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_path = os.path.join(self.log_dir, log_filename)

        self.max_edits_per_session = int(max_edits_per_session)
        self._session_edits = 0
        self._fingerprints = set()
        self._buffer = []

    def _default_log_dir(self) -> str:
        # Locate workspace root based on this file's location
        this_dir = os.path.abspath(os.path.dirname(__file__))
        workspace_root = os.path.normpath(os.path.join(this_dir, "..", ".."))
        cand = os.path.join(workspace_root, ".kilocode", "diagnostics")
        os.makedirs(cand, exist_ok=True)
        return cand

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def log_run(
        self,
        patch_hash: str,
        target_system: str,
        action: str,
        status: str,
        file_edited: Optional[str] = None,
        issue_summary: Optional[str] = None,
        fingerprint: Optional[str] = None,
        extra: Optional[str] = None,
    ) -> None:
        """
        Emit a diagnostic run entry. This will also flush immediately to disk.

        Example fields:
        - patch_hash: "Patch-A-20250807T232546Z"
        - timestamp: "2025-08-07T23:25:46Z"
        - target_system: "KnowledgeDrivenAgentSystem"
        - action: "initialize-diagnostics"
        - status: "applied"
        - file_edited: "src/..."
        - issue_summary: "Loop detected..."
        - fingerprint: "Fingerprint-12345"
        """
        entry: Dict[str, Any] = {
            "patch_hash": patch_hash,
            "timestamp": self._now_iso(),
            "target_system": target_system,
            "action": action,
            "status": status,
            "file_edited": file_edited,
            "issue_summary": issue_summary,
            "fingerprint": fingerprint,
            "extra": extra,
        }
        self._buffer.append(entry)
        self._session_edits += 1
        self.flush()

        if fingerprint:
            self._fingerprints.add(fingerprint)

    def should_block_loop(
        self, patch_hash: str, fingerprint: Optional[str] = None
    ) -> bool:
        """
        Decide whether to block further automatic edits in this session.

        Rules:
        - If the same fingerprint has been seen, block immediately.
        - If edits in the current session exceed max_edits_per_session, block.
        """
        if fingerprint and fingerprint in self._fingerprints:
            return True
        if self._session_edits >= self.max_edits_per_session:
            return True
        return False

    def flush(self) -> None:
        """Append buffered entries to the runtime log file."""
        if not self._buffer:
            return
        with open(self.log_path, "a", encoding="utf-8") as f:
            for rec in self._buffer:
                f.write(json.dumps(rec) + "\n")
        self._buffer.clear()

    def clear_session_state(self) -> None:
        """Reset session counters without deleting log history."""
        self._session_edits = 0
        self._fingerprints.clear()
