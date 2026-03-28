"""Tests for AG-UI endpoint wiring and session continuity."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.testclient import TestClient

import pytest

from agent_framework.ag_ui import AgentFrameworkAgent

from main import _create_ag_ui_app


class _FakeAgent:
    """Minimal streaming agent used to exercise the AG-UI adapter."""

    def __init__(self) -> None:
        self.captured_session = None
        self.server_tools = []

    async def run(self, messages, **kwargs):
        self.captured_session = kwargs.get("session")
        if False:
            yield None


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


class TestAGUIThreadContinuity:
    """AG-UI wrapper should map thread IDs to service session IDs."""

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
