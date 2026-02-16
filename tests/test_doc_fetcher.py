"""
Tests for sciagent_wizard.sources.doc_fetcher
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sciagent_wizard.models import DiscoverySource, PackageCandidate
from sciagent_wizard.sources.doc_fetcher import (
    fetch_package_docs,
    _extract_github,
    _readthedocs_url,
    _distinct_homepage,
    _strip_html,
    _is_duplicate,
    _compose_doc,
    _clean_readme,
    _fallback_doc,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_pkg(**overrides) -> PackageCandidate:
    defaults = dict(
        name="testpkg",
        source=DiscoverySource.PYPI,
        description="A test package",
        install_command="pip install testpkg",
        homepage="https://example.com",
        repository_url="https://github.com/owner/testpkg",
        python_package="testpkg",
    )
    defaults.update(overrides)
    return PackageCandidate(**defaults)


# ── _extract_github ─────────────────────────────────────────────────────


class TestExtractGithub:
    def test_extracts_from_repo_url(self):
        pkg = _make_pkg(repository_url="https://github.com/scipy/scipy")
        assert _extract_github(pkg) == ("scipy", "scipy")

    def test_extracts_from_homepage(self):
        pkg = _make_pkg(
            repository_url="",
            homepage="https://github.com/pandas-dev/pandas",
        )
        assert _extract_github(pkg) == ("pandas-dev", "pandas")

    def test_strips_dotgit_suffix(self):
        pkg = _make_pkg(repository_url="https://github.com/owner/repo.git")
        assert _extract_github(pkg) == ("owner", "repo")

    def test_returns_none_for_non_github(self):
        pkg = _make_pkg(repository_url="https://gitlab.com/x/y", homepage="")
        assert _extract_github(pkg) is None

    def test_returns_none_when_no_urls(self):
        pkg = _make_pkg(repository_url="", homepage="")
        assert _extract_github(pkg) is None


# ── _readthedocs_url ────────────────────────────────────────────────────


class TestReadthedocsUrl:
    def test_explicit_rtd_homepage(self):
        pkg = _make_pkg(homepage="https://mypackage.readthedocs.io/en/latest/")
        assert _readthedocs_url(pkg) == "https://mypackage.readthedocs.io/en/latest/"

    def test_generates_conventional_url(self):
        pkg = _make_pkg(homepage="https://example.com", repository_url="")
        url = _readthedocs_url(pkg)
        assert url == "https://testpkg.readthedocs.io/en/latest/"

    def test_underscores_become_hyphens(self):
        pkg = _make_pkg(python_package="my_cool_pkg", homepage="")
        url = _readthedocs_url(pkg)
        assert "my-cool-pkg" in url


# ── _distinct_homepage ──────────────────────────────────────────────────


class TestDistinctHomepage:
    def test_ignores_github_homepage(self):
        pkg = _make_pkg(homepage="https://github.com/owner/repo")
        assert _distinct_homepage(pkg, ("owner", "repo"), None) is None

    def test_ignores_rtd_homepage(self):
        pkg = _make_pkg(homepage="https://pkg.readthedocs.io/en/latest/")
        assert _distinct_homepage(pkg, None, "https://pkg.readthedocs.io/en/latest/") is None

    def test_ignores_pypi_homepage(self):
        pkg = _make_pkg(homepage="https://pypi.org/project/testpkg/")
        assert _distinct_homepage(pkg, None, None) is None

    def test_returns_distinct_homepage(self):
        pkg = _make_pkg(homepage="https://my-project.org")
        assert _distinct_homepage(pkg, None, None) == "https://my-project.org"

    def test_returns_none_when_empty(self):
        pkg = _make_pkg(homepage="")
        assert _distinct_homepage(pkg, None, None) is None


# ── _strip_html ─────────────────────────────────────────────────────────


class TestStripHtml:
    def test_removes_tags(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_collapses_blank_lines(self):
        result = _strip_html("line1\n\n\n\n\nline2")
        assert result == "line1\n\nline2"

    def test_strips_whitespace(self):
        assert _strip_html("  <div>text</div>  ") == "text"


# ── _is_duplicate ───────────────────────────────────────────────────────


class TestIsDuplicate:
    def test_detects_duplicate(self):
        existing = [("source1", "abcdefghij" * 50)]
        assert _is_duplicate("abcdefghij" * 50, existing) is True

    def test_allows_distinct(self):
        existing = [("source1", "zzzzqqqq" * 60)]
        assert _is_duplicate("aaaabbbb" * 60, existing) is False

    def test_empty_existing(self):
        assert _is_duplicate("anything", []) is False


# ── _clean_readme ───────────────────────────────────────────────────────


class TestCleanReadme:
    def test_removes_badge_links(self):
        text = "[![Build](https://img.shields.io/badge)](https://ci.example.com) Hello"
        cleaned = _clean_readme(text)
        assert "img.shields.io" not in cleaned
        assert "Hello" in cleaned

    def test_removes_standalone_badges(self):
        text = "![build status](https://img.shields.io/build/pass)\nContent"
        cleaned = _clean_readme(text)
        assert "img.shields.io" not in cleaned
        assert "Content" in cleaned

    def test_preserves_regular_content(self):
        text = "# My Package\n\nThis is a library for science."
        assert _clean_readme(text) == text


# ── _compose_doc ────────────────────────────────────────────────────────


class TestComposeDoc:
    def test_includes_header_and_content(self):
        pkg = _make_pkg(keywords=["science", "data"])
        doc = _compose_doc(pkg, "# README\n\nSome docs here.", "GitHub README")
        assert "# testpkg" in doc
        assert "pip install testpkg" in doc
        assert "GitHub README" in doc
        assert "Some docs here." in doc

    def test_includes_homepage_and_repo(self):
        pkg = _make_pkg(
            homepage="https://example.com",
            repository_url="https://github.com/owner/repo",
        )
        doc = _compose_doc(pkg, "content", "PyPI description")
        assert "https://example.com" in doc
        assert "https://github.com/owner/repo" in doc

    def test_no_keywords_ok(self):
        pkg = _make_pkg(keywords=[])
        doc = _compose_doc(pkg, "body", "source")
        assert "# testpkg" in doc


# ── _fallback_doc ───────────────────────────────────────────────────────


class TestFallbackDoc:
    def test_contains_essential_info(self):
        pkg = _make_pkg()
        doc = _fallback_doc(pkg)
        assert "# testpkg" in doc
        assert "pip install testpkg" in doc
        assert "import testpkg" in doc
        assert "not available" in doc.lower()

    def test_hyphenated_import(self):
        pkg = _make_pkg(python_package="my-pkg")
        doc = _fallback_doc(pkg)
        assert "import my_pkg" in doc


# ── fetch_package_docs (integration with mocked HTTP) ───────────────────


class TestFetchPackageDocs:
    @pytest.fixture
    def sample_pkg(self):
        return _make_pkg(
            name="neo",
            python_package="neo",
            repository_url="https://github.com/NeuralEnsemble/python-neo",
            homepage="https://neo.readthedocs.io",
        )

    @pytest.mark.asyncio
    async def test_returns_fallback_on_network_error(self, sample_pkg):
        """When all HTTP requests fail, we still get a fallback doc."""
        with patch("sciagent_wizard.sources.doc_fetcher.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            # Make all requests raise
            mock_client.get.side_effect = Exception("Network error")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            docs = await fetch_package_docs([sample_pkg])

        assert "neo" in docs
        assert "# neo" in docs["neo"]

    @pytest.mark.asyncio
    async def test_returns_dict_keyed_by_name(self, sample_pkg):
        """Result dict keys match package names."""
        with patch("sciagent_wizard.sources.doc_fetcher.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("offline")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            docs = await fetch_package_docs([sample_pkg])

        assert set(docs.keys()) == {"neo"}

    @pytest.mark.asyncio
    async def test_handles_multiple_packages(self):
        """Multiple packages each get their own entry."""
        pkgs = [
            _make_pkg(name="alpha", python_package="alpha"),
            _make_pkg(name="beta", python_package="beta"),
        ]
        with patch("sciagent_wizard.sources.doc_fetcher.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("offline")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            docs = await fetch_package_docs(pkgs)

        assert "alpha" in docs
        assert "beta" in docs
