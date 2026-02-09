"""
Code Tools — sandboxed Python code execution with scientific rigor enforcement.

This is the *generic* sandbox shared by all sciagent-based agents.
Domain-specific agents can inject extra libraries / loaders via
``BaseScientificAgent._get_execution_environment()``.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import io
import logging
import re
import traceback
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..guardrails.scanner import CodeScanner
from ..guardrails.validator import SANITY_CHECK_HEADER, validate_data_integrity

logger = logging.getLogger(__name__)

# Module-level singletons
_output_dir: Optional[Path] = None
_scanner = CodeScanner()

# Base globals for sandboxed execution
SAFE_GLOBALS: Dict[str, Any] = {"__builtins__": __builtins__}


# ── output dir helpers ──────────────────────────────────────────────────

def set_output_dir(path: "str | Path") -> Path:
    """Set the module-level output directory for code execution."""
    global _output_dir
    _output_dir = Path(path).resolve()
    _output_dir.mkdir(parents=True, exist_ok=True)
    return _output_dir


def get_output_dir() -> Optional[Path]:
    """Return the current output directory (may be ``None``)."""
    return _output_dir


# ── scanner access ──────────────────────────────────────────────────────

def get_scanner() -> CodeScanner:
    """Return the module-level ``CodeScanner`` singleton.

    Domain agents can call this to add extra forbidden/warning patterns::

        from sciagent.tools.code_tools import get_scanner
        scanner = get_scanner()
        scanner.add_forbidden(...)
    """
    return _scanner


# ── execution environment ───────────────────────────────────────────────

def get_execution_environment(
    output_dir: Optional["str | Path"] = None,
    extra_env: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a sandboxed execution environment with scientific libraries.

    Args:
        output_dir: Optional directory to expose as ``OUTPUT_DIR``.
        extra_env: Additional name→object pairs injected into the sandbox.

    Returns:
        Dict of globals for ``exec()``.
    """
    env = SAFE_GLOBALS.copy()

    # Resolve OUTPUT_DIR
    resolved_dir = None
    if output_dir is not None:
        resolved_dir = Path(output_dir).resolve()
    elif _output_dir is not None:
        resolved_dir = _output_dir

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
        import importlib

        mod = importlib.import_module(module_name)
        for alias in (aliases or [module_name]):
            env[alias] = mod
    except ImportError:
        pass


# ── script archiving ────────────────────────────────────────────────────

def _save_script(code: str, output_dir: Optional["str | Path"] = None) -> Optional[Path]:
    """Save executed code to ``OUTPUT_DIR/scripts/`` for reproducibility."""
    target_dir: Optional[Path] = None
    if output_dir is not None:
        target_dir = Path(output_dir).resolve()
    elif _output_dir is not None:
        target_dir = _output_dir

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


# ── public API ──────────────────────────────────────────────────────────

def execute_code(
    code: str,
    context: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = 30.0,
    enforce_rigor: bool = True,
    inject_sanity_checks: bool = True,
    output_dir: Optional["str | Path"] = None,
    extra_env: Optional[Dict[str, Any]] = None,
    _figure_push_fn: Optional[Any] = None,
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

    Returns:
        Dict with ``success``, ``output``, ``error``, ``result``,
        ``variables``, ``figures``, ``rigor_warnings``.
    """
    rigor_warnings: List[str] = []

    # Rigor check — scan for forbidden patterns
    if enforce_rigor:
        rigor_check = _scanner.check(code)
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
    exec_globals = get_execution_environment(output_dir=output_dir, extra_env=extra_env)
    exec_locals: Dict[str, Any] = {}

    # Archive script
    _save_script(code, output_dir)

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
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            open_figs = plt.get_fignums()
            if open_figs:
                figures_data = []
                for fig_num in open_figs:
                    fig = plt.figure(fig_num)
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
                    buf.seek(0)
                    fig_data = {
                        "figure_number": fig_num,
                        "image_base64": base64.b64encode(buf.read()).decode("utf-8"),
                        "format": "png",
                    }
                    figures_data.append(fig_data)
                    buf.close()

                    # Push to web UI if callback provided
                    if _figure_push_fn is not None:
                        try:
                            _figure_push_fn(fig_data)
                        except Exception as q_err:
                            logger.debug("Failed to push figure to queue: %s", q_err)

                plt.close("all")
                result["figures"] = figures_data
        except Exception as fig_err:
            logger.warning("Failed to capture matplotlib figures: %s", fig_err)

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        result["output"] = stdout_capture.getvalue()

    return result


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

    dangerous_calls = ["eval", "exec", "compile", "__import__", "open", "os.system"]
    dangerous_attrs = ["__class__", "__bases__", "__subclasses__"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in dangerous_calls:
                result["warnings"].append(
                    f"Potentially dangerous call: {node.func.id}()"
                )
        if isinstance(node, ast.Attribute) and node.attr in dangerous_attrs:
            result["warnings"].append(f"Accessing special attribute: {node.attr}")

    return result


def run_custom_analysis(
    code: str,
    file_path: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    validate_first: bool = True,
    load_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """Run custom analysis code, optionally loading a data file first.

    Args:
        code: Python code to execute.
        file_path: Path to a data file.
        data: Pre-loaded data dict.
        validate_first: Validate syntax before executing.
        load_fn: A callable ``(path) -> (dataX, dataY, dataC)`` for loading
                 domain-specific files.  If ``None`` and ``file_path`` is
                 given, an error is returned.

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

    context: Dict[str, Any] = {}

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
            context["dataX"] = dataX
            context["dataY"] = dataY
            context["dataC"] = dataC
            context["file_path"] = file_path
        except Exception as e:
            return {"success": False, "error": f"Failed to load data: {e}"}

    if data:
        context.update(data)

    return execute_code(code, context=context)
