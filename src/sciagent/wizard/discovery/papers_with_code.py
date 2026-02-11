"""
Papers With Code discovery — search for methods/repos with linked papers.

Uses the public Papers With Code API v1:
https://paperswithcode.com/api/v1/
"""

from __future__ import annotations

import logging
import re
from typing import List

from ..models import DiscoverySource, PackageCandidate

logger = logging.getLogger(__name__)

_API_BASE = "https://paperswithcode.com/api/v1"


async def search_papers_with_code(
    keywords: List[str],
    *,
    max_results: int = 20,
) -> List[PackageCandidate]:
    """Search Papers With Code for repositories linked to domain papers.

    Strategy:
    1. Search papers by keyword.
    2. For papers with linked repositories, extract the repo and any
       associated Python package.

    Args:
        keywords: Domain-related search terms.
        max_results: Cap on returned candidates.

    Returns:
        List of ``PackageCandidate``.
    """
    import httpx

    candidates: List[PackageCandidate] = []
    seen_repos: set[str] = set()
    query = " ".join(keywords)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # ── Search papers ───────────────────────────────────────
            resp = await client.get(
                f"{_API_BASE}/papers/",
                params={"q": query, "items_per_page": str(min(max_results * 2, 50))},
                follow_redirects=True,
            )
            if resp.status_code != 200:
                logger.warning("Papers With Code papers endpoint returned %d", resp.status_code)
                return []

            data = resp.json()
            papers = data.get("results", [])

            for paper in papers:
                paper_id = paper.get("id")
                if not paper_id:
                    continue

                # Fetch repos for this paper
                try:
                    repo_resp = await client.get(
                        f"{_API_BASE}/papers/{paper_id}/repositories/",
                        follow_redirects=True,
                    )
                    if repo_resp.status_code != 200:
                        continue
                    repos = repo_resp.json().get("results", [])
                except Exception:
                    continue

                for repo in repos:
                    repo_url = repo.get("url", "")
                    if not repo_url or repo_url in seen_repos:
                        continue
                    seen_repos.add(repo_url)

                    is_official = repo.get("is_official", False)
                    stars = repo.get("stars", 0) or 0
                    framework = repo.get("framework", "") or ""

                    cand = _build_candidate(
                        paper=paper,
                        repo_url=repo_url,
                        is_official=is_official,
                        stars=stars,
                        framework=framework,
                        keywords=keywords,
                    )
                    candidates.append(cand)

                    if len(candidates) >= max_results:
                        return candidates

    except Exception as exc:
        logger.warning("Papers With Code search failed: %s", exc)

    return candidates[:max_results]


def _build_candidate(
    paper: dict,
    repo_url: str,
    is_official: bool,
    stars: int,
    framework: str,
    keywords: List[str],
) -> PackageCandidate:
    """Build a ``PackageCandidate`` from a paper+repo pair."""
    title = paper.get("title", "") or ""
    abstract = paper.get("abstract", "") or ""
    arxiv_id = paper.get("arxiv_id", "")
    url_abs = paper.get("url_abs", "") or ""

    # Guess package name from repo URL (last path component)
    repo_name = repo_url.rstrip("/").split("/")[-1] if repo_url else ""

    # Relevance
    search_text = f"{title} {abstract} {repo_name}".lower()
    hit_count = sum(1 for kw in keywords if kw.lower() in search_text)
    relevance = min(hit_count / max(len(keywords), 1), 1.0)

    # Boost for official repos and popular ones
    if is_official:
        relevance = min(relevance + 0.1, 1.0)
    if stars > 100:
        relevance = min(relevance + 0.1, 1.0)
    if stars > 1000:
        relevance = min(relevance + 0.1, 1.0)
    if "python" in framework.lower():
        relevance = min(relevance + 0.05, 1.0)

    dois = []
    if arxiv_id:
        dois.append(f"arxiv:{arxiv_id}")

    return PackageCandidate(
        name=repo_name or title[:60],
        source=DiscoverySource.PAPERS_WITH_CODE,
        description=title[:300],
        install_command=f"pip install {repo_name}" if repo_name else "",
        homepage=url_abs or repo_url,
        repository_url=repo_url,
        citations=stars,  # use stars as a proxy
        relevance_score=round(relevance, 3),
        peer_reviewed=bool(arxiv_id),
        publication_dois=dois,
        keywords=[kw for kw in keywords if kw.lower() in search_text],
        python_package=repo_name,
    )
