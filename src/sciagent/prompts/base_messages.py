"""
Base system-message building blocks for scientific coding agents.

These are *domain-agnostic* principles and policies.  Domain-specific
agents compose these with their own expertise sections via
:func:`build_system_message`.

Prompt text lives in sibling ``.md`` files (easy to read, edit, and diff).
The module loads them once at import time and re-exports the same public
names as before, so downstream code is unchanged.
"""

from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent


def _load(name: str) -> str:
    """Read a Markdown prompt file from the prompts directory."""
    return (_PROMPT_DIR / name).read_text(encoding="utf-8")


# ── Generic scientific-rigor principles ─────────────────────────────────
BASE_SCIENTIFIC_PRINCIPLES = _load("scientific_rigor.md")

# ── Code-execution policy ───────────────────────────────────────────────
CODE_EXECUTION_POLICY = _load("code_execution.md")

# ── OUTPUT_DIR policy ───────────────────────────────────────────────────
OUTPUT_DIR_POLICY = _load("output_dir.md")

# ── Reproducible script generation ──────────────────────────────────────
REPRODUCIBLE_SCRIPT_POLICY = _load("reproducible_script.md")

# ── Thinking out loud ──────────────────────────────────────────────────
THINKING_OUT_LOUD_POLICY = _load("thinking_out_loud.md")

# ── Communication style ────────────────────────────────────────────────
COMMUNICATION_STYLE_POLICY = _load("communication_style.md")

# ── Incremental execution ──────────────────────────────────────────────
INCREMENTAL_EXECUTION_POLICY = _load("incremental_execution.md")


def build_system_message(
    *sections: str,
    base_principles: bool = True,
    code_policy: bool = True,
    output_dir_policy: bool = True,
    reproducible_script_policy: bool = True,
    incremental_policy: bool = True,
    thinking_policy: bool = True,
    communication_policy: bool = True,
) -> str:
    """Compose a system message from generic policies + domain sections.

    Usage::

        msg = build_system_message(
            MY_DOMAIN_EXPERTISE,
            MY_TOOL_INSTRUCTIONS,
            MY_WORKFLOW,
        )

    The ``base_principles``, ``code_policy``, etc. flags control whether
    the corresponding generic section is prepended automatically.

    Args:
        *sections: Domain-specific text blocks appended in order.
        base_principles: Include scientific rigor principles.
        code_policy: Include code-execution policy.
        output_dir_policy: Include OUTPUT_DIR instructions.
        reproducible_script_policy: Include reproducible script instructions.
        incremental_policy: Include incremental execution principle.
        thinking_policy: Include "think out loud" instructions.
        communication_policy: Include communication style guide.

    Returns:
        The assembled system message string.
    """
    parts: list[str] = []

    if base_principles:
        parts.append(BASE_SCIENTIFIC_PRINCIPLES)
    if code_policy:
        parts.append(CODE_EXECUTION_POLICY)
    if output_dir_policy:
        parts.append(OUTPUT_DIR_POLICY)
    if reproducible_script_policy:
        parts.append(REPRODUCIBLE_SCRIPT_POLICY)
    if incremental_policy:
        parts.append(INCREMENTAL_EXECUTION_POLICY)
    if thinking_policy:
        parts.append(THINKING_OUT_LOUD_POLICY)
    if communication_policy:
        parts.append(COMMUNICATION_STYLE_POLICY)

    parts.extend(sections)
    return "\n\n".join(parts)
