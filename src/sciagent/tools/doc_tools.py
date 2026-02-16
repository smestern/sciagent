"""
doc_tools — Read reference documentation at runtime.

Provides a ``read_doc`` tool that lets the agent fetch full doc contents
on demand, keeping the system prompt lean while still giving access to
detailed API references, workflows, and parameter tables.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .registry import tool

logger = logging.getLogger(__name__)

# Module-level docs directory — set by the agent at startup.
_docs_dir: Optional[Path] = None


def set_docs_dir(path: str | Path | None) -> None:
    """Set the directory where documentation files are stored."""
    global _docs_dir
    if path is None:
        _docs_dir = None
    else:
        _docs_dir = Path(path).resolve()
    logger.debug("docs_dir set to %s", _docs_dir)


def get_docs_dir() -> Optional[Path]:
    """Return the currently configured docs directory."""
    return _docs_dir


@tool(
    name="read_doc",
    description=(
        "Read a reference document by name. Returns the full content "
        "of the requested document. Call with name='list' or no name "
        "to see all available documents. Use this to access detailed "
        "API references, parameter tables, and workflow guides."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": (
                    "Document name (e.g. 'IPFX', 'Tools', 'Operations'). "
                    "Use 'list' to see all available documents."
                ),
            },
        },
        "required": ["name"],
    },
)
def read_doc(name: str = "") -> Dict[str, Any]:
    """Read a reference document by name.

    Parameters
    ----------
    name : str
        Document name (case-insensitive, with or without ``.md`` extension).
        Use ``"list"`` or leave empty to see all available documents.

    Returns
    -------
    dict
        ``{"content": str, "path": str}`` on success, or
        ``{"error": str, "available": list[str]}`` on failure.
    """
    if _docs_dir is None:
        return {"error": "No docs directory configured for this agent."}

    if not _docs_dir.is_dir():
        return {"error": f"Docs directory not found: {_docs_dir}"}

    # Collect available docs
    available = sorted(
        p.stem for p in _docs_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".md"
    )

    # List mode
    if not name or name.strip().lower() == "list":
        return {
            "available_docs": available,
            "usage": "Call read_doc with one of the names above to read its full content.",
        }

    # Resolve the requested document
    clean = name.strip().removesuffix(".md").removesuffix(".MD")

    # Try exact match first, then case-insensitive
    target: Optional[Path] = None
    for candidate in _docs_dir.iterdir():
        if not candidate.is_file() or candidate.suffix.lower() != ".md":
            continue
        if candidate.stem == clean:
            target = candidate
            break
        if candidate.stem.lower() == clean.lower():
            target = candidate  # keep looking for exact match

    if target is None:
        return {
            "error": f"Document '{name}' not found.",
            "available": available,
        }

    try:
        content = target.read_text(encoding="utf-8")
    except Exception as exc:
        return {"error": f"Failed to read {target.name}: {exc}"}

    return {
        "content": content,
        "path": str(target),
        "name": target.stem,
    }


# ── Auto-generated docs summary for system prompt ───────────────


def _extract_description(path: Path, max_chars: int = 120) -> str:
    """Extract a short description from the first few lines of a doc.

    Looks for the first non-empty, non-heading line and returns it
    (truncated to *max_chars*).  Block-quote prefixes (``>``) are
    stripped so that front-matter like ``> **Purpose**: …`` is usable.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    for line in lines[1:]:          # skip the ``# Title`` line
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue
        # Strip block-quote prefix
        if stripped.startswith(">"):
            stripped = stripped.lstrip(">").strip()
            if not stripped:
                continue
        # Skip lines that are just markdown links / TOC entries
        if stripped.startswith("1.") or stripped.startswith("- ["):
            continue
        # Skip front-matter metadata lines (e.g. **Source**: ..., **Docs**: ...)
        if stripped.startswith("**") and "**:" in stripped:
            tag = stripped.split("**:")[0].strip("* ").lower()
            if tag in ("source", "docs", "version", "date", "author", "license"):
                continue
        if len(stripped) > max_chars:
            return stripped[:max_chars].rsplit(" ", 1)[0] + " …"
        return stripped
    return ""


def summarize_available_docs() -> str:
    """Return a markdown snippet listing every doc with a one-line summary.

    Intended to be injected into the system prompt so the LLM knows
    which documents are available via ``read_doc(name)``.

    Returns an empty string when no docs directory is configured or
    the directory is empty.
    """
    if _docs_dir is None or not _docs_dir.is_dir():
        return ""

    entries: list[str] = []
    for p in sorted(_docs_dir.iterdir()):
        if not p.is_file() or p.suffix.lower() != ".md":
            continue
        desc = _extract_description(p)
        entry = f'- **"{p.stem}"**'
        if desc:
            entry += f" — {desc}"
        entries.append(entry)

    if not entries:
        return ""

    return "\n".join(entries)
