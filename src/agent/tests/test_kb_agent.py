"""Tests for the KB Search Agent (Microsoft Agent Framework)."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.kb_agent import (
    AgentResponse,
    Citation,
    _SYSTEM_PROMPT,
    create_agent,
    search_knowledge_base,
)
from agent.search_tool import SearchResult
from agent.security_middleware import SecurityFilterMiddleware
from agent_framework._compaction import (
    CompactionProvider,
    SlidingWindowStrategy,
    ToolResultCompactionStrategy,
)
from agent_framework._sessions import InMemoryHistoryProvider


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestDataclasses:
    """Test response dataclasses."""

    def test_citation(self) -> None:
        c = Citation(
            article_id="article-1",
            title="Test Article",
            section_header="Overview",
            chunk_index=0,
        )
        assert c.article_id == "article-1"
        assert c.title == "Test Article"

    def test_agent_response_defaults(self) -> None:
        r = AgentResponse(text="Hello")
        assert r.text == "Hello"
        assert r.citations == []
        assert r.images == []

    def test_agent_response_with_data(self) -> None:
        r = AgentResponse(
            text="Answer",
            citations=[Citation("a", "T", "S", 0)],
            images=["https://example.com/img.png"],
        )
        assert len(r.citations) == 1
        assert len(r.images) == 1


# ---------------------------------------------------------------------------
# System prompt tests
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    """Test the system prompt content."""

    def test_prompt_mentions_search_tool(self) -> None:
        assert "search_knowledge_base" in _SYSTEM_PROMPT

    def test_prompt_mentions_citations(self) -> None:
        assert "source" in _SYSTEM_PROMPT.lower() or "cite" in _SYSTEM_PROMPT.lower()

    def test_prompt_mentions_images(self) -> None:
        assert "image" in _SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# Tool function tests
# ---------------------------------------------------------------------------


class TestSearchKnowledgeBaseTool:
    """Test the search_knowledge_base tool function directly."""

    @patch("agent.kb_agent.get_image_url")
    @patch("agent.kb_agent.search_kb")
    def test_returns_json_results(self, mock_search: MagicMock, mock_get_url: MagicMock) -> None:
        mock_search.return_value = [
            SearchResult(
                id="article_0",
                article_id="article",
                chunk_index=0,
                content="Test content",
                title="Test Article",
                section_header="Section",
                department="engineering",
                image_urls=[],
                score=0.9,
            )
        ]
        mock_get_url.return_value = "/api/images/article/images/fig.png"

        result = search_knowledge_base("test query")
        parsed = json.loads(result)

        assert "results" in parsed
        assert "summary" in parsed
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["title"] == "Test Article"
        assert parsed["results"][0]["content"] == "Test content"

    @patch("agent.kb_agent.get_image_url")
    @patch("agent.kb_agent.search_kb")
    def test_includes_citation_fields(self, mock_search: MagicMock, mock_get_url: MagicMock) -> None:
        """Function result includes chunk_index and image_urls for citation extraction."""
        mock_search.return_value = [
            SearchResult(
                id="a_0", article_id="a", chunk_index=3,
                content="C", title="T", section_header="S",
                department="engineering",
                image_urls=["images/fig.png"], score=0.5,
            )
        ]
        mock_get_url.return_value = "/api/images/a/images/fig.png"

        result = search_knowledge_base("query")
        parsed = json.loads(result)

        assert parsed["results"][0]["article_id"] == "a"
        assert parsed["results"][0]["chunk_index"] == 3
        assert parsed["results"][0]["image_urls"] == ["images/fig.png"]

    @patch("agent.kb_agent.get_image_url")
    @patch("agent.kb_agent.search_kb")
    def test_resolves_images(self, mock_search: MagicMock, mock_get_url: MagicMock) -> None:
        mock_search.return_value = [
            SearchResult(
                id="a_0", article_id="article", chunk_index=0,
                content="C", title="T", section_header="S",
                department="engineering",
                image_urls=["images/fig.png"], score=0.5,
            )
        ]
        mock_get_url.return_value = "/api/images/article/images/fig.png"

        result = search_knowledge_base("query")
        parsed = json.loads(result)

        assert len(parsed["results"][0]["images"]) == 1
        assert "fig.png" in parsed["results"][0]["images"][0]["url"]

    @patch("agent.kb_agent.search_kb")
    def test_handles_search_error(self, mock_search: MagicMock) -> None:
        mock_search.side_effect = RuntimeError("connection error")

        result = search_knowledge_base("query")
        parsed = json.loads(result)

        assert "error" in parsed


# ---------------------------------------------------------------------------
# create_agent() factory tests
# ---------------------------------------------------------------------------


class TestCreateAgent:
    """Test the create_agent factory function."""

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_returns_chat_agent(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() returns an Agent instance."""
        mock_agent_instance = MagicMock()
        mock_agent_cls.return_value = mock_agent_instance

        agent = create_agent()

        assert agent is mock_agent_instance
        mock_credential.assert_called_once()
        mock_client_cls.assert_called_once()
        mock_agent_cls.assert_called_once()

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_agent_has_search_tool(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() configures the search tool."""
        create_agent()

        call_kwargs = mock_agent_cls.call_args
        assert search_knowledge_base in call_kwargs.kwargs["tools"]

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_agent_name(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() sets the agent name."""
        create_agent()

        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["name"] == "KBSearchAgent"

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_client_uses_vision_middleware(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() configures vision middleware on the client."""
        create_agent()

        call_kwargs = mock_client_cls.call_args
        middleware = call_kwargs.kwargs["middleware"]
        assert len(middleware) == 1
        from agent.vision_middleware import VisionImageMiddleware
        assert isinstance(middleware[0], VisionImageMiddleware)

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.get_bearer_token_provider")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_uses_default_credential(
        self,
        mock_credential: MagicMock,
        mock_token_provider: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() uses credential with DefaultAzureCredential."""
        create_agent()

        mock_credential.assert_called_once()
        mock_token_provider.assert_called_once_with(
            mock_credential.return_value,
            "https://cognitiveservices.azure.com/.default",
        )
        client_kwargs = mock_client_cls.call_args.kwargs
        assert client_kwargs["credential"] is mock_token_provider.return_value

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_agent_has_context_providers(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() configures InMemoryHistoryProvider + CompactionProvider."""
        create_agent()

        call_kwargs = mock_agent_cls.call_args.kwargs
        providers = call_kwargs["context_providers"]
        assert len(providers) == 2
        assert isinstance(providers[0], InMemoryHistoryProvider)
        assert isinstance(providers[1], CompactionProvider)
        compaction = providers[1]
        assert isinstance(compaction.before_strategy, SlidingWindowStrategy)
        assert compaction.before_strategy.keep_last_groups == 3
        assert isinstance(compaction.after_strategy, ToolResultCompactionStrategy)
        assert compaction.after_strategy.keep_last_tool_call_groups == 1

    @patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "test-key-123"})
    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    def test_uses_api_key_when_provided(
        self,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() uses API key when AZURE_OPENAI_API_KEY is set."""
        create_agent()

        client_kwargs = mock_client_cls.call_args.kwargs
        assert client_kwargs["api_key"] == "test-key-123"
        assert "credential" not in client_kwargs


# ---------------------------------------------------------------------------
# SDK rc3 upgrade validation — verifies new class/kwarg names
# ---------------------------------------------------------------------------


class TestSDKUpgradeValidation:
    """Verify the SDK rc3 upgrade: Agent (not ChatAgent), client= (not chat_client=), etc."""

    def test_imports_agent_not_chat_agent(self) -> None:
        """Module imports Agent from agent_framework, not ChatAgent."""
        from agent import kb_agent

        assert hasattr(kb_agent, "Agent")
        # Verify the imported Agent comes from agent_framework
        from agent_framework import Agent

        assert kb_agent.Agent is Agent

    def test_imports_content_not_old_classes(self) -> None:
        """Vision middleware imports Content (unified), not legacy content classes."""
        from agent import vision_middleware

        from agent_framework import Content

        assert vision_middleware.Content is Content

    def test_imports_message_not_chat_message(self) -> None:
        """Vision middleware imports Message, not ChatMessage."""
        from agent import vision_middleware

        from agent_framework import Message

        assert vision_middleware.Message is Message

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_agent_instantiated_with_client_kwarg(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() passes client= (not chat_client=) to Agent."""
        create_agent()

        agent_kwargs = mock_agent_cls.call_args.kwargs
        assert "client" in agent_kwargs
        assert "chat_client" not in agent_kwargs
        assert agent_kwargs["client"] is mock_client_cls.return_value

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.get_bearer_token_provider")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_credential_path_uses_credential_kwarg(
        self,
        mock_credential: MagicMock,
        mock_token_provider: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """Credential path uses credential= (not ad_token_provider=) on the client."""
        create_agent()

        client_kwargs = mock_client_cls.call_args.kwargs
        assert "credential" in client_kwargs
        assert "ad_token_provider" not in client_kwargs

    @patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "key-456"})
    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    def test_api_key_path_does_not_use_credential_kwarg(
        self,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """API key path uses api_key=, not credential=."""
        create_agent()

        client_kwargs = mock_client_cls.call_args.kwargs
        assert "api_key" in client_kwargs
        assert client_kwargs["api_key"] == "key-456"

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_agent_has_instructions(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """Agent receives instructions (system prompt)."""
        create_agent()

        agent_kwargs = mock_agent_cls.call_args.kwargs
        assert "instructions" in agent_kwargs
        assert agent_kwargs["instructions"] == _SYSTEM_PROMPT

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_agent_has_security_filter_middleware(
        self,
        mock_credential: MagicMock,
        mock_client_cls: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() registers SecurityFilterMiddleware on the agent."""
        create_agent()

        agent_kwargs = mock_agent_cls.call_args.kwargs
        middleware = agent_kwargs["middleware"]
        assert any(isinstance(m, SecurityFilterMiddleware) for m in middleware)


# ---------------------------------------------------------------------------
# Security filter wiring tests
# ---------------------------------------------------------------------------


class TestSecurityFilterWiring:
    """Test that search_knowledge_base builds OData filter from departments."""

    @patch("agent.kb_agent.search_kb")
    def test_passes_security_filter_with_departments(self, mock_search: MagicMock) -> None:
        mock_search.return_value = []

        search_knowledge_base("query", departments=["engineering"])

        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args
        assert call_kwargs.kwargs["security_filter"] == "search.in(department, 'engineering', ',')"

    @patch("agent.kb_agent.search_kb")
    def test_passes_security_filter_with_multiple_departments(self, mock_search: MagicMock) -> None:
        mock_search.return_value = []

        search_knowledge_base("query", departments=["engineering", "research"])

        call_kwargs = mock_search.call_args
        assert call_kwargs.kwargs["security_filter"] == "search.in(department, 'engineering,research', ',')"

    @patch("agent.kb_agent.search_kb")
    def test_no_filter_when_departments_empty(self, mock_search: MagicMock) -> None:
        mock_search.return_value = []

        search_knowledge_base("query", departments=[])

        call_kwargs = mock_search.call_args
        assert call_kwargs.kwargs["security_filter"] is None

    @patch("agent.kb_agent.search_kb")
    def test_no_filter_when_no_kwargs(self, mock_search: MagicMock) -> None:
        mock_search.return_value = []

        search_knowledge_base("query")

        call_kwargs = mock_search.call_args
        assert call_kwargs.kwargs["security_filter"] is None
