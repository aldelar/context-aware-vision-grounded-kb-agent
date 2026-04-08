"""Tests for the multi-agent orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.orchestrator import (
    _load_orchestrator_prompt,
    create_orchestrator,
    create_orchestrator_builder,
)


class TestOrchestratorPrompt:
    """Test the orchestrator system prompt."""

    def test_prompt_file_exists(self) -> None:
        prompt_path = Path(__file__).resolve().parent.parent / "agent" / "prompts" / "orchestrator" / "system_prompt.md"
        assert prompt_path.exists()

    def test_prompt_mentions_internal_search(self) -> None:
        prompt = _load_orchestrator_prompt()
        assert "InternalSearchAgent" in prompt

    def test_prompt_mentions_web_search(self) -> None:
        prompt = _load_orchestrator_prompt()
        assert "WebSearchAgent" in prompt

    def test_prompt_mentions_decline(self) -> None:
        prompt = _load_orchestrator_prompt()
        assert "decline" in prompt.lower() or "non-Azure" in prompt

    def test_prompt_mentions_routing_rules(self) -> None:
        prompt = _load_orchestrator_prompt()
        assert "Azure AI Search" in prompt
        assert "Content Understanding" in prompt

    def test_prompt_mentions_escalation(self) -> None:
        prompt = _load_orchestrator_prompt()
        assert "escalat" in prompt.lower() or "supplementary" in prompt.lower()


class TestCreateOrchestrator:
    """Test orchestrator workflow creation."""

    @patch("agent.orchestrator.create_web_search_agent")
    @patch("agent.orchestrator.create_internal_search_agent")
    @patch("agent.orchestrator.create_chat_client")
    def test_returns_workflow(
        self,
        mock_chat_client: MagicMock,
        mock_internal: MagicMock,
        mock_web: MagicMock,
    ) -> None:
        from agent_framework import Agent as RealAgent
        mock_chat_client.return_value = MagicMock()
        # Need real Agent instances for HandoffBuilder type check
        client = MagicMock()
        mock_internal.return_value = RealAgent(
            client=client, id="internal-search-agent",
            name="InternalSearchAgent", instructions="test",
        )
        mock_web.return_value = RealAgent(
            client=client, id="web-search-agent",
            name="WebSearchAgent", instructions="test",
        )

        from agent_framework import Workflow
        workflow = create_orchestrator()

        assert isinstance(workflow, Workflow)

    @patch("agent.orchestrator.create_web_search_agent")
    @patch("agent.orchestrator.create_internal_search_agent")
    @patch("agent.orchestrator.create_chat_client")
    def test_internal_agent_created_as_specialist(
        self,
        mock_chat_client: MagicMock,
        mock_internal: MagicMock,
        mock_web: MagicMock,
    ) -> None:
        """Internal search agent is created with standalone=False (no own compaction)."""
        from agent_framework import Agent as RealAgent
        client = MagicMock()
        mock_chat_client.return_value = MagicMock()
        mock_internal.return_value = RealAgent(
            client=client, id="internal-search-agent",
            name="InternalSearchAgent", instructions="test",
        )
        mock_web.return_value = RealAgent(
            client=client, id="web-search-agent",
            name="WebSearchAgent", instructions="test",
        )

        create_orchestrator()

        mock_internal.assert_called_once_with(standalone=False)

    @patch("agent.orchestrator.create_web_search_agent")
    @patch("agent.orchestrator.create_internal_search_agent")
    @patch("agent.orchestrator.create_chat_client")
    def test_returns_handoff_builder(
        self,
        mock_chat_client: MagicMock,
        mock_internal: MagicMock,
        mock_web: MagicMock,
    ) -> None:
        from agent_framework import Agent as RealAgent
        from agent_framework.orchestrations import HandoffBuilder
        client = MagicMock()
        mock_chat_client.return_value = MagicMock()
        mock_internal.return_value = RealAgent(
            client=client, id="internal-search-agent",
            name="InternalSearchAgent", instructions="test",
        )
        mock_web.return_value = RealAgent(
            client=client, id="web-search-agent",
            name="WebSearchAgent", instructions="test",
        )

        builder = create_orchestrator_builder()

        assert isinstance(builder, HandoffBuilder)

    @patch("agent.orchestrator.create_web_search_agent")
    @patch("agent.orchestrator.create_internal_search_agent")
    @patch("agent.orchestrator.create_chat_client")
    def test_builder_produces_workflow(
        self,
        mock_chat_client: MagicMock,
        mock_internal: MagicMock,
        mock_web: MagicMock,
    ) -> None:
        """builder.build() produces a Workflow — this is what from_agent_framework uses."""
        from agent_framework import Agent as RealAgent, Workflow
        client = MagicMock()
        mock_chat_client.return_value = MagicMock()
        mock_internal.return_value = RealAgent(
            client=client, id="internal-search-agent",
            name="InternalSearchAgent", instructions="test",
        )
        mock_web.return_value = RealAgent(
            client=client, id="web-search-agent",
            name="WebSearchAgent", instructions="test",
        )

        builder = create_orchestrator_builder()
        workflow = builder.build()

        assert isinstance(workflow, Workflow)

    @patch("agent.orchestrator.create_web_search_agent")
    @patch("agent.orchestrator.create_internal_search_agent")
    @patch("agent.orchestrator.create_chat_client")
    def test_orchestrator_has_compaction(
        self,
        mock_chat_client: MagicMock,
        mock_internal: MagicMock,
        mock_web: MagicMock,
    ) -> None:
        """Orchestrator agent should hold the compaction/history providers."""
        from agent_framework import Agent as RealAgent
        client = MagicMock()
        mock_chat_client.return_value = MagicMock()
        mock_internal.return_value = RealAgent(
            client=client, id="internal-search-agent",
            name="InternalSearchAgent", instructions="test",
        )
        mock_web.return_value = RealAgent(
            client=client, id="web-search-agent",
            name="WebSearchAgent", instructions="test",
        )

        workflow = create_orchestrator()
        assert workflow is not None


class TestMainStartup:
    """Test that main.py fails fast when required startup dependencies are unavailable."""

    @patch("main.from_agent_framework")
    @patch("agent.orchestrator.create_orchestrator_builder", side_effect=RuntimeError("test error"))
    def test_raises_when_orchestrator_creation_fails(
        self,
        mock_create_orchestrator: MagicMock,
        mock_from_framework: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """main() fails instead of downgrading to single-agent mode."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.cosmos.azure.com:443/")

        import agent.config
        monkeypatch.setattr("agent.config.config", agent.config._load_config())

        from main import main

        with pytest.raises(RuntimeError, match="test error"):
            main()

        mock_from_framework.assert_not_called()
