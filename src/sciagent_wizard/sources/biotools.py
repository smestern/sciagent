"""
bio.tools discovery — search the ELIXIR bio.tools registry.

bio.tools is a curated registry of bioscience software with EDAM ontology
annotations. Its REST API is open and well-documented:
https://bio.tools/api/tool/
"""

from __future__ import annotations

import logging
from typing import List

from sciagent_wizard.models import DiscoverySource, PackageCandidate

logger = logging.getLogger(__name__)

_API_BASE = "https://bio.tools/api/tool/"


async def search_biotools(
    keywords: List[str],
    *,
    max_results: int = 20,
) -> List[PackageCandidate]:
    """Search the bio.tools registry for tools matching *keywords*.

    Args:
        keywords: Domain-related search terms.
        max_results: Cap on returned candidates.

    Returns:
        List of ``PackageCandidate`` from bio.tools.
    """
    import httpx

    candidates: List[PackageCandidate] = []
    query = " ".join(keywords)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                _API_BASE,
                params={
                    "q": query,
                    "format": "json",
                    "page": "1",
                    "sort": "score",
                },
                follow_redirects=True,
            )
            if resp.status_code != 200:
                logger.warning("bio.tools returned %d", resp.status_code)
                return []

            data = resp.json()
            tools = data.get("list", [])

            for tool in tools[:max_results]:
                cand = _parse_tool(tool, keywords)
                if cand is not None:
                    candidates.append(cand)

    except Exception as exc:
        logger.warning("bio.tools search failed: %s", exc)

    return candidates


def _parse_tool(tool: dict, keywords: List[str]) -> PackageCandidate | None:
    """Convert a bio.tools API result into a ``PackageCandidate``."""
    name = tool.get("name", "")
    if not name:
        return None

    description = tool.get("description", "") or ""
    homepage = tool.get("homepage", "") or ""

    # Extract publication DOIs
    pubs = tool.get("publication", []) or []
    dois = []
    for pub in pubs:
        doi = pub.get("doi")
        if doi:
            dois.append(doi)

    # Extract topics (EDAM ontology terms)
    topics = tool.get("topic", []) or []
    topic_labels = [t.get("term", "") for t in topics if t.get("term")]

    # Check for Python in language list
    languages = tool.get("language", []) or []
    has_python = any("python" in str(lang).lower() for lang in languages)

    # Try to find a download/repository link
    links = tool.get("link", []) or []
    repo_url = ""
    for link in links:
        link_type = (link.get("type") or "").lower()
        url = link.get("url", "")
        if "repository" in link_type or "github" in link_type:
            repo_url = url
            break

    # Downloads / install info
    downloads = tool.get("download", []) or []
    install_cmd = ""
    python_package = ""
    for dl in downloads:
        dl_type = (dl.get("type") or "").lower()
        dl_url = dl.get("url", "")
        if "package" in dl_type and "pypi" in dl_url.lower():
            # Extract package name from PyPI URL
            parts = dl_url.rstrip("/").split("/")
            python_package = parts[-1] if parts else ""
            install_cmd = f"pip install {python_package}"
            break

    if not install_cmd and has_python:
        # Guess: package name is often the lowercase tool name
        python_package = name.lower().replace(" ", "-")
        install_cmd = f"pip install {python_package}"

    # Relevance scoring
    search_text = f"{name} {description} {' '.join(topic_labels)}".lower()
    hit_count = sum(1 for kw in keywords if kw.lower() in search_text)
    relevance = min(hit_count / max(len(keywords), 1), 1.0)

    # Boost for having publications (peer reviewed)
    if dois:
        relevance = min(relevance + 0.15, 1.0)

    # Boost if Python is listed
    if has_python:
        relevance = min(relevance + 0.1, 1.0)

    return PackageCandidate(
        name=name,
        source=DiscoverySource.BIOTOOLS,
        description=description[:300],
        install_command=install_cmd,
        homepage=homepage,
        repository_url=repo_url,
        relevance_score=round(relevance, 3),
        peer_reviewed=len(dois) > 0,
        publication_dois=dois,
        keywords=topic_labels,
        python_package=python_package,
    )
