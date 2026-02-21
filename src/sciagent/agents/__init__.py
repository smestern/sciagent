"""
sciagent.agents — Default scientific-workflow agent presets.

These are **domain-agnostic** agent configurations that implement common
scientific workflow roles (planning, QC, rigor review, reporting, code
review).  Each preset is a ready-to-use :class:`~sciagent.config.AgentConfig`
paired with a prompt string and VS Code / Claude tool lists.

Domain-specific knowledge is injected via clearly marked *extension
points* — placeholder sections in the prompt where users append their own
expertise, bounds, or terminology.

Quick reference::

    from sciagent.agents import ALL_DEFAULT_AGENTS, get_agent_config

    for name, cfg in ALL_DEFAULT_AGENTS.items():
        print(name, cfg.display_name)

    rigor_cfg = get_agent_config("rigor-reviewer")
"""

from __future__ import annotations

from typing import Dict, Optional

from sciagent.config import AgentConfig

from .rigor_reviewer import RIGOR_REVIEWER_CONFIG
from .planner import ANALYSIS_PLANNER_CONFIG
from .data_qc import DATA_QC_CONFIG
from .report_writer import REPORT_WRITER_CONFIG
from .code_reviewer import CODE_REVIEWER_CONFIG

# Canonical ordered mapping: slug → AgentConfig
ALL_DEFAULT_AGENTS: Dict[str, AgentConfig] = {
    "rigor-reviewer": RIGOR_REVIEWER_CONFIG,
    "analysis-planner": ANALYSIS_PLANNER_CONFIG,
    "data-qc": DATA_QC_CONFIG,
    "report-writer": REPORT_WRITER_CONFIG,
    "code-reviewer": CODE_REVIEWER_CONFIG,
}

__all__ = [
    "ALL_DEFAULT_AGENTS",
    "get_agent_config",
    "list_agent_configs",
    "RIGOR_REVIEWER_CONFIG",
    "ANALYSIS_PLANNER_CONFIG",
    "DATA_QC_CONFIG",
    "REPORT_WRITER_CONFIG",
    "CODE_REVIEWER_CONFIG",
]

DEFAULT_AGENT_PATHS = ["./agents/*.agent.md",
                       "/docs/agents/*.agent.md",
                       "/.copilot/*.agent.md",
                       "/.claude/agents/*.agent.md",
                       "/.github/agents/*.agent.md"]  # Example path pattern for custom agent configs


def get_agent_config(name: str) -> Optional[AgentConfig]:
    """Return a default agent config by slug name, or ``None``."""
    return ALL_DEFAULT_AGENTS.get(name)

def list_agent_configs() -> Dict[str, AgentConfig]:
    """Return a dict of all default agent configs."""
    return ALL_DEFAULT_AGENTS

def load_agent_config_from_markdown(md_path: str) -> AgentConfig:
    """Load an agent config from a custom Markdown file."""
    from sciagent.prompts.markdown import parse_agent_markdown
    return parse_agent_markdown(md_path)

#on startup load agent configs from default agents directory (for VS Code extension)(if they have the same name as the default agents, they will override the built-in ones)

def load_agent_configs_from_directory(dir_path: str) -> Dict[str, AgentConfig]:
    """Load agent configs from a directory of Markdown files."""
    from sciagent.prompts.markdown import parse_agent_markdown
    import os
    import glob 

    agent_configs = {}

    # Look for .agent.md files in the specified directory
    agent_configs_paths = glob.glob(dir_path + "/*.agent.md")
    agent_configs_paths += glob.glob(dir_path + "/*.md")  # Also consider .md files as potential agent configs

    for md_path in agent_configs_paths:
        agent_config = parse_agent_markdown(md_path)
        agent_configs[agent_config.name] = agent_config
    return agent_configs

# Load on module import

def initialize_agent_configs():
    """Initialize the global agent configs, loading any custom ones from disk."""
    import os
    for path_pattern in DEFAULT_AGENT_PATHS:
        dir_path = os.path.abspath(os.getcwd() + "/" + path_pattern.rsplit("/", 1)[0])  # Extract directory from pattern
        if os.path.exists(dir_path):
            custom_configs = load_agent_configs_from_directory(dir_path)
            ALL_DEFAULT_AGENTS.update(custom_configs)

initialize_agent_configs()