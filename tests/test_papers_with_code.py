"""
Tests for sciagent.wizard.discovery.papers_with_code
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from sciagent.wizard.models import DiscoverySource, PackageCandidate
from sciagent.wizard.discovery.papers_with_code import (
    search_papers_with_code,
    _build_candidate,
)


# ── _build_candidate ───────────────────────────────────────────────────


class TestBuildCandidate:
    def test_basic_build(self):
        paper = {
            "title": "A neural network method",
            "abstract": "We present a method for neuroscience analysis",
            "arxiv_id": "2301.12345",
            "url_abs": "https://arxiv.org/abs/2301.12345",
        }
        cand = _build_candidate(
            paper=paper,
            repo_url="https://github.com/owner/neural-net",
            is_official=True,
            stars=500,
            framework="PyTorch",
            keywords=["neuroscience", "analysis"],
        )
        assert cand.name == "neural-net"
        assert cand.source == DiscoverySource.PAPERS_WITH_CODE
        assert cand.repository_url == "https://github.com/owner/neural-net"
        assert cand.peer_reviewed is True  # has arxiv_id
        assert "arxiv:2301.12345" in cand.publication_dois
        assert cand.relevance_score > 0

    def test_official_repo_boosts_relevance(self):
        paper = {"title": "alpha beta", "abstract": "gamma"}
        unofficial = _build_candidate(paper, "https://github.com/a/b", False, 0, "", ["alpha", "beta", "gamma", "delta", "epsilon"])
        official = _build_candidate(paper, "https://github.com/a/b", True, 0, "", ["alpha", "beta", "gamma", "delta", "epsilon"])
        assert official.relevance_score > unofficial.relevance_score

    def test_stars_boost_relevance(self):
        paper = {"title": "alpha beta", "abstract": "gamma"}
        low = _build_candidate(paper, "https://github.com/a/b", False, 10, "", ["alpha", "beta", "gamma", "delta", "epsilon"])
        high = _build_candidate(paper, "https://github.com/a/b", False, 1500, "", ["alpha", "beta", "gamma", "delta", "epsilon"])
        assert high.relevance_score > low.relevance_score

    def test_python_framework_boost(self):
        paper = {"title": "alpha beta", "abstract": "gamma"}
        no_py = _build_candidate(paper, "https://github.com/a/b", False, 0, "TensorFlow", ["alpha", "beta", "gamma", "delta", "epsilon"])
        py = _build_candidate(paper, "https://github.com/a/b", False, 0, "Python", ["alpha", "beta", "gamma", "delta", "epsilon"])
        assert py.relevance_score > no_py.relevance_score

    def test_no_arxiv_means_not_peer_reviewed(self):
        paper = {"title": "test", "abstract": ""}
        cand = _build_candidate(paper, "https://github.com/a/b", False, 0, "", ["test"])
        assert cand.peer_reviewed is False
        assert cand.publication_dois == []

    def test_empty_repo_url_fallback(self):
        paper = {"title": "My Long Paper Title About Something", "abstract": ""}
        cand = _build_candidate(paper, "", False, 0, "", ["test"])
        assert cand.name == "My Long Paper Title About Something"


# ── search_papers_with_code ─────────────────────────────────────────────


def _mock_client(paper_response=None, repo_responses=None, paper_exc=None):
    """Build a mock httpx.AsyncClient with configurable responses."""
    mock = AsyncMock()

    if paper_exc:
        mock.get = AsyncMock(side_effect=paper_exc)
    else:
        async def mock_get(url, **kwargs):
            resp = MagicMock()
            if "/repositories/" in url:
                if repo_responses:
                    resp.status_code = 200
                    resp.json.return_value = repo_responses
                else:
                    resp.status_code = 200
                    resp.json.return_value = {"results": []}
            else:
                if paper_response is not None:
                    resp.status_code = paper_response.get("status_code", 200)
                    resp.json.return_value = paper_response.get("json", {})
                else:
                    resp.status_code = 200
                    resp.json.return_value = {"results": []}
            return resp

        mock.get = AsyncMock(side_effect=mock_get)

    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


class TestSearchPapersWithCode:
    @pytest.mark.asyncio
    async def test_returns_empty_on_non_200(self):
        """Papers endpoint returning non-200 should yield empty."""
        mock_client = _mock_client(paper_response={"status_code": 403, "json": {}})

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await search_papers_with_code(["neuroscience"])

        assert results == []

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self):
        """The reported error: resp.json() raises JSONDecodeError (empty body)."""
        mock = AsyncMock()

        async def mock_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.side_effect = json.JSONDecodeError(
                "Expecting value", "", 0
            )
            return resp

        mock.get = AsyncMock(side_effect=mock_get)
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock):
            results = await search_papers_with_code(["electrophysiology"])

        assert results == []

    @pytest.mark.asyncio
    async def test_handles_network_exception(self):
        """Connection errors should be caught and return empty."""
        mock_client = _mock_client(paper_exc=Exception("Connection refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await search_papers_with_code(["test"])

        assert results == []

    @pytest.mark.asyncio
    async def test_parses_paper_with_repos(self):
        """A successful response with papers and repos yields candidates."""
        mock = AsyncMock()

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            resp = MagicMock()
            resp.status_code = 200
            if "/repositories/" in url:
                resp.json.return_value = {
                    "results": [
                        {
                            "url": "https://github.com/owner/cool-repo",
                            "is_official": True,
                            "stars": 200,
                            "framework": "PyTorch",
                        }
                    ]
                }
            else:
                resp.json.return_value = {
                    "results": [
                        {
                            "id": "paper1",
                            "title": "Cool Neuroscience Method",
                            "abstract": "A method for neuroscience",
                            "arxiv_id": "2301.00001",
                            "url_abs": "https://arxiv.org/abs/2301.00001",
                        }
                    ]
                }
            return resp

        mock.get = AsyncMock(side_effect=mock_get)
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock):
            results = await search_papers_with_code(["neuroscience"])

        assert len(results) == 1
        assert results[0].name == "cool-repo"
        assert results[0].repository_url == "https://github.com/owner/cool-repo"

    @pytest.mark.asyncio
    async def test_skips_papers_without_id(self):
        """Papers missing an id field should be skipped."""
        mock_client = _mock_client(
            paper_response={
                "status_code": 200,
                "json": {"results": [{"title": "No ID paper"}]},
            }
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await search_papers_with_code(["test"])

        assert results == []

    @pytest.mark.asyncio
    async def test_deduplicates_repos(self):
        """Same repo URL across papers should only appear once."""
        mock = AsyncMock()

        async def mock_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "/repositories/" in url:
                resp.json.return_value = {
                    "results": [
                        {"url": "https://github.com/owner/same-repo", "is_official": False, "stars": 0, "framework": ""}
                    ]
                }
            else:
                resp.json.return_value = {
                    "results": [
                        {"id": "p1", "title": "Paper 1", "abstract": ""},
                        {"id": "p2", "title": "Paper 2", "abstract": ""},
                    ]
                }
            return resp

        mock.get = AsyncMock(side_effect=mock_get)
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock):
            results = await search_papers_with_code(["test"])

        assert len(results) == 1  # same repo, only counted once

    @pytest.mark.asyncio
    async def test_repo_fetch_failure_continues(self):
        """If fetching repos for a paper fails, other papers still process."""
        mock = AsyncMock()
        call_idx = 0

        async def mock_get(url, **kwargs):
            nonlocal call_idx
            resp = MagicMock()
            resp.status_code = 200
            if "/repositories/" in url:
                call_idx += 1
                if call_idx == 1:
                    raise Exception("repo fetch failed")
                resp.json.return_value = {
                    "results": [
                        {"url": "https://github.com/owner/good-repo", "is_official": False, "stars": 0, "framework": ""}
                    ]
                }
            else:
                resp.json.return_value = {
                    "results": [
                        {"id": "p1", "title": "Paper 1", "abstract": ""},
                        {"id": "p2", "title": "Paper 2", "abstract": ""},
                    ]
                }
            return resp

        mock.get = AsyncMock(side_effect=mock_get)
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock):
            results = await search_papers_with_code(["test"])

        assert len(results) == 1
        assert results[0].name == "good-repo"
