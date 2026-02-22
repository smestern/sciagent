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


def _make_skill_md(
    config: AgentConfig,
    instructions: str,
    *,
    argument_hint: Optional[str] = None,
    user_invokable: bool = True,
) -> str:
    """Generate a VS Code Agent Skill ``SKILL.md`` from an ``AgentConfig``.

    Skills follow the `agentskills.io <https://agentskills.io/>`_
    specification: YAML frontmatter with ``name``, ``description``, and
    optional ``argument-hint``, ``user-invokable``, followed by Markdown
    instructions in the body.
    """
    desc = config.description[:1024]  # spec max length
    hint = (
        argument_hint
        or f"Provide your data or results for"
        f" {config.display_name}."
    )

    lines = [
        "---",
        f"name: {config.name}",
        "description: >-",
        f"  {desc}",
        f"argument-hint: {hint}",
    ]
    if not user_invokable:
        lines.append("user-invokable: false")
    lines.append("---")
    lines.append("")

    # Rewrite instructions in skill-style (procedural guidelines)
    lines.append(f"# {config.display_name}")
    lines.append("")
    lines.append(instructions)
    lines.append("")
    lines.append("## Domain Customization")
    lines.append("")
    lines.append("<!-- Add domain-specific guidance below this line. -->")

    return "\n".join(lines) + "\n"


# ── Default skill template copying ──────────────────────────────────────

_DEFAULT_SKILLS = [
    "scientific-rigor",
    "analysis-planner",
    "data-qc",
    "rigor-reviewer",
    "report-writer",
    "code-reviewer",
]
"""Names of the 6 default skill directories
shipped in ``templates/skills/``."""


def _find_templates_skills_dir() -> Optional[Path]:
    """Locate the ``templates/skills/`` directory shipped with sciagent."""
    # Walk upward from this file to find the repo/package root
    here = Path(__file__).resolve().parent
    for ancestor in [
        here, here.parent,
        here.parent.parent,
        here.parent.parent.parent,
    ]:
        candidate = ancestor / "templates" / "skills"
        if candidate.is_dir():
            return candidate
    # Fallback: installed package — look relative to package data
    import importlib.resources as _res

    try:
        ref = _res.files("sciagent").joinpath("../../templates/skills")
        if Path(str(ref)).is_dir():
            return Path(str(ref))
    except Exception:
        pass
    return None


def copy_default_skills(output_dir: str | Path) -> List[Path]:
    """Copy the 6 default skill templates
    into ``<output_dir>/.github/skills/``.

    Returns:
        List of paths to the copied ``SKILL.md`` files.
    """
    import shutil

    src_root = _find_templates_skills_dir()
    if src_root is None:
        logger.warning(
            "Could not locate templates/skills/ directory — "
            "default skills will not be copied."
        )
        return []

    out = Path(output_dir)
    copied: List[Path] = []

    for skill_name in _DEFAULT_SKILLS:
        src_dir = src_root / skill_name
        if not src_dir.is_dir():
            logger.warning("Default skill directory not found: %s", src_dir)
            continue

        dst_dir = out / ".github" / "skills" / skill_name
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)
        copied.append(dst_dir / "SKILL.md")
        logger.info("Copied default skill: %s", dst_dir)

    return copied


def agent_to_copilot_files(
    config: AgentConfig,
    output_dir: str | Path,
    *,
    domain_prompt: str = "",
    tools_vscode: Optional[List[str]] = None,
    tools_claude: Optional[str] = None,
    fmt: str = "both",
    skills: bool = False,
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
        skills: If ``True``, also generate a VS Code Agent Skill
            (``SKILL.md``) alongside the agent files.

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

    if skills:
        skill_dir = out / ".github" / "skills" / config.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(
            _make_skill_md(config, instructions),
            encoding="utf-8",
        )
        logger.info("Wrote skill: %s", skill_path)

    return out
