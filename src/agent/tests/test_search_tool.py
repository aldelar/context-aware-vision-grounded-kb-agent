"""Tests for the AI Search hybrid query tool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent.search_tool import SearchResult, search_kb


class TestSearchResult:
    """Test the SearchResult dataclass."""

    def test_defaults(self) -> None:
        result = SearchResult(
            id="article_0",
            article_id="article",
            chunk_index=0,
            content="test content",
            title="Test",
            section_header="Section",
        )
        assert result.image_urls == []
        assert result.score == 0.0
        assert result.department == ""

    def test_with_images(self) -> None:
        result = SearchResult(
            id="article_0",
            article_id="article",
            chunk_index=0,
            content="test",
            title="Test",
            section_header="",
            image_urls=["images/fig1.png", "images/fig2.png"],
            score=0.95,
        )
        assert len(result.image_urls) == 2
        assert result.score == 0.95


class TestSearchKb:
    """Test the search_kb function."""

    def test_empty_query_returns_empty(self) -> None:
        assert search_kb("") == []
        assert search_kb("   ") == []

    @patch("agent.search_tool._search_client")
    @patch("agent.search_tool._embed_query")
    def test_hybrid_search_returns_results(
        self, mock_embed: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_embed.return_value = [0.1] * 1536

        mock_result = {
            "id": "content-understanding_0",
            "article_id": "content-understanding",
            "chunk_index": 0,
            "content": "Azure Content Understanding is...",
            "title": "What is Content Understanding?",
            "section_header": "Overview",
            "image_urls": ["images/framework.png"],
            "department": "engineering",
            "@search.score": 0.87,
        }
        mock_client.search.return_value = [mock_result]

        results = search_kb("What is Content Understanding?")

        assert len(results) == 1
        r = results[0]
        assert r.id == "content-understanding_0"
        assert r.article_id == "content-understanding"
        assert r.chunk_index == 0
        assert r.content == "Azure Content Understanding is..."
        assert r.title == "What is Content Understanding?"
        assert r.section_header == "Overview"
        assert r.image_urls == ["images/framework.png"]
        assert r.score == 0.87
        assert r.department == "engineering"

    @patch("agent.search_tool._search_client")
    @patch("agent.search_tool._embed_query")
    def test_search_with_no_images(
        self, mock_embed: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_embed.return_value = [0.1] * 1536

        mock_result = {
            "id": "article_1",
            "article_id": "article",
            "chunk_index": 1,
            "content": "Some text",
            "title": "Title",
            "section_header": "Header",
            "image_urls": None,
            "@search.score": 0.5,
        }
        mock_client.search.return_value = [mock_result]

        results = search_kb("some query")

        assert len(results) == 1
        assert results[0].image_urls == []

    @patch("agent.search_tool._search_client")
    @patch("agent.search_tool._embed_query")
    def test_search_respects_top_parameter(
        self, mock_embed: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_embed.return_value = [0.1] * 1536
        mock_client.search.return_value = []

        search_kb("query", top=3)

        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs["top"] == 3
