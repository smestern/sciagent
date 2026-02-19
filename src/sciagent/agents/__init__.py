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
    "RIGOR_REVIEWER_CONFIG",
    "ANALYSIS_PLANNER_CONFIG",
    "DATA_QC_CONFIG",
    "REPORT_WRITER_CONFIG",
    "CODE_REVIEWER_CONFIG",
]


def get_agent_config(name: str) -> Optional[AgentConfig]:
    """Return a default agent config by slug name, or ``None``."""
    return ALL_DEFAULT_AGENTS.get(name)
