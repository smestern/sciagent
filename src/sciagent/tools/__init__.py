"""sciagent.tools — Generic scientific analysis tools."""

# ── Execution context (DI replacement for module-level singletons) ──
from .context import ExecutionContext, get_active_context, set_active_context

# ── Sandboxed execution ────────────────────────────────────────────
from .sandbox import (
    SAFE_GLOBALS,
    execute_code,
    get_execution_environment,
    run_custom_analysis,
    validate_code,
)

# ── Script archiving ──────────────────────────────────────────────
from .scripts import retrieve_session_log, save_reproducible_script

# ── Legacy compatibility accessors (delegate to ExecutionContext) ──
from .code_tools import (
    get_output_dir,
    get_scanner,
    notify_file_loaded,
    set_file_loaded_hook,
    set_output_dir,
)

# ── Session log ───────────────────────────────────────────────────
from .session_log import SessionLog, get_session_log, set_session_log

# ── Other tool modules ───────────────────────────────────────────
from .fitting_tools import fit_exponential, fit_double_exponential
from .doc_tools import read_doc, set_docs_dir, get_docs_dir
from .registry import tool
from .registry import collect_tools, verify_tool_schemas

__all__ = [
    # Context
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
    "get_scanner",
    "notify_file_loaded",
    "set_file_loaded_hook",
    # Session log
    "SessionLog",
    "get_session_log",
    "set_session_log",
    # Fitting
    "fit_exponential",
    "fit_double_exponential",
    # Docs
    "read_doc",
    "set_docs_dir",
    "get_docs_dir",
    # Registry
    "tool",
    "collect_tools",
    "verify_tool_schemas",
]
