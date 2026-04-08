"""Tests for the Web Search Agent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.web_search_agent import (
    _load_web_search_prompt,
    create_web_search_agent,
)


class TestWebSearchPrompt:
    """Test the web search agent system prompt."""

    def test_prompt_file_exists(self) -> None:
        prompt_path = Path(__file__).resolve().parent.parent / "agent" / "prompts" / "web_search_agent" / "system_prompt.md"
        assert prompt_path.exists()

    def test_loaded_prompt_is_non_empty(self) -> None:
        prompt = _load_web_search_prompt()
        assert len(prompt) > 100

    def test_prompt_mentions_web_search(self) -> None:
        prompt = _load_web_search_prompt()
        assert "web_search" in prompt

    def test_prompt_mentions_citations(self) -> None:
        prompt = _load_web_search_prompt()
        assert "Web Ref" in prompt

    def test_prompt_does_not_mention_internal_search(self) -> None:
        prompt = _load_web_search_prompt()
        assert "search_knowledge_base" not in prompt


class TestCreateWebSearchAgent:
    """Test the web search agent factory."""

    @patch("agent.web_search_agent.Agent")
    @patch("agent.web_search_agent.create_chat_client")
    def test_returns_agent(
        self,
        mock_create_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        mock_agent_instance = MagicMock()
        mock_agent_cls.return_value = mock_agent_instance
        mock_create_client.return_value = MagicMock()

        agent = create_web_search_agent()

        assert agent is mock_agent_instance
        mock_agent_cls.assert_called_once()

    @patch("agent.web_search_agent.Agent")
    @patch("agent.web_search_agent.create_chat_client")
    def test_agent_name_is_web_search(
        self,
        mock_create_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        mock_create_client.return_value = MagicMock()
        create_web_search_agent()

        kwargs = mock_agent_cls.call_args.kwargs
        assert kwargs["name"] == "WebSearchAgent"
        assert kwargs["id"] == "web-search-agent"

    @patch("agent.web_search_agent.Agent")
    @patch("agent.web_search_agent.create_chat_client")
    def test_has_vision_middleware_only(
        self,
        mock_create_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        mock_create_client.return_value = MagicMock()
        create_web_search_agent()

        kwargs = mock_agent_cls.call_args.kwargs
        middleware = kwargs["middleware"]
        from agent.vision_middleware import VisionImageMiddleware
        assert len(middleware) == 1
        assert isinstance(middleware[0], VisionImageMiddleware)

    @patch("agent.web_search_agent.Agent")
    @patch("agent.web_search_agent.create_chat_client")
    def test_no_security_middleware(
        self,
        mock_create_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        mock_create_client.return_value = MagicMock()
        create_web_search_agent()

        kwargs = mock_agent_cls.call_args.kwargs
        middleware = kwargs["middleware"]
        from agent.security_middleware import SecurityFilterMiddleware
        assert not any(isinstance(m, SecurityFilterMiddleware) for m in middleware)

    @patch("agent.web_search_agent.Agent")
    @patch("agent.web_search_agent.create_chat_client")
    def test_no_context_providers(
        self,
        mock_create_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """Web search agent should have no compaction/history providers (orchestrator handles this)."""
        mock_create_client.return_value = MagicMock()
        create_web_search_agent()

        kwargs = mock_agent_cls.call_args.kwargs
        assert "context_providers" not in kwargs or not kwargs.get("context_providers")

    @patch("agent.web_search_agent.Agent")
    @patch("agent.web_search_agent.create_chat_client")
    def test_has_mcp_tool(
        self,
        mock_create_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """Web search agent should have the MCP web search tool wired."""
        mock_create_client.return_value = MagicMock()
        create_web_search_agent()

        kwargs = mock_agent_cls.call_args.kwargs
        tools = kwargs["tools"]
        assert len(tools) == 1
        from agent_framework import MCPStreamableHTTPTool
        assert isinstance(tools[0], MCPStreamableHTTPTool)
