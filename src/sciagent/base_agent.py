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

import logging
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from copilot import CopilotClient
from copilot.types import Tool, SessionConfig, CustomAgentConfig

from .config import AgentConfig

logger = logging.getLogger(__name__)


def _create_tool(
    name: str,
    description: str,
    handler: Callable,
    parameters: Optional[Dict[str, Any]] = None,
) -> Tool:
    """Create a ``Tool`` object for the Copilot SDK.

    Args:
        name: Tool name (function name).
        description: What the tool does.
        handler: The function to call.
        parameters: JSON Schema for the tool's parameters.

    Returns:
        A Copilot SDK ``Tool`` instance.
    """
    return Tool(
        name=name,
        description=description,
        handler=handler,
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

        # Resolve output directory
        _out = output_dir or self.config.output_dir
        if _out is not None:
            self._output_dir = Path(_out).resolve()
        else:
            self._output_dir = Path(tempfile.mkdtemp(prefix="sciagent_"))
        self._output_dir.mkdir(parents=True, exist_ok=True)

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
        base_system = self._get_system_message()
        if custom_system_message:
            system_message = {"mode": "append", "content": custom_system_message}
        else:
            system_message = {"mode": "append", "content": base_system}

        all_tools = self._tools.copy()
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
