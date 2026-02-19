"""
sandbox — Sandboxed Python code execution with scientific rigor enforcement.

This is the *generic* sandbox shared by all sciagent-based agents.
Domain-specific agents can inject extra libraries / loaders via
``BaseScientificAgent._get_execution_environment()``.
"""

from __future__ import annotations

import ast
import importlib
import io
import logging
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..guardrails.scanner import CodeScanner
from ..guardrails.validator import SANITY_CHECK_HEADER, validate_data_integrity
from .context import ExecutionContext, get_active_context
from .registry import tool
from .session_log import get_session_log

logger = logging.getLogger(__name__)

# Base globals for sandboxed execution
SAFE_GLOBALS: Dict[str, Any] = {"__builtins__": __builtins__}


# ── Execution environment ───────────────────────────────────────────────


def get_execution_environment(
    output_dir: Optional["str | Path"] = None,
    extra_env: Optional[Dict[str, Any]] = None,
    ctx: Optional[ExecutionContext] = None,
) -> Dict[str, Any]:
    """Build a sandboxed execution environment with scientific libraries.

    Args:
        output_dir: Optional directory to expose as ``OUTPUT_DIR``.
        extra_env: Additional name→object pairs injected into the sandbox.
        ctx: Optional ``ExecutionContext`` (falls back to active context).

    Returns:
        Dict of globals for ``exec()``.
    """
    ctx = ctx or get_active_context()
    env = SAFE_GLOBALS.copy()

    # Resolve OUTPUT_DIR
    resolved_dir = None
    if output_dir is not None:
        resolved_dir = Path(output_dir).resolve()
    elif ctx is not None and ctx.output_dir is not None:
        resolved_dir = ctx.output_dir

    if resolved_dir is not None:
        resolved_dir.mkdir(parents=True, exist_ok=True)
        env["OUTPUT_DIR"] = resolved_dir
        env["Path"] = Path

    # Core scientific libraries
    _try_import(env, "numpy", aliases=["np", "numpy"])
    _try_import(env, "pandas", aliases=["pd", "pandas"])

    try:
        import scipy
        from scipy import signal, stats, optimize

        env["scipy"] = scipy
        env["signal"] = signal
        env["stats"] = stats
        env["optimize"] = optimize
    except ImportError:
        pass

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.show = lambda *a, **kw: None
        plt.ion = lambda *a, **kw: None
        env["plt"] = plt
        env["matplotlib"] = matplotlib
    except ImportError:
        pass

    # Extra domain-specific libraries
    if extra_env:
        env.update(extra_env)

    return env


def _try_import(env: dict, module_name: str, aliases: Optional[List[str]] = None) -> None:
    """Try to import a module and add it under one or more aliases."""
    try:
        mod = importlib.import_module(module_name)
        for alias in (aliases or [module_name]):
            env[alias] = mod
    except ImportError:
        pass


# ── Code validation ─────────────────────────────────────────────────────


@tool(
    name="validate_code",
    description="Validate Python code syntax and check for dangerous operations",
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to validate"},
        },
        "required": ["code"],
    },
)
def validate_code(code: str) -> Dict[str, Any]:
    """Validate Python code without executing it.

    Checks syntax and potentially dangerous operations.

    Args:
        code: Python code to validate.

    Returns:
        Dict with ``valid``, ``errors``, and ``warnings``.
    """
    result: Dict[str, Any] = {"valid": False, "errors": [], "warnings": []}

    try:
        tree = ast.parse(code)
        result["valid"] = True
    except SyntaxError as e:
        result["errors"].append(f"Syntax error at line {e.lineno}: {e.msg}")
        return result

    dangerous_calls = [
        "eval", "exec", "compile", "__import__", "open", "os.system",
    ]
    dangerous_attrs = ["__class__", "__bases__", "__subclasses__"]

    # Additional dangerous module-level calls (subprocess.*, os.popen, etc.)
    dangerous_module_calls = {
        "subprocess": {"run", "Popen", "call", "check_output", "check_call"},
        "os": {"system", "popen", "execl", "execle", "execlp", "execv",
               "execve", "execvp", "execvpe", "spawnl", "spawnle"},
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in dangerous_calls:
                result["warnings"].append(
                    f"Potentially dangerous call: {node.func.id}()"
                )
        # Detect module.func() calls like subprocess.run(), os.popen()
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                mod = node.func.value.id
                func = node.func.attr
                if mod in dangerous_module_calls and func in dangerous_module_calls[mod]:
                    result["warnings"].append(
                        f"BLOCKED: {mod}.{func}() — shell execution is not "
                        f"permitted inside the sandbox."
                    )
        if isinstance(node, ast.Attribute) and node.attr in dangerous_attrs:
            result["warnings"].append(f"Accessing special attribute: {node.attr}")

    return result


# ── Core execution ──────────────────────────────────────────────────────


@tool(
    name="execute_code",
    description=(
        "Execute custom Python code for analysis. Code is validated for "
        "scientific rigor. numpy, scipy, matplotlib, and pandas are available. "
        "If the tool returns needs_confirmation=True, present the warnings to "
        "the user and ask whether to proceed. If they agree, call again with "
        "confirmed=True."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
            "context": {"type": "object", "description": "Variables to make available"},
            "confirmed": {
                "type": "boolean",
                "description": (
                    "Set to true after the user has confirmed a rigor warning. "
                    "When true, WARNING-level rigor patterns are skipped "
                    "(CRITICAL violations still block)."
                ),
                "default": False,
            },
        },
        "required": ["code"],
    },
)
def execute_code(
    code: str,
    context: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = 30.0,
    enforce_rigor: bool = True,
    inject_sanity_checks: bool = True,
    output_dir: Optional["str | Path"] = None,
    extra_env: Optional[Dict[str, Any]] = None,
    _figure_push_fn: Optional[Any] = None,
    ctx: Optional[ExecutionContext] = None,
    confirmed: bool = False,
) -> Dict[str, Any]:
    """Execute custom Python code in a controlled environment.

    Args:
        code: Python code to execute.
        context: Variables injected into the namespace.
        timeout: (advisory) max execution time in seconds.
        enforce_rigor: Check for forbidden patterns before execution.
        inject_sanity_checks: Prepend ``_validate_input`` helpers.
        output_dir: Directory for OUTPUT_DIR and script archiving.
        extra_env: Additional sandbox globals (domain loaders, etc.).
        _figure_push_fn: Optional callback ``(fig_dict) -> None`` for
            pushing captured figures to a web UI queue.
        ctx: Optional ``ExecutionContext`` (falls back to active context).
        confirmed: When ``True``, the user has acknowledged rigor
            warnings — WARNING-level matches are allowed through.
            CRITICAL violations still block regardless.

    Returns:
        Dict with ``success``, ``output``, ``error``, ``result``,
        ``variables``, ``figures``, ``rigor_warnings``, and optionally
        ``needs_confirmation``.
    """
    from .figures import capture_figures
    from .scripts import save_script

    ctx = ctx or get_active_context()
    scanner = ctx.scanner if ctx else CodeScanner()
    rigor_warnings: List[str] = []

    # Rigor check — scan for forbidden patterns
    if enforce_rigor:
        rigor_check = scanner.check(code)

        # Hard-block violations (CRITICAL patterns in STANDARD, all in STRICT)
        if not rigor_check["passed"]:
            return {
                "success": False,
                "output": "",
                "error": (
                    "SCIENTIFIC RIGOR VIOLATION — Code blocked:\n"
                    + "\n".join(rigor_check["violations"])
                ),
                "result": None,
                "variables": {},
                "figures": [],
                "rigor_warnings": rigor_check["violations"],
            }

        # Needs-confirmation items — require user acknowledgement
        if rigor_check["needs_confirmation"] and not confirmed:
            confirmation_items = rigor_check["needs_confirmation"]
            return {
                "success": False,
                "needs_confirmation": True,
                "output": "",
                "error": None,
                "result": None,
                "variables": {},
                "figures": [],
                "rigor_warnings": confirmation_items,
                "message": (
                    "⚠️ RIGOR WARNING — The following concerns were detected:\n"
                    + "\n".join(f"• {w}" for w in confirmation_items)
                    + "\n\nPresent these warnings to the user and ask whether "
                    "to proceed. If they confirm, re-call execute_code with "
                    "confirmed=True."
                ),
            }

        # Informational warnings — always pass through
        rigor_warnings.extend(rigor_check["warnings"])

    # Validate input data integrity
    if context:
        import numpy as np

        for key, value in context.items():
            if isinstance(value, np.ndarray):
                integrity = validate_data_integrity(value, key)
                if not integrity["valid"]:
                    return {
                        "success": False,
                        "output": "",
                        "error": (
                            "DATA INTEGRITY ISSUE — Analysis blocked:\n"
                            + "\n".join(integrity["issues"])
                        ),
                        "result": None,
                        "variables": {},
                        "figures": [],
                        "rigor_warnings": integrity["issues"],
                    }
                rigor_warnings.extend(integrity["warnings"])

    # Inject sanity check helpers
    if inject_sanity_checks:
        code = SANITY_CHECK_HEADER + code

    # Build execution environment
    exec_globals = get_execution_environment(
        output_dir=output_dir, extra_env=extra_env, ctx=ctx,
    )
    exec_locals: Dict[str, Any] = {}

    # Resolve the output dir for script archiving
    _resolved_out = None
    if output_dir is not None:
        _resolved_out = Path(output_dir).resolve()
    elif ctx is not None and ctx.output_dir is not None:
        _resolved_out = ctx.output_dir

    # Archive script
    save_script(code, output_dir=_resolved_out)

    # Inject context
    if context:
        exec_locals.update(context)

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    result: Dict[str, Any] = {
        "success": False,
        "output": "",
        "error": None,
        "result": None,
        "variables": {},
        "figures": [],
        "rigor_warnings": rigor_warnings or None,
    }

    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exec(code, exec_globals, exec_locals)

        result["success"] = True
        result["output"] = stdout_capture.getvalue()

        stderr_output = stderr_capture.getvalue()
        if stderr_output:
            result["output"] += f"\n[stderr]: {stderr_output}"

        # Extract user-defined variables
        import types
        import numpy as np

        for name, value in exec_locals.items():
            if name.startswith("_"):
                continue
            if isinstance(value, types.ModuleType):
                continue
            if isinstance(value, np.ndarray):
                if value.size <= 100:
                    result["variables"][name] = value.tolist()
                else:
                    result["variables"][name] = (
                        f"<ndarray shape={value.shape} dtype={value.dtype}>"
                    )
            elif isinstance(value, (int, float, str, bool, list, dict)):
                result["variables"][name] = value
            else:
                result["variables"][name] = str(type(value))

        # Capture matplotlib figures
        result["figures"] = capture_figures(
            output_dir=_resolved_out,
            figure_push_fn=_figure_push_fn,
        )

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        result["output"] = stdout_capture.getvalue()

    # Record in session log
    _log = ctx.session_log if ctx else get_session_log()
    if _log is not None:
        _log.record(
            code=code,
            success=result["success"],
            error=result.get("error", "") or "",
        )

    return result


def run_custom_analysis(
    code: str,
    file_path: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    validate_first: bool = True,
    load_fn: Optional[Any] = None,
    ctx: Optional[ExecutionContext] = None,
) -> Dict[str, Any]:
    """Run custom analysis code, optionally loading a data file first.

    Args:
        code: Python code to execute.
        file_path: Path to a data file.
        data: Pre-loaded data dict.
        validate_first: Validate syntax before executing.
        load_fn: A callable ``(path) -> (dataX, dataY, dataC)`` for loading
                 domain-specific files.
        ctx: Optional ``ExecutionContext``.

    Returns:
        Execution result dict.
    """
    if validate_first:
        validation = validate_code(code)
        if not validation["valid"]:
            return {
                "success": False,
                "error": f"Code validation failed: {validation['errors']}",
                "validation": validation,
            }
        if validation["warnings"]:
            logger.warning("Code warnings: %s", validation["warnings"])

    context_vars: Dict[str, Any] = {}

    if file_path:
        if load_fn is None:
            return {
                "success": False,
                "error": (
                    "No data loader configured. Provide a load_fn or "
                    "override _get_execution_environment in your agent."
                ),
            }
        try:
            dataX, dataY, dataC = load_fn(file_path)
            context_vars["dataX"] = dataX
            context_vars["dataY"] = dataY
            context_vars["dataC"] = dataC
            context_vars["file_path"] = file_path
        except Exception as e:
            return {"success": False, "error": f"Failed to load data: {e}"}

    if data:
        context_vars.update(data)

    return execute_code(code, context=context_vars, ctx=ctx)
