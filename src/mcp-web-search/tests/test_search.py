"""Tests for Microsoft Learn-backed web search."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mcp_web_search.search import web_search


class TestWebSearchSuccess:
    """Tests for successful Microsoft Learn API calls."""

    @pytest.mark.asyncio
    async def test_successful_search_filters_to_microsoft_learn(self) -> None:
        learn_response = {
            "results": [
                {
                    "title": "Azure Cosmos DB Overview",
                    "description": "Azure Cosmos DB is a globally distributed database.",
                    "url": "https://learn.microsoft.com/azure/cosmos-db/overview",
                },
                {
                    "title": "Blocked result",
                    "description": "Should be filtered out.",
                    "url": "https://example.com/blocked",
                },
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = learn_response
        mock_response.raise_for_status.return_value = None

        with patch("mcp_web_search.search.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await web_search("cosmos db partitioning")

        parsed = json.loads(result)
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["ref_number"] == 1
        assert parsed["results"][0]["title"] == "Azure Cosmos DB Overview"
        assert parsed["results"][0]["source_url"] == "https://learn.microsoft.com/azure/cosmos-db/overview"
        assert parsed["summary"] == "1 results from learn.microsoft.com"

    @pytest.mark.asyncio
    async def test_returns_empty_results_when_no_microsoft_learn_hits(self) -> None:
        learn_response = {
            "results": [
                {
                    "title": "External result",
                    "description": "Should be filtered out.",
                    "url": "https://example.com/blocked",
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = learn_response
        mock_response.raise_for_status.return_value = None

        with patch("mcp_web_search.search.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await web_search("cosmos db partitioning")

        parsed = json.loads(result)
        assert parsed["results"] == []
        assert parsed["summary"] == "0 results from learn.microsoft.com"


class TestWebSearchHttpError:
    """Tests for HTTP and connection failures from Microsoft Learn search."""

    @pytest.mark.asyncio
    async def test_http_error_raises_search_failed(self) -> None:
        with patch("mcp_web_search.search.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "500 Server Error",
                    request=httpx.Request("GET", "https://learn.microsoft.com/api/search"),
                    response=httpx.Response(500),
                )
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="Search failed"):
                await web_search("test")

    @pytest.mark.asyncio
    async def test_connection_error_raises_search_failed(self) -> None:
        with patch("mcp_web_search.search.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="Search failed"):
                await web_search("test")