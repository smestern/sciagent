"""
BaseScientificAgent — Abstract base class for scientific coding agents.

Subclass this and implement ``_load_tools()`` (required) and optionally
override ``_get_system_message()`` to inject domain expertise.

Example::

    from sciagent import BaseScientificAgent, AgentConfig

    class MyAgent(BaseScientificAgent):
        def _load_tools(self):
            from my_tools import my_tool_fn
            return [self._create_tool("my_tool", "Does a thing", my_tool_fn, {...})]

        def _get_system_message(self) -> str:
            from sciagent.prompts import BASE_SCIENTIFIC_PRINCIPLES
            return BASE_SCIENTIFIC_PRINCIPLES + "\\n\\n" + MY_DOMAIN_EXPERTISE
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from copilot import CopilotClient
from copilot.types import Tool, ToolInvocation, ToolResult, SessionConfig, CustomAgentConfig

from .config import AgentConfig

logger = logging.getLogger(__name__)


def _normalize_result(result: Any) -> ToolResult:
    """Convert any return value to a ``ToolResult``.

    * ``None`` → empty success
    * ``str`` → success with that text
    * dict already shaped as ``ToolResult`` → pass through
    * anything else → JSON-serialise
    """
    if result is None:
        return ToolResult(textResultForLlm="", resultType="success")

    if isinstance(result, dict) and "resultType" in result and "textResultForLlm" in result:
        return result  # type: ignore[return-value]

    if isinstance(result, str):
        return ToolResult(textResultForLlm=result, resultType="success")

    try:
        json_str = json.dumps(result, default=str)
    except (TypeError, ValueError) as exc:
        json_str = repr(result)

    return ToolResult(textResultForLlm=json_str, resultType="success")


def _create_tool(
    name: str,
    description: str,
    handler: Callable,
    parameters: Optional[Dict[str, Any]] = None,
) -> Tool:
    """Create a ``Tool`` object for the Copilot SDK.

    Wraps *handler* so it receives unpacked ``arguments`` from the
    ``ToolInvocation`` dict rather than the raw invocation envelope.
    The return value is normalised into a ``ToolResult``.

    Args:
        name: Tool name (function name).
        description: What the tool does.
        handler: The function to call (receives keyword arguments).
        parameters: JSON Schema for the tool's parameters.

    Returns:
        A Copilot SDK ``Tool`` instance.
    """

    def _wrapped_handler(invocation: ToolInvocation) -> ToolResult:
        args = invocation.get("arguments") or {}
        # If the SDK already parsed arguments into a dict, unpack them
        # as keyword arguments into the real handler.
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                args = {}
        try:
            result = handler(**args)
            # Support async handlers
            if asyncio.iscoroutine(result):
                result = asyncio.get_event_loop().run_until_complete(result)
        except Exception as exc:
            logger.exception("Tool %s raised an error", name)
            return ToolResult(
                textResultForLlm=f"Error invoking tool {name}: {exc}",
                resultType="failure",
            )
        return _normalize_result(result)

    return Tool(
        name=name,
        description=description,
        handler=_wrapped_handler,
        parameters=parameters or {"type": "object", "properties": {}},
    )


class BaseScientificAgent:
    """Abstract base class for scientific analysis agents.

    Wraps the GitHub Copilot SDK client and provides:

    * output_dir management (scripts, figures, analysis artefacts)
    * session lifecycle (start / stop / create_session / resume)
    * tool registration via the ``_load_tools()`` hook
    * system-message composition via ``_get_system_message()``

    Subclasses **must** implement ``_load_tools() -> list[Tool]``.
    """

    # Expose the helper so subclasses don't need to import it.
    _create_tool = staticmethod(_create_tool)

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        *,
        model: Optional[str] = None,
        log_level: str = "info",
        output_dir: Optional[str | Path] = None,
    ):
        """Initialise the agent.

        Args:
            config: ``AgentConfig`` with domain-specific settings.
                    Falls back to generic defaults.
            model: LLM model override (takes precedence over ``config.model``).
            log_level: Logging level forwarded to the Copilot SDK.
            output_dir: Override for the output directory (takes precedence
                        over ``config.output_dir``).
        """
        self.config = config or AgentConfig()
        self.model = model or self.config.model

        # Track whether the user explicitly set --output-dir
        self._user_specified_output_dir = output_dir is not None

        # Resolve output directory
        _out = output_dir or self.config.output_dir
        if _out is not None:
            self._output_dir = Path(_out).resolve()
        else:
            self._output_dir = Path(tempfile.mkdtemp(prefix="sciagent_"))
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Session log for reproducible script generation
        from .tools.session_log import SessionLog, set_session_log
        self._session_log = SessionLog()
        set_session_log(self._session_log)

        self._client = CopilotClient({"log_level": log_level})
        self._tools: List[Tool] = []
        self._sessions: Dict[str, Any] = {}
        self._tools = self._load_tools()

    # -- output_dir property --------------------------------------------------

    @property
    def output_dir(self) -> Path:
        """The directory where the agent saves scripts, plots, and outputs."""
        return self._output_dir

    @output_dir.setter
    def output_dir(self, value: str | Path) -> None:
        """Change the output directory at runtime (creates it if needed)."""
        self._output_dir = Path(value).resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Agent output_dir set to %s", self._output_dir)

    # -- hooks for subclasses --------------------------------------------------

    def _load_tools(self) -> List[Tool]:
        """Return the list of tools available to this agent.

        **Subclasses must override this.**

        Returns:
            List of ``Tool`` objects.
        """
        raise NotImplementedError(
            "Subclasses must implement _load_tools() to register domain-specific tools."
        )

    def _get_system_message(self) -> str:
        """Return the system message for the agent.

        The default implementation composes the generic scientific-rigor
        principles with any ``config.instructions``.  Override to inject
        domain-specific expertise.
        """
        from .prompts.base_messages import BASE_SCIENTIFIC_PRINCIPLES

        parts = [BASE_SCIENTIFIC_PRINCIPLES]
        if self.config.instructions:
            parts.append(self.config.instructions)
        return "\n\n".join(parts)

    def _get_execution_environment(self) -> Dict[str, Any]:
        """Build extra globals injected into the code sandbox.

        Override to add domain-specific libraries/data loaders.
        The base implementation returns ``config.extra_libraries``.
        """
        return {}

    def _get_script_imports(self) -> List[str]:
        """Return extra library names the reproducible script should import.

        Override in domain agents to add domain-specific imports
        (e.g. ``["pyabf", "ipfx"]`` for patchAgent).
        """
        return list(self.config.extra_libraries) if self.config.extra_libraries else []

    # -- base tools (inherited by all domain agents) ---------------------------

    def _base_tools(self) -> List[Tool]:
        """Return framework-level tools shared by all domain agents.

        These are merged into the session automatically.  Domain agents
        do **not** need to register these in ``_load_tools()``.
        """
        from .tools.code_tools import retrieve_session_log, save_reproducible_script

        return [
            _create_tool(
                "get_session_log",
                (
                    "Retrieve the session log of all code executed during this session "
                    "(successes and failures). Use this to review what was run before "
                    "composing a reproducible script via save_reproducible_script. "
                    "Returns a summary and the full list of execution records."
                ),
                retrieve_session_log,
                {"type": "object", "properties": {}},
            ),
            _create_tool(
                "save_reproducible_script",
                (
                    "Save a curated, standalone reproducible Python script combining "
                    "the successful analysis steps from this session. You (the agent) "
                    "write the script — review the session log, select working parts, "
                    "and compose a clean script with proper imports, argparse for "
                    "--input-file and --output-dir, error handling, and comments. "
                    "The script must be syntactically valid Python."
                ),
                save_reproducible_script,
                {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": (
                                "The complete Python script content. Must be valid Python. "
                                "Should include argparse with --input-file and --output-dir."
                            ),
                        },
                        "filename": {
                            "type": "string",
                            "description": "Output filename (default: reproducible_analysis.py)",
                        },
                    },
                    "required": ["code"],
                },
            ),
        ]

    # -- working directory resolution -----------------------------------------

    def update_working_dir_from_file(self, file_path: str) -> None:
        """Auto-resolve a working directory adjacent to the analysed file.

        Only acts when no explicit ``--output-dir`` was provided by the user.
        Creates a directory named ``<agent_name>_output`` next to the file.
        Falls back to a temp directory if the parent is not writable.
        """
        if self._user_specified_output_dir:
            return  # user explicitly chose a dir; respect it

        from .data.resolver import resolve_working_dir
        new_dir = resolve_working_dir(file_path, self.config.name)

        if new_dir != self._output_dir:
            self.output_dir = new_dir
            # Sync module-level singleton in code_tools
            from .tools.code_tools import set_output_dir
            set_output_dir(new_dir)
            logger.info("Working directory set to %s (near %s)", new_dir, file_path)

    # -- session lifecycle -----------------------------------------------------

    async def start(self):
        """Start the Copilot SDK client."""
        await self._client.start()
        logger.info("%s started", self.config.display_name)

    async def stop(self):
        """Stop the client and destroy all sessions."""
        for session_id in list(self._sessions.keys()):
            try:
                await self._sessions[session_id].destroy()
            except Exception as e:
                logger.warning("Error destroying session %s: %s", session_id, e)
        self._sessions.clear()
        await self._client.stop()
        logger.info("%s stopped", self.config.display_name)

    async def create_session(
        self,
        custom_system_message: Optional[str] = None,
        model: Optional[str] = None,
        additional_tools: Optional[List[Tool]] = None,
    ):
        """Create a new agent session.

        Args:
            custom_system_message: Optional extra text appended to the system message.
            model: Optional model override for this session.
            additional_tools: Extra tools merged into the session.

        Returns:
            The created ``CopilotSession`` object.
        """
        # Reset session log for the new session
        self._session_log.clear()

        # Wire up the file-loaded hook
        from .tools.code_tools import set_file_loaded_hook
        set_file_loaded_hook(self.update_working_dir_from_file)

        base_system = self._get_system_message()
        if custom_system_message:
            system_message = {"mode": "append", "content": custom_system_message}
        else:
            system_message = {"mode": "append", "content": base_system}

        all_tools = self._tools.copy()
        all_tools.extend(self._base_tools())
        if additional_tools:
            all_tools.extend(additional_tools)

        agent_config: CustomAgentConfig = {
            "name": self.config.name,
            "display_name": self.config.display_name,
            "description": self.config.description,
            "prompt": base_system,
            "infer": True,
        }

        config: SessionConfig = {
            "model": model or self.model,
            "tools": all_tools,
            "system_message": system_message,
            "custom_agents": [agent_config],
            "streaming": True,
        }

        session = await self._client.create_session(config)
        self._sessions[session.session_id] = session
        logger.info("Created session: %s", session.session_id)
        return session

    async def resume_session(self, session_id: str):
        """Resume an existing session by id."""
        session = await self._client.resume_session(session_id)
        self._sessions[session_id] = session
        logger.info("Resumed session: %s", session_id)
        return session

    # -- read-only properties --------------------------------------------------

    @property
    def tools(self) -> List[Tool]:
        """Get the list of registered tools."""
        return self._tools

    @property
    def client(self) -> CopilotClient:
        """Get the underlying Copilot client."""
        return self._client
