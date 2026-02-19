"""
ExecutionContext — Dependency-injected runtime state for tool execution.

Replaces the module-level singletons (``_output_dir``, ``_scanner``,
``_session_log``, ``_on_file_loaded``) with a single context object
owned by each ``BaseScientificAgent`` instance.

This makes multi-agent-per-process possible and testing trivial —
just construct a context with the pieces you need.

Legacy global accessors (``set_output_dir``, ``get_output_dir``, etc.)
are preserved for backward compatibility but delegate to the
module-level ``_active_context`` singleton.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from ..guardrails.scanner import CodeScanner
from .session_log import SessionLog

logger = logging.getLogger(__name__)


class ExecutionContext:
    """Runtime state shared across tool invocations within one agent.

    Attributes:
        output_dir: Directory for saving scripts, figures, and outputs.
        scanner: Code scanner for scientific rigor enforcement.
        session_log: Log of all code executions in this session.
        on_file_loaded: Optional callback ``(file_path: str) -> None``
            invoked when a data file is loaded (e.g. to update working dir).
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        scanner: Optional[CodeScanner] = None,
        session_log: Optional[SessionLog] = None,
        on_file_loaded: Optional[Callable[[str], None]] = None,
        intercept_all_tools: bool = True,
    ) -> None:
        self.output_dir = output_dir
        self.scanner = scanner or CodeScanner()
        self.session_log = session_log or SessionLog()
        self.on_file_loaded = on_file_loaded
        self.intercept_all_tools = intercept_all_tools

    def notify_file_loaded(self, file_path: str) -> None:
        """Record a file load and trigger the hook."""
        self.session_log.record_file_load(file_path)
        if self.on_file_loaded is not None:
            try:
                self.on_file_loaded(file_path)
            except Exception as exc:
                logger.warning("File-loaded hook error: %s", exc)


# ── Module-level active context (backward-compat singleton) ─────────────

_active_context: Optional[ExecutionContext] = None


def set_active_context(ctx: Optional[ExecutionContext]) -> None:
    """Set the module-level active context (used by legacy accessors)."""
    global _active_context
    _active_context = ctx


def get_active_context() -> Optional[ExecutionContext]:
    """Return the current active context."""
    return _active_context
