"""Tests for SecurityFilterMiddleware.

Verifies that the middleware reads ContextVar claims, resolves departments,
injects them into context.kwargs for downstream tools, and sets OTel span
attributes for trace visibility.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.security_middleware import SecurityFilterMiddleware
from middleware.request_context import user_claims_var, resolved_departments_var


@pytest.fixture(autouse=True)
def _reset_context_vars():
    """Reset ContextVars before each test."""
    token_claims = user_claims_var.set({})
    token_depts = resolved_departments_var.set([])
    yield
    user_claims_var.reset(token_claims)
    resolved_departments_var.reset(token_depts)


class TestSecurityFilterMiddleware:
    """Test the SecurityFilterMiddleware process method."""

    @pytest.mark.asyncio
    async def test_injects_departments_into_kwargs(self) -> None:
        user_claims_var.set({
            "user_id": "u1",
            "tenant_id": "t1",
            "groups": ["group-guid-1"],
            "roles": ["contributor"],
        })

        middleware = SecurityFilterMiddleware()
        context = MagicMock()
        context.kwargs = {}
        context.function.name = "search_knowledge_base"
        call_next = AsyncMock()

        await middleware.process(context, call_next)

        assert context.kwargs["departments"] == ["engineering"]
        assert context.kwargs["roles"] == ["contributor"]
        assert context.kwargs["tenant_id"] == "t1"
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_groups_no_departments(self) -> None:
        user_claims_var.set({
            "user_id": "u1",
            "tenant_id": "t1",
            "groups": [],
            "roles": [],
        })

        middleware = SecurityFilterMiddleware()
        context = MagicMock()
        context.kwargs = {}
        context.function.name = "search_knowledge_base"
        call_next = AsyncMock()

        await middleware.process(context, call_next)

        assert context.kwargs["departments"] == []
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_claims_no_departments(self) -> None:
        """Default empty claims result in no departments."""
        middleware = SecurityFilterMiddleware()
        context = MagicMock()
        context.kwargs = {}
        context.function.name = "search_knowledge_base"
        call_next = AsyncMock()

        await middleware.process(context, call_next)

        assert context.kwargs["departments"] == []
        assert context.kwargs["roles"] == []
        assert context.kwargs["tenant_id"] == ""
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sets_resolved_departments_contextvar(self) -> None:
        user_claims_var.set({
            "user_id": "u1",
            "groups": ["group-guid-1"],
            "roles": [],
        })

        middleware = SecurityFilterMiddleware()
        context = MagicMock()
        context.kwargs = {}
        context.function.name = "search_knowledge_base"
        call_next = AsyncMock()

        await middleware.process(context, call_next)

        assert resolved_departments_var.get() == ["engineering"]

    @pytest.mark.asyncio
    async def test_sets_otel_span_attributes(self) -> None:
        """OTel span attributes are set for trace visibility."""
        user_claims_var.set({
            "user_id": "u1",
            "groups": ["group-guid-1"],
            "roles": [],
        })

        middleware = SecurityFilterMiddleware()
        context = MagicMock()
        context.kwargs = {}
        context.function.name = "search_knowledge_base"
        call_next = AsyncMock()

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        with patch("agent.security_middleware.trace") as mock_trace:
            mock_trace.get_current_span.return_value = mock_span
            await middleware.process(context, call_next)

        mock_span.set_attribute.assert_any_call("security.departments", ["engineering"])
        mock_span.set_attribute.assert_any_call("security.groups", ["group-guid-1"])
        mock_span.set_attribute.assert_any_call("security.user_id", "u1")
