"""
Ranking and deduplication for multi-source package discovery.

Combines results from PyPI, bio.tools, Papers With Code, SciCrunch,
and PubMed into a single ranked list, boosting packages that appear
across multiple sources.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from ..models import DiscoverySource, PackageCandidate

logger = logging.getLogger(__name__)

# Bonus for each additional source that confirms a candidate
_MULTI_SOURCE_BOOST = 0.12

# Minimum relevance to keep a candidate in the final list
_MIN_RELEVANCE = 0.05


def rank_and_deduplicate(
    candidates: List[PackageCandidate],
) -> List[PackageCandidate]:
    """Merge duplicates and sort by composite relevance score.

    Deduplication key: normalised ``pip_name`` (lowercased, hyphens
    collapsed).  When two candidates refer to the same package, their
    metadata is merged and a multi-source bonus is applied.

    Args:
        candidates: Raw candidates from all discovery sources.

    Returns:
        Sorted list (highest relevance first), deduplicated.
    """
    buckets: dict[str, list[PackageCandidate]] = {}

    for cand in candidates:
        key = _normalise_key(cand)
        buckets.setdefault(key, []).append(cand)

    merged: list[PackageCandidate] = []
    for key, group in buckets.items():
        best = group[0]
        sources_seen: set[DiscoverySource] = {best.source}

        for other in group[1:]:
            best = best.merge(other)
            sources_seen.add(other.source)

        # Multi-source boost
        extra = max(0, len(sources_seen) - 1) * _MULTI_SOURCE_BOOST
        best.relevance_score = min(round(best.relevance_score + extra, 3), 1.0)

        if best.relevance_score >= _MIN_RELEVANCE:
            merged.append(best)

    # Sort: relevance descending, then citations descending, then name
    merged.sort(key=lambda c: (-c.relevance_score, -c.citations, c.name.lower()))
    return merged


def _normalise_key(cand: PackageCandidate) -> str:
    """Produce a stable deduplication key from a candidate."""
    raw = cand.pip_name or cand.name
    return raw.lower().replace("_", "-").replace(" ", "-").strip("-")


# ── Public one-shot helper ──────────────────────────────────────────────


async def discover_packages(
    keywords: List[str],
    *,
    max_per_source: int = 20,
    sources: Optional[List[str]] = None,
) -> List[PackageCandidate]:
    """Run all discovery sources in parallel and return ranked results.

    This is the main entry point used by the wizard agent's
    ``search_packages`` tool.

    Args:
        keywords: Domain-related search terms.
        max_per_source: Per-source result cap.
        sources: Subset of source names to query (default: all).
            Valid names: ``"pypi"``, ``"biotools"``, ``"papers_with_code"``,
            ``"scicrunch"``, ``"pubmed"``.

    Returns:
        Ranked, deduplicated list of ``PackageCandidate``.
    """
    from .pypi import search_pypi
    from .biotools import search_biotools
    from .papers_with_code import search_papers_with_code
    from .scicrunch import search_scicrunch
    from .pubmed import search_pubmed

    source_map = {
        "pypi": search_pypi,
        "biotools": search_biotools,
        "papers_with_code": search_papers_with_code,
        "scicrunch": search_scicrunch,
        "pubmed": search_pubmed,
    }

    active = sources or list(source_map.keys())

    # Launch searches concurrently
    tasks = []
    task_names = []
    for name in active:
        fn = source_map.get(name)
        if fn is None:
            logger.warning("Unknown source: %s", name)
            continue
        tasks.append(fn(keywords, max_results=max_per_source))
        task_names.append(name)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_candidates: list[PackageCandidate] = []
    for name, result in zip(task_names, results):
        if isinstance(result, Exception):
            logger.warning("Source %s failed: %s", name, result)
            continue
        logger.info("Source %s returned %d candidates", name, len(result))
        all_candidates.extend(result)

    ranked = rank_and_deduplicate(all_candidates)
    logger.info(
        "Discovery complete: %d raw → %d ranked candidates",
        len(all_candidates),
        len(ranked),
    )
    return ranked
