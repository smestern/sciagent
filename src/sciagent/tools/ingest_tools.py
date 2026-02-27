"""
ingest_tools — Runtime library documentation ingestion for any sciagent.

Provides an ``ingest_library_docs`` tool that lets a running agent
deep-crawl a Python package's documentation (ReadTheDocs, GitHub,
PyPI) and produce a structured API reference in ``library_api.md``
format.  The result is written to the agent's ``docs_dir`` so it
becomes immediately available via ``read_doc(name)``.

Requires the ``sciagent[wizard]`` extra.  If the wizard package is
not installed, the tool returns a helpful error message.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .registry import tool
from .doc_tools import get_docs_dir

logger = logging.getLogger(__name__)


@tool(
    name="ingest_library_docs",
    description=(
        "Deep-crawl documentation for a Python package and generate "
        "a structured API reference document. Crawls ReadTheDocs API "
        "pages, GitHub source code, and PyPI metadata, then uses an "
        "LLM to extract classes, functions, pitfalls, and recipes "
        "into a standard reference format.\n\n"
        "The generated document is saved to the agent's docs directory "
        "and becomes available via read_doc(name). Use this when you "
        "need detailed API information about a library you want to "
        "work with.\n\n"
        "Example: ingest_library_docs(package_name='scipy') will "
        "produce a 'scipy_api.md' reference in your docs folder."
    ),
    parameters={
        "type": "object",
        "properties": {
            "package_name": {
                "type": "string",
                "description": (
                    "The PyPI package name (e.g. 'numpy', 'pandas', "
                    "'scikit-learn')."
                ),
            },
            "github_url": {
                "type": "string",
                "description": (
                    "Optional GitHub repository URL for deeper source-code "
                    "analysis. If omitted, the tool will try to discover "
                    "it from PyPI metadata."
                ),
            },
        },
        "required": ["package_name"],
    },
)
def ingest_library_docs(
    package_name: str,
    github_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Ingest library documentation and write to docs_dir.

    Parameters
    ----------
    package_name : str
        PyPI package name.
    github_url : str, optional
        GitHub repository URL for deeper crawling.

    Returns
    -------
    dict
        ``{"status": "success", "doc_name": ..., "path": ...}``
        on success, or ``{"error": ...}`` on failure.
    """
    # Check that the docs ingestor is available (via plugin system)
    from sciagent.plugins import get_tool_provider

    _provider = get_tool_provider("ingest_package_docs_sync")
    if _provider is None:
        return {
            "error": (
                "The docs ingestor requires the sciagent-wizard package. "
                "Install it with: pip install sciagent-wizard"
            ),
        }
    ingest_package_docs_sync = _provider()

    # Determine output directory
    docs_dir = get_docs_dir()
    if docs_dir is None:
        # Try to use the execution context's output_dir
        try:
            from .context import get_active_context
            ctx = get_active_context()
            if ctx and ctx.output_dir:
                docs_dir = ctx.output_dir / "docs"
                docs_dir.mkdir(parents=True, exist_ok=True)
                # Also set it for read_doc
                from .doc_tools import set_docs_dir
                set_docs_dir(docs_dir)
                logger.info("Created docs_dir at %s", docs_dir)
        except Exception:
            pass

    if docs_dir is None:
        return {
            "error": (
                "No docs directory configured. Set docs_dir in your agent's "
                "config or call set_docs_dir() first."
            ),
        }

    # Run the ingestor
    try:
        markdown = ingest_package_docs_sync(package_name, github_url)
    except Exception as exc:
        logger.exception("Docs ingestion failed for %s", package_name)
        return {"error": f"Ingestion failed: {exc}"}

    if not markdown or len(markdown) < 50:
        return {
            "error": f"Ingestion produced no meaningful content for {package_name}.",
        }

    # Write to docs_dir
    safe_name = package_name.replace("-", "_").replace(" ", "_").lower()
    doc_name = f"{safe_name}_api"
    doc_path = Path(docs_dir) / f"{doc_name}.md"

    try:
        doc_path.write_text(markdown, encoding="utf-8")
    except Exception as exc:
        return {"error": f"Failed to write doc file: {exc}"}

    word_count = len(markdown.split())
    logger.info(
        "Ingested %s API docs → %s (%d words)",
        package_name, doc_path, word_count,
    )

    return {
        "status": "success",
        "doc_name": doc_name,
        "path": str(doc_path),
        "word_count": word_count,
        "message": (
            f"API reference for {package_name} has been saved as "
            f"'{doc_name}'. You can now use read_doc('{doc_name}') "
            f"to access it."
        ),
    }
