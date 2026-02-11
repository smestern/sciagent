"""
SciCrunch / RRID discovery — search for Research Resource Identifiers.

SciCrunch aggregates scientific resource registries. The public API
is at https://scicrunch.org/api/
"""

from __future__ import annotations

import logging
import os
from typing import List

from ..models import DiscoverySource, PackageCandidate

logger = logging.getLogger(__name__)

_API_BASE = "https://scicrunch.org/api/1"


async def search_scicrunch(
    keywords: List[str],
    *,
    max_results: int = 15,
) -> List[PackageCandidate]:
    """Search SciCrunch for scientific software resources.

    Note: SciCrunch may require an API key for full results. Set the
    environment variable ``SCICRUNCH_API_KEY`` if you have one. Without
    a key the search still works but may return fewer results.

    Args:
        keywords: Domain-related search terms.
        max_results: Cap on returned candidates.

    Returns:
        List of ``PackageCandidate``.
    """
    import httpx

    candidates: List[PackageCandidate] = []
    api_key = os.environ.get("SCICRUNCH_API_KEY", "")
    query = " ".join(keywords)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            params = {
                "q": query,
                "l": str(max_results),
                "type": "tool",  # filter to software tools
            }
            if api_key:
                params["key"] = api_key

            resp = await client.get(
                f"{_API_BASE}/resource/fields/search",
                params=params,
                follow_redirects=True,
            )
            if resp.status_code != 200:
                logger.warning("SciCrunch returned %d", resp.status_code)
                return []

            data = resp.json()
            results = data.get("result", [])
            if isinstance(results, dict):
                results = results.get("results", [])

            for entry in results[:max_results]:
                cand = _parse_entry(entry, keywords)
                if cand:
                    candidates.append(cand)

    except Exception as exc:
        logger.warning("SciCrunch search failed: %s", exc)

    return candidates


def _parse_entry(entry: dict, keywords: List[str]) -> PackageCandidate | None:
    """Parse a SciCrunch search result."""
    # SciCrunch results have varying schemas—be defensive
    fields = entry if isinstance(entry, dict) else {}
    name = (
        fields.get("name")
        or fields.get("resource_name")
        or fields.get("title")
        or ""
    )
    if not name:
        return None

    description = fields.get("description", "") or fields.get("summary", "") or ""
    url = fields.get("url", "") or fields.get("homepage", "") or ""
    rrid = fields.get("rrid", "") or fields.get("RRID", "") or ""

    # Try to identify if it's a Python package
    description_lower = description.lower()
    has_python = "python" in description_lower or "pip install" in description_lower

    # Guess a pip name
    python_package = ""
    install_cmd = ""
    if has_python:
        python_package = name.lower().replace(" ", "-").replace("_", "-")
        install_cmd = f"pip install {python_package}"

    # Relevance
    search_text = f"{name} {description}".lower()
    hit_count = sum(1 for kw in keywords if kw.lower() in search_text)
    relevance = min(hit_count / max(len(keywords), 1), 1.0)

    if rrid:
        relevance = min(relevance + 0.1, 1.0)

    return PackageCandidate(
        name=name,
        source=DiscoverySource.SCICRUNCH,
        description=description[:300],
        install_command=install_cmd,
        homepage=url,
        relevance_score=round(relevance, 3),
        peer_reviewed=bool(rrid),
        keywords=[kw for kw in keywords if kw.lower() in search_text],
        python_package=python_package,
    )
