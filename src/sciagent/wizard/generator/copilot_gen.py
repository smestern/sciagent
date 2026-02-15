"""
copilot_gen — Generate VS Code custom agent + Claude Code sub-agent configs.

Produces a directory with:

    .github/agents/<name>.agent.md      VS Code Copilot custom agent
    .claude/agents/<name>.md            Claude Code sub-agent
    .github/instructions/<name>.instructions.md   Shared instructions
    docs/                                Package documentation
    README.md
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..models import WizardState
from .docs_gen import write_docs
from .prompt_gen import _build_expertise_text
from .template_renderer import render_docs as render_doc_templates

logger = logging.getLogger(__name__)


def generate_copilot_project(
    state: WizardState,
    output_dir: Optional[str | Path] = None,
) -> Path:
    """Generate a VS Code / Claude Code agent config project.

    Args:
        state: Populated ``WizardState``.
        output_dir: Parent directory. Defaults to CWD.

    Returns:
        Path to the generated project directory.
    """
    base = Path(output_dir) if output_dir else Path.cwd()
    slug = state.agent_name.replace(" ", "_").replace("-", "_")
    project_dir = base / slug
    project_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Generating copilot/claude agent config in %s", project_dir)

    # ── Shared domain expertise (instructions) ──────────────────────
    expertise = _build_expertise_text(state)
    docs_ref = _docs_reference(state)
    full_instructions = expertise
    if docs_ref:
        full_instructions += "\n\n" + docs_ref

    # ── .github/instructions/<name>.instructions.md ─────────────────
    instructions_dir = project_dir / ".github" / "instructions"
    instructions_dir.mkdir(parents=True, exist_ok=True)
    instructions_path = instructions_dir / f"{state.agent_name}.instructions.md"
    instructions_path.write_text(full_instructions, encoding="utf-8")

    # ── .github/agents/<name>.agent.md (VS Code format) ─────────────
    agents_dir = project_dir / ".github" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    vscode_path = agents_dir / f"{state.agent_name}.agent.md"
    vscode_path.write_text(
        _vscode_agent_md(state, full_instructions), encoding="utf-8"
    )

    # ── .claude/agents/<name>.md (Claude Code format) ───────────────
    claude_dir = project_dir / ".claude" / "agents"
    claude_dir.mkdir(parents=True, exist_ok=True)
    claude_path = claude_dir / f"{state.agent_name}.md"
    claude_path.write_text(
        _claude_agent_md(state, full_instructions), encoding="utf-8"
    )

    # ── Package docs ────────────────────────────────────────────────
    docs_dir = project_dir / "docs"
    render_doc_templates(state, docs_dir)
    if state.package_docs:
        write_docs(state, docs_dir)

    # ── README ──────────────────────────────────────────────────────
    readme_path = project_dir / "README.md"
    readme_path.write_text(_readme(state), encoding="utf-8")

    state.project_dir = str(project_dir)
    logger.info("Copilot/Claude agent config generated: %s", project_dir)
    return project_dir


# ── VS Code .agent.md ──────────────────────────────────────────────────


def _vscode_agent_md(state: WizardState, instructions: str) -> str:
    """Generate a VS Code custom agent file (.agent.md format)."""
    # Tools: map to VS Code built-in tool names
    tools = [
        "codebase",       # search/read workspace files
        "terminal",       # run commands (pip, python, etc.)
        "search",         # web search
        "fetch",          # fetch URLs
        "editFiles",      # create/edit files
        "findTestFiles",  # discover test files
    ]
    tools_yaml = "\n".join(f"  - {t}" for t in tools)

    # Handoffs: suggest a planning → implementation flow
    handoffs_yaml = ""
    if state.agent_name:
        handoffs_yaml = f"""handoffs:
  - label: "Plan Analysis"
    agent: {state.agent_name}-planner
    prompt: "Create an analysis plan for the data using the available domain packages."
    send: false
  - label: "Review Results"
    agent: {state.agent_name}-reviewer
    prompt: "Review the analysis results and check for any issues."
    send: false"""

    frontmatter = f"""---
description: >-
  {state.agent_description}
name: {state.agent_name}
tools:
{tools_yaml}
{handoffs_yaml}
---"""

    return f"{frontmatter}\n\n{instructions}\n"


# ── Claude Code sub-agent .md ──────────────────────────────────────────


def _claude_agent_md(state: WizardState, instructions: str) -> str:
    """Generate a Claude Code sub-agent file (.md with YAML frontmatter)."""
    tools = "Read, Write, Edit, Bash, Grep, Glob"

    frontmatter = f"""---
name: {state.agent_name}
description: >-
  {state.agent_description}
tools: {tools}
model: sonnet
---"""

    return f"{frontmatter}\n\n{instructions}\n"


# ── Helpers ─────────────────────────────────────────────────────────────


def _docs_reference(state: WizardState) -> str:
    """Build a section pointing the agent to the local docs."""
    if not state.package_docs:
        return ""
    lines = [
        "### Package Documentation",
        "",
        "Local reference documentation is available in the `docs/` directory "
        "for each installed library. Consult these docs when you need "
        "detailed API information or usage examples:",
        "",
    ]
    for name in sorted(state.package_docs.keys()):
        lines.append(f"- `docs/{name.lower().replace(' ', '_')}.md`")
    return "\n".join(lines)


def _readme(state: WizardState) -> str:
    """Generate a README for the copilot/claude agent project."""
    slug = state.agent_name
    pkgs = "\n".join(
        f"- **{p.name}**: {p.description[:80]}"
        for p in state.confirmed_packages
    )

    return f"""\
# {state.agent_display_name}

{state.agent_description}

> Auto-generated by the **sciagent self-assembly wizard**.

## Output Mode: Copilot / Claude Code Agent

This project contains agent configuration files for use with:

### VS Code GitHub Copilot

The custom agent is defined in `.github/agents/{slug}.agent.md`.

To use it:
1. Copy this project into your workspace
2. Open VS Code with GitHub Copilot enabled
3. Select **{state.agent_display_name}** from the Agents dropdown in chat

### Claude Code

The sub-agent is defined in `.claude/agents/{slug}.md`.

To use it:
1. Copy the `.claude/agents/` folder into your project
2. Run Claude Code — it will auto-detect the sub-agent
3. Ask Claude to use the **{state.agent_name}** agent

### Shared Instructions

Domain expertise and instructions are in:
`.github/instructions/{slug}.instructions.md`

### Package Documentation

Local docs for each domain package are in `docs/`.

## Domain Packages

{pkgs or "No additional packages configured."}
"""
