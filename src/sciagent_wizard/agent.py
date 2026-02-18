"""
WizardAgent — The self-assembly wizard is itself a scientific agent.

It uses LLM-driven conversation to interview the researcher about their
domain, discover relevant packages, analyze example data, and generate
a fully functional domain-specific agent project.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sciagent.base_agent import BaseScientificAgent, _create_tool
from sciagent.config import AgentConfig, SuggestionChip
from sciagent.prompts.base_messages import build_system_message

from .models import OutputMode, PendingQuestion, SUPPORTED_MODELS, WizardPhase, WizardState
from .prompts import WIZARD_EXPERTISE, PUBLIC_WIZARD_EXPERTISE
from . import tools as wizard_tools

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
        logger.info(
            "[WizardAgent] Created: guided_mode=%s, "
            "wizard_state id=%s",
            guided_mode, id(self._wizard_state),
        )
        super().__init__(WIZARD_CONFIG, **kwargs)

    @property
    def wizard_state(self) -> WizardState:
        return self._wizard_state

    @property
    def model(self) -> str:
        """Return the current model from wizard state (allows dynamic switching)."""
        return self._wizard_state.model

    @model.setter
    def model(self, value: str) -> None:
        """Update the model in wizard state."""
        self._wizard_state.model = value

    # ── Tool registration ───────────────────────────────────────────

    def _load_tools(self) -> List:
        state = self._wizard_state

        tools = [
            # ─ Model selection (for billing) ────────────────────────
            _create_tool(
                "set_model",
                (
                    "Set the LLM model for this wizard session. This controls "
                    "which model handles the conversation (for billing). Does "
                    "NOT affect the generated agent's model. Offer this choice "
                    "at the start of the conversation if the user wants to "
                    "change from the default (claude-opus-4.5)."
                ),
                lambda **kw: wizard_tools.tool_set_model(state, **kw),
                {
                    "type": "object",
                    "properties": {
                        "model": {
                            "type": "string",
                            "enum": list(SUPPORTED_MODELS),
                            "description": (
                                "The LLM model to use for this wizard session."
                            ),
                        },
                    },
                    "required": ["model"],
                },
            ),

            # ─ Discovery ────────────────────────────────────────────
            _create_tool(
                "search_packages",
                (
                    "Search peer-reviewed databases (PyPI, bio.tools, Papers "
                    "With Code, PubMed) and the web (Google CSE) for "
                    "scientific software relevant to the researcher's domain. "
                    "Returns ranked results with descriptions and relevance "
                    "scores. Call this after learning about the researcher's "
                    "domain.\n\n"
                    "IMPORTANT — search strategy:\n"
                    "• 'keywords' feeds database-style sources (PyPI, "
                    "bio.tools) that work well with individual terms.\n"
                    "• 'search_queries' feeds web search (Google CSE). "
                    "Provide 2–3 short, targeted phrases a human would type "
                    "into Google to find the right software. Each phrase "
                    "should combine a domain term with an intent word like "
                    "'python package', 'analysis software', or 'python "
                    "library'.\n"
                    "  Example — for an electrophysiology researcher:\n"
                    "    keywords: ['electrophysiology', 'patch-clamp', "
                    "'ABF', 'action potential', 'ion channel']\n"
                    "    search_queries: [\n"
                    "      'electrophysiology patch clamp python package',\n"
                    "      'ABF file analysis software python',\n"
                    "      'ion channel kinetics fitting python library'\n"
                    "    ]"
                ),
                lambda **kw: wizard_tools.tool_search_packages(state, **kw),
                {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Domain-specific search keywords. Include the "
                                "field name, key techniques, data types, and "
                                "any known software names. These feed "
                                "database-style sources (PyPI, bio.tools, "
                                "PubMed, Papers With Code)."
                            ),
                        },
                        "search_queries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "2–3 targeted search phrases for web search "
                                "(Google CSE). Each should be a short, "
                                "natural-language phrase (3–6 words) that a "
                                "human would type into Google to find "
                                "relevant software. Combine a "
                                "domain/technique "
                                "term with a software-intent word like "
                                "'python package', 'analysis software', or "
                                "'python library'. If omitted, phrases are "
                                "auto-generated from keywords."
                            ),
                        },
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Which databases to search. Options: pypi, "
                                "biotools, papers_with_code, pubmed, "
                                "google_cse. Default: all."
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
                lambda **kw: wizard_tools.tool_analyze_data(state, **kw),
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
                lambda **kw: wizard_tools.tool_show_recommendations(state),
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
                lambda **kw: wizard_tools.tool_confirm_packages(state, **kw),
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
                lambda **kw: wizard_tools.tool_set_identity(state, **kw),
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
                lambda **kw: wizard_tools.tool_generate(state, **kw),
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
                lambda **kw: wizard_tools.tool_install(state),
                {"type": "object", "properties": {}},
            ),

            # ─ Launch ───────────────────────────────────────────────
            _create_tool(
                "launch_agent",
                (
                    "Launch the generated agent in web mode. Only call after "
                    "generate_agent has succeeded."
                ),
                lambda **kw: wizard_tools.tool_launch(state, **kw),
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
                lambda **kw: wizard_tools.tool_get_state(state),
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
                lambda **kw: wizard_tools.tool_fetch_docs(state),
                {"type": "object", "properties": {}},
            ),

            # ─ Deep library API ingestion ───────────────────────────
            _create_tool(
                "ingest_library_api",
                (
                    "Deep-crawl a package's ReadTheDocs and GitHub docs, "
                    "then use an LLM to extract a structured API reference "
                    "(classes, functions, pitfalls, recipes) into the "
                    "library_api.md format. Use this after confirm_packages "
                    "for the PRIMARY library to get detailed API docs. "
                    "This is more thorough than fetch_package_docs — it "
                    "crawls API reference pages and source code, not just "
                    "the README."
                ),
                lambda **kw: wizard_tools.tool_ingest_library_api(state, **kw),
                {
                    "type": "object",
                    "properties": {
                        "package_name": {
                            "type": "string",
                            "description": (
                                "The PyPI package name to ingest docs for."
                            ),
                        },
                        "github_url": {
                            "type": "string",
                            "description": (
                                "Optional GitHub repository URL for deeper "
                                "source-code analysis."
                            ),
                        },
                    },
                    "required": ["package_name"],
                },
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
                lambda **kw: wizard_tools.tool_set_output_mode(
                    state, guided_mode=self._guided_mode, **kw
                ),
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
                lambda **kw: wizard_tools.tool_present_question(state, **kw),
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


# ── Factory ─────────────────────────────────────────────────────────────


def create_wizard(guided_mode: bool = False, **kwargs) -> WizardAgent:
    """Create a WizardAgent instance.

    Args:
        guided_mode: If True, run in public/guided mode with no freeform
            chat — users interact only via structured question cards.
        **kwargs: Forwarded to ``BaseScientificAgent.__init__``.
            Includes ``output_dir`` and optionally ``github_token``.
    """
    return WizardAgent(guided_mode=guided_mode, **kwargs)
