from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

from ..config import AgentConfig
from ..agents.converter import yaml_to_config

# Regex that matches YAML frontmatter delimited by ``---`` at the top of
# a file.  The first ``---`` must be the very first line; the closing
# ``---`` can appear anywhere after that.
_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n?",
    re.DOTALL,
)


def _load(name: str) -> str:
    """Read a Markdown prompt file from the prompts directory."""
    return Path(name).read_text(encoding="utf-8")


def _extract_frontmatter(md_text: str) -> Tuple[Dict[str, Any], str]:
    """Split *md_text* into a (frontmatter-dict, body) pair.

    If the text does not start with a ``---`` fenced YAML block the
    returned dict is empty and the full text is returned as the body.
    """
    match = _FRONTMATTER_RE.match(md_text)
    if match is None:
        return {}, md_text
    frontmatter: Dict[str, Any] = yaml.safe_load(match.group(1)) or {}
    body = md_text[match.end():]
    return frontmatter, body


def parse_agent_markdown(file: str) -> AgentConfig:
    """Parse a ``.agent.md`` file into an :class:`AgentConfig`.

    The file may contain YAML frontmatter between ``---`` delimiters at
    the top.  Recognised frontmatter keys (``name``, ``description``,
    ``model``, etc.) are mapped directly to :class:`AgentConfig` fields
    via :func:`~sciagent.agents.converter.yaml_to_config`.  Unknown keys
    (e.g. ``tools``, ``handoffs``) are silently ignored.

    The remaining Markdown body (everything after the closing ``---``) is
    stored as :attr:`AgentConfig.instructions`.

    If no frontmatter is present the entire file content is treated as
    instructions and all other fields take their defaults.
    """
    md_text = _load(file)
    frontmatter, body = _extract_frontmatter(md_text)

    # Inject the markdown body as instructions (frontmatter value wins
    # only if the body is empty).
    body = body.strip()
    if body:
        frontmatter.setdefault("instructions", body)

    if not frontmatter:
        # Plain markdown with no YAML block at all.
        return AgentConfig(instructions=md_text.strip())

    return yaml_to_config(frontmatter)
