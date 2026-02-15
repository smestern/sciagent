"""
Code Tools — backward-compatible re-exports.

The actual implementations have been split into focused modules:

- ``sandbox.py``  — ``execute_code``, ``validate_code``, ``run_custom_analysis``
- ``figures.py``  — matplotlib figure capture and saving
- ``scripts.py``  — ``save_reproducible_script``, ``retrieve_session_log``
- ``context.py``  — ``ExecutionContext`` (replaces module-level singletons)

This file preserves the old ``from sciagent.tools.code_tools import ...``
import paths so existing code continues to work.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .context import (
    ExecutionContext,
    get_active_context,
    set_active_context,
)
from .sandbox import (
    SAFE_GLOBALS,
    execute_code,
    get_execution_environment,
    run_custom_analysis,
    validate_code,
)
from .scripts import (
    retrieve_session_log,
    save_reproducible_script,
)
from .session_log import SessionLog, get_session_log, set_session_log

# Re-export scanner access
from ..guardrails.scanner import CodeScanner

logger = logging.getLogger(__name__)

# ── Legacy global accessors ─────────────────────────────────────────────
# These delegate to the active ExecutionContext for backward compat.


def set_output_dir(path: "str | Path") -> Path:
    """Set the output directory.  Creates an active context if needed."""
    resolved = Path(path).resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    ctx = get_active_context()
    if ctx is None:
        ctx = ExecutionContext(output_dir=resolved)
        set_active_context(ctx)
    else:
        ctx.output_dir = resolved
    return resolved


def get_output_dir() -> Optional[Path]:
    """Return the current output directory (may be ``None``)."""
    ctx = get_active_context()
    return ctx.output_dir if ctx else None


def set_file_loaded_hook(fn) -> None:
    """Set the file-loaded hook on the active context."""
    ctx = get_active_context()
    if ctx is None:
        ctx = ExecutionContext(on_file_loaded=fn)
        set_active_context(ctx)
    else:
        ctx.on_file_loaded = fn


def notify_file_loaded(file_path: str) -> None:
    """Notify the system that a data file was loaded."""
    ctx = get_active_context()
    if ctx is not None:
        ctx.notify_file_loaded(file_path)


def get_scanner() -> CodeScanner:
    """Return the active context's ``CodeScanner``."""
    ctx = get_active_context()
    return ctx.scanner if ctx else CodeScanner()


__all__ = [
    # New API
    "ExecutionContext",
    "get_active_context",
    "set_active_context",
    # Execution
    "execute_code",
    "validate_code",
    "run_custom_analysis",
    "get_execution_environment",
    "SAFE_GLOBALS",
    # Scripts
    "retrieve_session_log",
    "save_reproducible_script",
    # Legacy accessors
    "set_output_dir",
    "get_output_dir",
    "set_file_loaded_hook",
    "notify_file_loaded",
    "get_scanner",
    # Session log
    "SessionLog",
    "get_session_log",
    "set_session_log",
]
