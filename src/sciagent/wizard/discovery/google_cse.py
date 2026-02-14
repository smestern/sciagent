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

Requirements
------------
``pip install playwright && python -m playwright install chromium``
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, List, Optional

from ..models import DiscoverySource, PackageCandidate

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────

_DEFAULT_CX = "b40081397b0ad47ec"
_CSE_BASE = "https://cse.google.com/cse"

# PyPI / GitHub patterns used to extract package names
_PYPI_RE = re.compile(
    r"pypi\.org/project/([A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
_GITHUB_RE = re.compile(
    r"github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)


# ── Public entry point ──────────────────────────────────────────────────


async def search_google_cse(
    keywords: List[str],
    *,
    max_results: int = 20,
) -> List[PackageCandidate]:
    """Scrape a public Google CSE for scientific software results.

    Strategy
    --------
    1. Launch a headless Chromium browser via Playwright.
    2. Navigate to the public CSE page with the query.
    3. Wait for Google's CSE widget to render results.
    4. Extract title, URL, and snippet from each result element.
    5. Parse into ``PackageCandidate`` objects with relevance
       scoring.

    This approach bypasses bot-detection because a real browser
    (with valid TLS fingerprint, JS execution, etc.) makes the
    requests.

    Args:
        keywords: Domain-related search terms.
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

    cx = os.environ.get("GOOGLE_CSE_CX", _DEFAULT_CX)
    query = "+".join(keywords)
    url = f"{_CSE_BASE}?cx={cx}&q={query}"

    candidates: List[PackageCandidate] = []
    seen_links: set[str] = set()

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle")

                # Wait for the CSE widget to render results
                try:
                    await page.wait_for_selector(
                        ".gsc-result", timeout=12_000
                    )
                except Exception:
                    # No results rendered — may be empty or blocked
                    logger.info(
                        "Google CSE: no results rendered for %r",
                        " ".join(keywords),
                    )
                    return []

                # Extract every result element
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

                    cand = _build_candidate(
                        raw, keywords
                    )
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
