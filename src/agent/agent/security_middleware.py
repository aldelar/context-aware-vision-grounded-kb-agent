"""Security filter middleware — resolves groups and injects departments into tool kwargs.

Reads JWT claims from :data:`middleware.request_context.user_claims_var`,
resolves Entra group GUIDs to department names via
:func:`agent.group_resolver.resolve_departments`, and writes the resolved
values into ``context.kwargs`` so that tool functions receive them via
``**kwargs``.

Adds OTel span attributes so department filters are visible in traces.
"""

from __future__ import annotations

import logging

from agent_framework import FunctionMiddleware, FunctionInvocationContext
from opentelemetry import trace

from agent.group_resolver import resolve_departments
from middleware.request_context import user_claims_var, resolved_departments_var

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class SecurityFilterMiddleware(FunctionMiddleware):
    """Resolves user groups once per tool invocation and injects departments."""

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next,
    ) -> None:
        claims = user_claims_var.get()

        # Resolve group GUIDs → department names
        groups = claims.get("groups", [])
        departments = resolve_departments(groups) if groups else []

        # Store in ContextVar for other middleware to observe
        resolved_departments_var.set(departments)

        # Inject into tool kwargs so tools receive them via **kwargs
        context.kwargs["departments"] = departments
        context.kwargs["roles"] = claims.get("roles", [])
        context.kwargs["tenant_id"] = claims.get("tenant_id", "")

        logger.debug(
            "SecurityFilterMiddleware: departments=%s for function=%s",
            departments,
            context.function.name,
        )

        # Record security context on the current OTel span for trace visibility
        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("security.departments", departments)
            span.set_attribute("security.groups", groups)
            span.set_attribute("security.user_id", claims.get("user_id", ""))

        await call_next()
