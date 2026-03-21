"""Tests for security_filter parameter in search_kb.

Verifies that the OData filter expression is correctly passed to the
Azure AI Search client.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.search_tool import SearchResult, search_kb


@patch("agent.search_tool._embed_query")
@patch("agent.search_tool._search_client")
class TestSearchKbSecurityFilter:
    """Test search_kb with security_filter parameter."""

    def test_filter_passed_to_search_client(
        self, mock_client: MagicMock, mock_embed: MagicMock
    ) -> None:
        mock_embed.return_value = [0.0] * 1536
        mock_client.search.return_value = []

        search_kb("test query", security_filter="search.in(department, 'engineering', ',')")

        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs["filter"] == "search.in(department, 'engineering', ',')"

    def test_no_filter_when_none(
        self, mock_client: MagicMock, mock_embed: MagicMock
    ) -> None:
        mock_embed.return_value = [0.0] * 1536
        mock_client.search.return_value = []

        search_kb("test query")

        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs["filter"] is None

    def test_filter_none_explicit(
        self, mock_client: MagicMock, mock_embed: MagicMock
    ) -> None:
        mock_embed.return_value = [0.0] * 1536
        mock_client.search.return_value = []

        search_kb("test query", security_filter=None)

        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs["filter"] is None

    def test_multi_department_filter(
        self, mock_client: MagicMock, mock_embed: MagicMock
    ) -> None:
        mock_embed.return_value = [0.0] * 1536
        mock_client.search.return_value = []

        search_kb(
            "test query",
            security_filter="search.in(department, 'engineering,research', ',')",
        )

        call_kwargs = mock_client.search.call_args
        assert "engineering,research" in call_kwargs.kwargs["filter"]

    def test_results_returned_with_filter(
        self, mock_client: MagicMock, mock_embed: MagicMock
    ) -> None:
        mock_embed.return_value = [0.0] * 1536
        mock_client.search.return_value = [
            {
                "id": "eng_0",
                "article_id": "eng-article",
                "chunk_index": 0,
                "content": "Engineering content",
                "title": "Eng Title",
                "section_header": "Overview",
                "department": "engineering",
                "image_urls": [],
                "@search.score": 0.85,
            }
        ]

        results = search_kb(
            "test", security_filter="search.in(department, 'engineering', ',')"
        )

        assert len(results) == 1
        assert results[0].department == "engineering"
