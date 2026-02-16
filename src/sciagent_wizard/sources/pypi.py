"""
PyPI discovery — search for Python packages by keyword.

Uses the PyPI JSON API and Simple Index to find relevant scientific
packages.  The HTML search endpoint (``pypi.org/search``) is avoided
because it is behind JavaScript-based bot protection that blocks
programmatic access.

Strategy
--------
1. **Simple Index scan** — stream the full package-name index (the same
   endpoint ``pip`` itself uses) and collect names matching any keyword.
2. **Name generation** — produce plausible package names from common
   scientific-Python naming conventions (``py-``, ``sci-``, ``-tools``,
   keyword pairs, etc.).
3. **JSON API enrichment** — probe ``/pypi/{name}/json`` concurrently for
   metadata, then score by keyword overlap + classifier match.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import re
from typing import List
from urllib.parse import quote_plus

from sciagent_wizard.models import DiscoverySource, PackageCandidate

logger = logging.getLogger(__name__)

# ── PyPI API endpoints ──────────────────────────────────────────────────

_PYPI_JSON = "https://pypi.org/pypi/{}/json"
# The Simple Index is not behind bot protection (pip depends on it).
_PYPI_SIMPLE_INDEX = "https://pypi.org/simple/"

# Concurrency limit for JSON-API probes
_MAX_CONCURRENT = 15

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

# Common prefixes / suffixes for scientific Python packages
_PREFIXES = ("py", "python-", "sci", "lib")
_SUFFIXES = ("-py", "-python", "-lib", "-tools", "-kit", "-utils")


# ── Public entry point ──────────────────────────────────────────────────


async def search_pypi(
    keywords: List[str],
    *,
    max_results: int = 30,
) -> List[PackageCandidate]:
    """Search PyPI for packages matching *keywords*.

    Args:
        keywords: Domain-related search terms.
        max_results: Cap on returned candidates.

    Returns:
        List of ``PackageCandidate`` sorted by relevance (highest first).
    """
    import httpx

    # ── 1. Gather candidate names from multiple strategies ──────────
    generated = _generate_candidate_names(keywords)
    logger.info(
        "PyPI: generated %d candidate names from patterns", len(generated)
    )

    # Stream Simple Index for keyword-matching names
    index_names: List[str] = []
    try:
        index_names = await _search_simple_index(
            keywords, max_names=max_results * 5
        )
        logger.info(
            "PyPI: found %d names from Simple Index", len(index_names)
        )
    except Exception as exc:
        logger.warning("PyPI Simple Index search failed: %s", exc)

    # Merge: index hits first (they are real packages), then generated names
    all_names: List[str] = list(
        dict.fromkeys(index_names + generated)
    )
    # Cap probing to avoid excessive API calls
    all_names = all_names[:max(max_results * 5, 120)]

    # ── 2. Probe JSON API concurrently ──────────────────────────────
    found: List[PackageCandidate] = []
    seen: set[str] = set()
    sem = asyncio.Semaphore(_MAX_CONCURRENT)

    async with httpx.AsyncClient(
        timeout=15, follow_redirects=True
    ) as client:

        async def _probe(name: str) -> PackageCandidate | None:
            async with sem:
                try:
                    url = _PYPI_JSON.format(quote_plus(name))
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        return _parse_json_api(resp.json(), keywords)
                except Exception as exc:
                    logger.debug("PyPI probe failed for %s: %s", name, exc)
                return None

        results = await asyncio.gather(*[_probe(n) for n in all_names])

    for cand in results:
        if cand is not None and cand.name.lower() not in seen:
            seen.add(cand.name.lower())
            found.append(cand)

    # ── 3. Sort and return ──────────────────────────────────────────
    found.sort(key=lambda c: (-c.relevance_score, c.name.lower()))
    return found[:max_results]


# ── Simple-Index streaming search ───────────────────────────────────────


async def _search_simple_index(
    keywords: List[str],
    *,
    max_names: int = 100,
) -> List[str]:
    """Stream the PyPI Simple Index and collect names containing a keyword.

    The Simple Index lists every package on PyPI.  We stream the HTML in
    chunks and check each ``<a>`` tag for keyword matches, keeping memory
    usage low.
    """
    import httpx

    # Only use keywords of 3+ chars to avoid excessive false positives.
    # Also generate truncated stems from long keywords to improve recall
    # for domain-specific terms (e.g. "neuroscience" → "neuro").
    kw_literals = _expand_keywords(
        [kw.lower() for kw in keywords if len(kw.strip()) >= 3]
    )
    if not kw_literals:
        return []

    # For short keywords (< 7 chars), require word-boundary matches to
    # avoid flooding results (e.g. "elect" matching "selects").
    # For longer keywords, substring match is specific enough.
    patterns: List[str] = []
    for kw in kw_literals:
        escaped = re.escape(kw)
        if len(kw) < 7:
            # Word-boundary: delimited by hyphen, underscore, or string edge
            patterns.append(rf"(?:^|[-_]){escaped}(?:$|[-_])")
        else:
            patterns.append(escaped)
    kw_re = re.compile("|".join(patterns))
    name_re = re.compile(r">([^<]+)</a>")

    matching: List[str] = []

    async with httpx.AsyncClient(
        timeout=120, follow_redirects=True
    ) as client:
        async with client.stream(
            "GET", _PYPI_SIMPLE_INDEX, headers={"Accept": "text/html"}
        ) as resp:
            if resp.status_code != 200:
                logger.warning("Simple Index returned %d", resp.status_code)
                return []

            buffer = ""
            async for chunk in resp.aiter_text(chunk_size=65_536):
                buffer += chunk

                # Process up to the last complete </a> tag
                last_close = buffer.rfind("</a>")
                if last_close < 0:
                    continue
                processable = buffer[:last_close + 4]
                buffer = buffer[last_close + 4:]

                for m in name_re.finditer(processable):
                    pkg_name = m.group(1).strip()
                    if kw_re.search(pkg_name.lower()):
                        matching.append(pkg_name)
                        if len(matching) >= max_names:
                            # Sort by specificity before returning
                            return _sort_index_matches(matching, kw_literals)

            # Process leftover buffer
            for m in name_re.finditer(buffer):
                pkg_name = m.group(1).strip()
                if kw_re.search(pkg_name.lower()):
                    matching.append(pkg_name)
                    if len(matching) >= max_names:
                        return _sort_index_matches(matching, kw_literals)

    return _sort_index_matches(matching, kw_literals)


# ── Name generation ─────────────────────────────────────────────────────


def _sort_index_matches(names: List[str], keywords: List[str]) -> List[str]:
    """Sort index-discovered package names by specificity.

    Packages whose names are shorter relative to the keyword length are
    treated as more relevant (e.g. ``numpy`` is more specific than
    ``accelerated-numpy-fast-io``).
    """
    kw_len = max(len(kw) for kw in keywords) if keywords else 1

    def _score(name: str) -> float:
        ratio = kw_len / max(len(name), 1)  # higher = more specific
        # Bonus if exact match with any keyword
        if name.lower() in {kw.lower() for kw in keywords}:
            return 2.0
        return ratio

    return sorted(names, key=_score, reverse=True)


def _expand_keywords(keywords: List[str]) -> List[str]:
    """Expand keywords with truncated stems for better index coverage.

    Long domain-specific keywords often don't appear verbatim in package
    names.  For example ``electrophysiology`` → ``ephys``, ``electro``;
    ``neuroscience`` → ``neuro``.  We generate stems of various lengths
    to improve recall.
    """
    expanded: set[str] = set(keywords)

    for kw in keywords:
        if len(kw) <= 7:
            continue
        # Add truncated stems (min 5 chars, skipping very short fragments
        # that match unrelated words like "elect" in "selects")
        for length in range(5, min(len(kw) // 2 + 1, len(kw))):
            stem = kw[:length]
            if len(stem) >= 5:
                expanded.add(stem)

    return sorted(expanded)


def _generate_candidate_names(keywords: List[str]) -> List[str]:
    """Produce plausible PyPI package names from *keywords*.

    Creates variations using common scientific-Python naming patterns
    (``py-``, ``sci-``, ``-lib``, keyword pairs, concatenations, etc.).
    """
    names: set[str] = set()
    # Use expanded keywords for direct lookups only (not combinations)
    all_keywords = _expand_keywords(
        [kw.lower().strip() for kw in keywords if len(kw.strip()) >= 2]
    )
    # For combinations, use only the original keywords to avoid explosion
    cleaned = [kw.lower().strip() for kw in keywords if len(kw.strip()) >= 2]

    for kw in all_keywords:
        slug = kw.replace(" ", "-")
        nodash = kw.replace("-", "").replace(" ", "")
        under = kw.replace(" ", "_").replace("-", "_")

        # Direct forms
        names.update([kw, slug, nodash, under])

        # Prefixed
        for prefix in _PREFIXES:
            names.add(f"{prefix}{nodash}")     # e.g. "pybiology"
            names.add(f"{prefix}-{slug}")      # e.g. "py-biology"
            names.add(f"{prefix}_{under}")     # e.g. "py_biology"

        # Suffixed
        for suffix in _SUFFIXES:
            names.add(f"{slug}{suffix}")       # e.g. "biology-tools"

    # Pair combinations (original keywords only, not stems)
    for kw1, kw2 in itertools.combinations(cleaned, 2):
        a = kw1.replace(" ", "")
        b = kw2.replace(" ", "")
        names.update([
            f"{a}-{b}", f"{b}-{a}",
            f"{a}_{b}", f"{b}_{a}",
            f"{a}{b}", f"{b}{a}",
        ])

    # Filter out empty / invalid package names
    valid = {
        n for n in names
        if n and len(n) >= 2 and re.match(r"^[a-zA-Z0-9]", n)
    }
    return sorted(valid)


# ── JSON-API parsing ────────────────────────────────────────────────────


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
