"""Adapter integration tests for the KB Agent server.

``main.py`` uses ``from_agent_framework()`` from the Azure AI Agent Server
SDK to run the ChatAgent as an HTTP server on port 8088.

These tests verify:
1. The ``create_agent`` factory returns a valid ChatAgent.
2. ``from_agent_framework`` accepts our agent type.

Full HTTP endpoint tests (streaming, health, error handling) are covered
by integration tests that require a running server.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Agent factory tests
# ---------------------------------------------------------------------------


class TestCreateAgentFactory:
    """Test the create_agent() factory used by main()."""

    @patch("agent.kb_agent.ChatAgent.__init__", return_value=None)
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_factory_returns_agent(
        self,
        mock_cred: MagicMock,
        mock_client: MagicMock,
        mock_agent_init: MagicMock,
    ) -> None:
        """create_agent() returns a KBSearchAgent instance."""
        from agent.kb_agent import KBSearchAgent, create_agent

        agent = create_agent()

        mock_agent_init.assert_called_once()
        assert isinstance(agent, KBSearchAgent)


# ---------------------------------------------------------------------------
# from_agent_framework adapter tests
# ---------------------------------------------------------------------------


class TestFromAgentFramework:
    """Test that from_agent_framework accepts our agent."""

    @patch("agent.kb_agent.ChatAgent.__init__", return_value=None)
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_adapter_accepts_agent(
        self,
        mock_cred: MagicMock,
        mock_client: MagicMock,
        mock_agent_init: MagicMock,
    ) -> None:
        """from_agent_framework(agent) returns a runnable server."""
        from azure.ai.agentserver.agentframework import from_agent_framework

        from agent.kb_agent import create_agent

        agent = create_agent()
        server = from_agent_framework(agent)

        assert hasattr(server, "run")
        assert hasattr(server, "run_async")
