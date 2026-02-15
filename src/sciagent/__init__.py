"""
sciagent — A framework for building rigorous, human-in-the-loop scientific coding agents.

Provides base classes and infrastructure for creating domain-specific
scientific analysis agents powered by the GitHub Copilot SDK.

Quick start::

    from sciagent import BaseScientificAgent, AgentConfig

    class MyAgent(BaseScientificAgent):
        def _load_tools(self):
            return [...]

    agent = MyAgent(AgentConfig(name="my-agent", ...))
"""

try:
    from importlib.metadata import version as _meta_version

    __version__ = _meta_version("sciagent")
except Exception:
    __version__ = "0.0.0"  # fallback when not installed

from .config import AgentConfig

# Agent / CLI imports are guarded — Copilot SDK may not be installed.
try:
    from .base_agent import BaseScientificAgent
except ImportError:
    BaseScientificAgent = None  # type: ignore[assignment,misc]

try:
    from .cli import ScientificCLI
except ImportError:
    ScientificCLI = None  # type: ignore[assignment,misc]
