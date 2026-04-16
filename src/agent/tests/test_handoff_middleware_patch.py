"""Tests for the HandoffBuilder middleware cloning patch.

Verifies that ``_patch_handoff_clone_middleware()`` fixes the upstream bug
in ``agent-framework-orchestrations`` where ``_clone_chat_agent()`` passes
only ``agent.agent_middleware`` (agent-type) instead of ``agent.middleware``
(all types), silently dropping ``FunctionMiddleware`` instances like
``SecurityFilterMiddleware``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent_framework import Agent, FunctionMiddleware, FunctionInvocationContext
from agent_framework_orchestrations._handoff import HandoffAgentExecutor


class _StubFunctionMiddleware(FunctionMiddleware):
    """Minimal FunctionMiddleware for testing."""

    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        await call_next()


def _make_agent_with_function_middleware() -> Agent:
    """Create an Agent with a single FunctionMiddleware for testing."""
    client = MagicMock()
    return Agent(
        client=client,
        id="test-agent",
        name="TestAgent",
        instructions="test",
        middleware=[_StubFunctionMiddleware()],
    )


class TestHandoffCloneBug:
    """Characterise the upstream bug so the patch can be validated."""

    def test_original_agent_has_function_middleware(self) -> None:
        agent = _make_agent_with_function_middleware()

        assert agent.middleware is not None
        assert len(agent.middleware) == 1
        assert isinstance(agent.middleware[0], FunctionMiddleware)

    def test_agent_middleware_excludes_function_type(self) -> None:
        """``agent.agent_middleware`` only contains agent-type middleware."""
        agent = _make_agent_with_function_middleware()

        # agent_middleware is populated by AgentMiddlewareLayer with only agent-type
        assert agent.agent_middleware == []


class TestPatchHandoffCloneMiddleware:
    """Verify the monkey-patch restores FunctionMiddleware on cloned agents."""

    def test_patch_is_applied(self) -> None:
        from main import _patch_handoff_clone_middleware

        _patch_handoff_clone_middleware()

        assert getattr(HandoffAgentExecutor, "_kb_agent_middleware_patch", False) is True

    def test_patch_is_idempotent(self) -> None:
        from main import _patch_handoff_clone_middleware

        _patch_handoff_clone_middleware()
        _patch_handoff_clone_middleware()  # should not raise

    def test_cloned_agent_retains_function_middleware(self) -> None:
        from main import _patch_handoff_clone_middleware

        _patch_handoff_clone_middleware()

        agent = _make_agent_with_function_middleware()

        # Create a minimal executor instance to call _clone_chat_agent
        executor = HandoffAgentExecutor.__new__(HandoffAgentExecutor)
        cloned = executor._clone_chat_agent(agent)

        assert cloned.middleware is not None
        function_middleware = [
            m for m in cloned.middleware if isinstance(m, FunctionMiddleware)
        ]
        assert len(function_middleware) >= 1, (
            "FunctionMiddleware should survive cloning after patch"
        )

    def test_cloned_agent_preserves_identity(self) -> None:
        from main import _patch_handoff_clone_middleware

        _patch_handoff_clone_middleware()

        agent = _make_agent_with_function_middleware()

        executor = HandoffAgentExecutor.__new__(HandoffAgentExecutor)
        cloned = executor._clone_chat_agent(agent)

        assert cloned.id == agent.id
        assert cloned.name == agent.name
        assert cloned.description == agent.description

    def test_cloned_agent_has_store_false(self) -> None:
        """Handoff clones must set store=False to avoid duplicate persistence."""
        from main import _patch_handoff_clone_middleware

        _patch_handoff_clone_middleware()

        agent = _make_agent_with_function_middleware()

        executor = HandoffAgentExecutor.__new__(HandoffAgentExecutor)
        cloned = executor._clone_chat_agent(agent)

        assert cloned.default_options.get("store") is False
