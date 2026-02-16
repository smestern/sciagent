"""
Data models shared across the wizard subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ── Discovery models ────────────────────────────────────────────────────


class OutputMode(str, Enum):
    """Which output format the wizard should generate."""

    FULLSTACK = "fullstack"          # Full Python submodule (current mode)
    COPILOT_AGENT = "copilot_agent"  # VS Code .agent.md + Claude .md configs
    MARKDOWN = "markdown"            # Platform-agnostic markdown specification


class WizardPhase(str, Enum):
    """Tracks progress through the guided wizard flow."""

    INTAKE = "intake"              # Collecting initial form data
    DISCOVERY = "discovery"        # Searching for packages
    REFINEMENT = "refinement"      # Presenting & confirming packages
    CONFIGURATION = "configuration"  # Naming the agent, setting guardrails
    GENERATION = "generation"      # Generating output
    COMPLETE = "complete"          # Done


@dataclass
class PendingQuestion:
    """A structured question awaiting the user's response."""

    question: str
    options: List[str] = field(default_factory=list)
    allow_freetext: bool = False
    max_length: int = 100
    allow_multiple: bool = False
    field_name: str = ""  # optional: which WizardState field this populates


class DiscoverySource(str, Enum):
    """Where a package candidate was found."""

    PYPI = "pypi"
    BIOTOOLS = "bio.tools"
    PAPERS_WITH_CODE = "papers_with_code"
    PUBMED = "pubmed"
    GOOGLE_CSE = "google_cse"
    USER = "user"  # manually specified by the researcher


@dataclass
class PackageCandidate:
    """A discovered software package that may be useful in the researcher's domain."""

    name: str
    source: DiscoverySource
    description: str = ""
    install_command: str = ""  # e.g. "pip install neo"
    homepage: str = ""
    repository_url: str = ""
    citations: int = 0
    downloads: int = 0
    relevance_score: float = 0.0  # 0–1, higher = more relevant
    peer_reviewed: bool = False
    publication_dois: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    python_package: str = ""  # actual PyPI package name if different from name

    @property
    def pip_name(self) -> str:
        """The name to use with ``pip install``."""
        return self.python_package or self.name

    def merge(self, other: "PackageCandidate") -> "PackageCandidate":
        """Merge another candidate for the same package (union of metadata)."""
        return PackageCandidate(
            name=self.name,
            source=self.source,  # keep original source
            description=self.description or other.description,
            install_command=self.install_command or other.install_command,
            homepage=self.homepage or other.homepage,
            repository_url=self.repository_url or other.repository_url,
            citations=max(self.citations, other.citations),
            downloads=max(self.downloads, other.downloads),
            relevance_score=max(self.relevance_score, other.relevance_score),
            peer_reviewed=self.peer_reviewed or other.peer_reviewed,
            publication_dois=list(set(self.publication_dois + other.publication_dois)),
            keywords=list(set(self.keywords + other.keywords)),
            python_package=self.python_package or other.python_package,
        )


# ── Wizard state ────────────────────────────────────────────────────────


@dataclass
class DataFileInfo:
    """Metadata inferred from an uploaded example data file."""

    path: str
    extension: str
    columns: List[str] = field(default_factory=list)
    dtypes: Dict[str, str] = field(default_factory=dict)
    row_count: int = 0
    value_ranges: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    inferred_domain_hints: List[str] = field(default_factory=list)


@dataclass
class WizardState:
    """Accumulated state throughout the wizard conversation.

    Passed to the generator to produce the final agent project.
    """

    # ─ Researcher input ─────────────────────────────────────────────
    domain_description: str = ""
    research_goals: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    preferred_packages: List[str] = field(default_factory=list)

    # ─ Example data analysis ────────────────────────────────────────
    example_files: List[DataFileInfo] = field(default_factory=list)
    accepted_file_types: List[str] = field(default_factory=list)

    # ─ Discovery results ────────────────────────────────────────────
    all_candidates: List[PackageCandidate] = field(default_factory=list)
    confirmed_packages: List[PackageCandidate] = field(default_factory=list)

    # ─ Generated agent identity ─────────────────────────────────────
    agent_name: str = ""
    agent_display_name: str = ""
    agent_description: str = ""
    agent_emoji: str = "🔬"

    # ─ Guardrails derived from data ─────────────────────────────────
    bounds: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    forbidden_patterns: List[Tuple[str, str]] = field(default_factory=list)
    warning_patterns: List[Tuple[str, str]] = field(default_factory=list)

    # ─ Generated content (filled by generator) ──────────────────────
    domain_prompt: str = ""
    suggestion_chips: List[Tuple[str, str]] = field(default_factory=list)  # (label, prompt)

    # ─ Package documentation (fetched after confirmation) ───────────
    package_docs: Dict[str, str] = field(default_factory=dict)  # pkg name → markdown doc

    # ─ Output ───────────────────────────────────────────────────────
    output_mode: "OutputMode" = None  # type: ignore[assignment]  # set post-init
    output_dir: str = ""
    project_dir: str = ""

    # ─ Guided / public mode ─────────────────────────────────────────
    guided_mode: bool = False
    phase: "WizardPhase" = None  # type: ignore[assignment]  # set post-init
    data_types: List[str] = field(default_factory=list)
    analysis_goals: List[str] = field(default_factory=list)
    experience_level: str = ""  # beginner / intermediate / advanced
    pending_question: Optional["PendingQuestion"] = None

    def __post_init__(self):
        if self.output_mode is None:
            self.output_mode = OutputMode.FULLSTACK
        if self.phase is None:
            self.phase = WizardPhase.INTAKE

    def to_dict(self) -> Dict[str, Any]:
        """Serialise for LLM tool results / JSON storage."""
        d = {
            "domain_description": self.domain_description,
            "research_goals": self.research_goals,
            "keywords": self.keywords,
            "agent_name": self.agent_name,
            "agent_display_name": self.agent_display_name,
            "agent_description": self.agent_description,
            "accepted_file_types": self.accepted_file_types,
            "confirmed_packages": [
                {"name": p.name, "description": p.description, "source": p.source.value}
                for p in self.confirmed_packages
            ],
            "example_files": [
                {"path": f.path, "columns": f.columns, "rows": f.row_count}
                for f in self.example_files
            ],
            "bounds": self.bounds,
            "output_mode": self.output_mode.value,
            "package_docs_count": len(self.package_docs),
            "output_dir": self.output_dir,
            "project_dir": self.project_dir,
            "phase": self.phase.value,
            "guided_mode": self.guided_mode,
            "data_types": self.data_types,
            "analysis_goals": self.analysis_goals,
            "experience_level": self.experience_level,
        }
        return d
