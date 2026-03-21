"""Tests for shared.blob_storage.get_article_ids()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import azure.functions as func
import pytest

from shared.blob_storage import get_article_ids


class TestGetArticleIdsFromBody:
    """get_article_ids returns [article_id] when request body has article_id."""

    def test_returns_single_id_from_json_body(self):
        req = MagicMock(spec=func.HttpRequest)
        req.get_json.return_value = {"article_id": "my-article"}

        result = get_article_ids(req, "https://fake.blob.core.windows.net", "staging")

        assert result == ["my-article"]

    def test_does_not_call_list_articles_when_id_present(self):
        req = MagicMock(spec=func.HttpRequest)
        req.get_json.return_value = {"article_id": "specific-one"}

        with patch("shared.blob_storage.list_articles") as mock_list:
            get_article_ids(req, "https://fake.blob.core.windows.net", "staging")

        mock_list.assert_not_called()


class TestGetArticleIdsFallback:
    """get_article_ids falls back to list_articles when no article_id in body."""

    def test_falls_back_to_list_when_no_article_id_key(self):
        req = MagicMock(spec=func.HttpRequest)
        req.get_json.return_value = {"other_key": "value"}

        with patch("shared.blob_storage.list_articles", return_value=["a", "b"]) as mock_list:
            result = get_article_ids(req, "https://ep.blob.core.windows.net", "staging", depth=2)

        assert result == ["a", "b"]
        mock_list.assert_called_once_with("https://ep.blob.core.windows.net", "staging", depth=2)

    def test_falls_back_to_list_when_article_id_is_empty(self):
        req = MagicMock(spec=func.HttpRequest)
        req.get_json.return_value = {"article_id": ""}

        with patch("shared.blob_storage.list_articles", return_value=["x"]) as mock_list:
            result = get_article_ids(req, "https://ep.blob.core.windows.net", "serving")

        assert result == ["x"]
        mock_list.assert_called_once_with("https://ep.blob.core.windows.net", "serving", depth=1)

    def test_falls_back_to_list_when_article_id_is_none(self):
        req = MagicMock(spec=func.HttpRequest)
        req.get_json.return_value = {"article_id": None}

        with patch("shared.blob_storage.list_articles", return_value=["z"]) as mock_list:
            result = get_article_ids(req, "https://ep.blob.core.windows.net", "staging", depth=2)

        assert result == ["z"]
        mock_list.assert_called_once()

    def test_depth_defaults_to_one(self):
        """Without explicit depth, list_articles is called with depth=1."""
        req = MagicMock(spec=func.HttpRequest)
        req.get_json.return_value = {}

        with patch("shared.blob_storage.list_articles", return_value=["art"]) as mock_list:
            get_article_ids(req, "https://ep.blob.core.windows.net", "serving")

        mock_list.assert_called_once_with("https://ep.blob.core.windows.net", "serving", depth=1)


class TestGetArticleIdsInvalidJson:
    """get_article_ids handles invalid/empty JSON gracefully."""

    def test_falls_back_when_body_is_not_json(self):
        req = MagicMock(spec=func.HttpRequest)
        req.get_json.side_effect = ValueError("No JSON")

        with patch("shared.blob_storage.list_articles", return_value=["fallback"]) as mock_list:
            result = get_article_ids(req, "https://ep.blob.core.windows.net", "staging", depth=2)

        assert result == ["fallback"]
        mock_list.assert_called_once_with("https://ep.blob.core.windows.net", "staging", depth=2)

    def test_falls_back_when_get_json_raises_attribute_error(self):
        req = MagicMock(spec=func.HttpRequest)
        req.get_json.side_effect = AttributeError("oops")

        with patch("shared.blob_storage.list_articles", return_value=["fb"]) as mock_list:
            result = get_article_ids(req, "https://ep.blob.core.windows.net", "staging", depth=2)

        assert result == ["fb"]
        mock_list.assert_called_once()

    def test_returns_empty_when_no_json_and_no_blobs(self):
        req = MagicMock(spec=func.HttpRequest)
        req.get_json.side_effect = ValueError("No JSON")

        with patch("shared.blob_storage.list_articles", return_value=[]):
            result = get_article_ids(req, "https://ep.blob.core.windows.net", "staging")

        assert result == []
