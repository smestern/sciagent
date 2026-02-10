"""
SessionLog — Lightweight session-level recording of code executions and file loads.

The agent (LLM) queries this log via the ``get_session_log`` tool to review
what code was executed during a session — including successes *and* failures.
It then curates a clean, standalone script using ``save_reproducible_script``.

This is intentionally *not* an automatic script concatenator.  The LLM is
responsible for selecting the working parts, fixing issues, and composing
a proper reproducible analysis script.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SessionLog:
    """Record code executions and file loads for later review by the agent.

    Usage::

        log = SessionLog()
        log.record(code="x = np.mean(data)", success=True)
        log.record(code="bad code", success=False, error="SyntaxError")
        log.record_file_load("/data/cell.abf")

        # Agent retrieves the log to compose a reproducible script
        entries = log.get_log()
    """

    def __init__(self) -> None:
        self._entries: List[Dict[str, Any]] = []
        self._loaded_files: List[str] = []
        self._script_exported: bool = False

    # ── recording ────────────────────────────────────────────────────

    def record(
        self,
        code: str,
        success: bool,
        error: str = "",
        description: str = "",
    ) -> None:
        """Record a code execution step.

        Args:
            code: The Python code that was executed.
            success: Whether the execution succeeded.
            error: Error message (if ``success`` is ``False``).
            description: Optional human-readable description of the step.
        """
        self._entries.append({
            "step": len(self._entries) + 1,
            "timestamp": datetime.now().isoformat(),
            "code": code,
            "success": success,
            "error": error,
            "description": description,
        })
        status = "OK" if success else "FAIL"
        logger.debug("SessionLog: step %d [%s] %s", len(self._entries), status, description[:60])

    def record_file_load(self, file_path: str) -> None:
        """Record that a data file was loaded during this session."""
        canonical = str(Path(file_path).resolve())
        if canonical not in self._loaded_files:
            self._loaded_files.append(canonical)
            logger.debug("SessionLog: recorded file load %s", canonical)

    # ── querying ─────────────────────────────────────────────────────

    def get_log(self) -> List[Dict[str, Any]]:
        """Return all recorded entries (successes and failures)."""
        return list(self._entries)

    def get_successful_steps(self) -> List[Dict[str, Any]]:
        """Return only the entries where ``success`` is ``True``."""
        return [e for e in self._entries if e["success"]]

    def get_loaded_files(self) -> List[str]:
        """Return the list of file paths loaded during this session."""
        return list(self._loaded_files)

    # ── state ────────────────────────────────────────────────────────

    @property
    def has_entries(self) -> bool:
        """``True`` if at least one code execution was recorded."""
        return len(self._entries) > 0

    @property
    def has_successful_steps(self) -> bool:
        """``True`` if at least one successful execution was recorded."""
        return any(e["success"] for e in self._entries)

    @property
    def script_exported(self) -> bool:
        """``True`` if ``save_reproducible_script`` was already called."""
        return self._script_exported

    @script_exported.setter
    def script_exported(self, value: bool) -> None:
        self._script_exported = value

    def clear(self) -> None:
        """Reset the log for a new session."""
        self._entries.clear()
        self._loaded_files.clear()
        self._script_exported = False
        logger.debug("SessionLog: cleared")

    def summary(self) -> Dict[str, Any]:
        """Return a compact summary of the session log."""
        return {
            "total_steps": len(self._entries),
            "successful_steps": sum(1 for e in self._entries if e["success"]),
            "failed_steps": sum(1 for e in self._entries if not e["success"]),
            "loaded_files": list(self._loaded_files),
            "script_exported": self._script_exported,
        }


# ── Module-level singleton ──────────────────────────────────────────────

_session_log: Optional[SessionLog] = None


def set_session_log(log: SessionLog) -> None:
    """Set the module-level session log singleton."""
    global _session_log
    _session_log = log


def get_session_log() -> Optional[SessionLog]:
    """Return the current session log (may be ``None``)."""
    return _session_log
