"""Tests for prod-mode web search (Bing Web Search API)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mcp_web_search.search_prod import prod_web_search


class TestProdWebSearchNoApiKey:
    """Tests for the case where BING_SEARCH_API_KEY is not set."""

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self) -> None:
        """When BING_SEARCH_API_KEY is empty, runtime should fail loudly."""
        with patch.dict("os.environ", {"BING_SEARCH_API_KEY": ""}, clear=False):
            with pytest.raises(RuntimeError, match="BING_SEARCH_API_KEY"):
                await prod_web_search("test query", ["learn.microsoft.com"])

    @pytest.mark.asyncio
    async def test_missing_api_key_env_not_set_raises(self) -> None:
        """When BING_SEARCH_API_KEY is not in env at all, runtime should fail loudly."""
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("BING_SEARCH_API_KEY", None)
            with pytest.raises(RuntimeError, match="BING_SEARCH_API_KEY"):
                await prod_web_search("test query", ["learn.microsoft.com"])


class TestProdWebSearchEmptyWhitelist:
    """Tests when whitelist is empty."""

    @pytest.mark.asyncio
    async def test_empty_whitelist_raises(self) -> None:
        with patch.dict("os.environ", {"BING_SEARCH_API_KEY": "test-key"}, clear=False):
            with pytest.raises(RuntimeError, match="No whitelisted sites"):
                await prod_web_search("anything", [])


class TestProdWebSearchSuccess:
    """Tests for successful Bing API calls."""

    @pytest.mark.asyncio
    async def test_successful_search_parses_results(self) -> None:
        """Happy path: Bing returns results, they are parsed correctly."""
        bing_response = {
            "webPages": {
                "value": [
                    {
                        "name": "Azure Cosmos DB Overview",
                        "snippet": "Azure Cosmos DB is a globally distributed database.",
                        "url": "https://learn.microsoft.com/azure/cosmos-db/overview",
                    },
                    {
                        "name": "Cosmos DB Partitioning",
                        "snippet": "Choose a partition key for your containers.",
                        "url": "https://learn.microsoft.com/azure/cosmos-db/partitioning",
                    },
                ]
            }
        }

        mock_response = MagicMock()
        mock_response.json.return_value = bing_response
        mock_response.raise_for_status.return_value = None

        with (
            patch.dict("os.environ", {"BING_SEARCH_API_KEY": "test-key-12345"}),
            patch("mcp_web_search.search_prod.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await prod_web_search("cosmos db partitioning", ["learn.microsoft.com"])

        parsed = json.loads(result)
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["ref_number"] == 1
        assert parsed["results"][0]["title"] == "Azure Cosmos DB Overview"
        assert parsed["results"][0]["source_url"] == "https://learn.microsoft.com/azure/cosmos-db/overview"
        assert "learn.microsoft.com" in parsed["summary"]

    @pytest.mark.asyncio
    async def test_uses_subscription_key_header(self) -> None:
        """Verify the Ocp-Apim-Subscription-Key header is used (not Bearer token)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"webPages": {"value": []}}
        mock_response.raise_for_status.return_value = None

        with (
            patch.dict("os.environ", {"BING_SEARCH_API_KEY": "my-bing-key"}),
            patch("mcp_web_search.search_prod.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await prod_web_search("test", ["learn.microsoft.com"])

            # Verify the correct auth header was used
            call_kwargs = mock_client.get.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
            assert headers == {"Ocp-Apim-Subscription-Key": "my-bing-key"}


class TestProdWebSearchHttpError:
    """Tests for HTTP errors from Bing API."""

    @pytest.mark.asyncio
    async def test_http_error_raises_bing_search_failed(self) -> None:
        """When Bing returns an HTTP error, tool execution should fail."""
        with (
            patch.dict("os.environ", {"BING_SEARCH_API_KEY": "test-key"}),
            patch("mcp_web_search.search_prod.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "401 Unauthorized",
                    request=httpx.Request("GET", "https://api.bing.microsoft.com/v7.0/search"),
                    response=httpx.Response(401),
                )
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="Bing search failed"):
                await prod_web_search("test", ["learn.microsoft.com"])

    @pytest.mark.asyncio
    async def test_connection_error_raises_bing_search_failed(self) -> None:
        """When the HTTP connection fails, tool execution should fail."""
        with (
            patch.dict("os.environ", {"BING_SEARCH_API_KEY": "test-key"}),
            patch("mcp_web_search.search_prod.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="Bing search failed"):
                await prod_web_search("test", ["learn.microsoft.com"])


class TestProdWebSearchSiteFilter:
    """Tests for site-scoped query construction."""

    @pytest.mark.asyncio
    async def test_multiple_whitelist_sites_in_query(self) -> None:
        """Verify the site: filter includes all whitelisted domains."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"webPages": {"value": []}}
        mock_response.raise_for_status.return_value = None

        with (
            patch.dict("os.environ", {"BING_SEARCH_API_KEY": "test-key"}),
            patch("mcp_web_search.search_prod.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await prod_web_search("test", ["learn.microsoft.com", "azure.microsoft.com"])

            call_kwargs = mock_client.get.call_args
            params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
            query = params["q"]
            assert "site:learn.microsoft.com" in query
            assert "site:azure.microsoft.com" in query
            assert " OR " in query
