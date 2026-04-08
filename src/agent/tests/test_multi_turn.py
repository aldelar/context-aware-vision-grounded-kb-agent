"""Tests for multi-turn session wiring in main.py.

Verifies that from_agent_framework receives the correct session_repository
depending on whether COSMOS_ENDPOINT is configured.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required env vars so config loads without sys.exit."""
    monkeypatch.setenv("AI_SERVICES_ENDPOINT", "https://fake.openai.azure.com")
    monkeypatch.setenv("SEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("SERVING_BLOB_ENDPOINT", "https://fake.blob.core.windows.net")
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)


class TestSessionRepoWiring:
    """Verify main() passes session_repository to from_agent_framework."""

    @staticmethod
    def _configure_orchestrator_builder(mock_create_builder: MagicMock) -> None:
        mock_builder = MagicMock()
        mock_builder.build = MagicMock(name="workflow_factory")
        mock_create_builder.return_value = mock_builder

    @pytest.mark.asyncio
    async def test_streaming_patch_filters_null_text_deltas(self) -> None:
        """The startup workaround should skip null text deltas from streamed updates."""
        import main  # noqa: F401

        from azure.ai.agentserver.agentframework.models.agent_framework_output_streaming_converter import (
            AgentFrameworkOutputStreamingConverter,
        )

        from main import _patch_agentserver_streaming_converter

        _patch_agentserver_streaming_converter()

        converter = object.__new__(AgentFrameworkOutputStreamingConverter)
        update = SimpleNamespace(
            contents=[
                SimpleNamespace(type="text", text=None),
                SimpleNamespace(type="text", text="hello"),
                SimpleNamespace(type="function_call", arguments="{}", call_id="call-1", name="search"),
            ],
            author_name="assistant",
        )

        async def updates():
            yield update

        results = [
            item
            async for item in AgentFrameworkOutputStreamingConverter._read_updates(converter, updates())
        ]

        assert len(results) == 2
        assert results[0][0].type == "text"
        assert results[0][0].text == "hello"
        assert results[0][1] == "assistant"
        assert results[1][0].type == "function_call"

    @pytest.mark.asyncio
    async def test_streaming_patch_handles_null_text_inside_converter_state(self) -> None:
        """The text-content state patch should ignore null deltas instead of crashing."""
        from types import SimpleNamespace

        import main  # noqa: F401

        from azure.ai.agentserver.agentframework.models.agent_framework_output_streaming_converter import (
            _TextContentStreamingState,
        )

        from main import _patch_agentserver_streaming_converter

        _patch_agentserver_streaming_converter()

        parent = SimpleNamespace(
            context=SimpleNamespace(id_generator=SimpleNamespace(generate_message_id=lambda: "msg-1")),
            _build_created_by=lambda author_name: {"agent": {"name": author_name}},
            next_output_index=lambda: 0,
            next_sequence=(lambda counter=iter(range(1000)): lambda: next(counter))(),
            add_completed_output_item=lambda item: None,
        )
        state = _TextContentStreamingState(parent)

        async def contents():
            yield SimpleNamespace(text="Hello")
            yield SimpleNamespace(text=None)
            yield SimpleNamespace(text=" world")

        events = [event async for event in state.convert_contents(contents(), "assistant")]
        done_event = next(event for event in events if getattr(event, "type", None) == "response.output_text.done")
        assert done_event.text == "Hello world"

    @patch("agent.orchestrator.create_orchestrator_builder")
    @patch("main._patch_agentserver_streaming_converter")
    @patch("main.from_agent_framework")
    def test_main_applies_streaming_patch_before_server_start(
        self,
        mock_adapter: MagicMock,
        mock_patch_streaming: MagicMock,
        mock_create_builder: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """main() should install the streaming workaround before creating the server."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.cosmos.azure.com:443/")

        import agent.config
        monkeypatch.setattr("agent.config.config", agent.config._load_config())
        self._configure_orchestrator_builder(mock_create_builder)

        mock_server = MagicMock()
        mock_adapter.return_value = mock_server

        from main import main

        main()

        mock_patch_streaming.assert_called_once()
        mock_adapter.assert_called_once()

    @patch("agent.orchestrator.create_orchestrator_builder")
    @patch("main.from_agent_framework")
    def test_cosmos_endpoint_set_creates_repo(
        self,
        mock_adapter: MagicMock,
        mock_create_builder: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When COSMOS_ENDPOINT is set, session_repository is a CosmosAgentSessionRepository."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.cosmos.azure.com:443/")
        monkeypatch.setenv("COSMOS_DATABASE_NAME", "test-db")

        # Reload config to pick up new env vars
        import agent.config
        monkeypatch.setattr("agent.config.config", agent.config._load_config())
        self._configure_orchestrator_builder(mock_create_builder)

        mock_server = MagicMock()
        mock_adapter.return_value = mock_server

        from main import main
        main()

        mock_adapter.assert_called_once()
        call_kwargs = mock_adapter.call_args
        repo = call_kwargs.kwargs.get("session_repository") or call_kwargs[1].get("session_repository")

        from agent.session_repository import CosmosAgentSessionRepository
        assert isinstance(repo, CosmosAgentSessionRepository)

    @patch("agent.orchestrator.create_orchestrator_builder")
    @patch("main.from_agent_framework")
    def test_no_cosmos_endpoint_raises(
        self,
        mock_adapter: MagicMock,
        mock_create_builder: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When COSMOS_ENDPOINT is empty, startup fails instead of disabling persistence."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "")

        import agent.config
        monkeypatch.setattr("agent.config.config", agent.config._load_config())
        self._configure_orchestrator_builder(mock_create_builder)

        from main import main

        with pytest.raises(RuntimeError, match="COSMOS_ENDPOINT"):
            main()

        mock_adapter.assert_not_called()

    @patch("agent.orchestrator.create_orchestrator_builder")
    @patch("main.from_agent_framework")
    def test_repo_constructed_with_correct_params(
        self,
        mock_adapter: MagicMock,
        mock_create_builder: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CosmosAgentSessionRepository is constructed with endpoint and database_name from config."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://my-cosmos.documents.azure.com:443/")
        monkeypatch.setenv("COSMOS_DATABASE_NAME", "custom-db")

        import agent.config
        monkeypatch.setattr("agent.config.config", agent.config._load_config())
        self._configure_orchestrator_builder(mock_create_builder)

        mock_server = MagicMock()
        mock_adapter.return_value = mock_server

        from main import main
        main()

        call_kwargs = mock_adapter.call_args
        repo = call_kwargs.kwargs.get("session_repository") or call_kwargs[1].get("session_repository")

        assert repo._endpoint == "https://my-cosmos.documents.azure.com:443/"
        assert repo._database_name == "custom-db"

    @patch("agent.orchestrator.create_orchestrator_builder")
    @patch("main.from_agent_framework")
    def test_default_cosmos_database_name(
        self,
        mock_adapter: MagicMock,
        mock_create_builder: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When COSMOS_DATABASE_NAME is not set, the default 'kb-agent' is used."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.cosmos.azure.com:443/")
        monkeypatch.delenv("COSMOS_DATABASE_NAME", raising=False)

        import agent.config
        monkeypatch.setattr("agent.config.config", agent.config._load_config())
        self._configure_orchestrator_builder(mock_create_builder)

        mock_server = MagicMock()
        mock_adapter.return_value = mock_server

        from main import main
        main()

        call_kwargs = mock_adapter.call_args
        repo = call_kwargs.kwargs.get("session_repository") or call_kwargs[1].get("session_repository")

        from agent.session_repository import CosmosAgentSessionRepository
        assert isinstance(repo, CosmosAgentSessionRepository)
        assert repo._database_name == "kb-agent"

    @patch("agent.orchestrator.create_orchestrator_builder")
    @patch("main.from_agent_framework")
    def test_repo_uses_default_container_name(
        self,
        mock_adapter: MagicMock,
        mock_create_builder: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CosmosAgentSessionRepository uses 'agent-sessions' as default container."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.cosmos.azure.com:443/")
        monkeypatch.setenv("COSMOS_DATABASE_NAME", "test-db")

        import agent.config
        monkeypatch.setattr("agent.config.config", agent.config._load_config())
        self._configure_orchestrator_builder(mock_create_builder)

        mock_server = MagicMock()
        mock_adapter.return_value = mock_server

        from main import main
        main()

        call_kwargs = mock_adapter.call_args
        repo = call_kwargs.kwargs.get("session_repository") or call_kwargs[1].get("session_repository")

        assert repo._container_name == "agent-sessions"
