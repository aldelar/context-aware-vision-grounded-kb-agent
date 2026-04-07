"""Helpers for compacting persisted search tool results and resolving citations.

The live ``search_knowledge_base`` tool returns full chunk content so the agent can
answer with grounded context. When sessions are persisted, that payload is reduced
to a compact citation-friendly form that preserves stable chunk handles plus
summary text for resumed UI rendering.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterator

SEARCH_TOOL_NAME = "search_knowledge_base"
WEB_SEARCH_TOOL_NAME = "web_search"
_MAX_PREVIEW_CHARS = 280
_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_INDEXED_IMAGE_PATTERN = re.compile(r"\[Image:\s*[^\]]+\]\([^)]*\)", re.IGNORECASE)
_WHITESPACE_PATTERN = re.compile(r"\s+")


def compact_serialized_session_for_storage(serialized_session: Any) -> Any:
    """Return a storage-safe copy of the serialized session.

    Search tool messages are rewritten to retain only stable chunk references,
    summary text, and UI-safe metadata. The live in-memory agent interaction is
    unaffected because compaction runs only at persistence time.
    """
    if not isinstance(serialized_session, dict):
        return serialized_session

    for messages in _iter_message_lists(serialized_session):
        for message in messages:
            _compact_search_tool_message(message)
    return serialized_session


def find_citation_reference(
    serialized_session: Any,
    *,
    tool_call_id: str,
    ref_number: int,
) -> dict[str, Any] | None:
    """Resolve a compact stored citation row from a serialized session."""
    if not isinstance(serialized_session, dict):
        return None

    for messages in _iter_message_lists(serialized_session):
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") != "tool":
                continue

            function_result_content = _get_function_result_content(message)
            stored_tool_call_id = str(
                message.get("toolCallId")
                or (function_result_content.get("call_id") if function_result_content else "")
                or ""
            )
            if stored_tool_call_id != tool_call_id:
                continue

            payload = _parse_message_payload(message)
            if not _looks_like_search_payload(payload):
                continue

            results = payload.get("results")
            if not isinstance(results, list):
                continue

            for index, row in enumerate(results, start=1):
                compact_row = _compact_search_result_row(row, index=index)
                if compact_row.get("ref_number") == ref_number:
                    return compact_row

    return None


def _iter_message_lists(serialized_session: dict[str, Any]) -> Iterator[list[Any]]:
    direct_messages = serialized_session.get("messages")
    if isinstance(direct_messages, list):
        yield direct_messages

    state = serialized_session.get("state")
    if not isinstance(state, dict):
        return

    state_messages = state.get("messages")
    if isinstance(state_messages, list):
        yield state_messages

    in_memory = state.get("in_memory")
    if not isinstance(in_memory, dict):
        return

    in_memory_messages = in_memory.get("messages")
    if isinstance(in_memory_messages, list):
        yield in_memory_messages


def _compact_search_tool_message(message: Any) -> None:
    if not isinstance(message, dict) or message.get("role") != "tool":
        return

    payload_target, target_field, original_value = _get_message_payload_target(message)
    if target_field is None or payload_target is None:
        return

    payload = _coerce_payload(original_value)
    if not _is_search_tool_message(message, payload):
        return

    compacted_payload = _compact_search_payload(payload)
    if compacted_payload is None:
        return

    if isinstance(original_value, str):
        payload_target[target_field] = json.dumps(compacted_payload, ensure_ascii=False)
    else:
        payload_target[target_field] = compacted_payload


def _get_message_payload_field(message: dict[str, Any]) -> tuple[str | None, Any]:
    for field in ("content", "result", "output"):
        if field in message:
            return field, message.get(field)
    return None, None


def _get_function_result_content(message: dict[str, Any]) -> dict[str, Any] | None:
    contents = message.get("contents")
    if not isinstance(contents, list):
        return None

    for item in contents:
        if not isinstance(item, dict):
            continue
        if item.get("type") in {"function_result", "function_call_output"}:
            return item

    return None


def _get_content_payload_field(content: dict[str, Any]) -> tuple[str | None, Any]:
    for field in ("result", "output", "content"):
        if field in content:
            return field, content.get(field)
    return None, None


def _get_message_payload_target(message: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None, Any]:
    field, value = _get_message_payload_field(message)
    if field is not None:
        return message, field, value

    content = _get_function_result_content(message)
    if content is None:
        return None, None, None

    field, value = _get_content_payload_field(content)
    if field is None:
        return None, None, None

    return content, field, value


def _parse_message_payload(message: dict[str, Any]) -> dict[str, Any] | None:
    _target, _field, value = _get_message_payload_target(message)
    return _coerce_payload(value)


def _coerce_payload(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value

    if not isinstance(value, str):
        return None

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def _is_search_tool_message(message: dict[str, Any], payload: dict[str, Any] | None) -> bool:
    tool_name = message.get("name")
    if not tool_name:
        function_result_content = _get_function_result_content(message)
        if function_result_content:
            tool_name = function_result_content.get("name")
    if tool_name == SEARCH_TOOL_NAME:
        return True

    if tool_name == WEB_SEARCH_TOOL_NAME:
        return True

    return _looks_like_search_payload(payload)


def _looks_like_search_payload(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False

    results = payload.get("results")
    if not isinstance(results, list):
        return False

    if not results:
        return True

    first = results[0]
    if not isinstance(first, dict):
        return False

    return any(key in first for key in ("article_id", "chunk_index", "chunk_id", "title", "summary", "source_url"))


def _compact_search_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    results = payload.get("results")
    if not isinstance(results, list):
        return None

    compacted_results = [
        _compact_search_result_row(row, index=index)
        for index, row in enumerate(results, start=1)
    ]

    top_summary = _as_string(payload.get("summary")) or _build_top_summary(compacted_results)
    compacted_payload: dict[str, Any] = {
        "results": compacted_results,
        "summary": top_summary,
    }

    error = _as_string(payload.get("error"))
    if error:
        compacted_payload["error"] = error

    return compacted_payload


def _compact_search_result_row(row: Any, *, index: int) -> dict[str, Any]:
    record = row if isinstance(row, dict) else {}

    ref_number = _as_int(record.get("ref_number")) or index
    article_id = _as_string(record.get("article_id"))
    chunk_index = _as_int(record.get("chunk_index"))
    chunk_id = _as_string(record.get("chunk_id")) or _as_string(record.get("id"))
    if not chunk_id and article_id is not None and chunk_index is not None:
        chunk_id = f"{article_id}_{chunk_index}"

    summary = _as_string(record.get("summary")) or _build_preview(record.get("content"))
    preview = summary or _build_preview(record.get("content"))

    compacted: dict[str, Any] = {
        "ref_number": ref_number,
        "content_source": "summary",
    }

    if chunk_id:
        compacted["chunk_id"] = chunk_id
    if article_id:
        compacted["article_id"] = article_id
    if chunk_index is not None:
        compacted["chunk_index"] = chunk_index

    for field in ("indexed_at", "title", "section_header"):
        value = _as_string(record.get(field))
        if value:
            compacted[field] = value

    # Web search result fields
    source_url = _as_string(record.get("source_url"))
    if source_url:
        compacted["source_url"] = source_url
    anchor = _as_string(record.get("anchor"))
    if anchor:
        compacted["anchor"] = anchor

    if preview:
        compacted["summary"] = preview
        compacted["content"] = preview

    image_urls = _normalize_string_list(record.get("image_urls"))
    if image_urls:
        compacted["image_urls"] = image_urls

    images = _normalize_image_list(record.get("images"))
    if images:
        compacted["images"] = images

    return compacted


def _build_top_summary(results: list[dict[str, Any]]) -> str:
    titles = [title for result in results if (title := _as_string(result.get("title")))]
    if not titles:
        return f"{len(results)} result(s) available for citation replay"

    unique_titles = list(dict.fromkeys(titles))
    return f"{len(results)} results covering: {', '.join(unique_titles[:5])}"


def _build_preview(value: Any) -> str:
    text = _as_string(value)
    if not text:
        return ""

    text = _MARKDOWN_IMAGE_PATTERN.sub(" ", text)
    text = _INDEXED_IMAGE_PATTERN.sub(" ", text)
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    if len(text) <= _MAX_PREVIEW_CHARS:
        return text
    return f"{text[:_MAX_PREVIEW_CHARS - 1].rstrip()}…"


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    for entry in value:
        text = _as_string(entry)
        if text:
            normalized.append(text)
    return normalized


def _normalize_image_list(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, str]] = []
    for entry in value:
        if isinstance(entry, str):
            if entry:
                normalized.append({"url": entry})
            continue

        if not isinstance(entry, dict):
            continue

        url = _as_string(entry.get("url"))
        if not url:
            continue

        normalized_entry: dict[str, str] = {"url": url}
        alt = _as_string(entry.get("alt"))
        if alt:
            normalized_entry["alt"] = alt
        normalized.append(normalized_entry)

    return normalized


def _as_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None