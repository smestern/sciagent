"""
crawler — Deep documentation fetcher for the docs ingestor.

Goes beyond README-level scraping to retrieve actual API reference pages
from ReadTheDocs, GitHub source files, and PyPI metadata.  The collected
pages are fed to an LLM that structures them into ``library_api.md``.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx

from .models import IngestorState, ScrapedPage, SourceType

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

_PYPI_JSON = "https://pypi.org/pypi/{name}/json"
_GITHUB_README = "https://api.github.com/repos/{owner}/{repo}/readme"
_GITHUB_TREE = "https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
_GITHUB_RAW = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
_TIMEOUT = 30.0
_MAX_PAGE_CHARS = 15_000  # per-page cap
_MAX_TOTAL_CHARS = 80_000  # total cap across all pages
_MAX_PAGES = 20  # max pages to crawl

# Paths on ReadTheDocs sites that likely contain API reference content
_API_PATH_PATTERNS = re.compile(
    r"/(api|reference|modules?|autoapi|genindex|py-modindex"
    r"|classes|functions|package|autodoc)",
    re.IGNORECASE,
)

# Files we want from a GitHub repo
_INTERESTING_SOURCE_PATTERNS = re.compile(
    r"(^[^/]+\.py$"  # top-level .py files
    r"|__init__\.py$"  # package init files (1 level deep)
    r"|/core\.py$|/main\.py$|/api\.py$|/base\.py$)",  # common API entry points
    re.IGNORECASE,
)

# Directories in a repo that likely contain documentation
_DOC_DIRS = re.compile(
    r"^(docs?|documentation|notebooks?|examples?|tutorials?)/",
    re.IGNORECASE,
)

# File extensions worth reading inside doc directories
_DOC_FILE_EXTS = re.compile(
    r"\.(md|rst|ipynb|txt)$", re.IGNORECASE,
)

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|nav|footer|header)[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)
_WS_RE = re.compile(r"\n{3,}")


# ── Public API ──────────────────────────────────────────────────────────


async def crawl_package(
    package_name: str,
    github_url: Optional[str] = None,
) -> Tuple[Dict[str, str], List[ScrapedPage]]:
    """Crawl all available sources for *package_name*.

    Returns ``(metadata_dict, scraped_pages)`` where *metadata_dict*
    contains keys like ``pip_name``, ``homepage``, ``repository_url``,
    ``docs_url``, ``description``.
    """
    async with httpx.AsyncClient(
        timeout=_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "sciagent-docs-ingestor/1.0"},
    ) as client:
        # 1 — PyPI metadata (always first for package resolution)
        metadata = await _fetch_pypi_metadata(client, package_name)

        pip_name = metadata.get("pip_name", package_name)

        # 2 — Resolve GitHub owner/repo
        owner_repo = None
        if github_url:
            owner_repo = _extract_github(github_url)
        if not owner_repo:
            for url in (
                metadata.get("repository_url", ""),
                metadata.get("homepage", ""),
            ):
                owner_repo = _extract_github(url)
                if owner_repo:
                    break

        # 3 — Kick off parallel crawls
        tasks: List[asyncio.Task] = []

        # ReadTheDocs
        rtd_url = metadata.get("docs_url") or _guess_rtd_url(pip_name)
        tasks.append(asyncio.create_task(
            _crawl_readthedocs(client, rtd_url, pip_name)
        ))

        # GitHub README + source + docs/notebooks folders
        if owner_repo:
            owner, repo = owner_repo
            metadata.setdefault(
                "repository_url",
                f"https://github.com/{owner}/{repo}",
            )
            tasks.append(asyncio.create_task(
                _fetch_github_readme(client, owner, repo)
            ))
            tasks.append(asyncio.create_task(
                _crawl_github_source(client, owner, repo)
            ))
            tasks.append(asyncio.create_task(
                _crawl_github_docs_folder(
                    client, owner, repo,
                ),
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 4 — Collect pages, respecting caps
        all_pages: List[ScrapedPage] = []
        total_chars = 0

        for result in results:
            if isinstance(result, Exception):
                logger.warning("Crawl task failed: %s", result)
                continue
            if isinstance(result, list):
                for page in result:
                    if total_chars >= _MAX_TOTAL_CHARS:
                        break
                    if len(all_pages) >= _MAX_PAGES:
                        break
                    # Truncate individual pages
                    if page.char_count > _MAX_PAGE_CHARS:
                        page.content = page.content[:_MAX_PAGE_CHARS]
                        page.char_count = _MAX_PAGE_CHARS
                    all_pages.append(page)
                    total_chars += page.char_count
            elif isinstance(result, ScrapedPage):
                if total_chars < _MAX_TOTAL_CHARS and len(all_pages) < _MAX_PAGES:
                    if result.char_count > _MAX_PAGE_CHARS:
                        result.content = result.content[:_MAX_PAGE_CHARS]
                        result.char_count = _MAX_PAGE_CHARS
                    all_pages.append(result)
                    total_chars += result.char_count

        logger.info(
            "Crawled %d pages for %s (%d chars total)",
            len(all_pages), package_name, total_chars,
        )

        return metadata, all_pages


async def fetch_single_page(
    url: str,
    source_type: SourceType = SourceType.READTHEDOCS,
) -> Optional[ScrapedPage]:
    """Fetch a single page on demand (called by the LLM via tool)."""
    async with httpx.AsyncClient(
        timeout=_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "sciagent-docs-ingestor/1.0"},
    ) as client:
        text = await _fetch_webpage_text(client, url)
        if not text or len(text) < 50:
            return None
        title = _extract_title(text, url)
        return ScrapedPage(
            url=url,
            title=title,
            content=text[:_MAX_PAGE_CHARS],
            source_type=source_type,
        )


# ── PyPI ────────────────────────────────────────────────────────────────


async def _fetch_pypi_metadata(
    client: httpx.AsyncClient,
    package_name: str,
) -> Dict[str, str]:
    """Fetch metadata from the PyPI JSON API."""
    url = _PYPI_JSON.format(name=package_name)
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            logger.debug("PyPI 404 for %s, trying normalized name", package_name)
            # Try with dashes → underscores and vice versa
            alt = package_name.replace("-", "_")
            if alt == package_name:
                alt = package_name.replace("_", "-")
            resp = await client.get(_PYPI_JSON.format(name=alt))
            if resp.status_code != 200:
                return {"pip_name": package_name}

        data = resp.json()
        info = data.get("info", {})

        # Find docs URL from project_urls
        docs_url = ""
        project_urls = info.get("project_urls") or {}
        for key in ("Documentation", "Docs", "docs", "documentation",
                     "API Reference", "API", "Homepage"):
            if key in project_urls:
                val = project_urls[key]
                if "readthedocs" in val or "docs" in val.lower():
                    docs_url = val
                    break

        # Find repo URL
        repo_url = ""
        for key in ("Source", "Repository", "source", "repository",
                     "Source Code", "GitHub", "Code"):
            if key in project_urls:
                repo_url = project_urls[key]
                break

        return {
            "pip_name": info.get("name", package_name),
            "description": info.get("summary", ""),
            "homepage": info.get("home_page") or info.get("project_url", ""),
            "repository_url": repo_url,
            "docs_url": docs_url,
            "version": info.get("version", ""),
            "keywords": info.get("keywords", ""),
            "install_command": f"pip install {info.get('name', package_name)}",
        }
    except Exception as exc:
        logger.debug("PyPI metadata for %s: %s", package_name, exc)
        return {"pip_name": package_name}


# ── ReadTheDocs ─────────────────────────────────────────────────────────


async def _crawl_readthedocs(
    client: httpx.AsyncClient,
    base_url: str,
    pip_name: str,
) -> List[ScrapedPage]:
    """Crawl a ReadTheDocs (or Sphinx) site for API reference pages."""
    pages: List[ScrapedPage] = []

    if not base_url:
        return pages

    # Ensure trailing slash
    if not base_url.endswith("/"):
        base_url += "/"

    # 1 — Fetch the index page
    index_text = await _fetch_webpage_text(client, base_url)
    if not index_text:
        return pages

    pages.append(ScrapedPage(
        url=base_url,
        title=f"{pip_name} — Documentation Index",
        content=index_text[:_MAX_PAGE_CHARS],
        source_type=SourceType.READTHEDOCS,
    ))

    # 2 — Discover links to API reference pages
    api_links = _discover_api_links(base_url, index_text)

    # Also try common API paths if none were found
    if not api_links:
        for suffix in ("api/", "reference/", "api.html", "modules.html",
                        "autoapi/", "genindex.html"):
            candidate = urljoin(base_url, suffix)
            api_links.append(candidate)

    # 3 — Fetch discovered API pages (limit to avoid excessive crawling)
    seen_urls = {base_url}
    for link in api_links[:8]:
        if link in seen_urls:
            continue
        seen_urls.add(link)

        text = await _fetch_webpage_text(client, link)
        if not text or len(text) < 100:
            continue

        title = _extract_title(text, link)
        pages.append(ScrapedPage(
            url=link,
            title=title,
            content=text[:_MAX_PAGE_CHARS],
            source_type=SourceType.READTHEDOCS,
        ))

        # Follow sub-links from API pages (one level deeper)
        sub_links = _discover_api_links(link, text)
        for sub in sub_links[:4]:
            if sub in seen_urls:
                continue
            seen_urls.add(sub)
            sub_text = await _fetch_webpage_text(client, sub)
            if sub_text and len(sub_text) >= 100:
                pages.append(ScrapedPage(
                    url=sub,
                    title=_extract_title(sub_text, sub),
                    content=sub_text[:_MAX_PAGE_CHARS],
                    source_type=SourceType.READTHEDOCS,
                ))

            if len(pages) >= _MAX_PAGES:
                break
        if len(pages) >= _MAX_PAGES:
            break

    return pages


def _discover_api_links(base_url: str, html_text: str) -> List[str]:
    """Extract links from HTML that look like API reference pages."""
    links: List[str] = []
    # Find href attributes
    href_re = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
    for m in href_re.finditer(html_text):
        href = m.group(1)
        # Skip anchors, external links, static assets
        if href.startswith("#") or href.startswith("mailto:"):
            continue
        if any(href.endswith(ext) for ext in (".png", ".jpg", ".css", ".js", ".ico")):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Only follow links on the same domain
        base_parsed = urlparse(base_url)
        if parsed.hostname != base_parsed.hostname:
            continue

        # Prefer paths that look like API docs
        if _API_PATH_PATTERNS.search(parsed.path):
            links.insert(0, full_url)  # prioritise
        elif parsed.path.endswith(".html") or parsed.path.endswith("/"):
            links.append(full_url)

    # Deduplicate while preserving order
    seen: set = set()
    deduped: List[str] = []
    for link in links:
        if link not in seen:
            seen.add(link)
            deduped.append(link)
    return deduped


def _guess_rtd_url(pip_name: str) -> str:
    """Guess the ReadTheDocs URL from the pip name."""
    name = pip_name.replace("_", "-").lower()
    return f"https://{name}.readthedocs.io/en/latest/"


# ── GitHub ──────────────────────────────────────────────────────────────


async def _fetch_github_readme(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
) -> Optional[ScrapedPage]:
    """Fetch raw README from GitHub API."""
    url = _GITHUB_README.format(owner=owner, repo=repo)
    headers = {"Accept": "application/vnd.github.raw+json"}
    try:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            return None
        text = resp.text
        if not text:
            return None
        return ScrapedPage(
            url=f"https://github.com/{owner}/{repo}",
            title=f"{repo} — README",
            content=text[:_MAX_PAGE_CHARS],
            source_type=SourceType.GITHUB_README,
        )
    except Exception as exc:
        logger.debug("GitHub README for %s/%s: %s", owner, repo, exc)
        return None


async def _crawl_github_source(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    branch: str = "main",
) -> List[ScrapedPage]:
    """Fetch key Python source files from GitHub to extract docstrings."""
    pages: List[ScrapedPage] = []

    # Get the repo tree
    tree_url = _GITHUB_TREE.format(owner=owner, repo=repo, branch=branch)
    try:
        resp = await client.get(tree_url)
        if resp.status_code != 200:
            # Try 'master' branch
            if branch == "main":
                return await _crawl_github_source(client, owner, repo, "master")
            return pages
        tree = resp.json().get("tree", [])
    except Exception as exc:
        logger.debug("GitHub tree for %s/%s: %s", owner, repo, exc)
        return pages

    # Find interesting source files
    interesting: List[str] = []
    # Guess the package directory (often matches repo name)
    pkg_dir = repo.replace("-", "_").lower()

    for item in tree:
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        if not path.endswith(".py"):
            continue

        # Top-level module files
        if "/" not in path:
            interesting.append(path)
            continue

        # Files inside the main package directory
        parts = path.split("/")
        if parts[0].lower() == pkg_dir or parts[0].lower() == "src":
            # __init__.py at package root (1-2 levels)
            if len(parts) <= 3 and parts[-1] == "__init__.py":
                interesting.append(path)
            # Core module files
            elif len(parts) <= 3 and _INTERESTING_SOURCE_PATTERNS.search(path):
                interesting.append(path)

    # Fetch the files (limit to 6 most interesting)
    interesting = interesting[:6]

    for path in interesting:
        raw_url = _GITHUB_RAW.format(
            owner=owner, repo=repo, branch=branch, path=path,
        )
        try:
            resp = await client.get(raw_url)
            if resp.status_code != 200:
                continue
            content = resp.text
            if not content or len(content) < 50:
                continue

            # Extract docstrings and signatures (skip implementation bodies)
            extracted = _extract_api_surface(content)
            if extracted:
                pages.append(ScrapedPage(
                    url=raw_url,
                    title=f"Source: {path}",
                    content=extracted[:_MAX_PAGE_CHARS],
                    source_type=SourceType.GITHUB_SOURCE,
                ))
        except Exception as exc:
            logger.debug("GitHub source %s: %s", path, exc)

    return pages


async def _crawl_github_docs_folder(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    branch: str = "main",
) -> List[ScrapedPage]:
    """Fetch Markdown/RST/notebook files from docs/ or notebooks/ dirs.

    Many repos keep their real documentation (tutorials, API guides,
    examples) in these folders rather than publishing to ReadTheDocs.
    """
    pages: List[ScrapedPage] = []

    # Reuse the tree we already need
    tree_url = _GITHUB_TREE.format(
        owner=owner, repo=repo, branch=branch,
    )
    try:
        resp = await client.get(tree_url)
        if resp.status_code != 200:
            if branch == "main":
                return await _crawl_github_docs_folder(
                    client, owner, repo, "master",
                )
            return pages
        tree = resp.json().get("tree", [])
    except Exception as exc:
        logger.debug(
            "GitHub tree (docs) for %s/%s: %s",
            owner, repo, exc,
        )
        return pages

    # Collect doc files from recognized folders
    candidates: List[str] = []
    for item in tree:
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        if _DOC_DIRS.match(path) and _DOC_FILE_EXTS.search(path):
            candidates.append(path)

    if not candidates:
        return pages

    # Prioritise: .md/.rst first, then .ipynb, cap at 8 files
    def _sort_key(p: str) -> int:
        if p.endswith(".md") or p.endswith(".rst"):
            return 0
        if p.endswith(".ipynb"):
            return 1
        return 2

    candidates.sort(key=_sort_key)
    candidates = candidates[:8]

    for path in candidates:
        raw_url = _GITHUB_RAW.format(
            owner=owner, repo=repo, branch=branch, path=path,
        )
        try:
            resp = await client.get(raw_url)
            if resp.status_code != 200:
                continue
            content = resp.text
            if not content or len(content) < 50:
                continue

            # For notebooks, extract markdown + code cells
            if path.endswith(".ipynb"):
                content = _extract_notebook_content(content)
                if not content:
                    continue

            pages.append(ScrapedPage(
                url=raw_url,
                title=f"Docs: {path}",
                content=content[:_MAX_PAGE_CHARS],
                source_type=SourceType.GITHUB_SOURCE,
            ))
        except Exception as exc:
            logger.debug("GitHub doc %s: %s", path, exc)

    return pages


def _extract_notebook_content(raw_json: str) -> str:
    """Extract markdown and code cells from a Jupyter notebook JSON."""
    import json as _json

    try:
        nb = _json.loads(raw_json)
    except _json.JSONDecodeError:
        return ""

    cells = nb.get("cells", [])
    parts: List[str] = []
    for cell in cells:
        cell_type = cell.get("cell_type", "")
        source_lines = cell.get("source", [])
        if isinstance(source_lines, list):
            source = "".join(source_lines)
        else:
            source = str(source_lines)

        if not source.strip():
            continue

        if cell_type == "markdown":
            parts.append(source)
        elif cell_type == "code":
            parts.append(f"```python\n{source}\n```")

    return "\n\n".join(parts)


def _extract_api_surface(source: str) -> str:
    """Extract class/function signatures and docstrings from Python source.

    Strips function/method bodies to keep only the API surface.
    """
    lines = source.split("\n")
    output: List[str] = []
    in_docstring = False
    docstring_delim = None
    skip_body = False
    indent_level = 0

    for line in lines:
        stripped = line.strip()

        # Module-level docstring or comments at top
        if not stripped or stripped.startswith("#"):
            if not skip_body:
                output.append(line)
            continue

        # Track docstrings
        if in_docstring:
            output.append(line)
            if docstring_delim and docstring_delim in stripped:
                in_docstring = False
                docstring_delim = None
            continue

        # Detect start of docstring
        if stripped.startswith('"""') or stripped.startswith("'''"):
            delim = stripped[:3]
            output.append(line)
            if stripped.count(delim) == 1:
                in_docstring = True
                docstring_delim = delim
            continue

        # Class and function definitions
        if stripped.startswith(("class ", "def ", "async def ")):
            current_indent = len(line) - len(line.lstrip())
            skip_body = False
            indent_level = current_indent
            output.append(line)

            # Multi-line signature
            if ")" not in stripped and ":" not in stripped:
                # Continue reading the signature
                pass
            continue

        # Import statements
        if stripped.startswith(("import ", "from ")):
            output.append(line)
            continue

        # Decorators
        if stripped.startswith("@"):
            output.append(line)
            continue

        # Type aliases, constants (top-level assignments)
        current_indent = len(line) - len(line.lstrip())
        if current_indent == 0 and "=" in stripped:
            output.append(line)
            continue

        # Inside a function body — skip (but keep multi-line signatures)
        if stripped.endswith((",", "\\")) or (
            "(" in stripped and ")" not in stripped
        ):
            output.append(line)
            continue

    return "\n".join(output)


# ── Text processing ────────────────────────────────────────────────────


async def _fetch_webpage_text(
    client: httpx.AsyncClient,
    url: str,
) -> Optional[str]:
    """Fetch a web page and extract its text content."""
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        return _strip_html(resp.text)
    except Exception as exc:
        logger.debug("Webpage fetch %s: %s", url, exc)
        return None


def _strip_html(html: str) -> str:
    """Convert HTML to readable text, removing nav/script/style elements."""
    # Remove script, style, nav, footer, header blocks
    text = _SCRIPT_STYLE_RE.sub("", html)
    # Remove remaining tags
    text = _TAG_RE.sub("", text)
    # Decode common entities
    for entity, char in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                          ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")]:
        text = text.replace(entity, char)
    # Collapse whitespace
    text = _WS_RE.sub("\n\n", text)
    return text.strip()


def _extract_title(text: str, url: str) -> str:
    """Get a title from page text or fall back to the URL path."""
    for line in text.split("\n")[:10]:
        stripped = line.strip()
        if stripped and len(stripped) > 3 and len(stripped) < 200:
            if not stripped.startswith(("http", "/*", "<!--")):
                return stripped[:120]
    # Fallback to URL path
    path = urlparse(url).path.strip("/")
    return path.split("/")[-1] if path else url


def _extract_github(url: str) -> Optional[Tuple[str, str]]:
    """Extract (owner, repo) from a GitHub URL."""
    if not url:
        return None
    m = re.match(
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        url.strip(),
    )
    if m:
        return m.group(1), m.group(2)
    # Also handle URLs with extra path segments
    m = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)",
        url.strip(),
    )
    if m:
        return m.group(1), m.group(2)
    return None
