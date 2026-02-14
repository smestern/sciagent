"""
Integration tests — hit real APIs to diagnose live failures.

Run with:
    pytest tests/test_live_apis.py -v -s

These tests are marked with ``@pytest.mark.live`` so they can be
skipped during normal CI runs:
    pytest -m "not live"
"""

from __future__ import annotations

import asyncio
import logging
import pytest

from sciagent.wizard.models import PackageCandidate

# Show full logging output so we can see warnings/errors
logging.basicConfig(level=logging.DEBUG)

# Mark every test in this module as "live"
pytestmark = pytest.mark.live

# ── Shared keywords for all searches ───────────────────────────────────

KEYWORDS = ["electrophysiology", "neuroscience"]


# ── Helpers ─────────────────────────────────────────────────────────────


def _print_results(source: str, results: list[PackageCandidate]):
    print(f"\n{'=' * 60}")
    print(f"  {source}: {len(results)} results")
    print(f"{'=' * 60}")
    for i, c in enumerate(results[:10], 1):
        print(
            f"  {i:>2}. {c.name:<30}  rel={c.relevance_score:.3f}  "
            f"src={c.source.value}  peer={c.peer_reviewed}"
        )
        if c.description:
            print(f"      {c.description[:100]}")
        if c.homepage:
            print(f"      homepage: {c.homepage}")
        if c.repository_url:
            print(f"      repo:     {c.repository_url}")
    if not results:
        print("  (no results)")
    print()


# ── Individual source tests ─────────────────────────────────────────────


class TestLivePyPI:
    @pytest.mark.asyncio
    async def test_search_pypi(self):
        from sciagent.wizard.discovery.pypi import search_pypi

        results = await search_pypi(KEYWORDS, max_results=10)
        _print_results("PyPI", results)

        # Soft assertions — we just want to see what happens
        assert isinstance(results, list), "Expected a list back from PyPI"
        for c in results:
            assert isinstance(c, PackageCandidate)
            assert c.source.value == "pypi"


class TestLiveBiotools:
    @pytest.mark.asyncio
    async def test_search_biotools(self):
        from sciagent.wizard.discovery.biotools import search_biotools

        results = await search_biotools(KEYWORDS, max_results=10)
        _print_results("bio.tools", results)

        assert isinstance(results, list)
        for c in results:
            assert isinstance(c, PackageCandidate)
            assert c.source.value == "bio.tools"


class TestLivePapersWithCode:
    @pytest.mark.asyncio
    async def test_search_papers_with_code(self):
        from sciagent.wizard.discovery.papers_with_code import search_papers_with_code

        results = await search_papers_with_code(KEYWORDS, max_results=10)
        _print_results("Papers With Code", results)

        assert isinstance(results, list)
        for c in results:
            assert isinstance(c, PackageCandidate)
            assert c.source.value == "papers_with_code"


class TestLiveSciCrunch:
    @pytest.mark.asyncio
    async def test_search_scicrunch(self):
        from sciagent.wizard.discovery.scicrunch import search_scicrunch

        results = await search_scicrunch(KEYWORDS, max_results=10)
        _print_results("SciCrunch", results)

        assert isinstance(results, list)
        for c in results:
            assert isinstance(c, PackageCandidate)
            assert c.source.value == "scicrunch"


class TestLivePubMed:
    @pytest.mark.asyncio
    async def test_search_pubmed(self):
        from sciagent.wizard.discovery.pubmed import search_pubmed

        results = await search_pubmed(KEYWORDS, max_results=10)
        _print_results("PubMed", results)

        assert isinstance(results, list)
        for c in results:
            assert isinstance(c, PackageCandidate)
            assert c.source.value == "pubmed"


# ── Full pipeline test ──────────────────────────────────────────────────


class TestLiveDiscoverPackages:
    @pytest.mark.asyncio
    async def test_discover_all_sources(self):
        """Run the full discover_packages pipeline against all live APIs."""
        from sciagent.wizard.discovery.ranker import discover_packages

        results = await discover_packages(KEYWORDS, max_per_source=10)
        _print_results("discover_packages (all sources)", results)

        assert isinstance(results, list)
        # Check that results are sorted by relevance (descending)
        for i in range(len(results) - 1):
            assert results[i].relevance_score >= results[i + 1].relevance_score, (
                f"Results not sorted: {results[i].name}={results[i].relevance_score} "
                f"< {results[i+1].name}={results[i+1].relevance_score}"
            )

    @pytest.mark.asyncio
    async def test_discover_individual_sources(self):
        """Run discover_packages one source at a time to isolate failures."""
        from sciagent.wizard.discovery.ranker import discover_packages

        sources = ["pypi", "biotools", "papers_with_code", "scicrunch", "pubmed"]
        for source in sources:
            print(f"\n--- Testing source: {source} ---")
            try:
                results = await discover_packages(
                    KEYWORDS, max_per_source=5, sources=[source]
                )
                _print_results(f"discover({source})", results)
                print(f"  ✓ {source}: OK ({len(results)} results)")
            except Exception as exc:
                print(f"  ✗ {source}: FAILED — {type(exc).__name__}: {exc}")


# ── Doc fetcher live test ───────────────────────────────────────────────


class TestLiveDocFetcher:
    @pytest.mark.asyncio
    async def test_fetch_docs_for_known_package(self):
        """Fetch docs for a well-known package to check each source."""
        from sciagent.wizard.discovery.doc_fetcher import fetch_package_docs

        pkg = PackageCandidate(
            name="neo",
            source=__import__(
                "sciagent.wizard.models", fromlist=["DiscoverySource"]
            ).DiscoverySource.PYPI,
            description="Neo is a Python package for electrophysiology",
            install_command="pip install neo",
            homepage="https://neo.readthedocs.io",
            repository_url="https://github.com/NeuralEnsemble/python-neo",
            python_package="neo",
        )

        docs = await fetch_package_docs([pkg])
        print(f"\n{'=' * 60}")
        print(f"  Doc fetch for: {pkg.name}")
        print(f"{'=' * 60}")

        assert "neo" in docs
        doc_text = docs["neo"]
        print(f"  Length: {len(doc_text)} chars")
        print(f"  Preview:\n{doc_text[:500]}")
        print()

        assert len(doc_text) > 50, "Doc is too short — fetch likely failed"

if __name__ == "__main__":
    # Run the tests in this file when executed directly
    pytest.main([__file__, "-v", "-s"])