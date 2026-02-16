"""
Wizard prompt templates — system messages for both normal and public/guided mode.

Prompt text lives in sibling ``.md`` files for readability and diffability.
This module loads them at import time and re-exports the same public names
(``WIZARD_EXPERTISE``, ``PUBLIC_WIZARD_EXPERTISE``) so downstream imports
are unchanged.
"""

from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent


def _load(name: str) -> str:
    """Read a Markdown prompt file from the prompts directory."""
    return (_PROMPT_DIR / name).read_text(encoding="utf-8")


# ── Wizard system prompt ───────────────────────────────────────────────
WIZARD_EXPERTISE = _load("wizard_expertise.md")

# ── Public / guided-mode system prompt ─────────────────────────────────
PUBLIC_WIZARD_EXPERTISE = _load("public_wizard_expertise.md")
