"""Tests for the MCP web search server tool contract."""

from __future__ import annotations

import json

import pytest

from mcp_web_search.server import call_tool, list_tools


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
