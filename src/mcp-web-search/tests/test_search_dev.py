"""Tests for dev-mode web search (Microsoft Learn search API)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mcp_web_search.search_dev import dev_web_search


class TestDevWebSearchEmptyWhitelist:
    """Tests when whitelist is empty."""

    @pytest.mark.asyncio
    async def test_empty_whitelist_raises(self) -> None:
        with pytest.raises(RuntimeError, match="No whitelisted sites"):
            await dev_web_search("anything", [])


class TestDevWebSearchSuccess:
    """Tests for successful Microsoft Learn API calls."""

    @pytest.mark.asyncio
    async def test_successful_search_filters_to_whitelist(self) -> None:
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

        with patch("mcp_web_search.search_dev.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await dev_web_search("cosmos db partitioning", ["learn.microsoft.com"])

        parsed = json.loads(result)
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["ref_number"] == 1
        assert parsed["results"][0]["title"] == "Azure Cosmos DB Overview"
        assert parsed["results"][0]["source_url"] == "https://learn.microsoft.com/azure/cosmos-db/overview"


class TestDevWebSearchHttpError:
    """Tests for HTTP and connection failures from Microsoft Learn search."""

    @pytest.mark.asyncio
    async def test_http_error_raises_search_failed(self) -> None:
        with patch("mcp_web_search.search_dev.httpx.AsyncClient") as mock_client_cls:
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
                await dev_web_search("test", ["learn.microsoft.com"])

    @pytest.mark.asyncio
    async def test_connection_error_raises_search_failed(self) -> None:
        with patch("mcp_web_search.search_dev.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="Search failed"):
                await dev_web_search("test", ["learn.microsoft.com"])