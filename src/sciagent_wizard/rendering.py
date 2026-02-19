"""
template_renderer — Load and render agent documentation templates.

Templates are plain Markdown files stored in the ``templates/`` directory
alongside this module.  They use HTML-comment placeholders::

    <!-- REPLACE: key — Human-readable description and example -->
    <!-- REPEAT: name -->  ... section ...  <!-- END_REPEAT -->

The renderer performs simple string substitution from a context dict built
from :class:`~sciagent_wizard.models.WizardState`.  Unfilled placeholders
are **left intact** so the output is always valid Markdown and can be
completed manually.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from sciagent_wizard.models import WizardState

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# ── Regex patterns ──────────────────────────────────────────────────────

# Matches:  <!-- REPLACE: key — description -->
#   group 1 = key
#   group 2 = description (optional)
_REPLACE_RE = re.compile(
    r"<!--\s*REPLACE:\s*(\w+)\s*(?:—\s*(.*?))?\s*-->",
    re.DOTALL,
)

# Matches:  <!-- REPEAT: name --> ... <!-- END_REPEAT -->
_REPEAT_RE = re.compile(
    r"(<!--\s*REPEAT:\s*(\w+)\s*(?:—[^>]*)?\s*-->)"  # open
    r"(.*?)"  # body
    r"(<!--\s*END_REPEAT\s*-->)",  # close
    re.DOTALL,
)

# ── Template names ──────────────────────────────────────────────────────

TEMPLATE_FILES = [
    "agents.md",
    "operations.md",
    "skills.md",
    "tools.md",
    "library_api.md",
    "workflows.md",
]


# ── Public API ──────────────────────────────────────────────────────────


def render_template(
    template_name: str,
    context: Dict[str, str],
    repeat_context: Optional[Dict[str, List[Dict[str, str]]]] = None,
) -> str:
    """Render a single template with the given context.

    Args:
        template_name: Filename inside the ``templates/`` directory
            (e.g. ``"agents.md"``).
        context: ``{placeholder_key: replacement_text}``.  Keys that don't
            appear in the template are silently ignored.  Placeholders
            whose keys are *not* in *context* are left untouched.
        repeat_context: ``{repeat_name: [row_context, ...]}``. Each item
            in the list is a context dict applied to one copy of the
            repeated section.  If ``None`` or missing for a given repeat
            block, the block is left as-is (with its example content).

    Returns:
        The rendered Markdown string.
    """
    path = _TEMPLATES_DIR / template_name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    text = path.read_text(encoding="utf-8")
    return _render(text, context, repeat_context or {})


def render_docs(
    state: WizardState,
    output_dir: Path,
) -> List[Path]:
    """Render all documentation templates from wizard state and write them.

    Args:
        state: Populated ``WizardState``.
        output_dir: Directory to write the rendered ``.md`` files into.
            Created if it doesn't exist.

    Returns:
        List of paths to the written files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    context = _build_context(state)
    repeat_ctx = _build_repeat_context(state)
    written: List[Path] = []

    for name in TEMPLATE_FILES:
        try:
            rendered = render_template(name, context, repeat_ctx)
            dest = output_dir / name
            dest.write_text(rendered, encoding="utf-8")
            written.append(dest)
            logger.debug("Wrote template %s → %s", name, dest)
        except Exception as exc:
            logger.warning("Failed to render template %s: %s", name, exc)

    logger.info(
        "Rendered %d/%d documentation templates to %s",
        len(written),
        len(TEMPLATE_FILES),
        output_dir,
    )
    return written


def copy_blank_templates(output_dir: Path) -> List[Path]:
    """Copy the raw (unfilled) template files to *output_dir*.

    Useful for users who want to fill them in manually.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for name in TEMPLATE_FILES:
        src = _TEMPLATES_DIR / name
        if src.exists():
            dest = output_dir / name
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            written.append(dest)
    # Also copy the README
    readme = _TEMPLATES_DIR / "README.md"
    if readme.exists():
        dest = output_dir / "TEMPLATES_README.md"
        dest.write_text(readme.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(dest)
    return written


# ── Internal helpers ────────────────────────────────────────────────────


def _render(
    text: str,
    context: Dict[str, str],
    repeat_context: Dict[str, List[Dict[str, str]]],
) -> str:
    """Apply REPEAT expansion first, then REPLACE substitution."""

    # 1. Expand REPEAT blocks
    def _expand_repeat(m: re.Match) -> str:
        name = m.group(2)
        body = m.group(3)

        rows = repeat_context.get(name)
        if not rows:
            # No data — leave the block intact as a template example
            return m.group(0)

        parts: List[str] = []
        for row_ctx in rows:
            rendered_body = body
            for key, value in row_ctx.items():
                rendered_body = _replace_key(rendered_body, key, value)
            parts.append(rendered_body)

        return "\n".join(parts)

    text = _REPEAT_RE.sub(_expand_repeat, text)

    # 2. Apply top-level REPLACE substitutions
    for key, value in context.items():
        text = _replace_key(text, key, value)

    return text


def _replace_key(text: str, key: str, value: str) -> str:
    """Replace all ``<!-- REPLACE: key ... -->`` occurrences with *value*.

    The description after the key may span multiple lines and may contain
    ``>`` characters (e.g. Markdown block-quotes, return-type arrows),
    so we match non-greedily up to the closing ``-->``.
    """
    pattern = re.compile(
        r"<!--\s*REPLACE:\s*"
        + re.escape(key)
        + r"\s*(?:—.*?)?\s*-->",
        re.DOTALL,
    )
    return pattern.sub(value, text)


# ── Context builders ────────────────────────────────────────────────────


def _build_context(state: WizardState) -> Dict[str, str]:
    """Build a flat replacement context from wizard state."""
    ctx: Dict[str, str] = {}

    # ── agents.md ───────────────────────────────────────────────────
    if state.agent_display_name:
        ctx["agent_overview_table"] = _build_agent_overview_table(state)

    # ── operations.md ───────────────────────────────────────────────
    if state.research_goals:
        workflows = "\n".join(f"- {g}" for g in state.research_goals)
        ctx["standard_workflows"] = (
            f"### Research-Driven Workflows\n\n"
            f"Based on the research goals for this agent:\n\n{workflows}\n\n"
            f"Design your analysis workflows to address these goals "
            f"systematically."
        )

    if state.bounds:
        rows = [
            "| Parameter | Default Range | Context |",
            "|-----------|---------------|---------|"]
        for param, (lo, hi) in state.bounds.items():
            rows.append(
                f"| {param} | {lo} – {hi} | Expected range |"
            )
        ctx["analysis_parameters"] = "\n".join(rows)

        precision_rows = [
            "| Measurement | Precision | Units |",
            "|-------------|-----------|-------|",
        ]
        for param in state.bounds:
            precision_rows.append(f"| {param} | appropriate | domain units |")
        ctx["reporting_precision_table"] = "\n".join(precision_rows)

    # ── tools.md ────────────────────────────────────────────────────
    if state.confirmed_packages:
        toc_lines = []
        for pkg in state.confirmed_packages:
            anchor = (
                pkg.name.lower()
                .replace(" ", "-")
                .replace("_", "-")
                + "-tools"
            )
            desc = pkg.description[:60]
            toc_lines.append(
                f"- [{pkg.name} Tools](#{anchor}) — {desc}"
            )
        ctx["tool_categories_toc"] = "\n".join(toc_lines)

    # ── library_api.md ──────────────────────────────────────────────
    if state.confirmed_packages:
        primary = state.confirmed_packages[0]
        ctx["library_display_name"] = primary.name
        if primary.homepage:
            ctx["library_source_url"] = primary.homepage
        if primary.repository_url:
            ctx["library_docs_url"] = primary.repository_url
        elif primary.homepage:
            ctx["library_docs_url"] = primary.homepage

        # Build TOC from package docs if available
        if primary.name in state.package_docs:
            ctx["library_toc"] = (
                "1. [Overview](#1-overview)\n"
                "2. [API Reference](#2-api-reference)\n"
                "3. [Common Pitfalls](#3-common-pitfalls)\n"
                "4. [Quick-Start Recipes]"
                "(#4-quick-start-recipes)"
            )

    # ── workflows.md ────────────────────────────────────────────────
    if state.research_goals:
        overview_rows = [
            "| Workflow | Purpose | Key Steps |",
            "|----------|---------|-----------|",
        ]
        for i, goal in enumerate(state.research_goals, 1):
            overview_rows.append(
                f"| Workflow {i} | {goal[:60]} "
                f"| Load → Validate → Analyse → Report |"
            )
        ctx["workflow_overview_table"] = "\n".join(overview_rows)

    # ── skills.md ───────────────────────────────────────────────────
    if state.confirmed_packages:
        skills_rows = [
            "| Skill | Location | Description |",
            "|-------|----------|-------------|",
        ]
        for pkg in state.confirmed_packages:
            skills_rows.append(
                f"| {pkg.name} Analysis | tools/ | "
                f"Analysis using {pkg.name} |"
            )
        ctx["skills_overview_table"] = "\n".join(skills_rows)

    return ctx


def _build_repeat_context(
    state: WizardState,
) -> Dict[str, List[Dict[str, str]]]:
    """Build repeat-block contexts from wizard state."""
    repeat: Dict[str, List[Dict[str, str]]] = {}

    # ── tool_category (one per confirmed package) ───────────────────
    if state.confirmed_packages:
        categories: List[Dict[str, str]] = []
        for pkg in state.confirmed_packages:
            mod = pkg.pip_name.replace("-", "_")
            cat_ctx: Dict[str, str] = {
                "tool_category_name": f"{pkg.name} Tools",
                "tool_name": f"run_{mod}",
                "tool_short_description": (
                    f"Execute analysis code using the {pkg.name} library."
                ),
                "tool_signature": (
                    f"run_{mod}(code: str) -> str"
                ),
                "tool_parameters_table": (
                    "| Name | Type | Default | Description |\n"
                    "|------|------|---------|-------------|\n"
                    f"| code | str | required | Python code using {pkg.name} |"
                ),
                "tool_returns": (
                    "{\n"
                    '    "output": str,      # stdout from code execution\n'
                    '    "error": str,        # stderr (if any)\n'
                    '    "figures": list      # paths to generated figures\n'
                    "}"
                ),
            }
            categories.append(cat_ctx)
        repeat["tool_category"] = categories

    # ── skill_section (one per confirmed package) ───────────────────
    if state.confirmed_packages:
        skills: List[Dict[str, str]] = []
        for pkg in state.confirmed_packages:
            skill_ctx: Dict[str, str] = {
                "skill_name": f"{pkg.name} Analysis",
                "skill_file_path": f"skills/{pkg.pip_name}/",
                "skill_purpose": (
                    f"Perform analysis using the {pkg.name} library. "
                    f"{pkg.description[:100]}"
                ),
                "skill_capabilities": (
                    f"- Load and process data using {pkg.name}\n"
                    f"- Extract domain-specific features and measurements\n"
                    f"- Generate visualisations of results"
                ),
                "skill_trigger_keywords": (
                    f"{pkg.name.lower()}, analyse, analyze, extract, measure"
                ),
            }
            skills.append(skill_ctx)
        repeat["skill_section"] = skills

    # ── workflow_section (one per research goal) ────────────────────
    if state.research_goals:
        workflows: List[Dict[str, str]] = []
        for i, goal in enumerate(state.research_goals, 1):
            wf_ctx: Dict[str, str] = {
                "workflow_name": f"Workflow {i}: {goal[:50]}",
                "workflow_purpose": goal,
                "workflow_when_to_use": (
                    f'- User asks about "{goal[:40]}"\n'
                    f"- Data is appropriate for this type of analysis"
                ),
                "workflow_steps": (
                    "```\n"
                    "1. Load and inspect data\n"
                    "2. Validate data quality\n"
                    f"3. Run analysis for: {goal[:60]}\n"
                    "4. Validate results against expected ranges\n"
                    "5. Generate summary with visualisations\n"
                    "6. Export results\n"
                    "```"
                ),
                "workflow_parameters": (
                    "| Parameter | Default | Description |\n"
                    "|-----------|---------|-------------|\n"
                    "| *configure per workflow* | | |"
                ),
                "workflow_outputs": (
                    "- Summary table of results\n"
                    "- Visualisation figures\n"
                    "- Exported data files"
                ),
            }
            workflows.append(wf_ctx)
        repeat["workflow_section"] = workflows

    return repeat


def _build_agent_overview_table(state: WizardState) -> str:
    """Build the agent overview table for agents.md.

    Includes the 5 default sciagent agents plus the domain-specific main
    agent from the wizard conversation.
    """
    rows = [
        "| Agent | Role | Primary Skills |",
        "|-------|------|----------------|",
        f"| {state.agent_name} | Main coordinator | All skills |",
        "| analysis-planner | Analysis roadmap designer | Planning, incremental validation |",
        "| data-qc | Data quality gatekeeper | QC checks, outlier detection |",
        "| rigor-reviewer | Scientific rigor auditor | Statistical review, integrity checks |",
        "| report-writer | Report generator | Structured reports, figures, tables |",
        "| code-reviewer | Script correctness auditor | Code review, reproducibility |",
    ]
    return "\n".join(rows)
