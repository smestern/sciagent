"""
PubMed / Europe PMC discovery — mine recent literature for software mentions.

Uses the NCBI E-utilities API (PubMed) and Europe PMC REST API to find
papers mentioning software tools in the researcher's domain.
"""

from __future__ import annotations

import logging
import re
from typing import List

from ..models import DiscoverySource, PackageCandidate

logger = logging.getLogger(__name__)

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# Patterns to extract software mentions from abstracts
_GITHUB_RE = re.compile(r"github\.com/[\w\-]+/[\w\-]+", re.IGNORECASE)
_PYPI_RE = re.compile(r"(?:pip install|pypi\.org/project/)([\w\-]+)", re.IGNORECASE)
_SOFTWARE_NAME_RE = re.compile(
    r"(?:software|package|library|tool|toolkit|framework)\s+(?:called|named|known as)\s+[\"']?(\w[\w\-]*)",
    re.IGNORECASE,
)


async def search_pubmed(
    keywords: List[str],
    *,
    max_results: int = 20,
) -> List[PackageCandidate]:
    """Search PubMed and Europe PMC for software mentioned in domain papers.

    Strategy:
    1. Search Europe PMC (richer API, includes full-text snippets).
    2. Extract GitHub URLs, PyPI package names, and explicit software
       mentions from abstracts.
    3. De-duplicate and build ``PackageCandidate`` instances.

    Args:
        keywords: Domain-related search terms.
        max_results: Cap on returned candidates.

    Returns:
        List of ``PackageCandidate``.
    """
    import httpx

    candidates: List[PackageCandidate] = []
    seen: set[str] = set()

    # Build a query that targets software/methods papers
    domain_query = " ".join(keywords)
    query = f'({domain_query}) AND (software OR package OR "open source" OR github OR python)'

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(
                _EUROPEPMC,
                params={
                    "query": query,
                    "format": "json",
                    "resultType": "core",
                    "pageSize": str(min(max_results * 3, 50)),
                    "sort": "CITED desc",
                },
                follow_redirects=True,
            )
            if resp.status_code != 200:
                logger.warning("Europe PMC returned %d", resp.status_code)
                return []

            data = resp.json()
            results = data.get("resultList", {}).get("result", [])

            for paper in results:
                title = paper.get("title", "") or ""
                abstract = paper.get("abstractText", "") or ""
                doi = paper.get("doi", "") or ""
                cited_by = paper.get("citedByCount", 0) or 0
                text = f"{title} {abstract}"

                # Extract software mentions
                for match in _extract_software(text):
                    pkg_name, repo_url, source_type = match
                    if pkg_name.lower() in seen:
                        continue
                    seen.add(pkg_name.lower())

                    # Score
                    search_lower = text.lower()
                    hit_count = sum(1 for kw in keywords if kw.lower() in search_lower)
                    relevance = min(hit_count / max(len(keywords), 1), 1.0)
                    # Boost cited papers
                    if cited_by > 10:
                        relevance = min(relevance + 0.1, 1.0)
                    if cited_by > 100:
                        relevance = min(relevance + 0.1, 1.0)

                    candidates.append(
                        PackageCandidate(
                            name=pkg_name,
                            source=DiscoverySource.PUBMED,
                            description=f"Mentioned in: {title[:200]}",
                            install_command=f"pip install {pkg_name}" if source_type != "github" else "",
                            homepage=f"https://doi.org/{doi}" if doi else "",
                            repository_url=repo_url,
                            citations=cited_by,
                            relevance_score=round(relevance, 3),
                            peer_reviewed=True,
                            publication_dois=[doi] if doi else [],
                            keywords=[kw for kw in keywords if kw.lower() in search_lower],
                            python_package=pkg_name if source_type == "pypi" else "",
                        )
                    )

                    if len(candidates) >= max_results:
                        return candidates

    except Exception as exc:
        logger.warning("PubMed/Europe PMC search failed: %s", exc)

    return candidates[:max_results]


def _extract_software(text: str) -> List[tuple]:
    """Extract (name, repo_url, source_type) tuples from text.

    Returns:
        List of (package_name, repo_url, source_type) tuples.
        source_type is one of "github", "pypi", "named".
    """
    results: list[tuple] = []

    # GitHub repos
    for match in _GITHUB_RE.finditer(text):
        url = f"https://{match.group(0)}"
        name = url.rstrip("/").split("/")[-1]
        results.append((name, url, "github"))

    # PyPI packages
    for match in _PYPI_RE.finditer(text):
        name = match.group(1)
        results.append((name, "", "pypi"))

    # Explicitly named software
    for match in _SOFTWARE_NAME_RE.finditer(text):
        name = match.group(1)
        if len(name) > 2 and name.lower() not in {"the", "our", "this", "new", "for"}:
            results.append((name, "", "named"))

    return results
