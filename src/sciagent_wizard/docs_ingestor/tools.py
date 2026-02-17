"""
Ingestor tool implementations — called by the LLM during doc ingestion.

Each function receives the ``IngestorState`` as first arg, same pattern
as :mod:`sciagent_wizard.tools`.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging

from .models import IngestorState

logger = logging.getLogger(__name__)


# ── Async helper (same pattern as wizard tools) ────────────────────────


def _run_async(coro):
    """Run an async coroutine from a sync tool handler."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_thread_runner, coro)
        return future.result(timeout=120)


def _thread_runner(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Tool implementations ──────────────────────────────────────────────


def tool_request_page(state: IngestorState, url: str) -> str:
    """Fetch an additional documentation page by URL.

    The LLM can call this when it sees a reference to a page it
    hasn't read yet (e.g. from a table of contents).
    """
    from .crawler import fetch_single_page

    page = _run_async(fetch_single_page(url))

    if page is None:
        return json.dumps({
            "status": "error",
            "message": f"Could not fetch page: {url}",
        })

    state.scraped_pages.append(page)

    return json.dumps({
        "status": "success",
        "title": page.title,
        "char_count": page.char_count,
        "content": page.content[:8000],  # Return content so LLM can read it
    })


def tool_submit_core_classes(state: IngestorState, markdown: str) -> str:
    """Submit the Core Classes section of the API reference."""
    state.core_classes = markdown.strip()
    return json.dumps({
        "status": "accepted",
        "section": "core_classes",
        "char_count": len(state.core_classes),
        "sections_remaining": _remaining(state),
    })


def tool_submit_key_functions(state: IngestorState, markdown: str) -> str:
    """Submit the Key Functions section of the API reference."""
    state.key_functions = markdown.strip()
    return json.dumps({
        "status": "accepted",
        "section": "key_functions",
        "char_count": len(state.key_functions),
        "sections_remaining": _remaining(state),
    })


def tool_submit_pitfalls(state: IngestorState, markdown: str) -> str:
    """Submit the Common Pitfalls section."""
    state.common_pitfalls = markdown.strip()
    return json.dumps({
        "status": "accepted",
        "section": "common_pitfalls",
        "char_count": len(state.common_pitfalls),
        "sections_remaining": _remaining(state),
    })


def tool_submit_recipes(state: IngestorState, markdown: str) -> str:
    """Submit the Quick-Start Recipes section."""
    state.recipes = markdown.strip()
    return json.dumps({
        "status": "accepted",
        "section": "recipes",
        "char_count": len(state.recipes),
        "sections_remaining": _remaining(state),
    })


def tool_finalize(state: IngestorState) -> str:
    """Assemble all sections into the final library_api.md.

    Uses the rendering system from sciagent_wizard to fill the
    ``library_api.md`` template with the LLM-submitted sections.
    """
    missing = _remaining(state)
    if missing:
        return json.dumps({
            "status": "error",
            "message": (
                f"Cannot finalize — sections not yet submitted: "
                f"{', '.join(missing)}.  Submit them first."
            ),
        })

    # Build the template context
    context = {
        "library_display_name": state.package_name,
        "library_source_url": state.source_url or "",
        "library_docs_url": state.docs_url or "",
        "library_toc": _build_toc(state),
        "library_core_classes": state.core_classes,
        "library_key_functions": state.key_functions,
        "library_common_pitfalls": state.common_pitfalls,
        "library_recipes": state.recipes,
    }

    # Try the shared renderer first (regex is now fixed for
    # multi-line REPLACE blocks), fall back to manual assembly.
    try:
        from sciagent_wizard.rendering import render_template
        rendered = render_template("library_api.md", context)
    except Exception:
        rendered = _manual_assemble(state, context)

    state.final_markdown = rendered

    return json.dumps({
        "status": "finalized",
        "char_count": len(rendered),
        "preview": rendered[:500],
    })


# ── Helpers ────────────────────────────────────────────────────────────


def _remaining(state: IngestorState) -> list:
    """Return names of sections not yet submitted."""
    missing = []
    if not state.core_classes:
        missing.append("core_classes")
    if not state.key_functions:
        missing.append("key_functions")
    if not state.common_pitfalls:
        missing.append("common_pitfalls")
    if not state.recipes:
        missing.append("recipes")
    return missing


def _build_toc(state: IngestorState) -> str:
    """Build a table of contents from the submitted sections."""
    return (
        "1. [Core Classes](#1-core-classes)\n"
        "2. [Key Functions](#2-key-functions)\n"
        "3. [Common Pitfalls](#3-common-pitfalls)\n"
        "4. [Quick-Start Recipes](#4-quick-start-recipes)"
    )


def _manual_assemble(state: IngestorState, context: dict) -> str:
    """Manual fallback if the template renderer is unavailable."""
    name = context.get("library_display_name", state.package_name)
    source = context.get("library_source_url", "")
    docs = context.get("library_docs_url", "")

    parts = [
        f"# {name} API Reference\n",
        f"> **Source**: {source}" if source else "",
        f"> **Docs**: {docs}" if docs else "",
        (
            "> **Purpose**: This document provides the correct API surface for the\n"
            "> primary domain library that your agent wraps or exposes."
        ),
        "\n---\n",
        "## Table of Contents\n",
        _build_toc(state),
        "\n---\n",
        "## 1. Core Classes\n",
        state.core_classes,
        "\n---\n",
        "## 2. Key Functions\n",
        state.key_functions,
        "\n---\n",
        "## 3. Common Pitfalls\n",
        state.common_pitfalls,
        "\n---\n",
        "## 4. Quick-Start Recipes\n",
        state.recipes,
        "\n---\n",
        "## Notes\n",
        "- This document should be kept in sync with the library version your\n"
        "  agent targets.",
    ]
    return "\n\n".join(p for p in parts if p)
