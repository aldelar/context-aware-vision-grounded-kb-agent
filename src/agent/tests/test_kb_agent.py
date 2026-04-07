"""Tests for the KB Search Agent (Microsoft Agent Framework)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.kb_agent import (
    AgentResponse,
    Citation,
    _SYSTEM_PROMPT,
    _SYSTEM_PROMPT_PATH,
    _get_system_prompt_path,
    _load_system_prompt,
    _normalize_search_query,
    create_agent,
    search_knowledge_base,
)
from agent.search_tool import SearchResult
from agent.security_middleware import SecurityFilterMiddleware
from agent_framework import (
    CompactionProvider,
    InMemoryHistoryProvider,
    SlidingWindowStrategy,
    ToolResultCompactionStrategy,
)


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

    def test_prompt_file_exists(self) -> None:
        assert _SYSTEM_PROMPT_PATH.exists()
        assert _SYSTEM_PROMPT_PATH == Path("/home/aldelar/Code/context-aware-vision-grounded-kb-agent/src/agent/agent/prompts/system_prompt-dev.md")

    def test_prod_prompt_file_exists(self) -> None:
        prod_prompt_path = _get_system_prompt_path("prod")

        assert prod_prompt_path.exists()
        assert prod_prompt_path == Path("/home/aldelar/Code/context-aware-vision-grounded-kb-agent/src/agent/agent/prompts/system_prompt-prod.md")

    def test_loaded_prompt_matches_file(self) -> None:
        assert _load_system_prompt("dev") == _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()

    def test_loaded_prod_prompt_matches_file(self) -> None:
        prod_prompt_path = _get_system_prompt_path("prod")

        assert _load_system_prompt("prod") == prod_prompt_path.read_text(encoding="utf-8").strip()

    def test_prompt_mentions_search_tool(self) -> None:
        assert "search_knowledge_base" in _SYSTEM_PROMPT

    def test_prompt_mentions_citations(self) -> None:
        assert "source" in _SYSTEM_PROMPT.lower() or "cite" in _SYSTEM_PROMPT.lower()

    def test_prompt_mentions_images(self) -> None:
        assert "image" in _SYSTEM_PROMPT.lower()

    def test_prompt_forbids_narrating_tool_use(self) -> None:
        assert "Do NOT say things like \"let's search\"" in _SYSTEM_PROMPT

    def test_prompt_requires_inline_citations(self) -> None:
        assert "Cite sources inline using [Ref #N] markers" in _SYSTEM_PROMPT

    def test_prompt_forbids_external_docs_links(self) -> None:
        assert "Do NOT output bare external documentation links" in _SYSTEM_PROMPT

    def test_prompt_requires_cite_or_omit_behavior(self) -> None:
        assert "If you cannot cite a statement, omit it" in _SYSTEM_PROMPT

    def test_prompt_forbids_placeholder_image_urls(self) -> None:
        assert "Do NOT output placeholders such as <image-id>, <article-id>, <filename>" in _SYSTEM_PROMPT

    def test_prompt_forbids_resource_list_tails(self) -> None:
        assert 'Do NOT add a "For more resources"' in _SYSTEM_PROMPT

    def test_prompt_requires_image_lead_in(self) -> None:
        assert "explain the image's relevance in a cited sentence or bullet immediately before it" in _SYSTEM_PROMPT

    def test_prompt_forbids_orphan_citation_lines(self) -> None:
        assert "Do NOT leave a citation marker on its own line" in _SYSTEM_PROMPT

    def test_prompt_forbids_bulletized_image_lines(self) -> None:
        assert "The image line itself must begin with ![ and must NOT begin with -, *, or a numbered-list marker" in _SYSTEM_PROMPT

    def test_prompt_forbids_speculative_image_leadins(self) -> None:
        assert 'Do NOT write speculative lead-ins such as "a helpful diagram would illustrate"' in _SYSTEM_PROMPT

    def test_prompt_has_final_answer_checklist(self) -> None:
        assert "Before sending the final answer, verify" in _SYSTEM_PROMPT

    def test_prompt_includes_network_security_few_shot(self) -> None:
        assert "Example 1" in _SYSTEM_PROMPT
        assert "What are the network security options for Azure AI Search?" in _SYSTEM_PROMPT

    def test_prompt_includes_image_usage_few_shot(self) -> None:
        assert "Example 2" in _SYSTEM_PROMPT
        assert "include one helpful diagram if available" in _SYSTEM_PROMPT
        assert (
            "![Agentic retrieval architecture](/api/images/agentic-retrieval-overview-html_en-us/images/agentic-retrieval-architecture.png)"
            in _SYSTEM_PROMPT
        )
        assert "This diagram shows the request flow" in _SYSTEM_PROMPT

    def test_prod_prompt_restores_compact_instructions(self) -> None:
        prod_prompt = _load_system_prompt("prod")

        assert "Ground your answers in the search results" in prod_prompt
        assert "Do NOT say things like \"let's search\"" not in prod_prompt
        assert "Example 1" not in prod_prompt


# ---------------------------------------------------------------------------
# Tool function tests
# ---------------------------------------------------------------------------


class TestSearchKnowledgeBaseTool:
    """Test the search_knowledge_base tool function directly."""

    def test_normalize_search_query_plain_string(self) -> None:
        assert _normalize_search_query("  azure content understanding  ") == "azure content understanding"

    def test_normalize_search_query_typed_wrapper(self) -> None:
        assert _normalize_search_query({"type": "string", "value": "Azure Content Understanding"}) == (
            "Azure Content Understanding"
        )

    def test_normalize_search_query_nested_wrapper(self) -> None:
        assert _normalize_search_query({"query": {"type": "string", "value": "Azure AI Search"}}) == (
            "Azure AI Search"
        )

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
    def test_accepts_typed_query_wrapper(self, mock_search: MagicMock, mock_get_url: MagicMock) -> None:
        mock_search.return_value = []
        mock_get_url.return_value = "/api/images/article/images/fig.png"

        search_knowledge_base({"type": "string", "value": "Azure Content Understanding"})

        mock_search.assert_called_once_with("Azure Content Understanding", security_filter=None)

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

    def test_handles_malformed_query_wrapper(self) -> None:
        parsed = json.loads(search_knowledge_base({"type": "string"}))
        assert parsed["error"] == "Search query was missing or malformed."


# ---------------------------------------------------------------------------
# create_agent() factory tests
# ---------------------------------------------------------------------------


class TestCreateAgent:
    """Test the create_agent factory function."""

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.create_chat_client")
    def test_returns_chat_agent(
        self,
        mock_create_chat_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() returns an Agent instance."""
        mock_agent_instance = MagicMock()
        mock_agent_cls.return_value = mock_agent_instance
        mock_create_chat_client.return_value = MagicMock()

        agent = create_agent()

        assert agent is mock_agent_instance
        mock_create_chat_client.assert_called_once()
        mock_agent_cls.assert_called_once()

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.create_chat_client")
    def test_agent_has_search_tool(
        self,
        mock_create_chat_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() configures the search tool."""
        mock_create_chat_client.return_value = MagicMock()
        create_agent()

        call_kwargs = mock_agent_cls.call_args
        assert search_knowledge_base in call_kwargs.kwargs["tools"]

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.create_chat_client")
    def test_agent_name(
        self,
        mock_create_chat_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() sets the agent name."""
        mock_create_chat_client.return_value = MagicMock()
        create_agent()

        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["name"] == "KBSearchAgent"

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.create_chat_client")
    def test_agent_uses_security_and_vision_middleware(
        self,
        mock_create_chat_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() configures security and vision middleware on the agent."""
        mock_client = MagicMock()
        mock_create_chat_client.return_value = mock_client
        create_agent()

        _, kwargs = mock_agent_cls.call_args
        middleware = kwargs["middleware"]
        from agent.security_middleware import SecurityFilterMiddleware
        from agent.vision_middleware import VisionImageMiddleware

        assert len(middleware) == 2
        assert isinstance(middleware[0], SecurityFilterMiddleware)
        assert isinstance(middleware[1], VisionImageMiddleware)

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.create_chat_client")
    def test_agent_has_context_providers(
        self,
        mock_create_chat_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() configures InMemoryHistoryProvider + CompactionProvider."""
        mock_create_chat_client.return_value = MagicMock()
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
    @patch("agent.kb_agent.create_chat_client")
    def test_agent_instantiated_with_client_kwarg(
        self,
        mock_create_chat_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() passes client= (not chat_client=) to Agent."""
        mock_client = MagicMock()
        mock_create_chat_client.return_value = mock_client
        create_agent()

        agent_kwargs = mock_agent_cls.call_args.kwargs
        assert "client" in agent_kwargs
        assert "chat_client" not in agent_kwargs
        assert agent_kwargs["client"] is mock_client

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.create_chat_client")
    def test_agent_has_instructions(
        self,
        mock_create_chat_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """Agent receives instructions (system prompt)."""
        mock_create_chat_client.return_value = MagicMock()
        create_agent()

        agent_kwargs = mock_agent_cls.call_args.kwargs
        assert "instructions" in agent_kwargs
        assert agent_kwargs["instructions"] == _SYSTEM_PROMPT

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.create_chat_client")
    def test_agent_has_security_filter_middleware(
        self,
        mock_create_chat_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() registers SecurityFilterMiddleware on the agent."""
        mock_create_chat_client.return_value = MagicMock()
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
