"""
sciagent.wizard.discovery — Multi-source scientific software discovery.

Search peer-reviewed databases for domain-relevant software and rank
results into a unified list of ``PackageCandidate`` objects.
"""

from .pypi import search_pypi
from .biotools import search_biotools
from .papers_with_code import search_papers_with_code
from .scicrunch import search_scicrunch
from .pubmed import search_pubmed
from .ranker import rank_and_deduplicate, discover_packages

__all__ = [
    "search_pypi",
    "search_biotools",
    "search_papers_with_code",
    "search_scicrunch",
    "search_pubmed",
    "rank_and_deduplicate",
    "discover_packages",
]
