"""KB Agent — entry point for both local development and Foundry deployment.

Uses the ``from_agent_framework`` adapter from the Azure AI Agent Server SDK
to run the Agent as an HTTP server on port 8088.  The adapter handles:

- The Responses protocol (``/responses`` endpoint)
- SSE streaming (``agent.run_stream`` → Server-Sent Events)
- Health / readiness probes (``/liveness``, ``/readiness``)

Run locally::

    cd src/agent && uv run python main.py

The same ``main.py`` is used in the Dockerfile for Foundry hosted deployment.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from uuid import uuid4
from collections.abc import AsyncGenerator, Mapping
from typing import Any

# ---------------------------------------------------------------------------
# Compatibility shim for azure-ai-agentserver-agentframework 1.0.0b17
#
# The agentserver package imports ``BaseContextProvider`` and
# ``BaseHistoryProvider`` from ``agent_framework``.  These deprecated aliases
# were removed in MAF 1.0 GA — the canonical names are now
# ``ContextProvider`` and ``HistoryProvider``.  Re-inject the aliases so the
# agentserver can load without code changes on its side.
# ---------------------------------------------------------------------------
import agent_framework as _af

if not hasattr(_af, "BaseContextProvider"):
    _af.BaseContextProvider = _af.ContextProvider  # type: ignore[attr-defined]
if not hasattr(_af, "BaseHistoryProvider"):
    _af.BaseHistoryProvider = _af.HistoryProvider  # type: ignore[attr-defined]

from azure.ai.agentserver.agentframework import from_agent_framework
from azure.ai.agentserver.agentframework.persistence import AgentSessionRepository
from agent_framework import AgentResponse, AgentResponseUpdate, AgentSession, Message

# Setup observability — two paths:
#   1. APPLICATIONINSIGHTS_CONNECTION_STRING set → use Azure Monitor (traces + logs + metrics)
#   2. OTEL_EXPORTER_OTLP_ENDPOINT set → use generic OTLP exporter (e.g., Aspire Dashboard)
#   3. Neither → instrumentation enabled but no export (local dev fallback)
#
# configure_azure_monitor() sets up the OTel providers (TracerProvider, LoggerProvider,
# MeterProvider) with Azure Monitor exporters.  enable_instrumentation() then tells the
# agent framework to emit spans for tool calls, model invocations, etc.
_appinsights_conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
_otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
_observability_enabled = False
if _appinsights_conn:
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(
        connection_string=_appinsights_conn,
        logger_name="agent",        # only export our loggers (agent.*), not agent_framework's
        logging_level=logging.INFO,  # export INFO+ to App Insights (default is WARNING)
    )
    _observability_enabled = True
elif _otlp_endpoint:
    # Generic OTLP export — used in Docker dev (Aspire Dashboard) and any
    # environment that sets OTEL_EXPORTER_OTLP_ENDPOINT explicitly.
    from agent_framework.observability import configure_otel_providers

    configure_otel_providers()
    _observability_enabled = True

# Setup logging — force=True ensures a StreamHandler is added even when
# configure_azure_monitor() already attached an OTel handler to the root logger.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    force=True,
)
for _name in ("azure.core", "azure.identity", "httpx"):
    logging.getLogger(_name).setLevel(logging.WARNING)
# agent_framework INFO logs dump full tool call/response payloads (60KB+) which
# exceed App Insights' 64KB telemetry item limit and block the OTel exporter.
logging.getLogger("agent_framework").setLevel(logging.WARNING)
# Suppress noisy OpenTelemetry context-detach errors caused by async context
# propagation across task boundaries during SSE streaming.  These are harmless
# (open-telemetry/opentelemetry-python#4253).
logging.getLogger("opentelemetry.context").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)

if not _observability_enabled:
    logger.info("Agent framework observability disabled for local runtime")


def _patch_agentserver_streaming_converter() -> None:
    """Work around null text deltas emitted by some local streaming responses."""
    from azure.ai.agentserver.agentframework.models.agent_framework_output_streaming_converter import (
        AgentFrameworkOutputStreamingConverter,
        ItemContentOutputText,
        ResponsesAssistantMessageItemResource,
        ResponseContentPartAddedEvent,
        ResponseContentPartDoneEvent,
        ResponseOutputItemAddedEvent,
        ResponseOutputItemDoneEvent,
        ResponseTextDeltaEvent,
        ResponseTextDoneEvent,
        _TextContentStreamingState,
    )

    if getattr(AgentFrameworkOutputStreamingConverter, "_kb_agent_null_text_patch", False):
        return

    async def _read_updates_without_null_text(self, updates):
        async for update in updates:
            if not update.contents:
                continue

            author_name = getattr(update, "author_name", "") or ""
            accepted_types = {"text", "function_call", "user_input_request", "function_result", "error"}
            for content in update.contents:
                if content.type not in accepted_types:
                    continue
                if content.type == "text" and getattr(content, "text", None) is None:
                    logger.debug("Skipping null text delta from agent stream")
                    continue
                yield (content, author_name)

    AgentFrameworkOutputStreamingConverter._read_updates = _read_updates_without_null_text

    async def _convert_contents_without_null_text(self, contents, author_name):
        item_id = self._parent.context.id_generator.generate_message_id()
        output_index = self._parent.next_output_index()

        yield ResponseOutputItemAddedEvent(
            sequence_number=self._parent.next_sequence(),
            output_index=output_index,
            item=ResponsesAssistantMessageItemResource(
                id=item_id,
                status="in_progress",
                content=[],
                created_by=self._parent._build_created_by(author_name),
            ),
        )

        yield ResponseContentPartAddedEvent(
            sequence_number=self._parent.next_sequence(),
            item_id=item_id,
            output_index=output_index,
            content_index=0,
            part=ItemContentOutputText(text="", annotations=[], logprobs=[]),
        )

        text = ""
        async for content in contents:
            delta = getattr(content, "text", None)
            if delta is None:
                logger.debug("Skipping null text delta inside converter state")
                continue
            text += delta

            yield ResponseTextDeltaEvent(
                sequence_number=self._parent.next_sequence(),
                item_id=item_id,
                output_index=output_index,
                content_index=0,
                delta=delta,
            )

        yield ResponseTextDoneEvent(
            sequence_number=self._parent.next_sequence(),
            item_id=item_id,
            output_index=output_index,
            content_index=0,
            text=text,
        )

        content_part = ItemContentOutputText(text=text, annotations=[], logprobs=[])
        yield ResponseContentPartDoneEvent(
            sequence_number=self._parent.next_sequence(),
            item_id=item_id,
            output_index=output_index,
            content_index=0,
            part=content_part,
        )

        item = ResponsesAssistantMessageItemResource(
            id=item_id,
            status="completed",
            content=[content_part],
            created_by=self._parent._build_created_by(author_name),
        )
        yield ResponseOutputItemDoneEvent(
            sequence_number=self._parent.next_sequence(),
            output_index=output_index,
            item=item,
        )

        self._parent.add_completed_output_item(item)

    _TextContentStreamingState.convert_contents = _convert_contents_without_null_text
    AgentFrameworkOutputStreamingConverter._kb_agent_null_text_patch = True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


from ag_ui.core import MessagesSnapshotEvent, RunErrorEvent, RunFinishedEvent, RunStartedEvent, StateSnapshotEvent
from ag_ui.encoder import EventEncoder
from agent_framework.ag_ui import AgentFrameworkAgent
from agent_framework_ag_ui._message_adapters import agui_messages_to_snapshot_format
from agent_framework_ag_ui._types import AGUIRequest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from agent.group_resolver import resolve_departments
from agent.image_service import get_image_url
from agent.search_result_store import find_citation_reference
from agent.search_tool import build_security_filter, get_chunk_by_id
from middleware.request_context import user_claims_var
from middleware.jwt_auth import JWTAuthMiddleware, require_jwt_auth


class _PersistedSessionAgent:
    """Wrap AG-UI requests with the same session repository used by Responses."""

    def __init__(self, agent: Any, session_repository: AgentSessionRepository, *, is_workflow: bool = False) -> None:
        self._agent = agent
        self._session_repository = session_repository
        self._is_workflow = is_workflow

    def __getattr__(self, name: str) -> Any:
        return getattr(self._agent, name)

    @staticmethod
    def _coerce_message_dict(message: Any) -> dict[str, Any] | None:
        if isinstance(message, dict):
            return message

        if isinstance(message, Mapping):
            return dict(message)

        to_dict = getattr(message, "to_dict", None)
        if callable(to_dict):
            dumped = to_dict()
            if isinstance(dumped, dict):
                return dumped

        model_dump = getattr(message, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(exclude_none=True)
            if isinstance(dumped, dict):
                return dumped

        as_dict = getattr(message, "dict", None)
        if callable(as_dict):
            dumped = as_dict()
            if isinstance(dumped, dict):
                return dumped

        return None

    @staticmethod
    def _extract_tool_calls(message: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
        for key in ("toolCalls", "tool_calls"):
            tool_calls = message.get(key)
            if isinstance(tool_calls, list):
                normalized = [tool_call for tool_call in tool_calls if isinstance(tool_call, dict)]
                return key, normalized
        return None, []

    @staticmethod
    def _extract_tool_call_ids(message: dict[str, Any]) -> list[str]:
        _key, tool_calls = _PersistedSessionAgent._extract_tool_calls(message)
        return [
            call_id
            for tool_call in tool_calls
            if isinstance((call_id := tool_call.get("id")), str) and call_id
        ]

    @staticmethod
    def _extract_tool_result_id(message: dict[str, Any]) -> str | None:
        for key in ("toolCallId", "tool_call_id"):
            value = message.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _get_message_id(message: dict[str, Any]) -> str | None:
        for key in ("id", "message_id"):
            value = message.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _stringify_value(value: Any) -> str | None:
        if isinstance(value, str):
            return value
        if value is None:
            return None
        try:
            return json.dumps(value)
        except TypeError:
            return None

    @staticmethod
    def _get_content_blocks(message: dict[str, Any]) -> list[dict[str, Any]]:
        contents = message.get("contents")
        if not isinstance(contents, list):
            return []

        return [block for block in contents if isinstance(block, dict)]

    @staticmethod
    def _extract_text_from_contents(message: dict[str, Any]) -> str | None:
        text_parts = [
            text
            for block in _PersistedSessionAgent._get_content_blocks(message)
            if isinstance(block.get("type"), str)
            and block["type"] in {"text", "input_text", "output_text"}
            and isinstance((text := block.get("text") or block.get("value") or block.get("content")), str)
            and text.strip()
        ]
        return "\n".join(text_parts) if text_parts else None

    @staticmethod
    def _extract_tool_calls_from_contents(message: dict[str, Any]) -> list[dict[str, Any]]:
        tool_calls: list[dict[str, Any]] = []
        for index, block in enumerate(_PersistedSessionAgent._get_content_blocks(message)):
            if block.get("type") != "function_call":
                continue

            name = block.get("name")
            if not isinstance(name, str) or not name:
                continue

            call_id = block.get("call_id") or block.get("id")
            if not isinstance(call_id, str) or not call_id:
                continue

            arguments = _PersistedSessionAgent._stringify_value(block.get("arguments") or block.get("input")) or "{}"
            tool_calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": arguments,
                    },
                }
            )

        return tool_calls

    @staticmethod
    def _extract_tool_result_from_contents(message: dict[str, Any]) -> tuple[str | None, Any]:
        for block in _PersistedSessionAgent._get_content_blocks(message):
            if block.get("type") not in {"function_result", "function_call_output"}:
                continue

            call_id = block.get("call_id") or block.get("toolCallId")
            tool_call_id = call_id if isinstance(call_id, str) and call_id else None
            result = block.get("result")
            if result is None:
                result = block.get("output")
            return tool_call_id, result

        return None, None

    @staticmethod
    def _normalize_content_for_match(content: Any) -> str | None:
        serialized = _PersistedSessionAgent._stringify_value(content)
        if serialized is None:
            return None
        return " ".join(serialized.split())

    @staticmethod
    def _messages_equivalent(left: dict[str, Any], right: dict[str, Any]) -> bool:
        if left.get("role") != right.get("role"):
            return False

        left_tool_call_ids = _PersistedSessionAgent._extract_tool_call_ids(left)
        right_tool_call_ids = _PersistedSessionAgent._extract_tool_call_ids(right)
        if left_tool_call_ids or right_tool_call_ids:
            return left_tool_call_ids == right_tool_call_ids

        left_tool_result_id = _PersistedSessionAgent._extract_tool_result_id(left)
        right_tool_result_id = _PersistedSessionAgent._extract_tool_result_id(right)
        if left_tool_result_id or right_tool_result_id:
            if left_tool_result_id != right_tool_result_id:
                return False

        left_content = _PersistedSessionAgent._normalize_content_for_match(left.get("content"))
        right_content = _PersistedSessionAgent._normalize_content_for_match(right.get("content"))
        if left_content is not None or right_content is not None:
            return left_content == right_content

        return True

    @staticmethod
    def _normalize_stored_session_message(raw_message: Any, index: int) -> dict[str, Any] | None:
        message = _PersistedSessionAgent._coerce_message_dict(raw_message)
        if message is None:
            return None

        role = message.get("role")
        if not isinstance(role, str) or not role:
            return None

        normalized_message: dict[str, Any] = {
            "id": _PersistedSessionAgent._get_message_id(message) or f"{role}-{index + 1}",
            "role": role,
        }

        text_content = _PersistedSessionAgent._extract_text_from_contents(message)

        if role == "assistant":
            tool_calls = _PersistedSessionAgent._extract_tool_calls(message)[1] or _PersistedSessionAgent._extract_tool_calls_from_contents(message)
            if tool_calls:
                normalized_message["toolCalls"] = copy.deepcopy(tool_calls)

            content = text_content or message.get("content")
            if content is not None:
                normalized_message["content"] = copy.deepcopy(content)

            return normalized_message if tool_calls or content is not None else None

        if role == "tool":
            tool_call_id, result = _PersistedSessionAgent._extract_tool_result_from_contents(message)
            tool_call_id = tool_call_id or _PersistedSessionAgent._extract_tool_result_id(message)
            content = result
            if content is None:
                content = text_content or message.get("content")

            if tool_call_id is None or content is None:
                return None

            normalized_message["toolCallId"] = tool_call_id
            tool_name = message.get("toolName")
            if not isinstance(tool_name, str) or not tool_name:
                tool_name = next(
                    (
                        block.get("name")
                        for block in _PersistedSessionAgent._get_content_blocks(message)
                        if isinstance(block.get("name"), str) and block.get("name")
                    ),
                    None,
                )
            if isinstance(tool_name, str) and tool_name:
                normalized_message["toolName"] = tool_name
            normalized_message["content"] = copy.deepcopy(content)
            return normalized_message

        content = text_content or message.get("content")
        if content is None:
            return None

        normalized_message["content"] = copy.deepcopy(content)
        return normalized_message

    @staticmethod
    def _message_to_framework_message(message: dict[str, Any]) -> Message:
        role = str(message.get("role", "user"))
        contents: list[dict[str, Any]] = []

        _tool_calls_key, tool_calls = _PersistedSessionAgent._extract_tool_calls(message)
        for tool_call in tool_calls:
            function_payload = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {}
            name = function_payload.get("name") if isinstance(function_payload.get("name"), str) else None
            if not name:
                continue
            contents.append(
                {
                    "type": "function_call",
                    "call_id": tool_call.get("id"),
                    "name": name,
                    "arguments": function_payload.get("arguments") or "{}",
                }
            )

        if role == "tool":
            contents.append(
                {
                    "type": "function_result",
                    "call_id": _PersistedSessionAgent._extract_tool_result_id(message),
                    "result": copy.deepcopy(message.get("content")),
                }
            )
        else:
            content = message.get("content")
            if content is not None:
                if isinstance(content, list) and all(isinstance(item, dict) for item in content):
                    contents.extend(copy.deepcopy(content))
                else:
                    serialized = content if isinstance(content, str) else _PersistedSessionAgent._stringify_value(content)
                    if serialized is not None:
                        contents.append({"type": "text", "text": serialized})

        message_payload: dict[str, Any] = {
            "type": "chat_message",
            "role": role,
            "contents": contents,
            "additional_properties": copy.deepcopy(message.get("additional_properties") or {}),
        }

        message_id = _PersistedSessionAgent._get_message_id(message)
        if message_id:
            message_payload["message_id"] = message_id

        author_name = message.get("author_name") or message.get("name")
        if isinstance(author_name, str) and author_name:
            message_payload["author_name"] = author_name

        return Message.from_dict(message_payload)

    @staticmethod
    def _restore_message_objects(messages: list[dict[str, Any]], original_messages: list[Any]) -> list[Any]:
        if all(isinstance(message, Message) for message in original_messages):
            return [_PersistedSessionAgent._message_to_framework_message(message) for message in messages]
        return messages

    @staticmethod
    def _has_visible_content(message: dict[str, Any]) -> bool:
        content = message.get("content")
        if isinstance(content, str):
            return bool(content.strip())
        if isinstance(content, list):
            return len(content) > 0
        return content is not None

    @staticmethod
    def _build_assistant_content_message(message: dict[str, Any], tool_calls_key: str | None) -> dict[str, Any] | None:
        if not _PersistedSessionAgent._has_visible_content(message):
            return None

        content_message = copy.deepcopy(message)
        if tool_calls_key:
            content_message.pop(tool_calls_key, None)
        content_message.pop("toolCalls", None)
        content_message.pop("tool_calls", None)

        message_id = _PersistedSessionAgent._get_message_id(content_message)
        if isinstance(message_id, str) and message_id:
            content_message["id"] = f"{message_id}-response"

        return content_message

    @staticmethod
    def _normalize_replayed_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        consumed_indexes: set[int] = set()

        for index, raw_message in enumerate(messages):
            if index in consumed_indexes:
                continue

            message_dict = _PersistedSessionAgent._normalize_stored_session_message(raw_message, index)
            if message_dict is None:
                normalized.append(raw_message)
                continue

            message = copy.deepcopy(message_dict)

            if message.get("role") != "assistant":
                normalized.append(message)
                continue

            tool_calls_key, tool_calls = _PersistedSessionAgent._extract_tool_calls(message)
            if not tool_calls:
                normalized.append(message)
                continue

            expected_tool_call_ids = _PersistedSessionAgent._extract_tool_call_ids(message)
            if not expected_tool_call_ids:
                normalized.append(message)
                continue

            turn_end = len(messages)
            for candidate_index in range(index + 1, len(messages)):
                candidate = _PersistedSessionAgent._normalize_stored_session_message(messages[candidate_index], candidate_index)
                if candidate is not None and candidate.get("role") == "user":
                    turn_end = candidate_index
                    break

            immediate_ids: list[str] = []
            cursor = index + 1
            while cursor < turn_end:
                candidate = _PersistedSessionAgent._normalize_stored_session_message(messages[cursor], cursor)
                if candidate is None or candidate.get("role") != "tool":
                    break

                tool_result_id = _PersistedSessionAgent._extract_tool_result_id(candidate)
                if tool_result_id in expected_tool_call_ids:
                    immediate_ids.append(tool_result_id)
                cursor += 1

            if immediate_ids == expected_tool_call_ids:
                normalized.append(message)
                continue

            moved_tool_messages: list[dict[str, Any]] = []
            consumed_tool_indexes: set[int] = set()
            for tool_call_id in expected_tool_call_ids:
                for candidate_index in range(index + 1, turn_end):
                    if candidate_index in consumed_tool_indexes:
                        continue

                    candidate = _PersistedSessionAgent._normalize_stored_session_message(messages[candidate_index], candidate_index)
                    if candidate is None or candidate.get("role") != "tool":
                        continue

                    if _PersistedSessionAgent._extract_tool_result_id(candidate) != tool_call_id:
                        continue

                    moved_tool_messages.append(copy.deepcopy(candidate))
                    consumed_tool_indexes.add(candidate_index)
                    break

            if moved_tool_messages:
                stripped_tool_call_message = copy.deepcopy(message)
                stripped_tool_call_message.pop("content", None)
                normalized.append(stripped_tool_call_message)
                normalized.extend(moved_tool_messages)
                content_message = _PersistedSessionAgent._build_assistant_content_message(message, tool_calls_key)
                if content_message is not None:
                    normalized.append(content_message)
                consumed_indexes.update(consumed_tool_indexes)
                logger.info(
                    "Normalized AG-UI replayed tool transcript for %s tool call(s)",
                    len(moved_tool_messages),
                )
                continue

            content_message = _PersistedSessionAgent._build_assistant_content_message(message, tool_calls_key)
            if content_message is not None:
                normalized.append(content_message)
                logger.warning(
                    "Dropped historical tool call metadata for assistant message %s because matching tool results were absent",
                    message.get("id", "<unknown>"),
                )
            else:
                logger.warning(
                    "Dropped assistant tool call message %s because matching tool results were absent and no visible content remained",
                    message.get("id", "<unknown>"),
                )

        return normalized

    @staticmethod
    def _collect_missing_tool_call_ids(messages: list[Any]) -> list[str]:
        missing_tool_call_ids: set[str] = set()

        for index, raw_message in enumerate(messages):
            message = _PersistedSessionAgent._normalize_stored_session_message(raw_message, index)
            if message is None:
                continue

            expected_tool_call_ids = _PersistedSessionAgent._extract_tool_call_ids(message)
            if not expected_tool_call_ids:
                continue

            turn_end = len(messages)
            for candidate_index in range(index + 1, len(messages)):
                candidate = _PersistedSessionAgent._normalize_stored_session_message(messages[candidate_index], candidate_index)
                if candidate is not None and candidate.get("role") == "user":
                    turn_end = candidate_index
                    break

            observed_tool_call_ids: list[str] = []
            cursor = index + 1
            while cursor < turn_end:
                candidate = _PersistedSessionAgent._normalize_stored_session_message(messages[cursor], cursor)
                if candidate is None or candidate.get("role") != "tool":
                    break

                observed_tool_call_ids.append(_PersistedSessionAgent._extract_tool_result_id(candidate) or "")
                cursor += 1

            for tool_call_index, tool_call_id in enumerate(expected_tool_call_ids):
                if tool_call_index >= len(observed_tool_call_ids) or observed_tool_call_ids[tool_call_index] != tool_call_id:
                    missing_tool_call_ids.add(tool_call_id)

        return list(missing_tool_call_ids)

    @staticmethod
    def _extract_session_history_messages(session: AgentSession | None) -> list[dict[str, Any]]:
        if session is None:
            return []

        state = getattr(session, "state", None)
        if not isinstance(state, dict):
            return []

        candidate_lists: list[Any] = []
        if isinstance(state.get("messages"), list):
            candidate_lists.append(state.get("messages"))

        in_memory = state.get("in_memory")
        if isinstance(in_memory, dict) and isinstance(in_memory.get("messages"), list):
            candidate_lists.append(in_memory.get("messages"))

        for candidate_list in candidate_lists:
            normalized_messages = [
                message
                for index, raw_message in enumerate(candidate_list)
                if (message := _PersistedSessionAgent._normalize_stored_session_message(raw_message, index)) is not None
            ]
            if normalized_messages:
                return normalized_messages

        return []

    @staticmethod
    def _merge_stored_history(
        request_messages: list[Any],
        stored_messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]] | None:
        stored_index_by_id: dict[str, int] = {}
        for index, stored_message in enumerate(stored_messages):
            message_id = _PersistedSessionAgent._get_message_id(stored_message)
            if isinstance(message_id, str) and message_id:
                stored_index_by_id[message_id] = index

        matched_request_indexes: list[int] = []
        normalized_request_messages: list[dict[str, Any] | None] = []
        for index, raw_message in enumerate(request_messages):
            message = _PersistedSessionAgent._normalize_stored_session_message(raw_message, index)
            normalized_request_messages.append(message)
            if message is None:
                continue

            message_id = _PersistedSessionAgent._get_message_id(message)
            if isinstance(message_id, str) and message_id in stored_index_by_id:
                matched_request_indexes.append(index)

        if not matched_request_indexes:
            stored_replay_messages = [
                message
                for message in stored_messages
                if message.get("role") != "tool"
            ]
            matched_prefix_length = 0
            while (
                matched_prefix_length < len(stored_replay_messages)
                and matched_prefix_length < len(normalized_request_messages)
            ):
                request_message = normalized_request_messages[matched_prefix_length]
                if request_message is None:
                    break
                if not _PersistedSessionAgent._messages_equivalent(
                    request_message,
                    stored_replay_messages[matched_prefix_length],
                ):
                    break
                matched_prefix_length += 1

            if matched_prefix_length == 0:
                return None

            tail_messages = [
                copy.deepcopy(message)
                for message in normalized_request_messages[matched_prefix_length:]
                if message is not None
            ]
            return [
                *(copy.deepcopy(message) for message in stored_messages),
                *tail_messages,
            ]

        first_matched_request_index = matched_request_indexes[0]
        last_matched_request_index = matched_request_indexes[-1]

        prefix_messages = [
            copy.deepcopy(message)
            for message in normalized_request_messages[:first_matched_request_index]
            if message is not None and not isinstance(_PersistedSessionAgent._get_message_id(message), str)
            or (
                message is not None
                and isinstance(_PersistedSessionAgent._get_message_id(message), str)
                and _PersistedSessionAgent._get_message_id(message) not in stored_index_by_id
            )
        ]
        tail_messages = [
            copy.deepcopy(message)
            for message in normalized_request_messages[last_matched_request_index + 1 :]
            if message is not None and not isinstance(_PersistedSessionAgent._get_message_id(message), str)
            or (
                message is not None
                and isinstance(_PersistedSessionAgent._get_message_id(message), str)
                and _PersistedSessionAgent._get_message_id(message) not in stored_index_by_id
            )
        ]

        return [
            *prefix_messages,
            *(copy.deepcopy(message) for message in stored_messages),
            *tail_messages,
        ]

    @staticmethod
    def _summarize_message_flow(messages: list[Any]) -> list[str]:
        summary: list[str] = []
        for index, raw_message in enumerate(messages):
            message = _PersistedSessionAgent._normalize_stored_session_message(raw_message, index)
            if message is None:
                summary.append(type(raw_message).__name__)
                continue

            role = str(message.get("role", "unknown"))
            message_id = _PersistedSessionAgent._get_message_id(message) or "<no-id>"
            tool_call_ids = _PersistedSessionAgent._extract_tool_call_ids(message)
            tool_result_id = _PersistedSessionAgent._extract_tool_result_id(message)
            if tool_call_ids:
                summary.append(f"{role}:{message_id}:tool_calls={','.join(tool_call_ids)}")
            elif tool_result_id:
                summary.append(f"{role}:{message_id}:tool_result={tool_result_id}")
            else:
                summary.append(f"{role}:{message_id}")

        return summary

    @staticmethod
    def _merge_session_metadata(*sessions: Any) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for candidate in sessions:
            metadata = getattr(candidate, "metadata", None)
            if isinstance(metadata, dict):
                merged.update(metadata)
        return merged

    @staticmethod
    def _merge_session_state(
        stored_session: AgentSession | None,
        request_session: AgentSession | None,
        *,
        include_history: bool,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {}

        for session in (stored_session, request_session):
            if session is None:
                continue

            for key, value in getattr(session, "state", {}).items():
                if not include_history and key in {"in_memory", "messages"}:
                    continue
                merged[key] = copy.deepcopy(value)

        return merged

    @staticmethod
    def _get_session_message_count(session: AgentSession | None) -> int:
        if session is None:
            return 0

        state = getattr(session, "state", None)
        if not isinstance(state, dict):
            return 0

        in_memory = state.get("in_memory", {})
        if isinstance(in_memory, dict):
            messages = in_memory.get("messages", [])
            if isinstance(messages, list) and messages:
                return len(messages)

        direct_messages = state.get("messages", [])
        if isinstance(direct_messages, list):
            return len(direct_messages)

        return 0

    @classmethod
    def _extract_visible_request_messages(cls, raw_messages: list[Any]) -> list[dict[str, Any]]:
        normalized_messages = [
            message
            for index, raw_message in enumerate(raw_messages)
            if (message := cls._normalize_stored_session_message(raw_message, index)) is not None
        ]
        if not normalized_messages:
            return []

        return cls._normalize_replayed_messages(normalized_messages)

    @classmethod
    def _extract_workflow_response_messages(cls, updates: list[Any]) -> list[Message]:
        response_updates = [update for update in updates if isinstance(update, AgentResponseUpdate)]
        if not response_updates:
            return []

        response = AgentResponse.from_updates(response_updates)
        normalized_messages = [
            message
            for index, raw_message in enumerate(response.messages)
            if (message := cls._normalize_stored_session_message(raw_message, index)) is not None
        ]
        if not normalized_messages:
            return []

        normalized_messages = cls._normalize_replayed_messages(normalized_messages)
        return [cls._message_to_framework_message(message) for message in normalized_messages]

    @classmethod
    def _coerce_framework_messages(cls, candidate: Any) -> list[Message]:
        if isinstance(candidate, AgentResponse):
            messages = getattr(candidate, "messages", None)
            return list(messages) if isinstance(messages, list) else []

        if isinstance(candidate, Message):
            return [candidate]

        normalized_message = cls._normalize_stored_session_message(candidate, 0)
        if normalized_message is not None:
            return [cls._message_to_framework_message(normalized_message)]

        if isinstance(candidate, list):
            coerced_messages: list[Message] = []
            for index, item in enumerate(candidate):
                if isinstance(item, Message):
                    coerced_messages.append(item)
                    continue

                normalized_item = cls._normalize_stored_session_message(item, index)
                if normalized_item is None:
                    return []
                coerced_messages.append(cls._message_to_framework_message(normalized_item))

            return coerced_messages

        return []

    @classmethod
    def _extract_request_payload_messages(cls, payload: Any) -> list[Message]:
        direct_messages = cls._coerce_framework_messages(payload)
        if direct_messages:
            return direct_messages

        if isinstance(payload, Mapping):
            for key in ("agent_response", "response", "full_conversation", "messages", "data"):
                nested_payload = payload.get(key)
                if nested_payload is None:
                    continue

                nested_messages = cls._extract_request_payload_messages(nested_payload)
                if nested_messages:
                    return nested_messages

            return []

        for attr in ("agent_response", "response", "full_conversation", "messages", "data"):
            nested_payload = getattr(payload, attr, None)
            if nested_payload is None or nested_payload is payload:
                continue

            nested_messages = cls._extract_request_payload_messages(nested_payload)
            if nested_messages:
                return nested_messages

        return []

    @classmethod
    def _extract_workflow_pending_request_messages(
        cls,
        pending_requests: Mapping[str, Any] | None,
    ) -> list[Message]:
        if not isinstance(pending_requests, Mapping):
            return []

        extracted_messages: list[Message] = []
        for request_event in pending_requests.values():
            request_messages = cls._extract_request_payload_messages(getattr(request_event, "data", request_event))
            for message in request_messages:
                cls._append_history_message_if_new(extracted_messages, message)

        return extracted_messages

    @classmethod
    def _extract_workflow_approval_update_messages(cls, updates: list[Any]) -> list[Message]:
        extracted_messages: list[Message] = []

        for update in updates:
            update_message = cls._coerce_message_dict(update)
            if update_message is None:
                continue

            for block in cls._get_content_blocks(update_message):
                if block.get("type") != "function_approval_request":
                    continue

                function_call = block.get("function_call")
                if not isinstance(function_call, Mapping):
                    continue

                function_name = function_call.get("name")
                if not isinstance(function_name, str) or function_name not in {"request_info", "confirm_changes"}:
                    continue

                for message in cls._extract_request_payload_messages(function_call.get("arguments")):
                    cls._append_history_message_if_new(extracted_messages, message)

        return extracted_messages

    @classmethod
    def _append_history_message_if_new(cls, history: list[Message], message: Message) -> None:
        normalized_message = cls._normalize_stored_session_message(message, len(history))
        if normalized_message is None:
            return

        if history:
            last_message = cls._normalize_stored_session_message(history[-1], len(history) - 1)
            if last_message is not None and cls._messages_equivalent(last_message, normalized_message):
                return

        history.append(message)

    @classmethod
    def _append_workflow_history_message_if_new(
        cls,
        history: list[Message],
        message: Message,
        turn_start_index: int,
    ) -> None:
        normalized_message = cls._normalize_stored_session_message(message, len(history))
        if normalized_message is None:
            return

        for index in range(max(turn_start_index, 0), len(history)):
            existing_message = cls._normalize_stored_session_message(history[index], index)
            if existing_message is not None and cls._messages_equivalent(existing_message, normalized_message):
                return

        history.append(message)

    @classmethod
    def _seed_workflow_history_from_updates(
        cls,
        active_session: AgentSession,
        stored_session: AgentSession | None,
        raw_messages: list[Any],
        updates: list[Any],
        pending_request_events: Mapping[str, Any] | None = None,
    ) -> int:
        base_history = cls._extract_session_history_messages(stored_session)
        using_stored_history = bool(base_history)
        if not base_history:
            base_history = cls._extract_visible_request_messages(raw_messages)

        synthesized_history = [cls._message_to_framework_message(message) for message in base_history]

        if using_stored_history:
            visible_request_messages = cls._extract_visible_request_messages(raw_messages)
            latest_user_message = next(
                (message for message in reversed(visible_request_messages) if message.get("role") == "user"),
                None,
            )
            if latest_user_message is not None:
                cls._append_history_message_if_new(
                    synthesized_history,
                    cls._message_to_framework_message(latest_user_message),
                )

        current_turn_start_index = len(synthesized_history)
        for index in range(len(synthesized_history) - 1, -1, -1):
            existing_message = cls._normalize_stored_session_message(synthesized_history[index], index)
            if existing_message is not None and existing_message.get("role") == "user":
                current_turn_start_index = index
                break

        for message in cls._extract_workflow_response_messages(updates):
            cls._append_workflow_history_message_if_new(
                synthesized_history,
                message,
                current_turn_start_index,
            )

        for message in cls._extract_workflow_pending_request_messages(pending_request_events):
            cls._append_workflow_history_message_if_new(
                synthesized_history,
                message,
                current_turn_start_index,
            )

        for message in cls._extract_workflow_approval_update_messages(updates):
            cls._append_workflow_history_message_if_new(
                synthesized_history,
                message,
                current_turn_start_index,
            )

        if not synthesized_history:
            return 0

        if not isinstance(active_session.state, dict):
            active_session.state = {}

        in_memory = active_session.state.get("in_memory")
        if not isinstance(in_memory, dict):
            in_memory = {}
            active_session.state["in_memory"] = in_memory

        in_memory["messages"] = synthesized_history
        return len(synthesized_history)

    async def run(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncGenerator[Any, None]:
        raw_messages = messages
        preserve_framework_messages = all(isinstance(message, Message) for message in raw_messages)
        session = kwargs.get("session")
        conversation_id = getattr(session, "service_session_id", None)
        active_session = session
        provider_conversation_id = conversation_id if not raw_messages else None
        stored_session: AgentSession | None = None

        if conversation_id:
            stored_session = await self._session_repository.get(conversation_id)

            if self._is_workflow:
                # WorkflowAgent uses internal handoff protocol messages
                # (request_info, confirm_changes) that normalization corrupts.
                # Pass only the last user message — the workflow creates a fresh
                # Workflow per request and doesn't need the replay history.
                last_user_messages = [
                    msg for msg in raw_messages
                    if (self._coerce_message_dict(msg) or {}).get("role") == "user"
                ]
                messages = last_user_messages[-1:] if last_user_messages else raw_messages
                if preserve_framework_messages and messages:
                    messages = self._restore_message_objects(
                        [self._normalize_stored_session_message(m, 0) or m for m in messages],
                        messages,
                    )
            elif raw_messages and stored_session is not None:
                missing_tool_call_ids = self._collect_missing_tool_call_ids(raw_messages)
                if missing_tool_call_ids:
                    stored_history_messages = self._extract_session_history_messages(stored_session)
                    repaired_messages = self._merge_stored_history(raw_messages, stored_history_messages)
                    if repaired_messages is not None and not self._collect_missing_tool_call_ids(repaired_messages):
                        messages = self._restore_message_objects(repaired_messages, raw_messages)
                        logger.info(
                            "Rebuilt malformed AG-UI replay from stored session history for thread %s",
                            conversation_id,
                        )
                    else:
                        normalized_messages = self._normalize_replayed_messages(raw_messages)
                        messages = (
                            self._restore_message_objects(normalized_messages, raw_messages)
                            if preserve_framework_messages
                            else normalized_messages
                        )
                        logger.warning(
                            "Malformed AG-UI replay remained after stored-session repair for thread %s; missing tool_call_ids=%s flow=%s",
                            conversation_id,
                            missing_tool_call_ids,
                            self._summarize_message_flow(raw_messages),
                        )
                else:
                    normalized_messages = self._normalize_replayed_messages(raw_messages)
                    messages = (
                        self._restore_message_objects(normalized_messages, raw_messages)
                        if preserve_framework_messages
                        else normalized_messages
                    )
            else:
                normalized_messages = self._normalize_replayed_messages(raw_messages)
                messages = (
                    self._restore_message_objects(normalized_messages, raw_messages)
                    if preserve_framework_messages
                    else normalized_messages
                )

            # AG-UI already replays the full browser transcript on each turn.
            # Reusing persisted history here duplicates prior messages and can
            # break tool-call adjacency on follow-up requests.
            should_reuse_stored_session = stored_session is not None and not messages

            if should_reuse_stored_session:
                active_session = stored_session
            elif active_session is None:
                active_session = AgentSession(service_session_id=conversation_id)

            if active_session is not None:
                if stored_session is not None and active_session is not stored_session:
                    active_session.state = self._merge_session_state(
                        stored_session,
                        active_session,
                        include_history=False,
                    )

                merged_metadata = self._merge_session_metadata(stored_session, active_session, session)
                if merged_metadata:
                    active_session.metadata = merged_metadata

                active_session.service_session_id = provider_conversation_id
                if provider_conversation_id is None:
                    logger.info(
                        "Disabled provider-side conversation continuation for replayed AG-UI thread %s",
                        conversation_id,
                    )
            kwargs["session"] = active_session
        else:
            if not self._is_workflow:
                normalized_messages = self._normalize_replayed_messages(raw_messages)
                messages = (
                    self._restore_message_objects(normalized_messages, raw_messages)
                    if preserve_framework_messages
                    else normalized_messages
                )

        captured_updates: list[Any] = []
        run_completed = False
        try:
            async for update in self._agent.run(messages, **kwargs):
                if self._is_workflow:
                    captured_updates.append(update)
                yield update
            run_completed = True
        finally:
            if conversation_id and active_session is not None:
                active_session.service_session_id = conversation_id
                msg_count = self._get_session_message_count(active_session)
                pending_request_events = None
                if self._is_workflow:
                    maybe_pending_requests = getattr(self._agent, "latest_pending_requests", None)
                    if isinstance(maybe_pending_requests, Mapping):
                        pending_request_events = maybe_pending_requests
                should_synthesize_workflow_history = self._is_workflow and msg_count == 0 and (
                    run_completed or bool(captured_updates) or bool(pending_request_events)
                )
                if should_synthesize_workflow_history:
                    msg_count = self._seed_workflow_history_from_updates(
                        active_session,
                        stored_session,
                        raw_messages,
                        captured_updates,
                        pending_request_events,
                    )
                    if msg_count:
                        if run_completed:
                            logger.warning(
                                "Synthesized workflow session history for thread %s from streamed updates (message_count=%d)",
                                conversation_id,
                                msg_count,
                            )
                        else:
                            logger.warning(
                                "Synthesized workflow session history for thread %s after AG-UI interrupted the workflow stream (message_count=%d)",
                                conversation_id,
                                msg_count,
                            )
                logger.info(
                    "Persisting session for thread %s (message_count=%d)",
                    conversation_id,
                    msg_count,
                )
                await self._session_repository.set(conversation_id, active_session)


async def _build_ag_ui_connect_restore_events(
    input_data: Mapping[str, Any],
    session_repository: AgentSessionRepository | None,
) -> tuple[str, list[Any]] | None:
    """Build AG-UI restore events for an existing thread connect request.

    CopilotKit clears the local AG-UI agent messages and state before calling
    ``connectAgent``. When the request is only reattaching to an existing
    thread, stream the persisted session snapshot directly so the connect flow
    restores the current transcript instead of wiping the UI to empty.
    """
    if session_repository is None:
        return None

    thread_id = input_data.get("thread_id")
    if not isinstance(thread_id, str) or not thread_id.strip():
        return None

    if input_data.get("messages") or input_data.get("resume") is not None:
        return None

    stored_session = await session_repository.get(thread_id)
    if stored_session is None:
        return None

    restored_state = _PersistedSessionAgent._merge_session_state(
        stored_session,
        None,
        include_history=False,
    )
    restored_messages = _PersistedSessionAgent._extract_session_history_messages(stored_session)
    if not restored_state and not restored_messages:
        return None

    run_id = input_data.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        run_id = uuid4().hex

    restore_events: list[Any] = [RunStartedEvent(thread_id=thread_id, run_id=run_id)]
    if restored_state:
        restore_events.append(StateSnapshotEvent(snapshot=restored_state))
    if restored_messages:
        restore_events.append(MessagesSnapshotEvent(messages=agui_messages_to_snapshot_format(restored_messages)))
    restore_events.append(RunFinishedEvent(thread_id=thread_id, run_id=run_id))
    return thread_id, restore_events


def _add_persisted_ag_ui_endpoint(
    app: FastAPI,
    protocol_runner: AgentFrameworkAgent,
    *,
    path: str = "/",
    session_repository: AgentSessionRepository | None = None,
) -> None:
    """Register the AG-UI endpoint with persisted connect-state restoration."""

    @app.post(path, tags=["AG-UI"], dependencies=[Depends(require_jwt_auth)], response_model=None)  # type: ignore[arg-type]
    async def agent_endpoint(request_body: AGUIRequest) -> StreamingResponse:
        try:
            input_data = request_body.model_dump(exclude_none=True)
            logger.debug(
                f"[{path}] Received request - Run ID: {input_data.get('run_id', 'no-run-id')}, "
                f"Thread ID: {input_data.get('thread_id', 'no-thread-id')}, "
                f"Messages: {len(input_data.get('messages', []))}"
            )
            logger.info(f"Received request at {path}: {input_data.get('run_id', 'no-run-id')}")

            async def event_generator() -> AsyncGenerator[str]:
                encoder = EventEncoder()
                event_count = 0
                try:
                    connect_restore = await _build_ag_ui_connect_restore_events(input_data, session_repository)
                    if connect_restore is not None:
                        thread_id, restore_events = connect_restore
                        logger.info(
                            "[%s] Restoring persisted AG-UI connect snapshot for thread %s",
                            path,
                            thread_id,
                        )
                        for event in restore_events:
                            event_count += 1
                            yield encoder.encode(event)
                        logger.info("[%s] Completed streaming %d restore events", path, event_count)
                        return

                    async for event in protocol_runner.run(input_data):
                        event_count += 1
                        event_type_name = getattr(event, "type", type(event).__name__)
                        if "TOOL_CALL" in str(event_type_name) or "RUN" in str(event_type_name):
                            if hasattr(event, "model_dump"):
                                event_data = event.model_dump(exclude_none=True)
                                logger.info(f"[{path}] Event {event_count}: {event_type_name} - {event_data}")
                            else:
                                logger.info(f"[{path}] Event {event_count}: {event_type_name}")

                        try:
                            encoded = encoder.encode(event)
                        except Exception as encode_error:
                            logger.exception("[%s] Failed to encode event %s", path, event_type_name)
                            run_error = RunErrorEvent(
                                message="An internal error has occurred while streaming events.",
                                code=type(encode_error).__name__,
                            )
                            try:
                                yield encoder.encode(run_error)
                            except Exception:
                                logger.exception("[%s] Failed to encode RUN_ERROR event", path)
                            return

                        logger.debug(
                            f"[{path}] Encoded as: {encoded[:200]}..."
                            if len(encoded) > 200
                            else f"[{path}] Encoded as: {encoded}"
                        )
                        yield encoded

                    logger.info(f"[{path}] Completed streaming {event_count} events")
                except Exception as stream_error:
                    logger.exception("[%s] Streaming failed", path)
                    run_error = RunErrorEvent(
                        message="An internal error has occurred while streaming events.",
                        code=type(stream_error).__name__,
                    )
                    try:
                        yield encoder.encode(run_error)
                    except Exception:
                        logger.exception("[%s] Failed to encode RUN_ERROR event", path)

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        except Exception as e:
            logger.error(f"Error in agent endpoint: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="An internal error has occurred.") from e


def _create_ag_ui_app(
    agent,
    session_repository: AgentSessionRepository | None = None,
) -> FastAPI:
    """Build the AG-UI FastAPI app mounted onto the Starlette agent server."""
    ag_ui_app = FastAPI(
        title="KB Agent AG-UI",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )
    wrapped_agent = agent
    if session_repository is not None:
        wrapped_agent = _PersistedSessionAgent(agent, session_repository)

    ag_ui_agent = AgentFrameworkAgent(agent=wrapped_agent, use_service_session=True)
    _add_persisted_ag_ui_endpoint(
        ag_ui_app,
        ag_ui_agent,
        path="/",
        session_repository=session_repository,
    )
    return ag_ui_app


def _create_citation_lookup_app(session_repository) -> FastAPI:
    """Build a protected API for transcript-scoped citation enrichment."""
    citation_app = FastAPI(
        title="KB Agent Citation Lookup",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )

    @citation_app.get(
        "/{thread_id}/{tool_call_id}/{ref_number}",
        dependencies=[Depends(require_jwt_auth)],
    )
    async def get_citation_chunk(thread_id: str, tool_call_id: str, ref_number: int) -> dict[str, Any]:
        if ref_number < 1:
            return {"status": "missing"}

        try:
            serialized_session = await session_repository.read_from_storage(thread_id)
        except Exception:
            logger.exception("Failed to read session for citation lookup (thread=%s)", thread_id)
            return {"status": "missing"}

        if not serialized_session:
            return {"status": "missing"}

        stored_citation = find_citation_reference(
            serialized_session,
            tool_call_id=tool_call_id,
            ref_number=ref_number,
        )
        if not stored_citation:
            return {"status": "missing"}

        chunk_id = stored_citation.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            return {"status": "missing"}

        claims = user_claims_var.get()
        groups = claims.get("groups", []) if isinstance(claims, dict) else []
        departments = resolve_departments(groups) if groups else []
        security_filter = build_security_filter(departments)

        try:
            current_chunk = get_chunk_by_id(chunk_id, security_filter=security_filter)
        except Exception:
            logger.exception("Failed to fetch chunk '%s' for citation lookup", chunk_id)
            return {"status": "missing"}

        citation = {
            **stored_citation,
            "chunk_id": current_chunk.id,
            "article_id": current_chunk.article_id,
            "chunk_index": current_chunk.chunk_index,
            "title": current_chunk.title or stored_citation.get("title"),
            "section_header": current_chunk.section_header or stored_citation.get("section_header"),
            "summary": current_chunk.summary or stored_citation.get("summary"),
            "content": current_chunk.content,
            "indexed_at": current_chunk.indexed_at or stored_citation.get("indexed_at"),
            "image_urls": list(current_chunk.image_urls),
            "images": [
                {"name": url.split("/")[-1], "url": get_image_url(current_chunk.article_id, url)}
                for url in current_chunk.image_urls
            ] if current_chunk.image_urls else [],
            "content_source": "full",
        }
        status = "ready"
        stored_indexed_at = stored_citation.get("indexed_at")
        if (
            isinstance(stored_indexed_at, str)
            and stored_indexed_at
            and current_chunk.indexed_at
            and stored_indexed_at != current_chunk.indexed_at
        ):
            status = "stale"

        return {"status": status, "citation": citation}

    return citation_app


def main() -> None:
    """Run the KB Agent as an HTTP server on port 8088."""
    logger.info("[KB-AGENT] Starting agent server (port 8088)…")
    _patch_agentserver_streaming_converter()

    from agent.config import config
    from agent.session_repository import CosmosAgentSessionRepository

    # Use the orchestrator HandoffBuilder. Multi-agent mode is required by spec.
    # from_agent_framework() accepts Callable[[], Workflow] — it wraps it in
    # AgentFrameworkWorkflowAdapter which calls the factory per request,
    # creating a fresh Workflow each time (no singleton reuse issues).
    # Note: HandoffBuilder is NOT a WorkflowBuilder subclass, so we pass
    # builder.build as the callable factory.
    from agent.orchestrator import create_orchestrator_builder

    builder = create_orchestrator_builder()
    agent_or_factory = builder.build  # Callable[[], Workflow]
    is_workflow = True
    logger.info("[KB-AGENT] Orchestrator HandoffBuilder created (multi-agent mode)")

    if not config.cosmos_endpoint:
        raise RuntimeError("[KB-AGENT] COSMOS_ENDPOINT is required; session persistence is mandatory")

    session_repo = CosmosAgentSessionRepository(
        endpoint=config.cosmos_endpoint,
        database_name=config.cosmos_database_name,
        container_name=config.cosmos_sessions_container,
    )
    logger.info("[KB-AGENT] Session persistence enabled (Cosmos DB)")

    # from_agent_framework() handles both Agent and Callable[[], Workflow].
    # For callables it creates AgentFrameworkWorkflowAdapter which builds
    # a fresh Workflow per request — no "already running" issues.
    server = from_agent_framework(agent_or_factory, session_repository=session_repo)
    server.app.add_middleware(JWTAuthMiddleware)

    # AG-UI endpoint: for workflows, create a per-request WorkflowAgent
    # to avoid "Workflow is already running" errors on sequential calls.
    # For single agent, use the custom _PersistedSessionAgent wrapper.
    if is_workflow:
        from agent.orchestrator import create_orchestrator

        class _PerRequestWorkflowAgent:
            """Creates a fresh WorkflowAgent per AG-UI run() call.

            AgentFrameworkAgent expects a SupportsAgentRun, but a WorkflowAgent
            singleton can't handle sequential requests (its Workflow keeps
            running-state).  This wrapper creates a disposable WorkflowAgent
            for each ``run()`` invocation and captures the session state
            so _PersistedSessionAgent can persist it.
            """

            def __init__(self) -> None:
                self.latest_pending_requests: dict[str, Any] = {}

            @property
            def name(self):
                return "KBAgentOrchestrator"

            async def create_session(self, *args, **kwargs):
                from agent_framework import AgentSession
                return AgentSession()

            async def get_session(self, *args, **kwargs):
                return None

            async def run(self, messages, **kwargs):
                self.latest_pending_requests = {}
                workflow = create_orchestrator()
                agent = workflow.as_agent(name="KBAgentOrchestrator")
                try:
                    async for update in agent.run(messages, **kwargs):
                        pending_requests = getattr(agent, "pending_requests", None)
                        if isinstance(pending_requests, dict) and pending_requests:
                            self.latest_pending_requests = dict(pending_requests)
                        yield update
                finally:
                    pending_requests = getattr(agent, "pending_requests", None)
                    if isinstance(pending_requests, dict):
                        self.latest_pending_requests = dict(pending_requests)

        ag_ui_app = FastAPI(
            title="KB Agent AG-UI",
            docs_url=None, redoc_url=None, openapi_url=None,
            redirect_slashes=False,
        )
        per_request_agent = _PerRequestWorkflowAgent()
        # Wrap with _PersistedSessionAgent for session persistence on AG-UI
        # (saves/loads conversation history via Cosmos DB session repository)
        wrapped_agent = per_request_agent
        if session_repo is not None:
            wrapped_agent = _PersistedSessionAgent(per_request_agent, session_repo, is_workflow=True)
        ag_ui_agent = AgentFrameworkAgent(agent=wrapped_agent, use_service_session=True)
        _add_persisted_ag_ui_endpoint(
            ag_ui_app,
            ag_ui_agent,
            path="/",
            session_repository=session_repo,
        )
        server.app.mount("/ag-ui", ag_ui_app)
    else:
        server.app.mount("/ag-ui", _create_ag_ui_app(agent_or_factory, session_repo))

    if session_repo is not None:
        server.app.mount("/citations", _create_citation_lookup_app(session_repo))
    server.run()


if __name__ == "__main__":
    main()
