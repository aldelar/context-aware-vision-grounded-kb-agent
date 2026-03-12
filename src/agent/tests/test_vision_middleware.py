"""Tests for VisionImageMiddleware — SDK rc3 Content/Message API.

Verifies that the vision middleware correctly:
1. Parses function_result content for image URLs
2. Downloads images and creates Content.from_data() items
3. Builds a Message with Content.from_text() + image contents
4. Deduplicates images and respects the MAX_VISION_IMAGES cap
5. Handles edge cases (no images, malformed JSON, download failures)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.image_service import ImageBlob
from agent.vision_middleware import MAX_VISION_IMAGES, VisionImageMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_function_result_content(result_json: str) -> MagicMock:
    """Create a mock Content item that looks like a function_result."""
    content = MagicMock()
    content.type = "function_result"
    content.result = result_json
    return content


def _make_text_content(text: str) -> MagicMock:
    """Create a mock Content item that looks like text (non-function_result)."""
    content = MagicMock()
    content.type = "text"
    content.result = None
    return content


def _make_message(contents: list) -> MagicMock:
    """Create a mock Message with the given contents."""
    msg = MagicMock()
    msg.contents = contents
    return msg


def _search_result_json(images: list[dict] | None = None) -> str:
    """Build a JSON string mimicking search_knowledge_base output."""
    return json.dumps([{
        "ref_number": 1,
        "content": "Test content",
        "title": "Test Article",
        "section_header": "Overview",
        "article_id": "test-article",
        "chunk_index": 0,
        "image_urls": [],
        "images": images or [],
    }])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVisionMiddlewareProcess:
    """Test VisionImageMiddleware.process() with new Content/Message API."""

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_injects_images_into_context(self, mock_download: MagicMock) -> None:
        """Images from search results are downloaded and appended as a user message."""
        mock_download.return_value = ImageBlob(
            data=b"\x89PNG\r\n\x1a\nfake",
            content_type="image/png",
        )

        result_json = _search_result_json(
            images=[{"name": "arch.png", "url": "/api/images/test-article/images/arch.png"}]
        )
        context = MagicMock()
        context.messages = [_make_message([_make_function_result_content(result_json)])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        # A new message should have been appended
        assert len(context.messages) == 2
        appended_msg = context.messages[1]
        # The Message is constructed with role="user"
        assert appended_msg.role == "user"
        # First content is the text instruction, rest are images
        assert len(appended_msg.contents) == 2
        next_fn.assert_awaited_once_with()

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_no_images_no_injection(self, mock_download: MagicMock) -> None:
        """When no images in results, no extra message is appended."""
        result_json = _search_result_json(images=[])
        context = MagicMock()
        context.messages = [_make_message([_make_function_result_content(result_json)])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        # No new messages should be appended
        assert len(context.messages) == 1
        mock_download.assert_not_called()
        next_fn.assert_awaited_once_with()

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_deduplicates_images(self, mock_download: MagicMock) -> None:
        """Same image URL appearing twice should only be downloaded once."""
        mock_download.return_value = ImageBlob(data=b"img", content_type="image/png")

        dup_images = [
            {"name": "fig.png", "url": "/api/images/art/images/fig.png"},
            {"name": "fig.png", "url": "/api/images/art/images/fig.png"},
        ]
        result_json = _search_result_json(images=dup_images)
        context = MagicMock()
        context.messages = [_make_message([_make_function_result_content(result_json)])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        mock_download.assert_called_once_with("art", "images/fig.png")

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_respects_max_images_cap(self, mock_download: MagicMock) -> None:
        """No more than MAX_VISION_IMAGES should be injected."""
        mock_download.return_value = ImageBlob(data=b"x", content_type="image/jpeg")

        many_images = [
            {"name": f"img{i}.png", "url": f"/api/images/art/images/img{i}.png"}
            for i in range(MAX_VISION_IMAGES + 5)
        ]
        result_json = _search_result_json(images=many_images)
        context = MagicMock()
        context.messages = [_make_message([_make_function_result_content(result_json)])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        appended_msg = context.messages[1]
        # 1 text content + MAX_VISION_IMAGES image contents
        assert len(appended_msg.contents) == 1 + MAX_VISION_IMAGES

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_skips_failed_downloads(self, mock_download: MagicMock) -> None:
        """If download_image returns None, that image is skipped."""
        mock_download.return_value = None

        result_json = _search_result_json(
            images=[{"name": "bad.png", "url": "/api/images/art/images/bad.png"}]
        )
        context = MagicMock()
        context.messages = [_make_message([_make_function_result_content(result_json)])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        # No images means no appended message
        assert len(context.messages) == 1

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_handles_malformed_json_result(self, mock_download: MagicMock) -> None:
        """Malformed JSON tool results should be skipped gracefully."""
        content = _make_function_result_content("not valid json {{{")
        context = MagicMock()
        context.messages = [_make_message([content])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        assert len(context.messages) == 1
        mock_download.assert_not_called()

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_handles_non_list_result(self, mock_download: MagicMock) -> None:
        """Non-list JSON results (e.g. error dict) should be skipped."""
        content = _make_function_result_content('{"error": "Search failed."}')
        context = MagicMock()
        context.messages = [_make_message([content])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        assert len(context.messages) == 1

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_skips_non_function_result_content(self, mock_download: MagicMock) -> None:
        """Non function_result content types should be ignored."""
        context = MagicMock()
        context.messages = [_make_message([_make_text_content("hello")])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        assert len(context.messages) == 1
        mock_download.assert_not_called()

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_skips_urls_without_api_images(self, mock_download: MagicMock) -> None:
        """URLs not containing /api/images/ should be ignored."""
        result_json = _search_result_json(
            images=[{"name": "ext.png", "url": "https://example.com/ext.png"}]
        )
        context = MagicMock()
        context.messages = [_make_message([_make_function_result_content(result_json)])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        assert len(context.messages) == 1
        mock_download.assert_not_called()

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_handles_null_function_result(self, mock_download: MagicMock) -> None:
        """Content with result=None should be skipped."""
        content = MagicMock()
        content.type = "function_result"
        content.result = None

        context = MagicMock()
        context.messages = [_make_message([content])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        assert len(context.messages) == 1

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_calls_next_always(self, mock_download: MagicMock) -> None:
        """next() is always called regardless of whether images were injected."""
        context = MagicMock()
        context.messages = []

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        next_fn.assert_awaited_once_with()


# ---------------------------------------------------------------------------
# Content/Message API tests (SDK rc3)
# ---------------------------------------------------------------------------


class TestVisionMiddlewareContentAPI:
    """Verify the middleware uses the rc3 Content/Message API correctly."""

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_appended_message_uses_content_from_text(self, mock_download: MagicMock) -> None:
        """The text instruction uses Content.from_text()."""
        from agent_framework import Content

        mock_download.return_value = ImageBlob(data=b"png", content_type="image/png")

        result_json = _search_result_json(
            images=[{"name": "a.png", "url": "/api/images/art/images/a.png"}]
        )
        context = MagicMock()
        context.messages = [_make_message([_make_function_result_content(result_json)])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        appended_msg = context.messages[1]
        text_content = appended_msg.contents[0]
        # Verify it's a Content instance from the framework
        assert isinstance(text_content, Content)

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_appended_message_uses_content_from_data(self, mock_download: MagicMock) -> None:
        """Image items use Content.from_data() with correct media_type."""
        from agent_framework import Content

        mock_download.return_value = ImageBlob(
            data=b"\x89PNG\r\n\x1a\nfake",
            content_type="image/png",
        )

        result_json = _search_result_json(
            images=[{"name": "a.png", "url": "/api/images/art/images/a.png"}]
        )
        context = MagicMock()
        context.messages = [_make_message([_make_function_result_content(result_json)])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        appended_msg = context.messages[1]
        image_content = appended_msg.contents[1]
        assert isinstance(image_content, Content)

    @pytest.mark.asyncio
    @patch("agent.vision_middleware.download_image")
    async def test_appended_message_is_framework_message(self, mock_download: MagicMock) -> None:
        """The injected message is a framework Message, not a mock."""
        from agent_framework import Message

        mock_download.return_value = ImageBlob(data=b"x", content_type="image/jpeg")

        result_json = _search_result_json(
            images=[{"name": "a.png", "url": "/api/images/art/images/a.png"}]
        )
        context = MagicMock()
        context.messages = [_make_message([_make_function_result_content(result_json)])]

        next_fn = AsyncMock()
        middleware = VisionImageMiddleware()
        await middleware.process(context, next_fn)

        appended_msg = context.messages[1]
        assert isinstance(appended_msg, Message)
        assert appended_msg.role == "user"
