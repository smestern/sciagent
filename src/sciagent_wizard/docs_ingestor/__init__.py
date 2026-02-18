"""
sciagent_wizard.docs_ingestor — Deep documentation ingestor.

Crawls ReadTheDocs, GitHub, and PyPI for a package's API surface,
then uses an LLM agent to produce a structured ``library_api.md``
reference.

Usage::

    # Programmatic (async)
    from sciagent_wizard.docs_ingestor import ingest_package_docs
    md = await ingest_package_docs("numpy")

    # Programmatic (sync helper)
    from sciagent_wizard.docs_ingestor import ingest_package_docs_sync
    md = ingest_package_docs_sync("numpy")

    # Standalone web app
    # sciagent-docs            (CLI entry point)
    # or: python -m sciagent_wizard.docs_ingestor
"""

from .agent import (
    DocsIngestorAgent,
    create_ingestor,
    ingest_package_docs,
    INGESTOR_CONFIG,
)
from .models import IngestorState, ScrapedPage, SourceType
from .crawler import crawl_package, fetch_single_page

__all__ = [
    "DocsIngestorAgent",
    "create_ingestor",
    "ingest_package_docs",
    "ingest_package_docs_sync",
    "crawl_package",
    "fetch_single_page",
    "IngestorState",
    "ScrapedPage",
    "SourceType",
    "INGESTOR_CONFIG",
    "main",
]


def ingest_package_docs_sync(
    package_name: str,
    github_url: str | None = None,
) -> str:
    """Synchronous wrapper around :func:`ingest_package_docs`.

    Runs the async ingestor in a new event loop. Safe to call from
    sync tool handlers (e.g. inside a running sciagent).
    """
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — safe to use asyncio.run
        return asyncio.run(ingest_package_docs(package_name, github_url))

    # Inside a running loop — offload to a thread
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:

        def _runner():
            return asyncio.run(ingest_package_docs(package_name, github_url))

        future = pool.submit(_runner)
        return future.result(timeout=300)


def main():
    """Entry point for ``sciagent-docs`` console script."""
    import sys

    # Load .env file if present (never overrides existing env vars)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    port = 5001
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    from .web import create_ingestor_app

    try:
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        console.print(Panel(
            "[bold]📚 SciAgent Docs Ingestor[/bold]\n"
            f"[dim]Open http://localhost:{port}/ingestor in your browser[/dim]\n"
            "[dim]Enter a package name to generate its API reference[/dim]",
            expand=False,
        ))
    except ImportError:
        print(f"📚 SciAgent Docs Ingestor — http://localhost:{port}/ingestor")

    app = create_ingestor_app()
    app.run(host="0.0.0.0", port=port)
