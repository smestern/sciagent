"""
AgentConfig — Configuration dataclass for scientific agents.

Centralises all domain-specific settings so generic infrastructure
(CLI, web UI, guardrails) can be parameterized without subclassing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SuggestionChip:
    """A labelled example prompt shown in the web UI / CLI help."""

    label: str
    prompt: str


@dataclass
class AgentConfig:
    """Configuration for a scientific coding agent.

    Attributes:
        name:              Machine-friendly slug (e.g. ``"patch-analyst"``).
        display_name:      Human-friendly title shown in UI.
        description:       One-line description of the agent's purpose.
        instructions:      Extra instructions appended to the
                           ``CustomAgentConfig.prompt`` sent to the SDK.
        accepted_file_types:
            File extensions the web upload/CLI will accept
            (e.g. ``[".csv", ".xlsx"]``).
        suggestion_chips:  Example prompts rendered in the web sidebar / CLI help.
        bounds:            Domain-specific sanity-check ranges, keyed by
                           parameter name → ``(lower, upper)`` tuple.
        forbidden_patterns:
            Extra regex+message pairs *added* to the default
            ``CodeScanner`` forbidden list.
        warning_patterns:
            Extra regex+message pairs *added* to the default
            ``CodeScanner`` warning list.
        extra_libraries:   Additional module-name → import-alias pairs
                           injected into the code sandbox environment.
        model:             Default LLM model name.
        output_dir:        Base directory for saving scripts/plots.
                           ``None`` → use a temp directory.
        logo_emoji:        Emoji for the CLI banner & web header.
        accent_color:      CSS hex colour for the web UI accent.
        github_url:        Optional link shown in the web header.
    """

    # Identity
    name: str = "sci-agent"
    display_name: str = "Scientific Analysis Agent"
    description: str = "An AI-powered scientific analysis assistant"

    # Prompt / instructions (domain expertise injected here)
    instructions: str = ""

    # File handling
    accepted_file_types: List[str] = field(default_factory=lambda: [".csv"])

    # UX
    suggestion_chips: List[SuggestionChip] = field(default_factory=list)
    logo_emoji: str = "🔬"
    accent_color: str = "#58a6ff"
    github_url: Optional[str] = None

    # Guardrails
    bounds: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    forbidden_patterns: List[Tuple[str, str]] = field(default_factory=list)
    warning_patterns: List[Tuple[str, str]] = field(default_factory=list)
    rigor_level: str = "standard"
    """Rigor enforcement level: ``"strict"``, ``"standard"``,
    ``"relaxed"``, or ``"bypass"``.  See
    :class:`~sciagent.guardrails.scanner.RigorLevel` for semantics."""
    intercept_all_tools: bool = True
    """When ``True``, every tool invocation is scanned for code-like
    strings that might bypass the sandbox (e.g. shell commands).  Set
    ``False`` to disable the middleware."""

    # Sandbox
    extra_libraries: Dict[str, str] = field(default_factory=dict)

    # Documentation
    docs_dir: Optional[str] = None

    # Runtime
    model: str = "claude-opus-4.5"
    output_dir: Optional[str] = None
