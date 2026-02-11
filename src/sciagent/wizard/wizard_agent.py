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

from .models import DiscoverySource, PackageCandidate, WizardState

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


# ── Wizard system prompt ───────────────────────────────────────────────

WIZARD_EXPERTISE = """\
## Self-Assembly Wizard — Agent Builder

You are the SciAgent Self-Assembly Wizard. Your job is to help
non-programmer researchers build their own domain-specific scientific
analysis agent.

### Your Workflow

1. **Interview** — Ask the researcher to describe:
   - Their scientific domain and sub-field
   - What kinds of data they work with (file formats, structure)
   - What analyses they typically perform
   - What software tools they already know about or use
   - Their research goals

2. **Discover** — Use `search_packages` to find relevant scientific
   software from peer-reviewed databases. Present results and explain
   what each package does.

3. **Analyze Example Data** — If the researcher provides example files,
   use `analyze_example_data` to understand the data structure and
   suggest appropriate tools.

4. **Recommend** — Use `show_recommendations` to present a curated
   list of packages. Explain why each is relevant. Let the researcher
   add or remove packages.

5. **Confirm** — Use `confirm_packages` to lock in the package selection.
   The researcher must explicitly agree before proceeding.

6. **Configure** — Use `set_agent_identity` to name the agent and give
   it a personality (emoji, description).

7. **Generate** — Use `generate_agent` to create the agent project.
   Show the researcher what was created and how to use it.

8. **Install & Launch** — Offer to install packages with
   `install_packages` and launch the agent with `launch_agent`.

### Important

- Be conversational and friendly — the researcher is NOT a programmer
- Explain technical concepts simply
- Always show what you're doing and why
- Never skip the confirmation step
- If the researcher mentions specific packages they want, add those too
- Suggest sensible defaults but let the researcher decide
"""


class WizardAgent(BaseScientificAgent):
    """The wizard agent that builds other agents."""

    def __init__(self, **kwargs):
        # The wizard manages its own state across the conversation
        self._wizard_state = WizardState()
        super().__init__(WIZARD_CONFIG, **kwargs)

    @property
    def wizard_state(self) -> WizardState:
        return self._wizard_state

    # ── Tool registration ───────────────────────────────────────────

    def _load_tools(self) -> List:
        state = self._wizard_state

        return [
            # ─ Discovery ────────────────────────────────────────────
            _create_tool(
                "search_packages",
                (
                    "Search peer-reviewed databases (PyPI, bio.tools, Papers "
                    "With Code, SciCrunch, PubMed) for scientific software "
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
                                "biotools, papers_with_code, scicrunch, pubmed. "
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
        ]

    # ── System message ──────────────────────────────────────────────

    def _get_system_message(self) -> str:
        return build_system_message(
            WIZARD_EXPERTISE,
            # Disable policies that don't apply to the wizard
            code_policy=False,
            output_dir_policy=False,
            reproducible_script_policy=False,
        )

    # ── Tool implementations ────────────────────────────────────────

    def _tool_search_packages(
        self,
        keywords: List[str],
        sources: Optional[List[str]] = None,
    ) -> str:
        """Search for domain-specific packages."""
        from .discovery.ranker import discover_packages

        loop = _get_or_create_loop()
        candidates = loop.run_until_complete(
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

        return json.dumps({
            "status": "generated",
            "project_dir": str(project_path),
            "files": [str(p.name) for p in project_path.iterdir() if p.is_file()],
            "instructions": {
                "cli": f"python -m {state.agent_name.replace('-', '_')}",
                "web": f"python -m {state.agent_name.replace('-', '_')} --web",
                "install": f"pip install -r {project_path / 'requirements.txt'}",
            },
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


# ── Factory ─────────────────────────────────────────────────────────────


def create_wizard(**kwargs) -> WizardAgent:
    """Create a WizardAgent instance."""
    return WizardAgent(**kwargs)


# ── Helpers ─────────────────────────────────────────────────────────────


def _get_or_create_loop() -> asyncio.AbstractEventLoop:
    """Get the running event loop or create a new one."""
    try:
        loop = asyncio.get_running_loop()
        # We're inside an async context — create a nested runner
        import concurrent.futures
        # Run in a thread pool to avoid blocking the event loop
        # This is a pragmatic workaround for sync tool handlers
        # calling async discovery functions
        new_loop = asyncio.new_event_loop()
        return new_loop
    except RuntimeError:
        # No running loop — normal sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
