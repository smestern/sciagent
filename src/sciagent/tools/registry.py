"""
Tool decorator — syntactic sugar for defining tools inline.

Example::

    from sciagent.tools.registry import tool

    @tool(
        name="analyze_data",
        description="Run analysis on data",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to file"},
            },
            "required": ["file_path"],
        },
    )
    def analyze_data(file_path: str):
        ...
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def tool(
    name: str,
    description: str,
    parameters: Optional[Dict[str, Any]] = None,
) -> Callable:
    """Decorator that attaches tool metadata to a function.

    The metadata is stored as ``_tool_meta`` on the function object.
    ``BaseScientificAgent._create_tool`` can then read it.

    Usage::

        @tool("my_tool", "Does a thing", {...})
        def my_tool(x: int) -> dict:
            ...

        # Later, in _load_tools:
        meta = my_tool._tool_meta
        self._create_tool(meta["name"], meta["description"], my_tool, meta["parameters"])
    """

    def decorator(fn: Callable) -> Callable:
        fn._tool_meta = {  # type: ignore[attr-defined]
            "name": name,
            "description": description,
            "parameters": parameters or {"type": "object", "properties": {}},
        }
        return fn

    return decorator


def collect_tools(module) -> list:
    """Scan a module for functions decorated with ``@tool`` and return
    a list of ``(name, description, handler, parameters)`` tuples.

    Useful in ``_load_tools()``::

        from sciagent.tools.registry import collect_tools
        from sciagent.base_agent import _create_tool
        import my_domain.tools as t

        tools = [_create_tool(*info) for info in collect_tools(t)]
    """
    results = []
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        meta = getattr(obj, "_tool_meta", None)
        if meta is not None:
            results.append((meta["name"], meta["description"], obj, meta["parameters"]))
    return results


def verify_tool_schemas(*modules) -> list[str]:
    """Check that ``@tool`` parameter schemas match function signatures.

    For every ``@tool``-decorated function in the given modules, verifies:
    1. Every ``required`` schema parameter exists in the function signature.
    2. Every required function parameter (no default) appears in the schema
       ``properties``.

    Args:
        *modules: One or more modules to scan.

    Returns:
        List of mismatch descriptions (empty = all OK).

    Example::

        from sciagent.tools.registry import verify_tool_schemas
        import my_domain.tools.io_tools as io
        import my_domain.tools.spike_tools as sp

        errors = verify_tool_schemas(io, sp)
        assert not errors, "\\n".join(errors)
    """
    import inspect

    mismatches: list[str] = []
    for module in modules:
        for name, _desc, handler, params in collect_tools(module):
            sig = inspect.signature(handler)
            sig_params = [p for p in sig.parameters if p != "self"]
            schema_props = list(params.get("properties", {}).keys())
            schema_required = params.get("required", [])

            for sp in schema_required:
                if sp not in sig_params:
                    mismatches.append(
                        f"{name}: schema requires '{sp}' but function has {sig_params}"
                    )

            for fp in sig_params:
                p = sig.parameters[fp]
                if p.default is inspect.Parameter.empty and fp not in schema_props:
                    mismatches.append(
                        f"{name}: function requires '{fp}' but not in schema {schema_props}"
                    )
    return mismatches
