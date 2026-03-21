"""Unit tests for fn_index.summarizer — chunk summary generation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from fn_index.summarizer import summarize_chunk, summarize_chunks


class TestSummarizeChunk:
    """Tests for the single-chunk summarizer."""

    @patch("fn_index.summarizer._get_client")
    def test_returns_summary_on_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="A concise summary."))]
        )
        mock_client.complete.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = summarize_chunk("Some content", "Article Title", "Section A")

        assert result == "A concise summary."
        mock_client.complete.assert_called_once()

    @patch("fn_index.summarizer._get_client")
    def test_returns_empty_string_on_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.complete.side_effect = RuntimeError("LLM unavailable")
        mock_get_client.return_value = mock_client

        result = summarize_chunk("Some content", "Title", "Section")

        assert result == ""

    @patch("fn_index.summarizer._get_client")
    def test_truncates_content_to_2000_chars(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Summary."))]
        )
        mock_client.complete.return_value = mock_response
        mock_get_client.return_value = mock_client

        long_content = "x" * 5000
        summarize_chunk(long_content, "Title", "Section")

        call_args = mock_client.complete.call_args
        prompt = call_args[1]["messages"][0]["content"]
        # The content portion should be truncated to 2000 chars
        assert "x" * 2000 in prompt
        assert "x" * 2001 not in prompt


class TestSummarizeChunks:
    """Tests for batch chunk summarization."""

    @patch("fn_index.summarizer.summarize_chunk")
    def test_returns_correct_count(self, mock_summarize):
        mock_summarize.return_value = "A summary."
        chunks = [
            SimpleNamespace(content="c1", title="T", section_header="S"),
            SimpleNamespace(content="c2", title="T", section_header="S"),
            SimpleNamespace(content="c3", title="T", section_header="S"),
        ]

        result = summarize_chunks(chunks)

        assert len(result) == 3
        assert mock_summarize.call_count == 3

    @patch("fn_index.summarizer.summarize_chunk")
    def test_preserves_order(self, mock_summarize):
        mock_summarize.side_effect = ["Summary 1", "Summary 2"]
        chunks = [
            SimpleNamespace(content="c1", title="T1", section_header="S1"),
            SimpleNamespace(content="c2", title="T2", section_header="S2"),
        ]

        result = summarize_chunks(chunks)

        assert result == ["Summary 1", "Summary 2"]

    @patch("fn_index.summarizer.summarize_chunk")
    def test_empty_chunks_returns_empty_list(self, mock_summarize):
        result = summarize_chunks([])

        assert result == []
        mock_summarize.assert_not_called()
