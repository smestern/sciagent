"""
Data models for the docs ingestor.

Tracks scraped pages, extracted API sections, and the final rendered
library_api.md output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SourceType(str, Enum):
    """Where a scraped page originated."""

    READTHEDOCS = "readthedocs"
    GITHUB_README = "github_readme"
    GITHUB_SOURCE = "github_source"
    PYPI = "pypi"
    HOMEPAGE = "homepage"


@dataclass
class ScrapedPage:
    """A single page of documentation content."""

    url: str
    title: str
    content: str
    source_type: SourceType
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.content)


@dataclass
class IngestorState:
    """Mutable state passed to every ingestor tool handler.

    Accumulates crawled docs and LLM-extracted sections until
    ``finalize()`` assembles the completed library_api.md.
    """

    package_name: str = ""
    pip_name: str = ""
    source_url: str = ""
    docs_url: str = ""

    # LLM model for this session (for billing)
    model: str = "claude-opus-4.5"

    # Raw crawled content
    scraped_pages: List[ScrapedPage] = field(default_factory=list)
    pypi_metadata: Dict[str, str] = field(default_factory=dict)

    # Sections filled by the LLM via tools
    core_classes: str = ""
    key_functions: str = ""
    common_pitfalls: str = ""
    recipes: str = ""

    # Final output
    final_markdown: Optional[str] = None

    @property
    def total_scraped_chars(self) -> int:
        return sum(p.char_count for p in self.scraped_pages)

    @property
    def sections_filled(self) -> List[str]:
        """Return names of sections the LLM has submitted."""
        filled = []
        if self.core_classes:
            filled.append("core_classes")
        if self.key_functions:
            filled.append("key_functions")
        if self.common_pitfalls:
            filled.append("common_pitfalls")
        if self.recipes:
            filled.append("recipes")
        return filled

    def to_dict(self) -> dict:
        return {
            "package_name": self.package_name,
            "pip_name": self.pip_name,
            "source_url": self.source_url,
            "docs_url": self.docs_url,
            "pages_scraped": len(self.scraped_pages),
            "total_chars": self.total_scraped_chars,
            "sections_filled": self.sections_filled,
            "finalized": self.final_markdown is not None,
            "model": self.model,
        }
