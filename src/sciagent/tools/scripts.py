"""
scripts — Reproducible script archiving and export.

Handles:
- Automatic archiving of every code snippet to ``OUTPUT_DIR/scripts/``
- Curated reproducible script export via ``save_reproducible_script``
- Session log retrieval for the agent to review before composing scripts
"""

from __future__ import annotations

import ast
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .context import ExecutionContext, get_active_context
from .session_log import get_session_log

logger = logging.getLogger(__name__)


def save_script(
    code: str,
    output_dir: Optional[Path] = None,
    ctx: Optional[ExecutionContext] = None,
) -> Optional[Path]:
    """Save executed code to ``output_dir/scripts/`` for reproducibility.

    Args:
        code: The Python code that was executed.
        output_dir: Override directory. Falls back to context's output_dir.
        ctx: Optional ``ExecutionContext``.

    Returns:
        Path to the saved script, or ``None`` if no directory available.
    """
    ctx = ctx or get_active_context()
    target_dir: Optional[Path] = output_dir
    if target_dir is None and ctx is not None:
        target_dir = ctx.output_dir

    if target_dir is None:
        return None

    scripts_dir = target_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_hash = hashlib.md5(code.encode()).hexdigest()[:6]
    dest = scripts_dir / f"script_{stamp}_{short_hash}.py"
    dest.write_text(code, encoding="utf-8")
    logger.debug("Saved script to %s", dest)
    return dest


def retrieve_session_log(
    ctx: Optional[ExecutionContext] = None,
) -> Dict[str, Any]:
    """Retrieve the session log of all code executed during this session.

    Returns a dict with:
    - ``summary``: counts of total / successful / failed steps and loaded files
    - ``entries``: list of all execution records (code, success, error, timestamp)

    Use this to review what was run before composing a reproducible script
    via ``save_reproducible_script``.
    """
    ctx = ctx or get_active_context()
    log = ctx.session_log if ctx else get_session_log()
    if log is None or not log.has_entries:
        return {
            "summary": {
                "total_steps": 0,
                "successful_steps": 0,
                "failed_steps": 0,
                "loaded_files": [],
            },
            "entries": [],
            "message": "No code has been executed in this session yet.",
        }
    return {
        "summary": log.summary(),
        "entries": log.get_log(),
    }


def save_reproducible_script(
    code: str,
    filename: str = "reproducible_analysis.py",
    output_dir: Optional["str | Path"] = None,
    ctx: Optional[ExecutionContext] = None,
) -> Dict[str, Any]:
    """Save a curated, standalone reproducible Python script.

    The agent should compose this script by reviewing the session log,
    selecting the working parts, and writing a clean, well-commented
    script with proper imports, argparse, and error handling.

    Args:
        code: The complete Python script content.
        filename: Output filename (saved in OUTPUT_DIR).
        output_dir: Override output directory.
        ctx: Optional ``ExecutionContext``.

    Returns:
        Dict with ``success``, ``path``, ``message``.
    """
    # Validate syntax
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {
            "success": False,
            "path": None,
            "message": f"Script has a syntax error at line {e.lineno}: {e.msg}",
        }

    # Resolve output directory
    ctx = ctx or get_active_context()
    target_dir: Optional[Path] = None
    if output_dir is not None:
        target_dir = Path(output_dir).resolve()
    elif ctx is not None and ctx.output_dir is not None:
        target_dir = ctx.output_dir

    if target_dir is None:
        return {
            "success": False,
            "path": None,
            "message": "No output directory configured.",
        }

    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / filename
    dest.write_text(code, encoding="utf-8")

    # Mark in session log
    log = ctx.session_log if ctx else get_session_log()
    if log is not None:
        log.script_exported = True

    logger.info("Reproducible script saved to %s", dest)
    return {
        "success": True,
        "path": str(dest),
        "message": f"Reproducible script saved to {dest}",
    }
