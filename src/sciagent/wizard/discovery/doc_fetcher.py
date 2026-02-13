"""
doc_fetcher — Fetch and summarise documentation for confirmed packages.

After the researcher confirms their package selection, this module
pulls README / quickstart content from PyPI, GitHub, ReadTheDocs,
and package homepages, then condenses each into a concise Markdown
reference suitable for embedding in the generated agent's ``docs/`` dir.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp

from ..models import PackageCandidate

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

_PYPI_JSON = "https://pypi.org/pypi/{name}/json"
_GITHUB_README = "https://api.github.com/repos/{owner}/{repo}/readme"
_TIMEOUT = aiohttp.ClientTimeout(total=30)
_MAX_DOC_CHARS = 12_000  # truncate raw docs before summarisation


# ── Public API ──────────────────────────────────────────────────────────


async def fetch_package_docs(
    packages: List[PackageCandidate],
) -> Dict[str, str]:
    """Fetch documentation for each package and return ``{name: markdown}``.

    Runs all fetches in parallel.  For each package the best available
    doc source is chosen:

    1. GitHub README (richest content)
    2. PyPI long_description (usually the same README)
    3. ReadTheDocs index / quickstart page
    4. Package homepage (generic scrape)

    The raw content is trimmed and formatted into a clean Markdown
    reference document per package.
    """
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
        tasks = [_fetch_one(session, pkg) for pkg in packages]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    docs: Dict[str, str] = {}
    for pkg, result in zip(packages, results):
        if isinstance(result, Exception):
            logger.warning("Doc fetch failed for %s: %s", pkg.name, result)
            docs[pkg.name] = _fallback_doc(pkg)
        elif result:
            docs[pkg.name] = result
        else:
            docs[pkg.name] = _fallback_doc(pkg)

    return docs


# ── Per-package fetcher ─────────────────────────────────────────────────


async def _fetch_one(
    session: aiohttp.ClientSession,
    pkg: PackageCandidate,
) -> str:
    """Try multiple sources for *pkg* and return the best doc found."""
    # Try sources in priority order; first non-empty wins
    github_owner_repo = _extract_github(pkg)

    raw_parts: List[Tuple[str, str]] = []  # (source_label, content)

    # 1 — GitHub README
    if github_owner_repo:
        owner, repo = github_owner_repo
        content = await _fetch_github_readme(session, owner, repo)
        if content:
            raw_parts.append(("GitHub README", content))

    # 2 — PyPI description (often duplicates GH README but serves as fallback)
    pypi_content = await _fetch_pypi_description(session, pkg.pip_name)
    if pypi_content and not _is_duplicate(pypi_content, raw_parts):
        raw_parts.append(("PyPI description", pypi_content))

    # 3 — ReadTheDocs
    rtd_url = _readthedocs_url(pkg)
    if rtd_url:
        rtd_content = await _fetch_webpage_text(session, rtd_url)
        if rtd_content and not _is_duplicate(rtd_content, raw_parts):
            raw_parts.append(("ReadTheDocs", rtd_content))

    # 4 — Homepage (if distinct from above)
    homepage = _distinct_homepage(pkg, github_owner_repo, rtd_url)
    if homepage:
        hp_content = await _fetch_webpage_text(session, homepage)
        if hp_content and not _is_duplicate(hp_content, raw_parts):
            raw_parts.append(("Homepage", hp_content))

    if not raw_parts:
        return _fallback_doc(pkg)

    # Pick the richest source (longest content) for the main body
    best_label, best_content = max(raw_parts, key=lambda x: len(x[1]))

    return _compose_doc(pkg, best_content, best_label)


# ── Source fetchers ─────────────────────────────────────────────────────


async def _fetch_pypi_description(
    session: aiohttp.ClientSession,
    pip_name: str,
) -> Optional[str]:
    """Fetch the long_description (rendered README) from PyPI JSON API."""
    url = _PYPI_JSON.format(name=pip_name)
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
            desc = data.get("info", {}).get("description", "")
            if len(desc) < 80:
                # Too short to be useful — probably just the summary
                return None
            return desc[:_MAX_DOC_CHARS]
    except Exception as exc:
        logger.debug("PyPI fetch for %s: %s", pip_name, exc)
        return None


async def _fetch_github_readme(
    session: aiohttp.ClientSession,
    owner: str,
    repo: str,
) -> Optional[str]:
    """Fetch raw README from GitHub API."""
    url = _GITHUB_README.format(owner=owner, repo=repo)
    headers = {"Accept": "application/vnd.github.raw+json"}
    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None
            text = await resp.text()
            return text[:_MAX_DOC_CHARS] if text else None
    except Exception as exc:
        logger.debug("GitHub README for %s/%s: %s", owner, repo, exc)
        return None


async def _fetch_webpage_text(
    session: aiohttp.ClientSession,
    url: str,
) -> Optional[str]:
    """Fetch a web page and extract its text content (basic HTML stripping)."""
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()
            return _strip_html(html)[:_MAX_DOC_CHARS]
    except Exception as exc:
        logger.debug("Webpage fetch %s: %s", url, exc)
        return None


# ── URL helpers ─────────────────────────────────────────────────────────


def _extract_github(pkg: PackageCandidate) -> Optional[Tuple[str, str]]:
    """Extract (owner, repo) from any URL in the package metadata."""
    for url in (pkg.repository_url, pkg.homepage):
        if not url:
            continue
        m = re.match(
            r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
            url,
        )
        if m:
            return m.group(1), m.group(2)
    return None


def _readthedocs_url(pkg: PackageCandidate) -> Optional[str]:
    """Return a ReadTheDocs URL if the homepage looks like one."""
    for url in (pkg.homepage, pkg.repository_url):
        if url and "readthedocs.io" in url:
            return url
    # Try the conventional URL
    name = pkg.pip_name.replace("_", "-").lower()
    return f"https://{name}.readthedocs.io/en/latest/"


def _distinct_homepage(
    pkg: PackageCandidate,
    github: Optional[Tuple[str, str]],
    rtd_url: Optional[str],
) -> Optional[str]:
    """Return the homepage URL only if it's distinct from GitHub / RTD."""
    hp = pkg.homepage
    if not hp:
        return None
    parsed = urlparse(hp)
    host = parsed.hostname or ""
    if "github.com" in host or "readthedocs.io" in host or "pypi.org" in host:
        return None
    return hp


# ── Text processing ────────────────────────────────────────────────────

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


def _strip_html(html: str) -> str:
    """Crude HTML → text conversion for webpage scraping."""
    text = _TAG_RE.sub("", html)
    text = _WS_RE.sub("\n\n", text)
    return text.strip()


def _is_duplicate(
    new_content: str,
    existing: List[Tuple[str, str]],
    threshold: float = 0.6,
) -> bool:
    """Rough duplication check — if >60 % of first 500 chars overlap."""
    snippet = new_content[:500]
    for _, existing_content in existing:
        overlap = sum(
            1 for c in snippet if c in existing_content[:500]
        )
        if overlap / max(len(snippet), 1) > threshold:
            return True
    return False


def _compose_doc(pkg: PackageCandidate, raw_content: str, source_label: str) -> str:
    """Format raw doc content into a clean reference document."""
    install = pkg.install_command or f"pip install {pkg.pip_name}"
    homepage = pkg.homepage or ""
    repo = pkg.repository_url or ""

    header_lines = [
        f"# {pkg.name}",
        "",
        f"> {pkg.description}" if pkg.description else "",
        "",
        "## Quick Reference",
        "",
        f"- **Install**: `{install}`",
    ]
    if homepage:
        header_lines.append(f"- **Homepage**: {homepage}")
    if repo:
        header_lines.append(f"- **Repository**: {repo}")
    if pkg.keywords:
        header_lines.append(f"- **Keywords**: {', '.join(pkg.keywords[:10])}")

    header_lines.extend([
        "",
        f"---",
        "",
        f"*Source: {source_label}*",
        "",
    ])

    # Clean up the raw content: remove badges, build-status images, etc.
    cleaned = _clean_readme(raw_content)

    return "\n".join(header_lines) + cleaned


def _clean_readme(text: str) -> str:
    """Remove common README noise (badges, CI links, etc.)."""
    # Remove badge images: [![...](...)(...)]
    text = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", "", text)
    # Remove standalone badge images: ![...](...)
    text = re.sub(r"!\[(?:build|ci|coverage|license|pypi|version|badge).*?\]\(.*?\)", "", text, flags=re.IGNORECASE)
    # Collapse excessive blank lines
    text = _WS_RE.sub("\n\n", text)
    return text.strip()


def _fallback_doc(pkg: PackageCandidate) -> str:
    """Minimal doc when no online sources are reachable."""
    install = pkg.install_command or f"pip install {pkg.pip_name}"
    desc = pkg.description or "No description available."
    homepage = pkg.homepage or ""

    lines = [
        f"# {pkg.name}",
        "",
        f"> {desc}",
        "",
        "## Quick Reference",
        "",
        f"- **Install**: `{install}`",
    ]
    if homepage:
        lines.append(f"- **Homepage**: {homepage}")
    if pkg.repository_url:
        lines.append(f"- **Repository**: {pkg.repository_url}")

    lines.extend([
        "",
        "## Usage",
        "",
        f"```python",
        f"import {pkg.pip_name.replace('-', '_')}",
        f"```",
        "",
        "*Documentation was not available at generation time. "
        "Refer to the homepage or repository for full API reference.*",
    ])
    return "\n".join(lines)
