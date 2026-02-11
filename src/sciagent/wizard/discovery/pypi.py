"""
PyPI discovery — search for Python packages by keyword.

Uses the PyPI JSON API and the ``pypi.org/search`` HTML endpoint
(with ``xmlrpc`` fallback) to find relevant scientific packages.
"""

from __future__ import annotations

import logging
import math
import re
from typing import List
from urllib.parse import quote_plus

from ..models import DiscoverySource, PackageCandidate

logger = logging.getLogger(__name__)

# PyPI JSON API base
_PYPI_JSON = "https://pypi.org/pypi/{}/json"
_PYPI_SEARCH = "https://pypi.org/search/"

# Science-related classifiers that boost relevance
_SCIENCE_CLASSIFIERS = {
    "Topic :: Scientific/Engineering",
    "Topic :: Scientific/Engineering :: Bio-Informatics",
    "Topic :: Scientific/Engineering :: Chemistry",
    "Topic :: Scientific/Engineering :: Physics",
    "Topic :: Scientific/Engineering :: Medical Science Apps.",
    "Topic :: Scientific/Engineering :: Astronomy",
    "Topic :: Scientific/Engineering :: Mathematics",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Topic :: Scientific/Engineering :: Image Recognition",
    "Topic :: Scientific/Engineering :: Information Analysis",
}


async def search_pypi(
    keywords: List[str],
    *,
    max_results: int = 30,
) -> List[PackageCandidate]:
    """Search PyPI for packages matching *keywords*.

    Strategy:
    1. Use the XML-RPC ``search`` endpoint (broad keyword search).
    2. For top hits, fetch the JSON API for richer metadata.
    3. Score by keyword overlap + classifier match + download popularity.

    Args:
        keywords: Domain-related search terms.
        max_results: Cap on returned candidates.

    Returns:
        List of ``PackageCandidate`` (unsorted — caller should rank).
    """
    import httpx

    candidates: List[PackageCandidate] = []
    seen: set[str] = set()
    query = " ".join(keywords)

    # ── 1. HTML search (scrape package names from search results) ────
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for page in range(1, 4):  # first 3 pages
                resp = await client.get(
                    _PYPI_SEARCH,
                    params={"q": query, "page": str(page)},
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    break
                # Extract package names from search result snippets
                names = re.findall(
                    r'<span class="package-snippet__name">([^<]+)</span>',
                    resp.text,
                )
                if not names:
                    break
                for name in names:
                    clean = name.strip()
                    if clean and clean.lower() not in seen:
                        seen.add(clean.lower())
                        candidates.append(_stub_candidate(clean))
                if len(candidates) >= max_results * 2:
                    break
    except Exception as exc:
        logger.warning("PyPI HTML search failed: %s", exc)

    # ── 2. Enrich top candidates via JSON API ───────────────────────
    enriched: List[PackageCandidate] = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for cand in candidates[: max_results * 2]:
                try:
                    resp = await client.get(
                        _PYPI_JSON.format(quote_plus(cand.name))
                    )
                    if resp.status_code != 200:
                        enriched.append(cand)
                        continue
                    data = resp.json()
                    enriched.append(_parse_json_api(data, keywords))
                except Exception:
                    enriched.append(cand)
    except Exception as exc:
        logger.warning("PyPI JSON enrichment failed: %s", exc)
        enriched = candidates  # fall back to stubs

    return enriched[:max_results]


def _stub_candidate(name: str) -> PackageCandidate:
    return PackageCandidate(
        name=name,
        source=DiscoverySource.PYPI,
        install_command=f"pip install {name}",
        python_package=name,
    )


def _parse_json_api(data: dict, keywords: List[str]) -> PackageCandidate:
    """Parse a PyPI JSON API response into a ``PackageCandidate``."""
    info = data.get("info", {})
    name = info.get("name", "")
    summary = info.get("summary", "") or ""
    description = info.get("description", "") or ""
    home_page = info.get("home_page", "") or info.get("project_url", "") or ""
    classifiers = info.get("classifiers", [])
    project_urls = info.get("project_urls") or {}

    repo_url = (
        project_urls.get("Source")
        or project_urls.get("Repository")
        or project_urls.get("GitHub")
        or project_urls.get("Code")
        or ""
    )

    # Keyword relevance scoring
    search_text = f"{name} {summary} {description}".lower()
    keyword_hits = sum(1 for kw in keywords if kw.lower() in search_text)
    kw_score = min(keyword_hits / max(len(keywords), 1), 1.0)

    # Science classifier bonus
    classifier_set = set(classifiers)
    sci_overlap = len(classifier_set & _SCIENCE_CLASSIFIERS)
    sci_score = min(sci_overlap / 3, 1.0)  # cap at 1

    relevance = 0.6 * kw_score + 0.4 * sci_score

    return PackageCandidate(
        name=name,
        source=DiscoverySource.PYPI,
        description=summary[:300],
        install_command=f"pip install {name}",
        homepage=home_page,
        repository_url=repo_url,
        relevance_score=round(relevance, 3),
        keywords=[kw for kw in keywords if kw.lower() in search_text],
        python_package=name,
    )
