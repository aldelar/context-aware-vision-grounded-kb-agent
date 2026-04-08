"""Tests for the MCP web search server tool contract."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from mcp_web_search.server import call_tool, create_session_manager, list_tools, server


class TestListTools:
    """Test tool listing."""

    @pytest.mark.asyncio
    async def test_returns_web_search_tool(self) -> None:
        tools = await list_tools()
        assert len(tools) == 1
        assert tools[0].name == "web_search"
        assert "query" in tools[0].inputSchema["properties"]


class TestCallTool:
    """Test tool invocation contract."""

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self) -> None:
        result = await call_tool("unknown_tool", {})
        parsed = json.loads(result[0].text)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self) -> None:
        result = await call_tool("web_search", {"query": ""})
        parsed = json.loads(result[0].text)
        assert "error" in parsed
        assert "required" in parsed["error"].lower()

    @pytest.mark.asyncio
    async def test_uses_runtime_search_dispatch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "dev")

        with patch("mcp_web_search.server._run_web_search", new=AsyncMock(return_value='{"results": [], "summary": "ok"}')) as mock_search:
            result = await call_tool("web_search", {"query": "test"})

        parsed = json.loads(result[0].text)
        assert parsed["summary"] == "ok"
        mock_search.assert_awaited_once_with("test")

    @pytest.mark.asyncio
    async def test_missing_environment_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        with pytest.raises(RuntimeError, match="ENVIRONMENT"):
            await call_tool("web_search", {"query": "test"})


class TestRuntimeConfiguration:
    """Test environment-driven runtime validation."""

    def test_invalid_environment_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "staging")

        from mcp_web_search.server import _validate_runtime_configuration

        with pytest.raises(RuntimeError, match="ENVIRONMENT"):
            _validate_runtime_configuration()

    def test_prod_environment_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "prod")

        from mcp_web_search.server import _validate_runtime_configuration

        assert _validate_runtime_configuration() == "prod"


class TestSessionManagerConfiguration:
    """Test the production transport configuration."""

    def test_uses_stateless_json_transport(self) -> None:
        with patch("mcp.server.streamable_http_manager.StreamableHTTPSessionManager") as mock_manager:
            create_session_manager()

        mock_manager.assert_called_once_with(
            server,
            json_response=True,
            stateless=True,
        )
