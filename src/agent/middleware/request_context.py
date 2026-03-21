"""Per-request context variables for security context propagation.

Defines ``ContextVar`` instances that carry JWT claims and resolved
department names through the async call stack.  Set by
:class:`middleware.jwt_auth.JWTAuthMiddleware` and read by
:class:`agent.security_middleware.SecurityFilterMiddleware`.
"""

from __future__ import annotations

from contextvars import ContextVar

user_claims_var: ContextVar[dict] = ContextVar("user_claims", default={})
"""Raw JWT claims extracted by the auth middleware.

Keys: ``user_id``, ``tenant_id``, ``groups`` (list[str]), ``roles`` (list[str]).
Default dev claims are set when ``REQUIRE_AUTH=false``.
"""

resolved_departments_var: ContextVar[list[str]] = ContextVar(
    "resolved_departments", default=[]
)
"""Department names resolved from Entra group GUIDs.

Populated by :class:`agent.security_middleware.SecurityFilterMiddleware`
after calling :func:`agent.group_resolver.resolve_departments`.
"""
