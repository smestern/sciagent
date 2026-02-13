"""
Tests for sciagent.wizard.discovery.scicrunch
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from sciagent.wizard.models import DiscoverySource, PackageCandidate
from sciagent.wizard.discovery.scicrunch import search_scicrunch, _parse_entry


# ── _parse_entry ────────────────────────────────────────────────────────


class TestParseEntry:
    def test_parses_basic_entry(self):
        entry = {
            "name": "CellProfiler",
            "description": "Cell image analysis software written in Python",
            "url": "https://cellprofiler.org",
            "rrid": "RRID:SCR_007358",
        }
        cand = _parse_entry(entry, ["image", "analysis"])
        assert cand is not None
        assert cand.name == "CellProfiler"
        assert cand.source == DiscoverySource.SCICRUNCH
        assert cand.peer_reviewed is True  # has RRID
        assert cand.relevance_score > 0

    def test_returns_none_when_no_name(self):
        entry = {"description": "something without a name"}
        assert _parse_entry(entry, ["test"]) is None

    def test_uses_resource_name_fallback(self):
        entry = {"resource_name": "MyTool", "description": "A tool"}
        cand = _parse_entry(entry, ["tool"])
        assert cand is not None
        assert cand.name == "MyTool"

    def test_uses_title_fallback(self):
        entry = {"title": "SomeTool", "description": "stuff"}
        cand = _parse_entry(entry, ["stuff"])
        assert cand is not None
        assert cand.name == "SomeTool"

    def test_python_package_detection(self):
        entry = {
            "name": "Neo",
            "description": "Python package for electrophysiology. pip install neo.",
        }
        cand = _parse_entry(entry, ["electrophysiology"])
        assert cand is not None
        assert cand.python_package != ""
        assert "pip install" in cand.install_command

    def test_no_install_for_non_python(self):
        entry = {
            "name": "SomeRTool",
            "description": "An R package for stats",
        }
        cand = _parse_entry(entry, ["stats"])
        assert cand is not None
        assert cand.install_command == ""
        assert cand.python_package == ""

    def test_rrid_boosts_relevance(self):
        base = {"name": "Tool", "description": "does things"}
        with_rrid = {"name": "Tool", "description": "does things", "rrid": "RRID:SCR_000001"}
        cand_no_rrid = _parse_entry(base, ["things", "alpha", "beta", "gamma"])
        cand_rrid = _parse_entry(with_rrid, ["things", "alpha", "beta", "gamma"])
        assert cand_rrid.relevance_score > cand_no_rrid.relevance_score

    def test_handles_non_dict_entry(self):
        assert _parse_entry("not a dict", ["test"]) is None

    def test_keyword_relevance(self):
        entry = {"name": "NeuroTool", "description": "neuroscience imaging analysis"}
        cand = _parse_entry(entry, ["neuroscience", "imaging", "analysis"])
        assert cand.relevance_score == 1.0  # all keywords match


# ── search_scicrunch ────────────────────────────────────────────────────


class TestSearchScicrunch:
    @pytest.mark.asyncio
    async def test_returns_empty_on_404(self):
        """SciCrunch returning 404 should yield an empty list (the reported error)."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await search_scicrunch(["neuroscience"])

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_500(self):
        """Any non-200 status should return empty."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await search_scicrunch(["data"])

        assert results == []

    @pytest.mark.asyncio
    async def test_parses_successful_response(self):
        """A valid 200 response with results should parse candidates."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "results": [
                    {"name": "ToolA", "description": "A neuroscience tool", "url": "https://a.com"},
                    {"name": "ToolB", "description": "Another tool", "url": "https://b.com"},
                ]
            }
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await search_scicrunch(["neuroscience"])

        assert len(results) == 2
        assert results[0].name == "ToolA"

    @pytest.mark.asyncio
    async def test_handles_result_as_list(self):
        """SciCrunch sometimes returns result as a list directly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": [
                {"name": "ListTool", "description": "In a list"},
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await search_scicrunch(["test"])

        assert len(results) == 1
        assert results[0].name == "ListTool"

    @pytest.mark.asyncio
    async def test_handles_network_exception(self):
        """Network errors should be caught and return empty."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await search_scicrunch(["test"])

        assert results == []

    @pytest.mark.asyncio
    async def test_respects_max_results(self):
        """Should not return more than max_results."""
        entries = [{"name": f"Tool{i}", "description": "test tool"} for i in range(20)]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"results": entries}}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await search_scicrunch(["test"], max_results=5)

        assert len(results) <= 5
