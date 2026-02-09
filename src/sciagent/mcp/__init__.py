"""
sciagent.mcp — Model Context Protocol server scaffold.

Subclass ``BaseMCPServer`` and call ``register_tool()`` to expose
your tools over the MCP protocol.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseMCPServer:
    """Minimal MCP server that dispatches JSON-RPC requests to registered tools.

    Usage::

        class MyMCPServer(BaseMCPServer):
            def __init__(self):
                super().__init__(name="my-agent", version="0.1.0")
                self.register_tool("my_tool", self.my_tool, {
                    "description": "Do something useful",
                    "inputSchema": {...}
                })

            async def my_tool(self, arguments: dict) -> Any:
                ...

        if __name__ == "__main__":
            MyMCPServer().run()
    """

    def __init__(self, name: str = "sciagent", version: str = "0.1.0"):
        self.name = name
        self.version = version
        self._tools: Dict[str, dict] = {}
        self._handlers: Dict[str, Callable] = {}
        self._initialized = False

    # ── Tool registration ───────────────────────────────────────────

    def register_tool(
        self,
        name: str,
        handler: Callable,
        schema: dict,
    ):
        """Register a tool with a JSON Schema description.

        Args:
            name: Tool name (must match ``inputSchema`` expectations).
            handler: ``async (arguments: dict) -> Any``
            schema: Dict with at least ``description`` and ``inputSchema``.
        """
        self._tools[name] = {
            "name": name,
            **schema,
        }
        self._handlers[name] = handler

    def register_tools_from_module(self, module):
        """Auto-register all ``@tool``-decorated functions in *module*.

        Requires the functions to be decorated with
        ``sciagent.tools.registry.tool``.
        """
        from sciagent.tools.registry import collect_tools

        for name, desc, params, fn in collect_tools(module):
            self.register_tool(name, _wrap_sync(fn), {
                "description": desc,
                "inputSchema": params,
            })

    # ── JSON-RPC dispatch ───────────────────────────────────────────

    async def handle_message(self, message: dict) -> Optional[dict]:
        """Process one JSON-RPC message and return a response (or ``None`` for notifications)."""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        if method == "initialize":
            return self._handle_initialize(msg_id, params)
        elif method == "notifications/initialized":
            self._initialized = True
            return None
        elif method == "tools/list":
            return self._handle_tools_list(msg_id)
        elif method == "tools/call":
            return await self._handle_tools_call(msg_id, params)
        else:
            return self._error_response(msg_id, -32601, f"Method not found: {method}")

    def _handle_initialize(self, msg_id, params):
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": self.name, "version": self.version},
            },
        }

    def _handle_tools_list(self, msg_id):
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": list(self._tools.values())},
        }

    async def _handle_tools_call(self, msg_id, params):
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        handler = self._handlers.get(tool_name)
        if not handler:
            return self._error_response(msg_id, -32602, f"Unknown tool: {tool_name}")

        try:
            result = await handler(arguments)
            content = self._format_result(result)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"content": content, "isError": False},
            }
        except Exception as exc:
            logger.exception("Tool execution error: %s", tool_name)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {exc}"}],
                    "isError": True,
                },
            }

    @staticmethod
    def _format_result(result) -> list:
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]
        return [{"type": "text", "text": str(result)}]

    @staticmethod
    def _error_response(msg_id, code, message):
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": code, "message": message},
        }

    # ── stdio transport ─────────────────────────────────────────────

    def run(self):
        """Run the server over stdin/stdout (JSON-RPC over stdio)."""
        import asyncio
        asyncio.run(self._stdio_loop())

    async def _stdio_loop(self):
        """Read JSON-RPC messages from stdin, dispatch, and write to stdout."""
        logger.info("MCP server %s v%s starting on stdio", self.name, self.version)
        reader = sys.stdin
        writer = sys.stdout

        buffer = ""
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, reader.readline)
            except (EOFError, KeyboardInterrupt):
                break

            if not line:
                break

            buffer += line.strip()
            if not buffer:
                continue

            try:
                message = json.loads(buffer)
                buffer = ""
            except json.JSONDecodeError:
                # Possibly incomplete — keep reading
                continue

            response = await self.handle_message(message)
            if response is not None:
                writer.write(json.dumps(response) + "\n")
                writer.flush()

        logger.info("MCP server shutting down")


# ── Helpers ─────────────────────────────────────────────────────────────

def _wrap_sync(fn: Callable) -> Callable:
    """Wrap a synchronous function into an async handler."""
    import asyncio
    import inspect

    if inspect.iscoroutinefunction(fn):
        async def _handler(arguments: dict):
            return await fn(**arguments)
    else:
        async def _handler(arguments: dict):
            return await asyncio.get_event_loop().run_in_executor(None, lambda: fn(**arguments))
    return _handler
