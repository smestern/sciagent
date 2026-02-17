"""
Wizard tool implementations — all tool handler methods for the WizardAgent.

These are extracted from the monolithic wizard_agent.py for clarity.
Each function receives the wizard state and performs its action.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    DiscoverySource,
    OutputMode,
    PackageCandidate,
    PendingQuestion,
    WizardState,
)

logger = logging.getLogger(__name__)


# ── Async helper ────────────────────────────────────────────────────────


def _run_async(coro):
    """Run an async coroutine from a sync tool handler.

    When called from within a running event loop (e.g. Quart web server),
    ``loop.run_until_complete()`` raises ``RuntimeError``. This helper
    detects that situation and runs the coroutine in a background thread
    with its own event loop instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — safe to use run_until_complete directly
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    # Already inside a running loop — offload to a thread
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_thread_runner, coro)
        return future.result(timeout=120)


def _thread_runner(coro):
    """Run a coroutine in a fresh event loop on this thread."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Tool implementations ───────────────────────────────────────────────


def tool_present_question(
    state: WizardState,
    question: str,
    options: List[str],
    allow_freetext: bool = False,
    max_length: int = 100,
    allow_multiple: bool = False,
) -> str:
    """Present a structured question to the user (guided mode only).

    Returns a special JSON payload that the WebSocket handler
    intercepts and renders as a clickable question card in the UI.
    """
    pending = PendingQuestion(
        question=question,
        options=options,
        allow_freetext=allow_freetext,
        max_length=max_length,
        allow_multiple=allow_multiple,
    )
    state.pending_question = pending

    return json.dumps({
        "__type__": "question_card",
        "question": question,
        "options": options,
        "allow_freetext": allow_freetext,
        "max_length": max_length,
        "allow_multiple": allow_multiple,
    })


def tool_search_packages(
    state: WizardState,
    keywords: List[str],
    sources: Optional[List[str]] = None,
    search_queries: Optional[List[str]] = None,
) -> str:
    """Search for domain-specific packages."""
    from .sources.ranker import discover_packages

    candidates = _run_async(
        discover_packages(
            keywords, sources=sources, search_queries=search_queries,
        )
    )

    # Store in wizard state
    state.keywords = keywords
    state.all_candidates = candidates

    # Format for LLM
    results = []
    for i, c in enumerate(candidates[:30], 1):
        results.append({
            "rank": i,
            "name": c.name,
            "description": c.description[:200],
            "source": c.source.value,
            "relevance": c.relevance_score,
            "peer_reviewed": c.peer_reviewed,
            "citations": c.citations,
            "install": c.install_command,
            "homepage": c.homepage,
        })

    return json.dumps({
        "total_found": len(candidates),
        "showing": len(results),
        "results": results,
    }, indent=2)


def tool_analyze_data(state: WizardState, file_paths: List[str]) -> str:
    """Analyze uploaded example data files."""
    from .analyzer import (
        analyze_example_files,
        infer_accepted_types,
        infer_bounds,
        collect_domain_hints,
    )

    infos = analyze_example_files(file_paths)
    state.example_files = infos
    state.accepted_file_types = infer_accepted_types(infos)
    state.bounds = infer_bounds(infos)

    hints = collect_domain_hints(infos)

    result: dict = {
        "files_analyzed": len(infos),
        "accepted_types": state.accepted_file_types,
        "domain_hints": hints,
        "files": [],
    }
    for fi in infos:
        result["files"].append({
            "path": fi.path,
            "extension": fi.extension,
            "columns": fi.columns[:30],
            "row_count": fi.row_count,
            "value_ranges": {
                k: {"min": v[0], "max": v[1]}
                for k, v in fi.value_ranges.items()
            },
            "hints": fi.inferred_domain_hints,
        })

    if state.bounds:
        result["inferred_bounds"] = {
            k: {"lower": v[0], "upper": v[1]}
            for k, v in state.bounds.items()
        }

    return json.dumps(result, indent=2)


def tool_show_recommendations(state: WizardState) -> str:
    """Show the current recommendation list."""
    if not state.all_candidates:
        return json.dumps({"error": "No packages found yet. Run search_packages first."})

    entries = []
    for i, c in enumerate(state.all_candidates[:30], 1):
        entries.append(
            f"{i}. **{c.name}** (relevance: {c.relevance_score:.0%}, "
            f"source: {c.source.value})\n"
            f"   {c.description[:150]}\n"
            f"   Install: `{c.install_command}`"
            + (f" | Peer-reviewed ✓" if c.peer_reviewed else "")
        )

    return "\n\n".join(entries)


def tool_confirm_packages(
    state: WizardState,
    selected_names: List[str],
    additional_packages: Optional[List[str]] = None,
) -> str:
    """Confirm the package selection."""
    confirmed: list[PackageCandidate] = []
    name_set = {n.lower() for n in selected_names}

    # Match from discovered candidates
    for cand in state.all_candidates:
        if cand.name.lower() in name_set or cand.pip_name.lower() in name_set:
            confirmed.append(cand)
            name_set.discard(cand.name.lower())
            name_set.discard(cand.pip_name.lower())

    # Add user-specified packages (not found by discovery)
    for extra in (additional_packages or []):
        if extra.lower() not in {c.pip_name.lower() for c in confirmed}:
            confirmed.append(PackageCandidate(
                name=extra,
                source=DiscoverySource.USER,
                install_command=f"pip install {extra}",
                python_package=extra,
                relevance_score=1.0,
            ))

    # Any remaining unmatched names → add as user-specified
    for leftover in name_set:
        confirmed.append(PackageCandidate(
            name=leftover,
            source=DiscoverySource.USER,
            install_command=f"pip install {leftover}",
            python_package=leftover,
            relevance_score=0.8,
        ))

    state.confirmed_packages = confirmed

    return json.dumps({
        "confirmed": len(confirmed),
        "packages": [
            {"name": p.name, "source": p.source.value, "install": p.install_command}
            for p in confirmed
        ],
    }, indent=2)


def tool_set_identity(
    state: WizardState,
    name: str,
    display_name: str,
    description: str,
    emoji: str = "🔬",
    domain_description: str = "",
    research_goals: Optional[List[str]] = None,
) -> str:
    """Set the generated agent's identity."""
    state.agent_name = name
    state.agent_display_name = display_name
    state.agent_description = description
    state.agent_emoji = emoji
    if domain_description:
        state.domain_description = domain_description
    if research_goals:
        state.research_goals = research_goals

    return json.dumps({
        "status": "identity_set",
        "name": name,
        "display_name": display_name,
        "description": description,
        "emoji": emoji,
    })


def tool_generate(
    state: WizardState,
    output_dir: Optional[str] = None,
    suggestion_chips: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Generate the agent project."""
    # Validation
    if not state.agent_name:
        return json.dumps({"error": "Agent identity not set. Call set_agent_identity first."})
    if not state.confirmed_packages:
        return json.dumps({"error": "No packages confirmed. Call confirm_packages first."})

    # Add suggestion chips if provided
    if suggestion_chips:
        state.suggestion_chips = [
            (chip.get("label", ""), chip.get("prompt", ""))
            for chip in suggestion_chips
        ]

    from .generators import generate_project

    out = output_dir or str(Path.cwd())
    project_path = generate_project(state, output_dir=out)

    # Build mode-specific instructions
    mode = state.output_mode
    if mode == OutputMode.COPILOT_AGENT:
        instructions = {
            "vscode": (
                f"Copy the .github/agents/ folder into your workspace "
                f"and select '{state.agent_display_name}' from the Agents dropdown."
            ),
            "claude_code": (
                f"Copy the .claude/agents/ folder into your project. "
                f"Claude Code will auto-detect the '{state.agent_name}' sub-agent."
            ),
            "docs": "Package documentation is in docs/",
        }
    elif mode == OutputMode.MARKDOWN:
        instructions = {
            "usage": (
                "Copy the contents of system-prompt.md into your preferred "
                "LLM's system prompt. See agent-spec.md for full details."
            ),
            "docs": "Package documentation is in docs/",
        }
    else:
        instructions = {
            "cli": f"python -m {state.agent_name.replace('-', '_')}",
            "web": f"python -m {state.agent_name.replace('-', '_')} --web",
            "install": f"pip install -r {project_path / 'requirements.txt'}",
        }

    return json.dumps({
        "status": "generated",
        "output_mode": mode.value,
        "project_dir": str(project_path),
        "files": [str(p.name) for p in project_path.iterdir() if p.is_file()],
        "instructions": instructions,
    }, indent=2)


def tool_install(state: WizardState) -> str:
    """Install confirmed packages via pip."""
    if not state.confirmed_packages:
        return json.dumps({"error": "No packages confirmed yet."})

    packages = [p.pip_name for p in state.confirmed_packages if p.pip_name]
    if not packages:
        return json.dumps({"status": "nothing_to_install"})

    results: list[dict] = []
    for pkg in packages:
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg],
                capture_output=True,
                text=True,
                timeout=120,
            )
            results.append({
                "package": pkg,
                "success": proc.returncode == 0,
                "message": proc.stdout[-300:] if proc.returncode == 0 else proc.stderr[-300:],
            })
        except Exception as exc:
            results.append({
                "package": pkg,
                "success": False,
                "message": str(exc),
            })

    succeeded = sum(1 for r in results if r["success"])
    return json.dumps({
        "installed": succeeded,
        "failed": len(results) - succeeded,
        "details": results,
    }, indent=2)


def tool_launch(state: WizardState, mode: str = "web") -> str:
    """Launch the generated agent."""
    project_dir = state.project_dir
    if not project_dir or not Path(project_dir).exists():
        return json.dumps({"error": "Agent not generated yet. Call generate_agent first."})

    slug = state.agent_name.replace("-", "_")

    if mode == "web":
        # Launch in a subprocess so the wizard doesn't block
        cmd = [sys.executable, "-m", slug, "--web"]
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(Path(project_dir).parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return json.dumps({
                "status": "launched",
                "mode": "web",
                "url": "http://localhost:5000",
                "pid": proc.pid,
                "command": " ".join(cmd),
            })
        except Exception as exc:
            return json.dumps({"error": f"Failed to launch: {exc}"})
    else:
        return json.dumps({
            "status": "ready",
            "mode": "cli",
            "command": f"python -m {slug}",
            "instructions": "Run this command in your terminal to start the CLI agent.",
        })


def tool_get_state(state: WizardState) -> str:
    """Return the current wizard state."""
    return json.dumps(state.to_dict(), indent=2)


def tool_fetch_docs(state: WizardState) -> str:
    """Fetch documentation for all confirmed packages."""
    if not state.confirmed_packages:
        return json.dumps({"error": "No packages confirmed yet. Call confirm_packages first."})

    from .sources.doc_fetcher import fetch_package_docs

    docs = _run_async(
        fetch_package_docs(state.confirmed_packages)
    )

    state.package_docs = docs

    # Summary for the LLM
    summary = []
    for name, content in docs.items():
        word_count = len(content.split())
        summary.append({
            "package": name,
            "doc_words": word_count,
            "has_content": word_count > 50,
        })

    return json.dumps({
        "status": "docs_fetched",
        "packages_documented": len(docs),
        "details": summary,
    }, indent=2)


def tool_set_output_mode(state: WizardState, mode: str, guided_mode: bool = False) -> str:
    """Set the output mode for agent generation."""
    try:
        output_mode = OutputMode(mode)
    except ValueError:
        return json.dumps({
            "error": f"Invalid mode '{mode}'. Must be one of: fullstack, copilot_agent, markdown"
        })

    # Enforce restriction in guided/public mode
    if guided_mode and output_mode == OutputMode.FULLSTACK:
        return json.dumps({
            "error": (
                "Fullstack mode is not available in public mode. "
                "Please choose 'copilot_agent' or 'markdown'."
            )
        })

    state.output_mode = output_mode

    descriptions = {
        OutputMode.FULLSTACK: (
            "Full Python submodule with CLI, web UI, code execution sandbox, "
            "and guardrails. The generated agent runs as a standalone application."
        ),
        OutputMode.COPILOT_AGENT: (
            "Configuration files for VS Code GitHub Copilot custom agent "
            "(.agent.md) and Claude Code sub-agent (.md). Includes shared "
            "instructions and package documentation."
        ),
        OutputMode.MARKDOWN: (
            "Platform-agnostic Markdown files (system prompt, tools reference, "
            "data guide, guardrails, workflow). Copy-paste into any LLM."
        ),
    }

    return json.dumps({
        "status": "output_mode_set",
        "mode": output_mode.value,
        "description": descriptions[output_mode],
    })


def tool_ingest_library_api(
    state: WizardState,
    package_name: str,
    github_url: Optional[str] = None,
) -> str:
    """Deep-crawl a package's docs and generate a structured API reference.

    Uses the docs ingestor agent to crawl ReadTheDocs, GitHub source,
    and PyPI, then fills out the ``library_api.md`` template with
    classes, functions, pitfalls, and recipes.

    The result is stored in ``state.package_docs[name + "_api"]``.
    """
    try:
        from .docs_ingestor import ingest_package_docs_sync
    except ImportError:
        return json.dumps({
            "error": "docs_ingestor module not available. "
                     "Is sciagent[wizard] installed?",
        })

    try:
        markdown = ingest_package_docs_sync(package_name, github_url)
    except Exception as exc:
        logger.exception("Library API ingestion failed for %s", package_name)
        return json.dumps({
            "error": f"Ingestion failed: {exc}",
        })

    # Store the result
    doc_key = f"{package_name}_api"
    state.package_docs[doc_key] = markdown

    word_count = len(markdown.split())
    return json.dumps({
        "status": "ingested",
        "package": package_name,
        "doc_key": doc_key,
        "word_count": word_count,
        "has_classes": "## 1. Core Classes" in markdown or "### `" in markdown,
        "has_functions": "## 2. Key Functions" in markdown,
        "has_pitfalls": "## 3. Common Pitfalls" in markdown,
        "has_recipes": "## 4. Quick-Start Recipes" in markdown,
    }, indent=2)
