"""
Tests for sciagent.wizard.discovery — search sources and ranking.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from sciagent.wizard.models import DiscoverySource, PackageCandidate
from sciagent.wizard.discovery.ranker import rank_and_deduplicate, discover_packages, _normalise_key
from sciagent.wizard.discovery.pypi import _stub_candidate, _parse_json_api


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_candidate(**overrides) -> PackageCandidate:
    defaults = dict(
        name="testpkg",
        source=DiscoverySource.PYPI,
        description="A test package",
        relevance_score=0.5,
    )
    defaults.update(overrides)
    return PackageCandidate(**defaults)


# ── rank_and_deduplicate ────────────────────────────────────────────────


class TestRankAndDeduplicate:
    def test_returns_sorted_by_relevance(self):
        candidates = [
            _make_candidate(name="low", relevance_score=0.1),
            _make_candidate(name="high", relevance_score=0.9),
            _make_candidate(name="mid", relevance_score=0.5),
        ]
        ranked = rank_and_deduplicate(candidates)
        names = [c.name for c in ranked]
        assert names == ["high", "mid", "low"]

    def test_deduplicates_same_name(self):
        candidates = [
            _make_candidate(name="scipy", source=DiscoverySource.PYPI, relevance_score=0.4),
            _make_candidate(name="scipy", source=DiscoverySource.BIOTOOLS, relevance_score=0.3),
        ]
        ranked = rank_and_deduplicate(candidates)
        assert len(ranked) == 1
        assert ranked[0].name == "scipy"

    def test_multi_source_boost(self):
        """Packages found from multiple sources get a relevance boost."""
        single = [
            _make_candidate(name="single-source", source=DiscoverySource.PYPI, relevance_score=0.5),
        ]
        multi = [
            _make_candidate(name="multi-source", source=DiscoverySource.PYPI, relevance_score=0.5),
            _make_candidate(name="multi-source", source=DiscoverySource.BIOTOOLS, relevance_score=0.3),
        ]
        ranked_single = rank_and_deduplicate(single)
        ranked_multi = rank_and_deduplicate(multi)
        assert ranked_multi[0].relevance_score > ranked_single[0].relevance_score

    def test_filters_below_minimum(self):
        candidates = [
            _make_candidate(name="too-low", relevance_score=0.01),
        ]
        ranked = rank_and_deduplicate(candidates)
        assert len(ranked) == 0

    def test_empty_input(self):
        assert rank_and_deduplicate([]) == []

    def test_merge_preserves_best_metadata(self):
        candidates = [
            _make_candidate(
                name="pkg",
                source=DiscoverySource.PYPI,
                description="",
                homepage="",
                citations=10,
            ),
            _make_candidate(
                name="pkg",
                source=DiscoverySource.BIOTOOLS,
                description="A bio tool",
                homepage="https://example.com",
                citations=5,
            ),
        ]
        ranked = rank_and_deduplicate(candidates)
        assert len(ranked) == 1
        assert ranked[0].description == "A bio tool"
        assert ranked[0].homepage == "https://example.com"
        assert ranked[0].citations == 10  # max of both


# ── _normalise_key ──────────────────────────────────────────────────────


class TestNormaliseKey:
    def test_lowercases(self):
        cand = _make_candidate(name="MyPackage")
        assert _normalise_key(cand) == "mypackage"

    def test_underscores_to_hyphens(self):
        cand = _make_candidate(name="my_package", python_package="my_package")
        assert _normalise_key(cand) == "my-package"

    def test_strips_trailing_hyphens(self):
        cand = _make_candidate(name="pkg-", python_package="pkg-")
        assert _normalise_key(cand) == "pkg"


# ── PyPI _stub_candidate ───────────────────────────────────────────────


class TestStubCandidate:
    def test_creates_basic_candidate(self):
        cand = _stub_candidate("numpy")
        assert cand.name == "numpy"
        assert cand.source == DiscoverySource.PYPI
        assert cand.install_command == "pip install numpy"
        assert cand.python_package == "numpy"


# ── PyPI _parse_json_api ───────────────────────────────────────────────


class TestParseJsonApi:
    def test_parses_basic_response(self):
        data = {
            "info": {
                "name": "scipy",
                "summary": "Scientific computing library",
                "description": "SciPy is a scientific computing library for Python",
                "home_page": "https://scipy.org",
                "classifiers": [
                    "Topic :: Scientific/Engineering",
                    "Programming Language :: Python :: 3",
                ],
                "project_urls": {
                    "Source": "https://github.com/scipy/scipy",
                },
            }
        }
        cand = _parse_json_api(data, ["scientific", "computing"])
        assert cand.name == "scipy"
        assert cand.source == DiscoverySource.PYPI
        assert "scipy" in cand.description.lower() or "scientific" in cand.description.lower()
        assert cand.homepage == "https://scipy.org"
        assert cand.repository_url == "https://github.com/scipy/scipy"
        assert cand.relevance_score > 0

    def test_keyword_relevance_scoring(self):
        data = {
            "info": {
                "name": "foo",
                "summary": "A package about electrophysiology data",
                "description": "Handles electrophysiology recordings",
                "classifiers": [],
                "project_urls": {},
            }
        }
        cand = _parse_json_api(data, ["electrophysiology"])
        assert cand.relevance_score > 0

    def test_science_classifier_boost(self):
        base_data = {
            "info": {
                "name": "scilib",
                "summary": "A library",
                "description": "Does things",
                "classifiers": [],
                "project_urls": {},
            }
        }
        sci_data = {
            "info": {
                "name": "scilib",
                "summary": "A library",
                "description": "Does things",
                "classifiers": [
                    "Topic :: Scientific/Engineering",
                    "Topic :: Scientific/Engineering :: Bio-Informatics",
                    "Topic :: Scientific/Engineering :: Chemistry",
                ],
                "project_urls": {},
            }
        }
        cand_base = _parse_json_api(base_data, ["library"])
        cand_sci = _parse_json_api(sci_data, ["library"])
        assert cand_sci.relevance_score > cand_base.relevance_score

    def test_handles_missing_fields(self):
        data = {"info": {"name": "minimal"}}
        cand = _parse_json_api(data, ["test"])
        assert cand.name == "minimal"
        assert cand.source == DiscoverySource.PYPI

    def test_repo_url_fallback_order(self):
        data = {
            "info": {
                "name": "pkg",
                "summary": "",
                "description": "",
                "classifiers": [],
                "project_urls": {
                    "Repository": "https://github.com/owner/repo",
                },
            }
        }
        cand = _parse_json_api(data, [])
        assert cand.repository_url == "https://github.com/owner/repo"


# ── discover_packages (integration with mocked sources) ─────────────────


class TestDiscoverPackages:
    @pytest.mark.asyncio
    async def test_returns_ranked_results(self):
        """With a single mocked source, results come back ranked."""
        fake_results = [
            _make_candidate(name="alpha", relevance_score=0.8),
            _make_candidate(name="beta", relevance_score=0.3),
        ]
        with patch(
            "sciagent.wizard.discovery.pypi.search_pypi",
            new_callable=AsyncMock,
            return_value=fake_results,
        ):
            results = await discover_packages(
                ["test"], sources=["pypi"]
            )
        assert len(results) == 2
        assert results[0].name == "alpha"

    @pytest.mark.asyncio
    async def test_handles_source_failure(self):
        """If a source raises, it's logged and skipped."""
        with patch(
            "sciagent.wizard.discovery.pypi.search_pypi",
            new_callable=AsyncMock,
            side_effect=Exception("API down"),
        ):
            results = await discover_packages(
                ["test"], sources=["pypi"]
            )
        assert results == []

    @pytest.mark.asyncio
    async def test_unknown_source_ignored(self):
        """Unknown source names are skipped gracefully."""
        results = await discover_packages(
            ["test"], sources=["nonexistent_source"]
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_multi_source_merge(self):
        """Results from multiple sources are merged and deduplicated."""
        pypi_results = [
            _make_candidate(name="shared-pkg", source=DiscoverySource.PYPI, relevance_score=0.5),
        ]
        biotools_results = [
            _make_candidate(name="shared-pkg", source=DiscoverySource.BIOTOOLS, relevance_score=0.4),
        ]
        with patch(
            "sciagent.wizard.discovery.pypi.search_pypi",
            new_callable=AsyncMock,
            return_value=pypi_results,
        ), patch(
            "sciagent.wizard.discovery.biotools.search_biotools",
            new_callable=AsyncMock,
            return_value=biotools_results,
        ):
            results = await discover_packages(
                ["test"], sources=["pypi", "biotools"]
            )
        # Should be deduplicated to 1
        assert len(results) == 1
        # Should have multi-source boost
        assert results[0].relevance_score > 0.5


# ── PackageCandidate.merge ──────────────────────────────────────────────


class TestPackageCandidateMerge:
    def test_merge_fills_blanks(self):
        a = _make_candidate(name="pkg", description="", homepage="https://a.com")
        b = _make_candidate(name="pkg", description="A package", homepage="")
        merged = a.merge(b)
        assert merged.description == "A package"
        assert merged.homepage == "https://a.com"

    def test_merge_takes_max_citations(self):
        a = _make_candidate(name="pkg", citations=10)
        b = _make_candidate(name="pkg", citations=25)
        merged = a.merge(b)
        assert merged.citations == 25

    def test_merge_unions_keywords(self):
        a = _make_candidate(name="pkg")
        a.keywords = ["bio"]
        b = _make_candidate(name="pkg")
        b.keywords = ["neuro"]
        merged = a.merge(b)
        assert set(merged.keywords) == {"bio", "neuro"}

    def test_merge_unions_dois(self):
        a = _make_candidate(name="pkg")
        a.publication_dois = ["10.1234/a"]
        b = _make_candidate(name="pkg")
        b.publication_dois = ["10.1234/b"]
        merged = a.merge(b)
        assert set(merged.publication_dois) == {"10.1234/a", "10.1234/b"}
