"""
Google Custom Search Engine discovery — scrape a public Google
Programmable Search Engine for scientific software results.

No API key is required.  The module uses Playwright to launch a
headless Chromium browser, navigates to the public CSE page, waits
for results to render, and extracts them from the DOM — the same
way a human user would see them in a browser.

The CSE engine ID defaults to the sciagent curated engine
(``b40081397b0ad47ec``) but can be overridden via the
``GOOGLE_CSE_CX`` environment variable.

Query Strategy
--------------
Instead of dumping all keywords into a single query, this module
runs **2–3 focused search phrases** in sequence on the same browser
session.  If the caller provides explicit ``queries`` (targeted
phrases like ``"patch clamp analysis python package"``), those are
used directly.  Otherwise, smart queries are auto-generated from
the raw ``keywords`` list by combining domain terms with software-
oriented suffixes.

Requirements
------------
``pip install playwright && python -m playwright install chromium``
"""

from __future__ import annotations

import logging
import os
import re
import urllib.parse
from typing import Any, List, Optional

from sciagent_wizard.models import DiscoverySource, PackageCandidate

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────

_DEFAULT_CX = "b40081397b0ad47ec"
_CSE_BASE = "https://cse.google.com/cse"

# Maximum number of separate queries to run per invocation
_MAX_QUERIES = 3

# Suffixes appended to domain terms when auto-generating queries
_SOFTWARE_SUFFIXES = [
    "python package",
    "analysis software",
    "python library",
]

# PyPI / GitHub patterns used to extract package names
_PYPI_RE = re.compile(
    r"pypi\.org/project/([A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
_GITHUB_RE = re.compile(
    r"github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)


# ── Query generation ───────────────────────────────────────────────────


def _generate_queries(keywords: List[str]) -> List[str]:
    """Build 2–3 focused search phrases from a raw keyword list.

    Strategy:
        * Pick the most specific / important keywords (the first few
          are typically the domain and technique).
        * Combine 1–2 domain keywords with a software-oriented suffix.
        * Yield at most ``_MAX_QUERIES`` phrases.

    Examples for keywords =
        ["electrophysiology", "patch-clamp", "ABF", "action potentials",
         "ion channel kinetics"]:

        → "electrophysiology patch-clamp python package"
        → "ABF action potentials analysis software"
        → "ion channel kinetics python library"
    """
    if not keywords:
        return []

    queries: list[str] = []

    # Prefer pairing 2 keywords per query for richer phrases.
    # With many keywords we still cap at _MAX_QUERIES total.
    chunk_size = 2 if len(keywords) >= 2 else 1
    for i in range(0, len(keywords), chunk_size):
        if len(queries) >= _MAX_QUERIES:
            break
        chunk = keywords[i:i + chunk_size]
        suffix = _SOFTWARE_SUFFIXES[len(queries) % len(_SOFTWARE_SUFFIXES)]
        phrase = " ".join(chunk) + " " + suffix
        queries.append(phrase)

    # Guarantee at least one query even for a single keyword
    if not queries:
        queries.append(f"{keywords[0]} {_SOFTWARE_SUFFIXES[0]}")

    return queries[:_MAX_QUERIES]


# ── Public entry point ──────────────────────────────────────────────────


async def search_google_cse(
    keywords: List[str],
    *,
    queries: Optional[List[str]] = None,
    max_results: int = 20,
) -> List[PackageCandidate]:
    """Scrape a public Google CSE for scientific software results.

    Strategy
    --------
    1. Build 2–3 focused search phrases from *queries* (preferred)
       or auto-generate them from *keywords*.
    2. Launch a single headless Chromium browser via Playwright.
    3. For each phrase, navigate to the CSE page, wait for results,
       and extract candidates.
    4. Deduplicate across queries and return merged results.

    Args:
        keywords: Domain-related search terms (used for relevance
            scoring and as fallback for query generation).
        queries: Pre-crafted targeted search phrases.  When provided
            these are used directly instead of auto-generating from
            *keywords*.  Each should be a short, natural-language
            phrase (2–5 words) focused on finding a specific tool,
            e.g. ``"patch clamp analysis python package"``.
        max_results: Cap on returned candidates.

    Returns:
        List of ``PackageCandidate`` from Google CSE results.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning(
            "Google CSE search skipped — install playwright: "
            "pip install playwright && "
            "python -m playwright install chromium"
        )
        return []

    # Determine which queries to run
    search_phrases = queries if queries else _generate_queries(keywords)
    if not search_phrases:
        return []

    logger.info(
        "Google CSE: running %d queries: %s",
        len(search_phrases),
        search_phrases,
    )

    cx = os.environ.get("GOOGLE_CSE_CX", _DEFAULT_CX)

    candidates: List[PackageCandidate] = []
    seen_links: set[str] = set()

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()

                for phrase in search_phrases:
                    if len(candidates) >= max_results:
                        break

                    encoded_q = urllib.parse.quote_plus(phrase)
                    url = f"{_CSE_BASE}?cx={cx}&q={encoded_q}"

                    try:
                        await page.goto(url, wait_until="networkidle")
                    except Exception as nav_exc:
                        logger.warning(
                            "Google CSE: navigation failed for %r: %s",
                            phrase,
                            nav_exc,
                        )
                        continue

                    # Wait for results to render
                    try:
                        await page.wait_for_selector(
                            ".gsc-result", timeout=12_000
                        )
                    except Exception:
                        logger.info(
                            "Google CSE: no results for query %r",
                            phrase,
                        )
                        continue

                    elements = await page.query_selector_all(
                        ".gsc-result"
                    )

                    for el in elements:
                        if len(candidates) >= max_results:
                            break

                        raw = await _extract_result(el)
                        if raw is None:
                            continue

                        link = raw["url"]
                        if link in seen_links:
                            continue
                        seen_links.add(link)

                        cand = _build_candidate(raw, keywords)
                        if cand is not None:
                            candidates.append(cand)

            finally:
                await browser.close()

    except Exception as exc:
        logger.warning("Google CSE search failed: %s", exc)

    return candidates[:max_results]


# ── DOM extraction ──────────────────────────────────────────────────────


async def _extract_result(
    el: Any,
) -> Optional[dict]:
    """Pull title, URL, and snippet from a ``.gsc-result`` element."""
    try:
        a_el = await el.query_selector("a.gs-title")
        if a_el is None:
            return None
        title = (await a_el.inner_text()).strip()
        href = (await a_el.get_attribute("href") or "").strip()
        if not title or not href:
            return None

        snip_el = await el.query_selector(".gs-snippet")
        snippet = ""
        if snip_el:
            snippet = (await snip_el.inner_text()).strip()

        return {
            "title": title,
            "url": href,
            "snippet": snippet,
        }
    except Exception:
        return None


# ── Candidate construction ──────────────────────────────────────────────


def _build_candidate(
    raw: dict, keywords: List[str]
) -> Optional[PackageCandidate]:
    """Convert an extracted CSE result into a ``PackageCandidate``."""
    title = raw["title"]
    link = raw["url"]
    snippet = raw.get("snippet", "")

    homepage = link
    repo_url = ""
    python_package = ""
    install_cmd = ""

    pypi_match = _PYPI_RE.search(link)
    if pypi_match:
        python_package = pypi_match.group(1)
        install_cmd = f"pip install {python_package}"

    github_match = _GITHUB_RE.search(link)
    if github_match:
        repo_url = (
            f"https://github.com/{github_match.group(1)}"
        )
        if not python_package:
            python_package = (
                github_match.group(1).split("/")[-1]
            )
            install_cmd = f"pip install {python_package}"

    name = python_package or _clean_title(title)
    if not name:
        return None

    # ── Relevance scoring ───────────────────────────────────────────
    search_text = f"{title} {snippet} {link}".lower()
    kw_lower = [kw.lower() for kw in keywords]
    hit_count = sum(
        1 for kw in kw_lower if kw in search_text
    )
    relevance = min(
        hit_count / max(len(keywords), 1), 1.0
    )

    if pypi_match:
        relevance = min(relevance + 0.15, 1.0)
    if github_match:
        relevance = min(relevance + 0.1, 1.0)
    if "python" in search_text:
        relevance = min(relevance + 0.05, 1.0)

    return PackageCandidate(
        name=name,
        source=DiscoverySource.GOOGLE_CSE,
        description=snippet[:300],
        install_command=install_cmd,
        homepage=homepage,
        repository_url=repo_url,
        relevance_score=round(relevance, 3),
        peer_reviewed=False,
        publication_dois=[],
        keywords=[
            kw
            for kw in keywords
            if kw.lower() in search_text
        ],
        python_package=python_package,
    )


def _clean_title(title: str) -> str:
    """Extract a usable name from a page title.

    Strips common suffixes like "· PyPI", "— Read the Docs",
    "| GitHub", etc. and returns the first meaningful segment.
    """
    for sep in (" · ", " \u2014 ", " - ", " | "):
        if sep in title:
            title = title.split(sep)[0]
            break
    name = re.sub(r"\s+", " ", title).strip()
    return name[:80]
