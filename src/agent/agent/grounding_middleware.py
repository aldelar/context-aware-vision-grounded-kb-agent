"""Grounding middleware for deterministic citation and image visibility.

This middleware runs after the chat model returns and patches the final
assistant text only when a grounded search result exists but the model omitted
all visible source or image markers. It preserves the model's answer body and
adds a minimal fallback footer so direct `/responses` clients still receive
discoverable sources.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from agent_framework import ChatContext, ChatMiddleware, ChatResponse, Content, Message

from agent.image_service import get_image_url

_CITATION_PATTERN = re.compile(r"\[Ref\s*#\d+\]|\bRef\s*#\d+\b", re.IGNORECASE)
_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]+\)|/api/images/|\.(?:png|jpe?g|svg|gif)\b", re.IGNORECASE)


def _extract_result_items(payload: object) -> list[dict[str, Any]]:
    """Return search result items from legacy list or current dict payloads."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, list):
            return [item for item in results if isinstance(item, dict)]

    return []


def _latest_search_results(messages: Sequence[Message]) -> list[dict[str, Any]]:
    """Return the latest parsed search-tool results from the chat context."""
    for msg in reversed(messages):
        for content in reversed(msg.contents):
            if content.type != "function_result" or content.result is None:
                continue
            try:
                parsed = json.loads(str(content.result))
            except (json.JSONDecodeError, TypeError):
                continue

            results = _extract_result_items(parsed)
            if results:
                return results

    return []


def _has_visible_citation(text: str) -> bool:
    return bool(_CITATION_PATTERN.search(text))


def _has_visible_image(text: str) -> bool:
    return bool(_IMAGE_PATTERN.search(text))


def _ref_number(result: dict[str, Any], fallback: int) -> int:
    value = result.get("ref_number")
    return value if isinstance(value, int) and value > 0 else fallback


def _first_image_url(result: dict[str, Any]) -> str | None:
    images = result.get("images")
    if isinstance(images, list):
        for image in images:
            if not isinstance(image, dict):
                continue
            url = image.get("url")
            if isinstance(url, str) and url.strip():
                return url.strip()

    article_id = result.get("article_id")
    image_urls = result.get("image_urls")
    if isinstance(article_id, str) and isinstance(image_urls, list):
        for image_path in image_urls:
            if isinstance(image_path, str) and image_path.strip():
                return get_image_url(article_id, image_path.strip())

    return None


def _build_sources_line(results: Sequence[dict[str, Any]]) -> str | None:
    refs: list[str] = []
    for index, result in enumerate(results, start=1):
        refs.append(f"[Ref #{_ref_number(result, index)}]")
        if len(refs) == 3:
            break

    if not refs:
        return None

    return f"Sources: {', '.join(refs)}"


def _build_image_line(results: Sequence[dict[str, Any]]) -> str | None:
    for result in results:
        image_url = _first_image_url(result)
        if not image_url:
            continue

        title = result.get("title")
        alt_text = title.strip() if isinstance(title, str) and title.strip() else "Relevant image"
        return f"Relevant image: ![{alt_text}]({image_url})"

    return None


def _normalize_grounded_text(text: str, results: Sequence[dict[str, Any]]) -> str:
    """Append deterministic grounding markers when the model omitted them."""
    if not results:
        return text

    stripped = text.strip()
    additions: list[str] = []

    if not _has_visible_citation(stripped):
        sources_line = _build_sources_line(results)
        if sources_line:
            additions.append(sources_line)

    if not _has_visible_image(stripped):
        image_line = _build_image_line(results)
        if image_line:
            additions.append(image_line)

    if not additions:
        return text

    separator = "\n\n" if stripped else ""
    addition_block = "\n".join(additions)
    return f"{stripped}{separator}{addition_block}"


def _apply_grounding_fallback(response: ChatResponse, source_messages: Sequence[Message]) -> ChatResponse:
    """Mutate the final assistant text in-place when grounding markers are missing."""
    results = _latest_search_results(source_messages)
    if not results or not response.messages:
        return response

    for message in reversed(response.messages):
        if message.role != "assistant":
            continue

        updated_text = _normalize_grounded_text(message.text, results)
        if updated_text == message.text:
            return response

        for content in message.contents:
            if content.type == "text":
                content.text = updated_text
                return response

        message.contents.insert(0, Content.from_text(updated_text))
        return response

    return response


class GroundingResponseMiddleware(ChatMiddleware):
    """Ensure grounded answers expose visible source and image references."""

    async def process(self, context: ChatContext, next) -> None:  # noqa: A002
        if context.stream:
            context.stream_result_hooks.append(
                lambda response: _apply_grounding_fallback(response, context.messages)
            )

        await next()

        if context.stream:
            return

        if isinstance(context.result, ChatResponse):
            _apply_grounding_fallback(context.result, context.messages)