"""Tests for AG-UI endpoint wiring and session continuity."""

from __future__ import annotations

import json
from types import SimpleNamespace

from starlette.applications import Starlette
from starlette.testclient import TestClient

import pytest

from agent_framework import AgentResponse, AgentResponseUpdate, AgentSession, Content, Message
from agent_framework.ag_ui import AgentFrameworkAgent

from main import _PersistedSessionAgent, _create_ag_ui_app


class _FakeAgent:
    """Minimal streaming agent used to exercise the AG-UI adapter."""

    def __init__(self) -> None:
        self.captured_session = None
        self.captured_messages = None
        self.captured_service_session_id = None
        self.server_tools = []
        self.next_service_session_id: str | None = None

    async def run(self, messages, **kwargs):
        self.captured_messages = messages
        self.captured_session = kwargs.get("session")
        self.captured_service_session_id = getattr(self.captured_session, "service_session_id", None)
        if self.captured_session is not None and self.next_service_session_id is not None:
            self.captured_session.service_session_id = self.next_service_session_id
        if False:
            yield None


class _FakeWorkflowStreamingAgent:
    def __init__(self, updates: list[AgentResponseUpdate]) -> None:
        self._updates = updates
        self.captured_messages = None
        self.captured_session = None
        self.latest_pending_requests: dict[str, object] = {}

    async def run(self, messages, **kwargs):
        self.captured_messages = messages
        self.captured_session = kwargs.get("session")
        for update in self._updates:
            yield update


class _MessageModel:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def model_dump(self, *, exclude_none: bool = False) -> dict[str, object]:
        return self._payload


def _parse_sse_events(response_text: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in response_text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


class TestAGUIEndpoint:
    """AG-UI endpoint composition on the existing Starlette server."""

    @pytest.mark.parametrize("path", ["/ag-ui", "/ag-ui/"])
    def test_mount_accepts_post_without_redirect(
        self,
        monkeypatch: pytest.MonkeyPatch,
        path: str,
    ) -> None:
        monkeypatch.setenv("REQUIRE_AUTH", "false")

        app = Starlette()
        app.mount("/ag-ui", _create_ag_ui_app(_FakeAgent()))
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            path,
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

        assert response.status_code == 200
        assert '"type":"RUN_STARTED"' in response.text

    def test_mount_enforces_auth_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("REQUIRE_AUTH", "true")

        app = Starlette()
        app.mount("/ag-ui", _create_ag_ui_app(_FakeAgent()))
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/ag-ui",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

        assert response.status_code == 401
        assert response.json()["detail"]["error"] == "unauthorized"

    def test_connect_restores_persisted_session_snapshot(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("REQUIRE_AUTH", "false")

        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.state = {
            "in_memory": {
                "messages": [
                    Message(role="user", contents=["Earlier question"], message_id="user-1"),
                    Message(role="assistant", contents=["Earlier answer"], message_id="assistant-1"),
                ]
            },
            "preferences": {"department": "engineering"},
        }
        repository = _FakeSessionRepository(session=stored_session)
        agent = _FakeAgent()

        app = Starlette()
        app.mount("/ag-ui", _create_ag_ui_app(agent, repository))
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/ag-ui",
            json={
                "thread_id": "thread-123",
                "run_id": "run-1",
                "messages": [],
            },
        )

        assert response.status_code == 200
        assert repository.requested_conversation_ids == ["thread-123"]
        assert agent.captured_messages is None

        events = _parse_sse_events(response.text)
        assert [event["type"] for event in events] == [
            "RUN_STARTED",
            "STATE_SNAPSHOT",
            "MESSAGES_SNAPSHOT",
            "RUN_FINISHED",
        ]
        assert events[1]["snapshot"] == {"preferences": {"department": "engineering"}}
        assert events[2]["messages"] == [
            {"id": "user-1", "role": "user", "content": "Earlier question"},
            {"id": "assistant-1", "role": "assistant", "content": "Earlier answer"},
        ]


class _FakeSessionRepository:
    def __init__(self, session: AgentSession | None = None) -> None:
        self.session = session
        self.saved: list[tuple[str, AgentSession]] = []
        self.requested_conversation_ids: list[str] = []

    async def get(self, conversation_id: str) -> AgentSession | None:
        self.requested_conversation_ids.append(conversation_id)
        return self.session

    async def set(self, conversation_id: str, session: AgentSession) -> None:
        self.saved.append((conversation_id, session))


class TestAGUIThreadContinuity:
    """AG-UI wrapper should map thread IDs to service session IDs."""

    @pytest.mark.asyncio
    async def test_persisted_session_agent_prefers_request_history_over_stored_session(self) -> None:
        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.metadata = {"persisted": True}
        stored_session.state = {
            "in_memory": {"messages": ["persisted-history"]},
            "preferences": {"department": "engineering"},
        }
        repository = _FakeSessionRepository(session=stored_session)
        agent = _FakeAgent()
        agent.next_service_session_id = "resp-999"
        wrapped_agent = _PersistedSessionAgent(agent, repository)

        request_session = AgentSession(service_session_id="thread-123")
        request_session.metadata = {"ag_ui_thread_id": "thread-123"}
        request_session.state = {
            "local": {"draft": True},
            "messages": ["client-state-history"],
            "in_memory": {"messages": ["client-in-memory-history"]},
        }

        updates = [
            update
            async for update in wrapped_agent.run(
                [{"role": "user", "content": "hello"}],
                session=request_session,
            )
        ]

        assert updates == []
        assert repository.requested_conversation_ids == ["thread-123"]
        assert agent.captured_session is request_session
        assert request_session.metadata == {
            "persisted": True,
            "ag_ui_thread_id": "thread-123",
        }
        assert request_session.state == {
            "preferences": {"department": "engineering"},
            "local": {"draft": True},
        }
        assert agent.captured_service_session_id is None
        assert request_session.service_session_id == "thread-123"
        assert repository.saved == [("thread-123", request_session)]

    @pytest.mark.asyncio
    async def test_persisted_session_agent_reuses_stored_session_when_request_history_absent(self) -> None:
        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.metadata = {"persisted": True}
        stored_session.state = {"in_memory": {"messages": ["persisted-history"]}}
        repository = _FakeSessionRepository(session=stored_session)
        agent = _FakeAgent()
        wrapped_agent = _PersistedSessionAgent(agent, repository)

        request_session = AgentSession(service_session_id="thread-123")
        request_session.metadata = {"ag_ui_thread_id": "thread-123"}

        updates = [
            update
            async for update in wrapped_agent.run(
                [],
                session=request_session,
            )
        ]

        assert updates == []
        assert repository.requested_conversation_ids == ["thread-123"]
        assert agent.captured_session is stored_session
        assert stored_session.metadata == {
            "persisted": True,
            "ag_ui_thread_id": "thread-123",
        }
        assert stored_session.state == {"in_memory": {"messages": ["persisted-history"]}}
        assert agent.captured_service_session_id == "thread-123"
        assert repository.saved == [("thread-123", stored_session)]

    @pytest.mark.asyncio
    async def test_workflow_persistence_synthesizes_history_from_stream_updates(self) -> None:
        repository = _FakeSessionRepository(session=None)
        workflow_agent = _FakeWorkflowStreamingAgent(
            [
                AgentResponseUpdate(
                    contents=[Content.from_text(text="Azure AI Search is a cloud search service.")],
                    role="assistant",
                    message_id="assistant-1",
                    response_id="run-1",
                    created_at="2026-04-08T10:00:00.000000Z",
                )
            ]
        )
        wrapped_agent = _PersistedSessionAgent(workflow_agent, repository, is_workflow=True)

        request_session = AgentSession(service_session_id="thread-123")
        raw_messages = [
            {"id": "user-1", "role": "user", "content": "Earlier question"},
            {"id": "assistant-0", "role": "assistant", "content": "Earlier answer"},
            {"id": "user-2", "role": "user", "content": "What is Azure AI Search?"},
        ]

        updates = [
            update
            async for update in wrapped_agent.run(
                raw_messages,
                session=request_session,
            )
        ]

        assert updates == workflow_agent._updates
        assert workflow_agent.captured_messages == [raw_messages[-1]]
        assert repository.saved == [("thread-123", request_session)]

        persisted_messages = _PersistedSessionAgent._extract_session_history_messages(request_session)
        assert persisted_messages == [
            {"id": "user-1", "role": "user", "content": "Earlier question"},
            {"id": "assistant-0", "role": "assistant", "content": "Earlier answer"},
            {"id": "user-2", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "assistant-1",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
            },
        ]

    @pytest.mark.asyncio
    async def test_workflow_persistence_appends_streamed_response_to_stored_history(self) -> None:
        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.state = {
            "in_memory": {
                "messages": [
                    Message(role="user", contents=["Earlier question"], message_id="stored-user-1"),
                    Message(role="assistant", contents=["Earlier answer"], message_id="stored-assistant-1"),
                ]
            }
        }
        repository = _FakeSessionRepository(session=stored_session)
        workflow_agent = _FakeWorkflowStreamingAgent(
            [
                AgentResponseUpdate(
                    contents=[Content.from_text(text="Azure AI Search indexes content into searchable fields.")],
                    role="assistant",
                    message_id="assistant-2",
                    response_id="run-2",
                    created_at="2026-04-08T10:05:00.000000Z",
                )
            ]
        )
        wrapped_agent = _PersistedSessionAgent(workflow_agent, repository, is_workflow=True)

        request_session = AgentSession(service_session_id="thread-123")

        updates = [
            update
            async for update in wrapped_agent.run(
                [
                    {"id": "user-2", "role": "user", "content": "How does indexing work?"},
                ],
                session=request_session,
            )
        ]

        assert updates == workflow_agent._updates
        assert repository.saved == [("thread-123", request_session)]

        persisted_messages = _PersistedSessionAgent._extract_session_history_messages(request_session)
        assert persisted_messages == [
            {"id": "stored-user-1", "role": "user", "content": "Earlier question"},
            {"id": "stored-assistant-1", "role": "assistant", "content": "Earlier answer"},
            {"id": "user-2", "role": "user", "content": "How does indexing work?"},
            {
                "id": "assistant-2",
                "role": "assistant",
                "content": "Azure AI Search indexes content into searchable fields.",
            },
        ]

    @pytest.mark.asyncio
    async def test_workflow_persistence_uses_pending_request_agent_response_when_updates_are_approval_only(self) -> None:
        repository = _FakeSessionRepository(session=None)
        workflow_agent = _FakeWorkflowStreamingAgent([])
        workflow_agent.latest_pending_requests = {
            "request-1": SimpleNamespace(
                data=SimpleNamespace(
                    agent_response=AgentResponse(
                        messages=[
                            Message(
                                role="assistant",
                                contents=[
                                    Content.from_function_call(
                                        call_id="tool-call-1",
                                        name="search_knowledge_base",
                                        arguments='{"query":"network security options for Azure AI Search"}',
                                    )
                                ],
                                message_id="assistant-tool-1",
                                author_name="InternalSearchAgent",
                            ),
                            Message(
                                role="tool",
                                contents=[
                                    Content.from_function_result(
                                        call_id="tool-call-1",
                                        result='{"results":[{"title":"Security in Azure AI Search"}]}',
                                    )
                                ],
                                message_id="tool-1",
                            ),
                            Message(
                                role="assistant",
                                contents=[Content.from_text(text="Use private endpoints and RBAC.")],
                                message_id="assistant-answer-1",
                                author_name="InternalSearchAgent",
                            ),
                        ],
                        response_id="run-3",
                        created_at="2026-04-08T10:10:00.000000Z",
                    )
                )
            )
        }
        wrapped_agent = _PersistedSessionAgent(workflow_agent, repository, is_workflow=True)

        request_session = AgentSession(service_session_id="thread-123")
        raw_messages = [
            {
                "id": "user-1",
                "role": "user",
                "content": "network security options for Azure AI Search",
            }
        ]

        updates = [
            update
            async for update in wrapped_agent.run(
                raw_messages,
                session=request_session,
            )
        ]

        assert updates == []
        assert repository.saved == [("thread-123", request_session)]

        persisted_messages = _PersistedSessionAgent._extract_session_history_messages(request_session)
        assert persisted_messages == [
            {
                "id": "user-1",
                "role": "user",
                "content": "network security options for Azure AI Search",
            },
            {
                "id": "assistant-tool-1",
                "role": "assistant",
                "toolCalls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": '{"query":"network security options for Azure AI Search"}',
                        },
                    }
                ],
            },
            {
                "id": "tool-1",
                "role": "tool",
                "toolCallId": "tool-call-1",
                "content": '{"results":[{"title":"Security in Azure AI Search"}]}',
            },
            {
                "id": "assistant-answer-1",
                "role": "assistant",
                "content": "Use private endpoints and RBAC.",
            },
        ]

    @pytest.mark.asyncio
    async def test_workflow_persistence_uses_pending_request_agent_response_when_stream_pauses_for_approval(self) -> None:
        repository = _FakeSessionRepository(session=None)
        agent_response = AgentResponse(
            messages=[
                Message(
                    role="assistant",
                    contents=[
                        Content.from_function_call(
                            call_id="tool-call-1",
                            name="search_knowledge_base",
                            arguments='{"query":"network security options for Azure AI Search"}',
                        )
                    ],
                    message_id="assistant-tool-1",
                    author_name="InternalSearchAgent",
                ),
                Message(
                    role="tool",
                    contents=[
                        Content.from_function_result(
                            call_id="tool-call-1",
                            result='{"results":[{"title":"Security in Azure AI Search"}]}',
                        )
                    ],
                    message_id="tool-1",
                ),
                Message(
                    role="assistant",
                    contents=[Content.from_text(text="Use private endpoints and RBAC.")],
                    message_id="assistant-answer-1",
                    author_name="InternalSearchAgent",
                ),
            ],
            response_id="run-4",
            created_at="2026-04-08T10:15:00.000000Z",
        )
        workflow_agent = _FakeWorkflowStreamingAgent(
            [
                AgentResponseUpdate.from_dict(
                    {
                        "type": "agent_response_update",
                        "contents": [
                            {
                                "type": "function_call",
                                "call_id": "request-1",
                                "name": "request_info",
                                "arguments": {
                                    "request_id": "request-1",
                                    "data": {"agent_response": agent_response},
                                },
                            },
                            {
                                "type": "function_approval_request",
                                "function_call": {
                                    "type": "function_call",
                                    "call_id": "request-1",
                                    "name": "request_info",
                                    "arguments": {
                                        "request_id": "request-1",
                                        "data": {"agent_response": agent_response},
                                    },
                                },
                                "user_input_request": True,
                                "id": "request-1",
                                "additional_properties": {"request_id": "request-1"},
                            },
                        ],
                        "role": "assistant",
                        "author_name": "KBAgentOrchestrator",
                        "response_id": "run-4",
                        "message_id": "approval-1",
                        "created_at": "2026-04-08T10:15:00.000000Z",
                    }
                )
            ]
        )
        workflow_agent.latest_pending_requests = {
            "request-1": SimpleNamespace(
                data=SimpleNamespace(
                    agent_response=agent_response,
                )
            )
        }
        wrapped_agent = _PersistedSessionAgent(workflow_agent, repository, is_workflow=True)

        request_session = AgentSession(service_session_id="thread-123")
        raw_messages = [
            Message(
                role="user",
                contents=[Content.from_text(text="network security options for Azure AI Search")],
                message_id="user-1",
            )
        ]

        streamed_updates: list[AgentResponseUpdate] = []
        stream = wrapped_agent.run(
            raw_messages,
            session=request_session,
        )
        streamed_updates.append(await anext(stream))
        await stream.aclose()

        assert streamed_updates == workflow_agent._updates
        assert repository.saved == [("thread-123", request_session)]

        persisted_messages = _PersistedSessionAgent._extract_session_history_messages(request_session)
        assert persisted_messages == [
            {
                "id": "user-1",
                "role": "user",
                "content": "network security options for Azure AI Search",
            },
            {
                "id": "assistant-tool-1",
                "role": "assistant",
                "toolCalls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": '{"query":"network security options for Azure AI Search"}',
                        },
                    }
                ],
            },
            {
                "id": "tool-1",
                "role": "tool",
                "toolCallId": "tool-call-1",
                "content": '{"results":[{"title":"Security in Azure AI Search"}]}',
            },
            {
                "id": "assistant-answer-1",
                "role": "assistant",
                "content": "Use private endpoints and RBAC.",
            },
        ]

    @pytest.mark.asyncio
    async def test_thread_id_becomes_service_session_id(self) -> None:
        agent = _FakeAgent()
        wrapper = AgentFrameworkAgent(agent=agent, use_service_session=True)

        events = [
            event
            async for event in wrapper.run(
                {
                    "messages": [{"role": "user", "content": "hello"}],
                    "threadId": "thread-123",
                }
            )
        ]

        assert [type(event).__name__ for event in events] == [
            "RunStartedEvent",
            "RunFinishedEvent",
        ]
        assert agent.captured_session is not None
        assert agent.captured_session.service_session_id == "thread-123"
        assert agent.captured_session.metadata["ag_ui_thread_id"] == "thread-123"

    def test_normalize_replayed_messages_reorders_tool_results_within_turn(self) -> None:
        replayed_messages = [
            {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "assistant-tool-1",
                "role": "assistant",
                "toolCalls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": '{"query":"azure ai search"}',
                        },
                    },
                ],
            },
            {
                "id": "assistant-answer-1",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
            },
            {
                "id": "tool-1",
                "role": "tool",
                "toolCallId": "tool-call-1",
                "toolName": "search_knowledge_base",
                "content": '{"results":[{"title":"Azure AI Search overview"}]}',
            },
            {"id": "user-2", "role": "user", "content": "How does indexing work?"},
        ]

        normalized = _PersistedSessionAgent._normalize_replayed_messages(replayed_messages)

        assert normalized == [
            {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "assistant-tool-1",
                "role": "assistant",
                "toolCalls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": '{"query":"azure ai search"}',
                        },
                    },
                ],
            },
            {
                "id": "tool-1",
                "role": "tool",
                "toolCallId": "tool-call-1",
                "toolName": "search_knowledge_base",
                "content": '{"results":[{"title":"Azure AI Search overview"}]}',
            },
            {
                "id": "assistant-answer-1",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
            },
            {"id": "user-2", "role": "user", "content": "How does indexing work?"},
        ]

    def test_normalize_replayed_messages_drops_orphaned_tool_calls_when_content_exists(self) -> None:
        replayed_messages = [
            {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "assistant-1",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
                "toolCalls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": '{"query":"azure ai search"}',
                        },
                    },
                ],
            },
            {"id": "user-2", "role": "user", "content": "How does indexing work?"},
        ]

        normalized = _PersistedSessionAgent._normalize_replayed_messages(replayed_messages)

        assert normalized == [
            {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "assistant-1-response",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
            },
            {"id": "user-2", "role": "user", "content": "How does indexing work?"},
        ]

    def test_normalize_replayed_messages_accepts_message_models(self) -> None:
        replayed_messages = [
            _MessageModel({"id": "user-1", "role": "user", "content": "What is Azure AI Search?"}),
            _MessageModel(
                {
                    "id": "assistant-1",
                    "role": "assistant",
                    "toolCalls": [
                        {
                            "id": "tool-call-1",
                            "type": "function",
                            "function": {
                                "name": "search_knowledge_base",
                                "arguments": '{"query":"azure ai search"}',
                            },
                        },
                    ],
                }
            ),
            _MessageModel(
                {
                    "id": "assistant-2",
                    "role": "assistant",
                    "content": "Azure AI Search is a cloud search service.",
                }
            ),
            _MessageModel({"id": "user-2", "role": "user", "content": "How does indexing work?"}),
        ]

        normalized = _PersistedSessionAgent._normalize_replayed_messages(replayed_messages)

        assert normalized == [
            {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
            {"id": "assistant-2", "role": "assistant", "content": "Azure AI Search is a cloud search service."},
            {"id": "user-2", "role": "user", "content": "How does indexing work?"},
        ]

    @pytest.mark.asyncio
    async def test_persisted_session_agent_rebuilds_malformed_history_from_stored_session(self) -> None:
        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.state = {
            "messages": [
                {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
                {
                    "id": "assistant-2",
                    "role": "assistant",
                    "toolCalls": [
                        {
                            "id": "tool-call-1",
                            "type": "function",
                            "function": {
                                "name": "search_knowledge_base",
                                "arguments": '{"query":"azure ai search"}',
                            },
                        },
                    ],
                },
                {
                    "id": "tool-3",
                    "role": "tool",
                    "toolCallId": "tool-call-1",
                    "content": '{"results":[{"title":"Azure AI Search overview"}]}',
                },
                {
                    "id": "assistant-4",
                    "role": "assistant",
                    "content": "Azure AI Search is a cloud search service.",
                },
            ]
        }
        repository = _FakeSessionRepository(session=stored_session)
        agent = _FakeAgent()
        wrapped_agent = _PersistedSessionAgent(agent, repository)

        request_session = AgentSession(service_session_id="thread-123")

        updates = [
            update
            async for update in wrapped_agent.run(
                [
                    _MessageModel({"id": "user-1", "role": "user", "content": "What is Azure AI Search?"}),
                    _MessageModel(
                        {
                            "id": "assistant-2",
                            "role": "assistant",
                            "toolCalls": [
                                {
                                    "id": "tool-call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_knowledge_base",
                                        "arguments": '{}',
                                    },
                                },
                            ],
                        }
                    ),
                    _MessageModel(
                        {
                            "id": "assistant-4",
                            "role": "assistant",
                            "content": "Azure AI Search is a cloud search service.",
                        }
                    ),
                    _MessageModel({"id": "user-5", "role": "user", "content": "How does indexing work?"}),
                ],
                session=request_session,
            )
        ]

        assert updates == []
        assert agent.captured_messages == [
            {"id": "user-1", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "assistant-2",
                "role": "assistant",
                "toolCalls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": '{"query":"azure ai search"}',
                        },
                    },
                ],
            },
            {
                "id": "tool-3",
                "role": "tool",
                "toolCallId": "tool-call-1",
                "content": '{"results":[{"title":"Azure AI Search overview"}]}',
            },
            {
                "id": "assistant-4",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
            },
            {"id": "user-5", "role": "user", "content": "How does indexing work?"},
        ]

    @pytest.mark.asyncio
    async def test_persisted_session_agent_rebuilds_history_from_internal_session_messages(self) -> None:
        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.state = {
            "in_memory": {
                "messages": [
                    {
                        "type": "message",
                        "role": "user",
                        "message_id": "stored-user-1",
                        "contents": [
                            {"type": "text", "text": "What is Azure AI Search?"},
                        ],
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "message_id": "stored-assistant-2",
                        "contents": [
                            {
                                "type": "function_call",
                                "call_id": "tool-call-1",
                                "name": "search_knowledge_base",
                                "arguments": '{"query":"azure ai search"}',
                            },
                        ],
                    },
                    {
                        "type": "message",
                        "role": "tool",
                        "contents": [
                            {
                                "type": "function_result",
                                "call_id": "tool-call-1",
                                "result": '{"results":[{"title":"Azure AI Search overview"}]}',
                            },
                        ],
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "message_id": "stored-assistant-4",
                        "contents": [
                            {"type": "text", "text": "Azure AI Search is a cloud search service."},
                        ],
                    },
                ]
            }
        }
        repository = _FakeSessionRepository(session=stored_session)
        agent = _FakeAgent()
        wrapped_agent = _PersistedSessionAgent(agent, repository)

        request_session = AgentSession(service_session_id="thread-123")

        updates = [
            update
            async for update in wrapped_agent.run(
                [
                    _MessageModel({"id": "request-user-1", "role": "user", "content": "What is Azure AI Search?"}),
                    _MessageModel(
                        {
                            "id": "request-assistant-2",
                            "role": "assistant",
                            "toolCalls": [
                                {
                                    "id": "tool-call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_knowledge_base",
                                        "arguments": '{}',
                                    },
                                },
                            ],
                        }
                    ),
                    _MessageModel(
                        {
                            "id": "request-assistant-4",
                            "role": "assistant",
                            "content": "Azure AI Search is a cloud search service.",
                        }
                    ),
                    _MessageModel({"id": "request-user-5", "role": "user", "content": "How does indexing work?"}),
                ],
                session=request_session,
            )
        ]

        assert updates == []
        assert agent.captured_messages == [
            {"id": "stored-user-1", "role": "user", "content": "What is Azure AI Search?"},
            {
                "id": "stored-assistant-2",
                "role": "assistant",
                "toolCalls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": '{"query":"azure ai search"}',
                        },
                    },
                ],
            },
            {
                "id": "tool-3",
                "role": "tool",
                "toolCallId": "tool-call-1",
                "content": '{"results":[{"title":"Azure AI Search overview"}]}',
            },
            {
                "id": "stored-assistant-4",
                "role": "assistant",
                "content": "Azure AI Search is a cloud search service.",
            },
            {"id": "request-user-5", "role": "user", "content": "How does indexing work?"},
        ]

    @pytest.mark.asyncio
    async def test_persisted_session_agent_rebuilds_history_from_framework_message_objects(self) -> None:
        stored_session = AgentSession(service_session_id="thread-123")
        stored_session.state = {
            "in_memory": {
                "messages": [
                    {
                        "type": "message",
                        "role": "user",
                        "message_id": "stored-user-1",
                        "contents": [
                            {"type": "text", "text": "What is Azure AI Search?"},
                        ],
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "message_id": "stored-assistant-2",
                        "contents": [
                            {
                                "type": "function_call",
                                "call_id": "tool-call-1",
                                "name": "search_knowledge_base",
                                "arguments": '{"query":"azure ai search"}',
                            },
                        ],
                    },
                    {
                        "type": "message",
                        "role": "tool",
                        "contents": [
                            {
                                "type": "function_result",
                                "call_id": "tool-call-1",
                                "result": '{"results":[{"title":"Azure AI Search overview"}]}',
                            },
                        ],
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "message_id": "stored-assistant-4",
                        "contents": [
                            {"type": "text", "text": "Azure AI Search is a cloud search service."},
                        ],
                    },
                ]
            }
        }
        repository = _FakeSessionRepository(session=stored_session)
        agent = _FakeAgent()
        wrapped_agent = _PersistedSessionAgent(agent, repository)

        request_session = AgentSession(service_session_id="thread-123")

        updates = [
            update
            async for update in wrapped_agent.run(
                [
                    Message(role="user", contents=["What is Azure AI Search?"], message_id="request-user-1"),
                    Message(
                        role="assistant",
                        contents=[
                            {
                                "type": "function_call",
                                "call_id": "tool-call-1",
                                "name": "search_knowledge_base",
                                "arguments": '{}',
                            },
                        ],
                        message_id="request-assistant-2",
                    ),
                    Message(
                        role="assistant",
                        contents=["Azure AI Search is a cloud search service."],
                        message_id="request-assistant-4",
                    ),
                    Message(role="user", contents=["How does indexing work?"], message_id="request-user-5"),
                ],
                session=request_session,
            )
        ]

        assert updates == []
        assert all(isinstance(message, Message) for message in agent.captured_messages)
        captured_messages = [message.to_dict() for message in agent.captured_messages]
        assert [message["role"] for message in captured_messages] == [
            "user",
            "assistant",
            "tool",
            "assistant",
            "user",
        ]
        assert [message.get("message_id") for message in captured_messages] == [
            "stored-user-1",
            "stored-assistant-2",
            "tool-3",
            "stored-assistant-4",
            "request-user-5",
        ]
        assert captured_messages[0]["contents"][0]["type"] == "text"
        assert captured_messages[0]["contents"][0]["text"] == "What is Azure AI Search?"
        assert captured_messages[1]["contents"][0]["type"] == "function_call"
        assert captured_messages[1]["contents"][0]["call_id"] == "tool-call-1"
        assert captured_messages[1]["contents"][0]["name"] == "search_knowledge_base"
        assert captured_messages[1]["contents"][0]["arguments"] == '{"query":"azure ai search"}'
        assert captured_messages[2]["contents"][0]["type"] == "function_result"
        assert captured_messages[2]["contents"][0]["call_id"] == "tool-call-1"
        assert captured_messages[2]["contents"][0]["result"] == '{"results":[{"title":"Azure AI Search overview"}]}'
        assert captured_messages[3]["contents"][0]["type"] == "text"
        assert captured_messages[3]["contents"][0]["text"] == "Azure AI Search is a cloud search service."
        assert captured_messages[4]["contents"][0]["type"] == "text"
        assert captured_messages[4]["contents"][0]["text"] == "How does indexing work?"
