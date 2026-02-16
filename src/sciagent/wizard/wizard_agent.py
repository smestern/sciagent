"""
WizardAgent — The self-assembly wizard is itself a scientific agent.

It uses LLM-driven conversation to interview the researcher about their
domain, discover relevant packages, analyze example data, and generate
a fully functional domain-specific agent project.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from sciagent.base_agent import BaseScientificAgent, _create_tool
from sciagent.config import AgentConfig, SuggestionChip
from sciagent.prompts.base_messages import build_system_message
from sciagent_wizard.prompts import WIZARD_EXPERTISE, PUBLIC_WIZARD_EXPERTISE

from .models import DiscoverySource, OutputMode, PackageCandidate, PendingQuestion, WizardPhase, WizardState

logger = logging.getLogger(__name__)

# ── Wizard configuration ───────────────────────────────────────────────

WIZARD_CONFIG = AgentConfig(
    name="sciagent-wizard",
    display_name="SciAgent Self-Assembly Wizard",
    description=(
        "Build your own domain-specific scientific analysis agent. "
        "Describe your field, upload example data, and I'll find the "
        "right tools and build a custom agent for you."
    ),
    instructions="",
    accepted_file_types=[
        ".csv", ".tsv", ".xlsx", ".xls",
        ".json", ".jsonl", ".txt",
        ".npy", ".npz",
        ".parquet", ".feather",
        ".abf", ".nwb",
        ".png", ".jpg", ".tif", ".tiff",
        ".fasta", ".fastq",
    ],
    suggestion_chips=[
        SuggestionChip(
            "Electrophysiology agent",
            "I study patch-clamp electrophysiology and need an agent that "
            "can analyze ABF files, extract action potentials, and fit "
            "ion channel kinetics.",
        ),
        SuggestionChip(
            "Genomics agent",
            "I work in genomics and need an agent that can process FASTQ "
            "files, run quality control, and perform differential expression "
            "analysis.",
        ),
        SuggestionChip(
            "Calcium imaging agent",
            "I do calcium imaging experiments and need an agent that can "
            "extract fluorescence traces from TIFF stacks, detect events, "
            "and plot activity.",
        ),
        SuggestionChip(
            "Chemistry agent",
            "I'm a chemist working with spectroscopy data (UV-Vis, NMR). "
            "I need an agent that can load spectra, fit peaks, and "
            "calculate concentrations.",
        ),
    ],
    logo_emoji="🧙",
    accent_color="#a855f7",
)


class WizardAgent(BaseScientificAgent):
    """The wizard agent that builds other agents."""

    def __init__(self, guided_mode: bool = False, **kwargs):
        # The wizard manages its own state across the conversation
        self._wizard_state = WizardState(guided_mode=guided_mode)
        self._guided_mode = guided_mode
        super().__init__(WIZARD_CONFIG, **kwargs)

    @property
    def wizard_state(self) -> WizardState:
        return self._wizard_state

    # ── Tool registration ───────────────────────────────────────────

    def _load_tools(self) -> List:
        state = self._wizard_state

        tools = [
            # ─ Discovery ────────────────────────────────────────────
            _create_tool(
                "search_packages",
                (
                    "Search peer-reviewed databases (PyPI, bio.tools, Papers "
                    "With Code, PubMed) for scientific software "
                    "relevant to the researcher's domain. Returns ranked "
                    "results with descriptions and relevance scores. "
                    "Call this after learning about the researcher's domain."
                ),
                self._tool_search_packages,
                {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Domain-specific search keywords. Include the "
                                "field name, key techniques, data types, and "
                                "any known software names."
                            ),
                        },
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Which databases to search. Options: pypi, "
                                "biotools, papers_with_code, pubmed. "
                                "Default: all."
                            ),
                        },
                    },
                    "required": ["keywords"],
                },
            ),

            # ─ Data analysis ────────────────────────────────────────
            _create_tool(
                "analyze_example_data",
                (
                    "Analyze example data files the researcher has uploaded. "
                    "Infers file types, column names, value ranges, and "
                    "domain-specific patterns. Use this to understand the "
                    "researcher's data before recommending packages."
                ),
                self._tool_analyze_data,
                {
                    "type": "object",
                    "properties": {
                        "file_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Paths to example data files.",
                        },
                    },
                    "required": ["file_paths"],
                },
            ),

            # ─ Recommendations ──────────────────────────────────────
            _create_tool(
                "show_recommendations",
                (
                    "Display the current list of discovered packages with "
                    "their relevance scores, descriptions, and sources. "
                    "Present this to the researcher for review."
                ),
                self._tool_show_recommendations,
                {"type": "object", "properties": {}},
            ),

            # ─ Package confirmation ─────────────────────────────────
            _create_tool(
                "confirm_packages",
                (
                    "Lock in the researcher's package selection. Pass the "
                    "list of package names they want to include. Can also "
                    "add manually-specified packages not found by discovery."
                ),
                self._tool_confirm_packages,
                {
                    "type": "object",
                    "properties": {
                        "selected_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Names of packages the researcher approved.",
                        },
                        "additional_packages": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Extra package names the researcher wants, not "
                                "found by automated discovery."
                            ),
                        },
                    },
                    "required": ["selected_names"],
                },
            ),

            # ─ Agent identity ───────────────────────────────────────
            _create_tool(
                "set_agent_identity",
                (
                    "Set the name, display name, description, and emoji for "
                    "the agent being built. Call after confirming packages."
                ),
                self._tool_set_identity,
                {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Machine-friendly slug (e.g. 'ephys-analyst')",
                        },
                        "display_name": {
                            "type": "string",
                            "description": "Human-friendly title (e.g. 'Electrophysiology Analyst')",
                        },
                        "description": {
                            "type": "string",
                            "description": "One-line description of what the agent does.",
                        },
                        "emoji": {
                            "type": "string",
                            "description": "An emoji for the agent's icon (e.g. '⚡')",
                        },
                        "domain_description": {
                            "type": "string",
                            "description": "Detailed description of the research domain.",
                        },
                        "research_goals": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of the researcher's main goals.",
                        },
                    },
                    "required": ["name", "display_name", "description"],
                },
            ),

            # ─ Generate project ─────────────────────────────────────
            _create_tool(
                "generate_agent",
                (
                    "Generate the complete agent project (config, tools, "
                    "prompt, agent class, entry point, README). Must have "
                    "confirmed packages and set agent identity first."
                ),
                self._tool_generate,
                {
                    "type": "object",
                    "properties": {
                        "output_dir": {
                            "type": "string",
                            "description": (
                                "Directory where the project will be created. "
                                "Defaults to the current working directory."
                            ),
                        },
                        "suggestion_chips": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "prompt": {"type": "string"},
                                },
                            },
                            "description": "Example prompts to show in the UI.",
                        },
                    },
                },
            ),

            # ─ Install ──────────────────────────────────────────────
            _create_tool(
                "install_packages",
                (
                    "Install the confirmed Python packages using pip. "
                    "Only call after the researcher has approved the list."
                ),
                self._tool_install,
                {"type": "object", "properties": {}},
            ),

            # ─ Launch ───────────────────────────────────────────────
            _create_tool(
                "launch_agent",
                (
                    "Launch the generated agent in web mode. Only call after "
                    "generate_agent has succeeded."
                ),
                self._tool_launch,
                {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["web", "cli"],
                            "description": "Launch in web or CLI mode. Default: web.",
                        },
                    },
                },
            ),

            # ─ State inspection ─────────────────────────────────────
            _create_tool(
                "get_wizard_state",
                "Get the current state of the wizard (what's been configured so far).",
                self._tool_get_state,
                {"type": "object", "properties": {}},
            ),

            # ─ Documentation fetching ───────────────────────────────
            _create_tool(
                "fetch_package_docs",
                (
                    "Fetch and generate local reference documentation for "
                    "all confirmed packages. Reads READMEs from PyPI, GitHub, "
                    "ReadTheDocs, and package homepages. Call this AFTER "
                    "confirm_packages to build docs the agent can reference."
                ),
                self._tool_fetch_docs,
                {"type": "object", "properties": {}},
            ),

            # ─ Output mode ──────────────────────────────────────────
            _create_tool(
                "set_output_mode",
                (
                    "Set the output format for the generated agent. Options: "
                    "'fullstack' (full Python submodule with web UI and CLI), "
                    "'copilot_agent' (VS Code custom agent + Claude Code sub-agent "
                    "config files), or 'markdown' (platform-agnostic Markdown "
                    "specification for any LLM). Default is fullstack."
                ),
                self._tool_set_output_mode,
                {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["fullstack", "copilot_agent", "markdown"],
                            "description": (
                                "The output mode: fullstack, copilot_agent, or markdown."
                            ),
                        },
                    },
                    "required": ["mode"],
                },
            ),
        ]

        # ─ Guided-mode only tools ──────────────────────────────────
        if self._guided_mode:
            tools.append(_create_tool(
                "present_question",
                (
                    "Present a structured question to the user. In guided "
                    "mode, this is the ONLY way to interact with the user. "
                    "Provide clear options for them to choose from. Use "
                    "allow_freetext=true only when you need a short text "
                    "answer (e.g. naming the agent)."
                ),
                self._tool_present_question,
                {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The question to ask the user.",
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Options for the user to choose from. Each "
                                "option is a short label string."
                            ),
                        },
                        "allow_freetext": {
                            "type": "boolean",
                            "description": (
                                "If true, allows the user to type a short "
                                "text answer instead of (or in addition to) "
                                "selecting options. Default: false."
                            ),
                        },
                        "max_length": {
                            "type": "integer",
                            "description": (
                                "Maximum character length for freetext input. "
                                "Default: 100."
                            ),
                        },
                        "allow_multiple": {
                            "type": "boolean",
                            "description": (
                                "If true, the user can select multiple "
                                "options. Default: false."
                            ),
                        },
                    },
                    "required": ["question", "options"],
                },
            ))

            # Remove install_packages and launch_agent in guided mode
            tools = [
                t for t in tools
                if getattr(t, "name", "") not in ("install_packages", "launch_agent")
            ]

        return tools

    # ── System message ──────────────────────────────────────────────

    def _get_system_message(self) -> str:
        expertise = PUBLIC_WIZARD_EXPERTISE if self._guided_mode else WIZARD_EXPERTISE
        return build_system_message(
            expertise,
            # Disable policies that don't apply to the wizard
            code_policy=False,
            output_dir_policy=False,
            reproducible_script_policy=False,
        )

    # ── Tool implementations ────────────────────────────────────────

    def _tool_present_question(
        self,
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
        self._wizard_state.pending_question = pending

        # Return a payload the WS handler will detect and forward as
        # a question_card event rather than plain text.
        return json.dumps({
            "__type__": "question_card",
            "question": question,
            "options": options,
            "allow_freetext": allow_freetext,
            "max_length": max_length,
            "allow_multiple": allow_multiple,
        })

    def _tool_search_packages(
        self,
        keywords: List[str],
        sources: Optional[List[str]] = None,
    ) -> str:
        """Search for domain-specific packages."""
        from .discovery.ranker import discover_packages

        candidates = _run_async(
            discover_packages(keywords, sources=sources)
        )

        # Store in wizard state
        self._wizard_state.keywords = keywords
        self._wizard_state.all_candidates = candidates

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

    def _tool_analyze_data(self, file_paths: List[str]) -> str:
        """Analyze uploaded example data files."""
        from .analyzer import (
            analyze_example_files,
            infer_accepted_types,
            infer_bounds,
            collect_domain_hints,
        )

        infos = analyze_example_files(file_paths)
        self._wizard_state.example_files = infos
        self._wizard_state.accepted_file_types = infer_accepted_types(infos)
        self._wizard_state.bounds = infer_bounds(infos)

        hints = collect_domain_hints(infos)

        result = {
            "files_analyzed": len(infos),
            "accepted_types": self._wizard_state.accepted_file_types,
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

        if self._wizard_state.bounds:
            result["inferred_bounds"] = {
                k: {"lower": v[0], "upper": v[1]}
                for k, v in self._wizard_state.bounds.items()
            }

        return json.dumps(result, indent=2)

    def _tool_show_recommendations(self) -> str:
        """Show the current recommendation list."""
        if not self._wizard_state.all_candidates:
            return json.dumps({"error": "No packages found yet. Run search_packages first."})

        entries = []
        for i, c in enumerate(self._wizard_state.all_candidates[:30], 1):
            entries.append(
                f"{i}. **{c.name}** (relevance: {c.relevance_score:.0%}, "
                f"source: {c.source.value})\n"
                f"   {c.description[:150]}\n"
                f"   Install: `{c.install_command}`"
                + (f" | Peer-reviewed ✓" if c.peer_reviewed else "")
            )

        return "\n\n".join(entries)

    def _tool_confirm_packages(
        self,
        selected_names: List[str],
        additional_packages: Optional[List[str]] = None,
    ) -> str:
        """Confirm the package selection."""
        confirmed: list[PackageCandidate] = []
        name_set = {n.lower() for n in selected_names}

        # Match from discovered candidates
        for cand in self._wizard_state.all_candidates:
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

        self._wizard_state.confirmed_packages = confirmed

        return json.dumps({
            "confirmed": len(confirmed),
            "packages": [
                {"name": p.name, "source": p.source.value, "install": p.install_command}
                for p in confirmed
            ],
        }, indent=2)

    def _tool_set_identity(
        self,
        name: str,
        display_name: str,
        description: str,
        emoji: str = "🔬",
        domain_description: str = "",
        research_goals: Optional[List[str]] = None,
    ) -> str:
        """Set the generated agent's identity."""
        self._wizard_state.agent_name = name
        self._wizard_state.agent_display_name = display_name
        self._wizard_state.agent_description = description
        self._wizard_state.agent_emoji = emoji
        if domain_description:
            self._wizard_state.domain_description = domain_description
        if research_goals:
            self._wizard_state.research_goals = research_goals

        return json.dumps({
            "status": "identity_set",
            "name": name,
            "display_name": display_name,
            "description": description,
            "emoji": emoji,
        })

    def _tool_generate(
        self,
        output_dir: Optional[str] = None,
        suggestion_chips: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Generate the agent project."""
        state = self._wizard_state

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

        from .generator.project import generate_project

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

    def _tool_install(self) -> str:
        """Install confirmed packages via pip."""
        if not self._wizard_state.confirmed_packages:
            return json.dumps({"error": "No packages confirmed yet."})

        packages = [p.pip_name for p in self._wizard_state.confirmed_packages if p.pip_name]
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

    def _tool_launch(self, mode: str = "web") -> str:
        """Launch the generated agent."""
        project_dir = self._wizard_state.project_dir
        if not project_dir or not Path(project_dir).exists():
            return json.dumps({"error": "Agent not generated yet. Call generate_agent first."})

        slug = self._wizard_state.agent_name.replace("-", "_")

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

    def _tool_get_state(self) -> str:
        """Return the current wizard state."""
        return json.dumps(self._wizard_state.to_dict(), indent=2)

    def _tool_fetch_docs(self) -> str:
        """Fetch documentation for all confirmed packages."""
        if not self._wizard_state.confirmed_packages:
            return json.dumps({"error": "No packages confirmed yet. Call confirm_packages first."})

        from .discovery.doc_fetcher import fetch_package_docs

        docs = _run_async(
            fetch_package_docs(self._wizard_state.confirmed_packages)
        )

        self._wizard_state.package_docs = docs

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

    def _tool_set_output_mode(self, mode: str) -> str:
        """Set the output mode for agent generation."""
        try:
            output_mode = OutputMode(mode)
        except ValueError:
            return json.dumps({
                "error": f"Invalid mode '{mode}'. Must be one of: fullstack, copilot_agent, markdown"
            })

        # Enforce restriction in guided/public mode
        if self._guided_mode and output_mode == OutputMode.FULLSTACK:
            return json.dumps({
                "error": (
                    "Fullstack mode is not available in public mode. "
                    "Please choose 'copilot_agent' or 'markdown'."
                )
            })

        self._wizard_state.output_mode = output_mode

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


# ── Factory ─────────────────────────────────────────────────────────────


def create_wizard(guided_mode: bool = False, **kwargs) -> WizardAgent:
    """Create a WizardAgent instance.

    Args:
        guided_mode: If True, run in public/guided mode with no freeform
            chat — users interact only via structured question cards.
    """
    return WizardAgent(guided_mode=guided_mode, **kwargs)


# ── Helpers ─────────────────────────────────────────────────────────────


def _run_async(coro):
    """Run an async coroutine from a sync tool handler.

    When called from within a running event loop (e.g. Quart web server),
    ``loop.run_until_complete()`` raises ``RuntimeError``. This helper
    detects that situation and runs the coroutine in a background thread
    with its own event loop instead.
    """
    import concurrent.futures

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
