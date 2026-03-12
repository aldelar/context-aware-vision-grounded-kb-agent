"""Tests for multi-turn session wiring in main.py.

Verifies that from_agent_framework receives the correct session_repository
depending on whether COSMOS_ENDPOINT is configured.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required env vars so config loads without sys.exit."""
    monkeypatch.setenv("AI_SERVICES_ENDPOINT", "https://fake.openai.azure.com")
    monkeypatch.setenv("SEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("SERVING_BLOB_ENDPOINT", "https://fake.blob.core.windows.net")


class TestSessionRepoWiring:
    """Verify main() passes session_repository to from_agent_framework."""

    @patch("main.from_agent_framework")
    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_cosmos_endpoint_set_creates_repo(
        self,
        mock_cred: MagicMock,
        mock_client: MagicMock,
        mock_agent_cls: MagicMock,
        mock_adapter: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When COSMOS_ENDPOINT is set, session_repository is a CosmosAgentSessionRepository."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.cosmos.azure.com:443/")
        monkeypatch.setenv("COSMOS_DATABASE_NAME", "test-db")

        # Reload config to pick up new env vars
        import agent.config
        monkeypatch.setattr("agent.config.config", agent.config._load_config())

        mock_server = MagicMock()
        mock_adapter.return_value = mock_server

        from main import main
        main()

        mock_adapter.assert_called_once()
        call_kwargs = mock_adapter.call_args
        repo = call_kwargs.kwargs.get("session_repository") or call_kwargs[1].get("session_repository")

        from agent.session_repository import CosmosAgentSessionRepository
        assert isinstance(repo, CosmosAgentSessionRepository)

    @patch("main.from_agent_framework")
    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_no_cosmos_endpoint_passes_none(
        self,
        mock_cred: MagicMock,
        mock_client: MagicMock,
        mock_agent_cls: MagicMock,
        mock_adapter: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When COSMOS_ENDPOINT is empty, session_repository is None."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "")

        import agent.config
        monkeypatch.setattr("agent.config.config", agent.config._load_config())

        mock_server = MagicMock()
        mock_adapter.return_value = mock_server

        from main import main
        main()

        mock_adapter.assert_called_once()
        call_kwargs = mock_adapter.call_args
        repo = call_kwargs.kwargs.get("session_repository") or call_kwargs[1].get("session_repository")
        assert repo is None

    @patch("main.from_agent_framework")
    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_repo_constructed_with_correct_params(
        self,
        mock_cred: MagicMock,
        mock_client: MagicMock,
        mock_agent_cls: MagicMock,
        mock_adapter: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CosmosAgentSessionRepository is constructed with endpoint and database_name from config."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://my-cosmos.documents.azure.com:443/")
        monkeypatch.setenv("COSMOS_DATABASE_NAME", "custom-db")

        import agent.config
        monkeypatch.setattr("agent.config.config", agent.config._load_config())

        mock_server = MagicMock()
        mock_adapter.return_value = mock_server

        from main import main
        main()

        call_kwargs = mock_adapter.call_args
        repo = call_kwargs.kwargs.get("session_repository") or call_kwargs[1].get("session_repository")

        assert repo._endpoint == "https://my-cosmos.documents.azure.com:443/"
        assert repo._database_name == "custom-db"

    @patch("main.from_agent_framework")
    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_default_cosmos_database_name(
        self,
        mock_cred: MagicMock,
        mock_client: MagicMock,
        mock_agent_cls: MagicMock,
        mock_adapter: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When COSMOS_DATABASE_NAME is not set, the default 'kb-agent' is used."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.cosmos.azure.com:443/")
        monkeypatch.delenv("COSMOS_DATABASE_NAME", raising=False)

        import agent.config
        monkeypatch.setattr("agent.config.config", agent.config._load_config())

        mock_server = MagicMock()
        mock_adapter.return_value = mock_server

        from main import main
        main()

        call_kwargs = mock_adapter.call_args
        repo = call_kwargs.kwargs.get("session_repository") or call_kwargs[1].get("session_repository")

        from agent.session_repository import CosmosAgentSessionRepository
        assert isinstance(repo, CosmosAgentSessionRepository)
        assert repo._database_name == "kb-agent"

    @patch("main.from_agent_framework")
    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_repo_uses_default_container_name(
        self,
        mock_cred: MagicMock,
        mock_client: MagicMock,
        mock_agent_cls: MagicMock,
        mock_adapter: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CosmosAgentSessionRepository uses 'agent-sessions' as default container."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.cosmos.azure.com:443/")
        monkeypatch.setenv("COSMOS_DATABASE_NAME", "test-db")

        import agent.config
        monkeypatch.setattr("agent.config.config", agent.config._load_config())

        mock_server = MagicMock()
        mock_adapter.return_value = mock_server

        from main import main
        main()

        call_kwargs = mock_adapter.call_args
        repo = call_kwargs.kwargs.get("session_repository") or call_kwargs[1].get("session_repository")

        assert repo._container_name == "agent-sessions"
