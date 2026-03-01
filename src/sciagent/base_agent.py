"""
BaseScientificAgent — Abstract base class for scientific coding agents.

Subclass this and implement ``_load_tools()`` (required) and optionally
override ``_get_system_message()`` to inject domain expertise.

Prefer using ``@tool`` decorators with ``collect_tools()`` over manual
``_create_tool()`` calls — this keeps JSON schemas next to the function
definitions and prevents schema drift.

Example::

    from sciagent import BaseScientificAgent, AgentConfig
    from sciagent.tools.registry import tool, collect_tools

    @tool("my_tool", "Does a thing", {
        "type": "object",
        "properties": {"x": {"type": "integer", "description": "Input"}},
        "required": ["x"],
    })
    def my_tool(x: int) -> dict:
        return {"result": x * 2}

    class MyAgent(BaseScientificAgent):
        def _load_tools(self):
            import my_tools  # module with @tool-decorated functions
            return [self._create_tool(*t) for t in collect_tools(my_tools)]

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
from copilot.types import PermissionHandler


def _model_error_handler(input_data, context):
    """Hook that retries transient model-call errors with generous limits.

    The default SDK behaviour retries 5 times with ~6 s total backoff,
    which is too aggressive for slow or overloaded model endpoints.
    We allow up to 8 retries and let the CLI compute its own backoff
    on top of that.
    """
    if input_data.get("errorContext") == "model_call" and input_data.get("recoverable", True):
        return {
            "errorHandling": "retry",
            "retryCount": 8,
            "suppressOutput": True,
        }
    return None

from .config import AgentConfig
from .agents import ALL_DEFAULT_AGENTS

logger = logging.getLogger(__name__)

# Tools whose arguments are already scanned inside their own handler —
# the middleware should not double-scan them.
_SELF_SCANNING_TOOLS = frozenset({
    "execute_code", "validate_code", "run_custom_analysis",
})

# Minimum argument string length to bother scanning (avoids false
# positives on short flag-like values).
_MIN_SCAN_LENGTH = 50


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

    **Middleware**: When ``AgentConfig.intercept_all_tools`` is enabled
    (the default) and the tool is *not* in ``_SELF_SCANNING_TOOLS``,
    every string argument longer than ``_MIN_SCAN_LENGTH`` is scanned by
    the active ``CodeScanner``.  If hard-block violations or
    needs-confirmation items are found the tool call is rejected with a
    descriptive message instructing the agent to ask the user.

    Args:
        name: Tool name (function name).
        description: What the tool does.
        handler: The function to call (receives keyword arguments).
        parameters: JSON Schema for the tool's parameters.

    Returns:
        A Copilot SDK ``Tool`` instance.
    """

    # If the handler is async, wrap it to run in a thread-based event loop
    # so it works even when called from inside a running loop.
    _is_async = asyncio.iscoroutinefunction(handler)

    def _wrapped_handler(invocation: ToolInvocation) -> ToolResult:
        args = invocation.get("arguments") or {}
        # If the SDK already parsed arguments into a dict, unpack them
        # as keyword arguments into the real handler.
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                args = {}

        # ── Rigor middleware — scan code-like strings in arguments ──
        if name not in _SELF_SCANNING_TOOLS:
            rejection = _rigor_middleware(name, args)
            if rejection is not None:
                return rejection

        try:
            if _is_async:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(asyncio.run, handler(**args)).result()
            else:
                result = handler(**args)
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


def _rigor_middleware(
    tool_name: str, args: Dict[str, Any],
) -> Optional[ToolResult]:
    """Scan string-valued tool arguments for rigor violations.

    Returns a ``ToolResult`` with ``resultType="failure"`` if the
    code scanner finds hard-block violations or needs-confirmation
    items.  Returns ``None`` to allow the call through.
    """
    from .tools.context import get_active_context

    ctx = get_active_context()
    if ctx is None:
        return None

    # Respect the intercept_all_tools config flag.
    if not ctx.intercept_all_tools:
        return None

    scanner = ctx.scanner

    issues: List[str] = []
    for key, value in args.items():
        if not isinstance(value, str) or len(value) < _MIN_SCAN_LENGTH:
            continue
        result = scanner.check(value)
        issues.extend(result["violations"])
        issues.extend(result["needs_confirmation"])

    if not issues:
        return None

    msg = (
        f"⚠️ RIGOR INTERCEPTION on tool '{tool_name}':\n"
        + "\n".join(f"• {i}" for i in issues)
        + "\n\nThe argument text contains code that would bypass the "
        "analysis sandbox.  Present these concerns to the user and ask "
        "whether to proceed.  If the user approves, use execute_code "
        "with confirmed=True instead."
    )
    return ToolResult(textResultForLlm=msg, resultType="failure")


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
        github_token: Optional[str] = None,
    ):
        """Initialise the agent.

        Args:
            config: ``AgentConfig`` with domain-specific settings.
                    Falls back to generic defaults.
            model: LLM model override (takes precedence over ``config.model``).
            log_level: Logging level forwarded to the Copilot SDK.
            output_dir: Override for the output directory (takes precedence
                        over ``config.output_dir``).
            github_token: Optional GitHub OAuth token (``gho_*`` / ``ghu_*``).
                          When provided, the Copilot SDK makes requests on
                          behalf of the authenticated user.
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

        # Build a CodeScanner with the configured rigor level & custom patterns
        from .guardrails.scanner import CodeScanner, RigorLevel
        rigor = RigorLevel.from_str(self.config.rigor_level)
        scanner = CodeScanner(rigor_level=rigor)
        if self.config.forbidden_patterns:
            scanner.add_forbidden_batch(self.config.forbidden_patterns)
        if self.config.warning_patterns:
            scanner.add_warning_batch(self.config.warning_patterns)

        # Execution context — replaces scattered module-level singletons
        from .tools.context import ExecutionContext, set_active_context
        self._exec_ctx = ExecutionContext(
            output_dir=self._output_dir,
            scanner=scanner,
            session_log=self._session_log,
            intercept_all_tools=self.config.intercept_all_tools,
        )
        set_active_context(self._exec_ctx)

        # Documentation directory for read_doc tool
        if self.config.docs_dir:
            from .tools.doc_tools import set_docs_dir
            set_docs_dir(self.config.docs_dir)

        _client_opts: Dict[str, Any] = {"log_level": log_level}
        if github_token:
            _client_opts["github_token"] = github_token
            _client_opts["use_logged_in_user"] = False
        self._client = CopilotClient(_client_opts)
        self._tools: List[Tool] = []
        self._sessions: Dict[str, Any] = {}
        self._tools = self._load_tools()
        self._subagents = ALL_DEFAULT_AGENTS

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

    def _get_available_tools(self) -> Optional[List[str]]:
        """Return an explicit allowlist of tool names for this session.

        When provided, this takes precedence over ``_get_excluded_tools()``
        per Copilot SDK semantics.
        """
        return None

    def _get_excluded_tools(self) -> Optional[List[str]]:
        """Return tool names to disable for this session."""
        return None

    # -- base tools (inherited by all domain agents) ---------------------------

    def _base_tools(self) -> List[Tool]:
        """Return framework-level tools shared by all domain agents.

        These are merged into the session automatically.  Domain agents
        do **not** need to register these in ``_load_tools()``.

        Uses ``collect_tools`` to auto-discover ``@tool``-decorated
        functions in the ``scripts`` module, avoiding hand-maintained
        JSON schemas.
        """
        from .tools.registry import collect_tools
        from .tools import scripts as scripts_mod
        from .tools.doc_tools import read_doc

        tools = [
            _create_tool(name, desc, handler, params)
            for name, desc, handler, params in collect_tools(scripts_mod)
        ]

        # Only add read_doc if a docs_dir is configured
        if self.config.docs_dir:
            meta = getattr(read_doc, "_tool_meta", None)
            if meta:
                tools.append(
                    _create_tool(meta["name"], meta["description"], read_doc, meta["parameters"])
                )

            # Add ingest_library_docs — lets agents expand their docs on-the-fly
            try:
                from .tools.ingest_tools import ingest_library_docs
                meta_ingest = getattr(ingest_library_docs, "_tool_meta", None)
                if meta_ingest:
                    tools.append(
                        _create_tool(
                            meta_ingest["name"],
                            meta_ingest["description"],
                            ingest_library_docs,
                            meta_ingest["parameters"],
                        )
                    )
            except ImportError:
                pass  # sciagent[wizard] extra not installed

        return tools

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
            # Sync via ExecutionContext (also keeps legacy accessors up-to-date)
            self._exec_ctx.output_dir = new_dir
            logger.info("Working directory set to %s (near %s)", new_dir, file_path)

    # -- session lifecycle -----------------------------------------------------

    async def start(self):
        """Start the Copilot SDK client."""
        await self._client.start()
        logger.info("%s started", self.config.display_name)

    async def stop(self):
        """Stop the client, destroying any remaining sessions to persist data."""
        for session_id in list(self._sessions.keys()):
            try:
                await self._sessions[session_id].destroy()
                logger.debug("Destroyed session %s on stop", session_id)
            except Exception as e:
                logger.warning("Error destroying session %s: %s", session_id, e)
        self._sessions.clear()
        await self._client.stop()
        logger.info("%s stopped", self.config.display_name)

    async def create_session(
        self,
        session_id: Optional[str] = None,
        custom_system_message: Optional[str] = None,
        model: Optional[str] = None,
        additional_tools: Optional[List[Tool]] = None,
    ):
        """Create a new agent session.

        Args:
            session_id: Optional custom session ID for persistence/resumption.
            custom_system_message: Optional extra text appended to the system message.
            model: Optional model override for this session.
            additional_tools: Extra tools merged into the session.

        Returns:
            The created ``CopilotSession`` object.
        """
        # Reset session log for the new session
        self._session_log.clear()

        # Wire up the file-loaded hook via ExecutionContext
        self._exec_ctx.on_file_loaded = self.update_working_dir_from_file

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

        config = SessionConfig(
            model=model or self.model,
            tools=all_tools,
            system_message=system_message,
            custom_agents=[agent_config, *[x.to_copilot_config() for x in self._subagents.values()]], #brute force inject subagent configs as custom agents (since the SDK doesn't have a first-class subagent concept)
            streaming=True,
            on_permission_request=PermissionHandler.approve_all,
            hooks={"on_error_occurred": _model_error_handler},
        )
        available_tools = self._get_available_tools()
        excluded_tools = self._get_excluded_tools()
        if available_tools:
            config["available_tools"] = available_tools
        elif excluded_tools:
            config["excluded_tools"] = excluded_tools
        if session_id:
            config["session_id"] = session_id

        session = await self._client.create_session(config)
        self._sessions[session.session_id] = session
        logger.info("Created session: %s", session.session_id)
        return session

    async def resume_session(self, session_id: str):
        """Resume an existing session by id.

        The session must have been previously created and destroyed
        (but not deleted) so that its data persists on disk.
        """
        session = await self._client.resume_session(session_id)
        self._sessions[session_id] = session
        logger.info("Resumed session: %s", session_id)
        return session

    async def destroy_session(self, session_id: str):
        """Destroy a session but keep its data on disk for later resumption."""
        session = self._sessions.pop(session_id, None)
        if session:
            await session.destroy()
            logger.info("Destroyed session (data persisted): %s", session_id)

    async def list_sessions(self):
        """List all persisted sessions available for resumption."""
        return await self._client.list_sessions()

    async def delete_session(self, session_id: str):
        """Permanently delete a session and all its data from disk."""
        self._sessions.pop(session_id, None)
        await self._client.delete_session(session_id)
        logger.info("Permanently deleted session: %s", session_id)

    # -- read-only properties --------------------------------------------------

    @property
    def tools(self) -> List[Tool]:
        """Get the list of registered tools."""
        return self._tools

    @property
    def client(self) -> CopilotClient:
        """Get the underlying Copilot client."""
        return self._client
