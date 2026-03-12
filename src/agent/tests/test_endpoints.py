"""Adapter integration tests for the KB Agent server.

``main.py`` uses ``from_agent_framework()`` from the Azure AI Agent Server
SDK to run the Agent as an HTTP server on port 8088.

These tests verify:
1. The ``create_agent`` factory returns a valid Agent.
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

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_factory_returns_agent(
        self,
        mock_cred: MagicMock,
        mock_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """create_agent() returns an Agent instance."""
        from agent.kb_agent import create_agent

        agent = create_agent()

        mock_agent_cls.assert_called_once()
        assert agent is mock_agent_cls.return_value


# ---------------------------------------------------------------------------
# from_agent_framework adapter tests
# ---------------------------------------------------------------------------


class TestFromAgentFramework:
    """Test that from_agent_framework accepts our agent."""

    @patch("agent.kb_agent.Agent")
    @patch("agent.kb_agent.AzureOpenAIChatClient")
    @patch("agent.kb_agent.DefaultAzureCredential")
    def test_adapter_accepts_agent(
        self,
        mock_cred: MagicMock,
        mock_client: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        """from_agent_framework(agent) returns a runnable server."""
        from azure.ai.agentserver.agentframework import from_agent_framework

        from agent.kb_agent import create_agent

        agent = create_agent()
        server = from_agent_framework(agent, session_repository=None)

        assert hasattr(server, "run")
        assert hasattr(server, "run_async")
