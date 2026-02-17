"""
DocsIngestorAgent — An agent that reads scraped documentation and
produces a structured library_api.md reference.

Uses the Copilot SDK (same as the wizard) with tools that let
the LLM iteratively submit sections of the API reference.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from sciagent.base_agent import BaseScientificAgent, _create_tool
from sciagent.config import AgentConfig

from .models import IngestorState, ScrapedPage
from .prompts import INGESTOR_EXPERTISE
from . import tools as ingestor_tools
from .crawler import crawl_package

logger = logging.getLogger(__name__)

# ── Agent configuration ────────────────────────────────────────────────

INGESTOR_CONFIG = AgentConfig(
    name="docs-ingestor",
    display_name="Library Docs Ingestor",
    description=(
        "Deep-crawl documentation for a Python package and produce "
        "a structured API reference in library_api.md format."
    ),
    instructions="",
    logo_emoji="📚",
    accent_color="#3b82f6",
)


class DocsIngestorAgent(BaseScientificAgent):
    """Agent that ingests package documentation into library_api.md."""

    def __init__(
        self,
        package_name: str = "",
        scraped_pages: Optional[List[ScrapedPage]] = None,
        **kwargs,
    ):
        self._ingestor_state = IngestorState(
            package_name=package_name,
            pip_name=package_name,
        )
        if scraped_pages:
            self._ingestor_state.scraped_pages = scraped_pages
        super().__init__(INGESTOR_CONFIG, **kwargs)

    @property
    def ingestor_state(self) -> IngestorState:
        return self._ingestor_state

    # ── Tool registration ───────────────────────────────────────────

    def _load_tools(self) -> List:
        state = self._ingestor_state

        return [
            _create_tool(
                "request_page",
                (
                    "Fetch an additional documentation page by URL. "
                    "Use this when you see a reference to an API page "
                    "in a table of contents or index that isn't in the "
                    "scraped pages provided. Returns the page content."
                ),
                lambda **kw: ingestor_tools.tool_request_page(state, **kw),
                {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Full URL of the page to fetch.",
                        },
                    },
                    "required": ["url"],
                },
            ),
            _create_tool(
                "submit_core_classes",
                (
                    "Submit the Core Classes section of the API reference. "
                    "Provide well-formatted Markdown documenting the main "
                    "classes with constructors, methods, parameter tables, "
                    "and return types."
                ),
                lambda **kw: ingestor_tools.tool_submit_core_classes(state, **kw),
                {
                    "type": "object",
                    "properties": {
                        "markdown": {
                            "type": "string",
                            "description": "Markdown content for Core Classes.",
                        },
                    },
                    "required": ["markdown"],
                },
            ),
            _create_tool(
                "submit_key_functions",
                (
                    "Submit the Key Functions section. Document standalone "
                    "functions with signatures, parameter tables, and return "
                    "types."
                ),
                lambda **kw: ingestor_tools.tool_submit_key_functions(state, **kw),
                {
                    "type": "object",
                    "properties": {
                        "markdown": {
                            "type": "string",
                            "description": "Markdown content for Key Functions.",
                        },
                    },
                    "required": ["markdown"],
                },
            ),
            _create_tool(
                "submit_pitfalls",
                (
                    "Submit the Common Pitfalls section. List gotchas, "
                    "naming conflicts, parameter confusion, and common "
                    "mistakes."
                ),
                lambda **kw: ingestor_tools.tool_submit_pitfalls(state, **kw),
                {
                    "type": "object",
                    "properties": {
                        "markdown": {
                            "type": "string",
                            "description": "Markdown content for Common Pitfalls.",
                        },
                    },
                    "required": ["markdown"],
                },
            ),
            _create_tool(
                "submit_recipes",
                (
                    "Submit the Quick-Start Recipes section. Provide "
                    "self-contained code snippets with imports for common "
                    "tasks."
                ),
                lambda **kw: ingestor_tools.tool_submit_recipes(state, **kw),
                {
                    "type": "object",
                    "properties": {
                        "markdown": {
                            "type": "string",
                            "description": "Markdown content for Quick-Start Recipes.",
                        },
                    },
                    "required": ["markdown"],
                },
            ),
            _create_tool(
                "finalize",
                (
                    "Assemble all submitted sections into the final "
                    "library_api.md document. Call this AFTER submitting "
                    "all four sections (core_classes, key_functions, "
                    "pitfalls, recipes)."
                ),
                lambda **kw: ingestor_tools.tool_finalize(state),
                {"type": "object", "properties": {}},
            ),
        ]

    # ── System message ──────────────────────────────────────────────

    def _get_system_message(self) -> str:
        state = self._ingestor_state
        parts = [INGESTOR_EXPERTISE]

        # Add package context
        parts.append(
            f"\n## Package: {state.package_name}\n"
            f"- **pip name**: {state.pip_name}\n"
            f"- **Source URL**: {state.source_url or 'unknown'}\n"
            f"- **Docs URL**: {state.docs_url or 'unknown'}\n"
        )

        # Add scraped pages as context
        if state.scraped_pages:
            parts.append("\n## Scraped Documentation Pages\n")
            for i, page in enumerate(state.scraped_pages, 1):
                parts.append(
                    f"### Page {i}: {page.title}\n"
                    f"*Source: {page.source_type.value} — {page.url}*\n\n"
                    f"{page.content}\n\n"
                    f"---\n"
                )

        return "\n".join(parts)

    # ── High-level API ──────────────────────────────────────────────

    async def ingest(
        self,
        package_name: str,
        github_url: Optional[str] = None,
    ) -> str:
        """Crawl docs and produce a filled library_api.md.

        This is the main programmatic API — call it from the wizard
        or from sciagent proper.

        Args:
            package_name: PyPI package name.
            github_url: Optional GitHub repo URL for deeper source crawling.

        Returns:
            The completed library_api.md Markdown string.
        """
        state = self._ingestor_state
        state.package_name = package_name
        state.pip_name = package_name

        # 1 — Crawl
        logger.info("Crawling documentation for %s ...", package_name)
        metadata, pages = await crawl_package(package_name, github_url)

        state.pip_name = metadata.get("pip_name", package_name)
        state.source_url = metadata.get("repository_url", "")
        state.docs_url = metadata.get("docs_url", "")
        state.pypi_metadata = metadata
        state.scraped_pages = pages

        if not pages:
            logger.warning("No documentation pages found for %s", package_name)
            return self._minimal_doc(package_name, metadata)

        logger.info(
            "Crawled %d pages (%d chars) for %s",
            len(pages),
            state.total_scraped_chars,
            package_name,
        )

        # 2 — Run the agent to extract and structure the docs
        await self.start()
        try:
            session = await self.create_session()

            # Send kickoff message
            kickoff = (
                f"I have scraped {len(pages)} documentation pages for "
                f"**{package_name}**. Please read through them and extract "
                f"the API reference into the four required sections:\n\n"
                f"1. Core Classes (submit_core_classes)\n"
                f"2. Key Functions (submit_key_functions)\n"
                f"3. Common Pitfalls (submit_pitfalls)\n"
                f"4. Quick-Start Recipes (submit_recipes)\n\n"
                f"Submit each section using the appropriate tool, "
                f"then call finalize."
            )

            # Use the on() + send() pattern (same as sciagent web app)
            from copilot.generated.session_events import (
                SessionEventType,
            )

            idle_event = asyncio.Event()

            def _handler(event):
                etype = event.type

                if etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
                    name = (
                        getattr(event.data, "tool_name", None)
                        or ""
                    )
                    logger.debug(
                        "Ingestor tool completed: %s", name,
                    )

                elif etype == SessionEventType.SESSION_ERROR:
                    err = (
                        getattr(event.data, "message", None)
                        or str(event.data)
                    )
                    logger.error(
                        "Ingestor session error: %s", err,
                    )
                    idle_event.set()

                elif etype == SessionEventType.SESSION_IDLE:
                    idle_event.set()

            unsub = session.on(_handler)
            try:
                await session.send({"prompt": kickoff})
                await idle_event.wait()
            finally:
                unsub()

            # Check if we got a result
            if state.final_markdown:
                return state.final_markdown

            # If the agent didn't finalize, try to do it ourselves
            if state.sections_filled:
                logger.warning(
                    "Agent didn't call finalize — assembling manually "
                    "(sections filled: %s)",
                    state.sections_filled,
                )
                ingestor_tools.tool_finalize(state)
                if state.final_markdown:
                    return state.final_markdown

            return self._minimal_doc(package_name, metadata)

        finally:
            await self.stop()

    def _minimal_doc(self, package_name: str, metadata: dict) -> str:
        """Produce a minimal doc when ingestion yields nothing useful."""
        install = metadata.get("install_command", f"pip install {package_name}")
        desc = metadata.get("description", "")
        source = metadata.get("repository_url", "")
        docs = metadata.get("docs_url", "")

        lines = [
            f"# {package_name} API Reference\n",
            f"> {desc}" if desc else "",
            f"> **Source**: {source}" if source else "",
            f"> **Docs**: {docs}" if docs else "",
            "",
            "---",
            "",
            f"Install: `{install}`",
            "",
            "```python",
            f"import {package_name.replace('-', '_')}",
            "```",
            "",
            "*Full API documentation was not available at ingestion time.*",
            f"*Refer to {docs or source or 'the package homepage'} "
            "for the complete API reference.*",
        ]
        return "\n".join(lines)


# ── Factory ─────────────────────────────────────────────────────────────


def create_ingestor(
    package_name: str = "",
    **kwargs,
) -> DocsIngestorAgent:
    """Create a DocsIngestorAgent instance."""
    return DocsIngestorAgent(package_name=package_name, **kwargs)


# ── Convenience function ────────────────────────────────────────────────


async def ingest_package_docs(
    package_name: str,
    github_url: Optional[str] = None,
) -> str:
    """One-shot: crawl + ingest → return filled library_api.md.

    This is the simplest way to use the ingestor programmatically::

        from sciagent_wizard.docs_ingestor import ingest_package_docs
        md = await ingest_package_docs("numpy")
    """
    agent = create_ingestor(package_name)
    return await agent.ingest(package_name, github_url)
