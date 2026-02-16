"""
markdown_gen — Generate platform-agnostic markdown agent specification.

Produces a self-contained set of Markdown files that define the agent's
persona, tools, data handling, guardrails, and workflow. These can be
pasted into any LLM interface (ChatGPT, Gemini, Claude, local models)
to recreate the agent's behaviour without any framework dependency.

Output structure::

    <output>/<agent_slug>/
        agent-spec.md          Full agent specification (links all others)
        system-prompt.md       Raw system prompt for copy-paste
        tools-reference.md     Package/tool documentation
        data-guide.md          Supported formats, data structure, ranges
        guardrails.md          Bounds, forbidden patterns, safety policies
        workflow.md            Step-by-step analysis workflow
        docs/                  Package documentation
        README.md
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sciagent_wizard.models import WizardState
from .docs_gen import write_docs
from .prompt_gen import _build_expertise_text
from sciagent_wizard.rendering import render_docs as render_doc_templates

logger = logging.getLogger(__name__)


def generate_markdown_project(
    state: WizardState,
    output_dir: Optional[str | Path] = None,
) -> Path:
    """Generate a platform-agnostic markdown agent specification.

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

    logger.info("Generating markdown agent spec in %s", project_dir)

    _write = lambda name, content: (project_dir / name).write_text(
        content, encoding="utf-8"
    )

    _write("system-prompt.md", _system_prompt(state))
    _write("tools-reference.md", _tools_reference(state))
    _write("data-guide.md", _data_guide(state))
    _write("guardrails.md", _guardrails(state))
    _write("workflow.md", _workflow(state))
    _write("agent-spec.md", _agent_spec(state))
    _write("README.md", _readme(state))

    # Package docs
    docs_dir = project_dir / "docs"
    render_doc_templates(state, docs_dir)
    if state.package_docs:
        write_docs(state, docs_dir)

    state.project_dir = str(project_dir)
    logger.info("Markdown agent spec generated: %s", project_dir)
    return project_dir


# ── Individual file generators ──────────────────────────────────────────


def _system_prompt(state: WizardState) -> str:
    """Generate the raw system prompt (copy-paste ready)."""
    expertise = _build_expertise_text(state)
    return f"""\
# System Prompt — {state.agent_display_name}

> Copy this entire file into the system prompt of your preferred LLM.
> For best results, also provide the contents of `tools-reference.md`,
> `data-guide.md`, and `guardrails.md` in the conversation.

---

{expertise}

---

### Behaviour Guidelines

- You are **{state.agent_display_name}** {state.agent_emoji}
- {state.agent_description}
- Always use the domain-specific packages listed above rather than
  writing custom implementations.
- Validate all data before analysis — check for missing values, outliers,
  and format errors.
- When generating code, include all necessary imports and make the code
  reproducible.
- Explain your analysis choices and any assumptions you make.
- If you're uncertain about a domain-specific detail, say so and suggest
  how to verify.
"""


def _tools_reference(state: WizardState) -> str:
    """Document available packages and how to use them."""
    lines = [
        f"# Tools & Packages Reference — {state.agent_display_name}",
        "",
        "This document lists all domain-specific Python packages available",
        "for analysis. Use these packages in your code rather than writing",
        "custom implementations.",
        "",
    ]

    for pkg in state.confirmed_packages:
        mod = pkg.pip_name.replace("-", "_")
        lines.extend([
            f"## {pkg.name}",
            "",
            f"- **Install**: `{pkg.install_command or f'pip install {pkg.pip_name}'}`",
            f"- **Import**: `import {mod}`",
        ])
        if pkg.description:
            lines.extend(["", pkg.description[:300]])
        if pkg.homepage:
            lines.append(f"- **Homepage**: {pkg.homepage}")
        if pkg.repository_url:
            lines.append(f"- **Repository**: {pkg.repository_url}")

        # Reference to detailed docs if available
        if pkg.name in state.package_docs:
            safe = pkg.name.lower().replace(" ", "_").replace("-", "_")
            lines.append(f"- **Detailed docs**: [docs/{safe}.md](docs/{safe}.md)")

        lines.extend(["", "---", ""])

    if not state.confirmed_packages:
        lines.append("*No domain-specific packages configured.*")

    return "\n".join(lines)


def _data_guide(state: WizardState) -> str:
    """Document supported data formats and structure."""
    lines = [
        f"# Data Guide — {state.agent_display_name}",
        "",
        "## Supported File Types",
        "",
    ]

    if state.accepted_file_types:
        for ft in state.accepted_file_types:
            lines.append(f"- `{ft}`")
    else:
        lines.append("- `.csv` (default)")

    lines.extend(["", "## Data Structure", ""])

    if state.example_files:
        for fi in state.example_files:
            lines.append(f"### {fi.extension.upper()} files")
            if fi.columns:
                cols = ", ".join(f"`{c}`" for c in fi.columns[:30])
                lines.append(f"- **Columns**: {cols}")
            if fi.row_count:
                lines.append(f"- **Typical row count**: ~{fi.row_count}")
            if fi.dtypes:
                type_items = ", ".join(
                    f"`{k}`: {v}" for k, v in list(fi.dtypes.items())[:10]
                )
                lines.append(f"- **Data types**: {type_items}")
            if fi.value_ranges:
                lines.append("- **Value ranges**:")
                for param, (lo, hi) in fi.value_ranges.items():
                    lines.append(f"  - `{param}`: {lo} – {hi}")
            if fi.inferred_domain_hints:
                hints = ", ".join(fi.inferred_domain_hints)
                lines.append(f"- **Domain patterns**: {hints}")
            lines.append("")
    else:
        lines.append(
            "No example data has been analyzed. Inspect the data structure "
            "before starting analysis."
        )

    # Expected value ranges (if bounds are set)
    if state.bounds:
        lines.extend(["", "## Expected Value Ranges", ""])
        lines.append(
            "Values outside these ranges should be flagged as potentially "
            "erroneous:"
        )
        lines.append("")
        for param, (lo, hi) in state.bounds.items():
            lines.append(f"- **{param}**: {lo} – {hi}")

    return "\n".join(lines)


def _guardrails(state: WizardState) -> str:
    """Document safety guardrails and validation policies."""
    lines = [
        f"# Guardrails & Safety — {state.agent_display_name}",
        "",
        "## Data Validation",
        "",
        "Before analysing data, always:",
        "",
        "1. Check for missing values (NaN, None, empty strings)",
        "2. Check for infinite values",
        "3. Check for zero-variance columns",
        "4. Verify data types match expectations",
        "5. Check value ranges against expected bounds (see below)",
        "",
    ]

    if state.bounds:
        lines.extend([
            "## Value Range Checks",
            "",
            "Flag values outside these ranges:",
            "",
        ])
        for param, (lo, hi) in state.bounds.items():
            lines.append(f"- **{param}**: expected {lo} – {hi}")
        lines.append("")

    if state.forbidden_patterns:
        lines.extend([
            "## Forbidden Patterns",
            "",
            "Never generate code that matches these patterns:",
            "",
        ])
        for pat, msg in state.forbidden_patterns:
            lines.append(f"- `{pat}`: {msg}")
        lines.append("")

    if state.warning_patterns:
        lines.extend([
            "## Warning Patterns",
            "",
            "These patterns should trigger a warning — proceed with caution:",
            "",
        ])
        for pat, msg in state.warning_patterns:
            lines.append(f"- `{pat}`: {msg}")
        lines.append("")

    lines.extend([
        "## Code Safety",
        "",
        "- Never generate synthetic data to replace real experimental data",
        "- Never manipulate results to achieve a desired statistical outcome",
        "- Always preserve raw data — work on copies",
        "- Include error handling in all analysis code",
        "- Make all analysis steps reproducible",
    ])

    return "\n".join(lines)


def _workflow(state: WizardState) -> str:
    """Describe the recommended analysis workflow."""
    lines = [
        f"# Analysis Workflow — {state.agent_display_name}",
        "",
        "Follow this workflow for rigorous scientific analysis:",
        "",
        "## 1. Data Loading",
        "",
        "- Load the data file and inspect its structure",
        "- Verify file format matches expected types",
        "- Display the first few rows / summary statistics",
        "",
        "## 2. Data Validation",
        "",
        "- Check for missing values, outliers, and format errors",
        "- Validate value ranges against expected bounds",
        "- Report any data quality issues before proceeding",
        "",
        "## 3. Analysis",
        "",
        "- Use the domain-specific packages for analysis",
        "- Prefer established library functions over custom code",
        "- Document each analysis step with comments",
        "",
    ]

    if state.confirmed_packages:
        lines.append("Available packages for analysis:")
        lines.append("")
        for pkg in state.confirmed_packages:
            lines.append(f"- **{pkg.name}**: {pkg.description[:80]}")
        lines.append("")

    lines.extend([
        "## 4. Visualisation",
        "",
        "- Generate clear, labelled plots for all results",
        "- Include axis labels, titles, and legends",
        "- Use appropriate plot types for the data",
        "- Save figures to the output directory",
        "",
        "## 5. Results & Export",
        "",
        "- Summarise key findings",
        "- Export results in a standard format (CSV, JSON)",
        "- Generate a reproducible script that captures the full analysis",
        "- Include all parameters and settings used",
    ])

    return "\n".join(lines)


def _agent_spec(state: WizardState) -> str:
    """Master specification that ties everything together."""
    return f"""\
# {state.agent_display_name} — Agent Specification

{state.agent_emoji} **{state.agent_display_name}**

{state.agent_description}

> Auto-generated by the **sciagent self-assembly wizard**.
> These files define a platform-agnostic scientific analysis agent.
> You can use them with any LLM (ChatGPT, Claude, Gemini, local models, etc.).

## How to Use

### Quick Start (any LLM)
1. Copy the contents of [system-prompt.md](system-prompt.md) into your LLM's system prompt
2. Refer to [tools-reference.md](tools-reference.md) for available packages
3. Follow [workflow.md](workflow.md) for the recommended analysis flow

### Full Context
For best results, provide the LLM with all of these files:
- [system-prompt.md](system-prompt.md) — Core system prompt and persona
- [tools-reference.md](tools-reference.md) — Available packages and APIs
- [data-guide.md](data-guide.md) — Supported data formats and structure
- [guardrails.md](guardrails.md) — Safety constraints and validation rules
- [workflow.md](workflow.md) — Step-by-step analysis workflow

### Package Documentation
Detailed documentation for each domain package is in `docs/`:
{"".join(chr(10) + f"- [docs/{n.lower().replace(' ', '_')}.md](docs/{n.lower().replace(' ', '_')}.md)" for n in sorted(state.package_docs.keys())) if state.package_docs else chr(10) + "*No package docs generated.*"}

### Extended Reference Documentation
The `docs/` directory also contains detailed reference templates:
- [docs/agents.md](docs/agents.md) — Sub-agent roster and roles
- [docs/operations.md](docs/operations.md) — Standard operating procedures
- [docs/skills.md](docs/skills.md) — Skill overview and trigger keywords
- [docs/tools.md](docs/tools.md) — Tool API reference
- [docs/library_api.md](docs/library_api.md) — Primary library reference
- [docs/workflows.md](docs/workflows.md) — Standard analysis workflows

## Agent Identity

| Field | Value |
|-------|-------|
| Name  | {state.agent_name} |
| Display Name | {state.agent_display_name} |
| Description | {state.agent_description} |
| Emoji | {state.agent_emoji} |

## Domain

{state.domain_description or "Not specified."}

## Research Goals

{"".join(chr(10) + f"- {g}" for g in state.research_goals) if state.research_goals else chr(10) + "Not specified."}

## Packages

| Package | Description | Install |
|---------|-------------|---------|
{"".join(f"| {p.name} | {p.description[:60]} | `{p.install_command}` |" + chr(10) for p in state.confirmed_packages) if state.confirmed_packages else "| *None* | | |" + chr(10)}
"""


def _readme(state: WizardState) -> str:
    """README for the markdown agent project."""
    return f"""\
# {state.agent_display_name}

{state.agent_description}

> Auto-generated by the **sciagent self-assembly wizard**.

## Output Mode: Platform-Agnostic Markdown

This project contains a complete agent specification in Markdown files.
These files are designed to work with **any** LLM platform — simply
paste the system prompt and relevant context into your preferred tool.

## Files

| File | Purpose |
|------|---------|
| `agent-spec.md` | Master specification linking everything |
| `system-prompt.md` | Core system prompt (copy-paste into any LLM) |
| `tools-reference.md` | Available packages and how to use them |
| `data-guide.md` | Supported data formats, structure, ranges |
| `guardrails.md` | Safety constraints and validation rules |
| `workflow.md` | Recommended step-by-step analysis workflow |
| `docs/` | Detailed package documentation |

## Quick Start

1. Open your preferred LLM (ChatGPT, Claude, Gemini, etc.)
2. Paste the contents of `system-prompt.md` as the system prompt
3. Start analysing your data!

For best results, also provide `tools-reference.md` and `data-guide.md`
in your conversation context.
"""
