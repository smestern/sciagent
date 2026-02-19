"""
converter — Bridge between ``AgentConfig`` and the copilot/claude generator.

Provides utilities to convert an :class:`~sciagent.config.AgentConfig`
(or a YAML config dict) into the ``WizardState`` shape expected by
:func:`~sciagent_wizard.generators.copilot.generate_copilot_project`,
and thin wrappers that produce ``.agent.md`` / ``.claude`` agent files
without running the full wizard.

Usage::

    from sciagent.agents.converter import agent_to_copilot_files
    from sciagent.config import AgentConfig

    cfg = AgentConfig(name="my-agent", description="My agent", ...)
    agent_to_copilot_files(cfg, output_dir="./my_project")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from sciagent.config import AgentConfig

logger = logging.getLogger(__name__)


# ── Lightweight WizardState stand-in ────────────────────────────────────
#
# We only need the fields that ``_vscode_agent_md`` and
# ``_claude_agent_md`` actually read — agent_name, agent_display_name,
# agent_description, and optionally confirmed_packages / package_docs.
# Rather than importing the full WizardState (which pulls in wizard
# dependencies), we use a thin shim.


@dataclass
class _MiniState:
    """Minimal stand-in for ``WizardState`` — just enough for the
    copilot generator helpers."""

    agent_name: str = ""
    agent_display_name: str = ""
    agent_description: str = ""
    domain_description: str = ""
    research_goals: List[str] = field(default_factory=list)
    accepted_file_types: List[str] = field(default_factory=list)
    bounds: Dict[str, tuple] = field(default_factory=dict)
    confirmed_packages: list = field(default_factory=list)
    package_docs: Dict[str, str] = field(default_factory=dict)
    example_files: list = field(default_factory=list)
    domain_prompt: str = ""
    project_dir: str = ""
    output_mode: str = "copilot_agent"


def config_to_mini_state(
    config: AgentConfig,
    domain_prompt: str = "",
) -> _MiniState:
    """Map an ``AgentConfig`` to the minimal state needed by the generator."""
    return _MiniState(
        agent_name=config.name,
        agent_display_name=config.display_name,
        agent_description=config.description,
        domain_description=config.instructions,
        accepted_file_types=config.accepted_file_types,
        bounds=config.bounds,
        domain_prompt=domain_prompt,
    )


# ── YAML → AgentConfig ─────────────────────────────────────────────────


def yaml_to_config(data: Dict[str, Any]) -> AgentConfig:
    """Parse a YAML dict into an ``AgentConfig``.

    Unknown keys are silently ignored so the YAML can carry extra
    metadata (e.g. ``tools_override``, ``domain_prompt``).
    """
    import dataclasses

    valid_fields = {f.name for f in dataclasses.fields(AgentConfig)}
    filtered = {}
    for k, v in data.items():
        if k in valid_fields:
            # Convert list-of-two-element-lists to tuples for bounds
            if k == "bounds" and isinstance(v, dict):
                filtered[k] = {
                    param: tuple(rng) for param, rng in v.items()
                }
            else:
                filtered[k] = v
    return AgentConfig(**filtered)


# ── Core generator ──────────────────────────────────────────────────────
#
# These functions produce the same output as the wizard's copilot
# generator but from a plain ``AgentConfig`` — no conversation needed.


_RIGOR_GUARDRAIL_INSTRUCTIONS = """\
### Scientific Rigor — Shell / Terminal Policy

**NEVER** use the `terminal` tool to execute data analysis or computation code.
All analysis must go through the provided analysis tools (e.g. `execute_code`)
which enforce scientific rigor checks automatically.

The `terminal` tool may be used **only** for environment setup tasks such as
`pip install`, `git` commands, or opening files — and only after describing the
command to the user.

If a rigor warning is raised by `execute_code` (indicated by
`needs_confirmation: true` in the result), you **MUST**:
1. Present the warnings to the user verbatim.
2. Ask whether to proceed.
3. If confirmed, re-call `execute_code` with `confirmed: true`.
4. Never silently bypass or suppress rigor warnings.
"""


def _make_vscode_agent_md(
    config: AgentConfig,
    instructions: str,
    tools_override: Optional[List[str]] = None,
) -> str:
    """Generate a VS Code ``.agent.md`` file from an ``AgentConfig``."""
    tools = tools_override or [
        "codebase", "terminal", "search",
        "fetch", "editFiles", "findTestFiles",
    ]
    tools_yaml = "\n".join(f"  - {t}" for t in tools)

    handoffs_yaml = ""
    if config.name:
        prompt_txt = (
            "Review the analysis results above"
            " for scientific rigor."
        )
        handoffs_yaml = (
            "handoffs:\n"
            '  - label: "Review Results"\n'
            "    agent: rigor-reviewer\n"
            f'    prompt: "{prompt_txt}"\n'
            "    send: false"
        )

    frontmatter = (
        f"---\n"
        f"description: >-\n"
        f"  {config.description}\n"
        f"name: {config.name}\n"
        f"tools:\n"
        f"{tools_yaml}\n"
        f"{handoffs_yaml}\n"
        f"---"
    )

    rigor = _RIGOR_GUARDRAIL_INSTRUCTIONS
    return (
        f"{frontmatter}\n\n{instructions}"
        f"\n\n{rigor}\n"
    )


def _make_claude_agent_md(
    config: AgentConfig,
    instructions: str,
    tools_override: Optional[str] = None,
) -> str:
    """Generate a Claude Code sub-agent ``.md`` file."""
    tools = tools_override or "Read, Write, Edit, Bash, Grep, Glob"

    frontmatter = (
        f"---\n"
        f"name: {config.name}\n"
        f"description: >-\n"
        f"  {config.description}\n"
        f"tools: {tools}\n"
        f"model: sonnet\n"
        f"---"
    )

    rigor = _RIGOR_GUARDRAIL_INSTRUCTIONS
    return (
        f"{frontmatter}\n\n{instructions}"
        f"\n\n{rigor}\n"
    )


def agent_to_copilot_files(
    config: AgentConfig,
    output_dir: str | Path,
    *,
    domain_prompt: str = "",
    tools_vscode: Optional[List[str]] = None,
    tools_claude: Optional[str] = None,
    fmt: str = "both",
) -> Path:
    """Generate VS Code / Claude Code agent files from an ``AgentConfig``.

    Args:
        config: The agent configuration.
        output_dir: Root directory for output.
        domain_prompt: Optional extra domain instructions appended to
            the config's ``instructions``.
        tools_vscode: Override the VS Code tool list.
        tools_claude: Override the Claude tool string.
        fmt: ``"vscode"``, ``"claude"``, or ``"both"`` (default).

    Returns:
        Path to the output directory.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    instructions = config.instructions
    if domain_prompt:
        instructions = f"{instructions}\n\n{domain_prompt}"

    if fmt in ("vscode", "both"):
        agents_dir = out / ".github" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        vscode_path = agents_dir / f"{config.name}.agent.md"
        vscode_path.write_text(
            _make_vscode_agent_md(config, instructions, tools_vscode),
            encoding="utf-8",
        )

        instructions_dir = out / ".github" / "instructions"
        instructions_dir.mkdir(parents=True, exist_ok=True)
        inst_path = instructions_dir / f"{config.name}.instructions.md"
        inst_path.write_text(instructions, encoding="utf-8")

        logger.info("Wrote VS Code agent: %s", vscode_path)

    if fmt in ("claude", "both"):
        claude_dir = out / ".claude" / "agents"
        claude_dir.mkdir(parents=True, exist_ok=True)
        claude_path = claude_dir / f"{config.name}.md"
        claude_path.write_text(
            _make_claude_agent_md(config, instructions, tools_claude),
            encoding="utf-8",
        )
        logger.info("Wrote Claude agent: %s", claude_path)

    return out
