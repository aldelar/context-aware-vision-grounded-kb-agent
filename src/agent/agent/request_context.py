"""Per-request context propagation via ``contextvars``.

The ``AgentFrameworkAIAgentAdapter`` sets ``_request_headers`` on the
``ChatAgent`` singleton *before* calling ``run`` / ``run_stream``.  Because
the agent instance is shared across concurrent requests, plain instance
attributes are **not** async-safe.

This module provides a ``ContextVar``-based mechanism to propagate
per-request values (starting with ``user_id``) so that tool functions can
read them without holding a reference to the agent.

Usage in tools::

    from agent.request_context import get_user_id

    def my_tool(query: str) -> str:
        user_id = get_user_id()      # returns "anonymous" if not set
        ...
"""

from __future__ import annotations

import contextvars

_user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "user_id", default="anonymous"
)


def get_user_id() -> str:
    """Return the ``user_id`` for the current async task."""
    return _user_id_var.get()


def set_user_id(value: str) -> contextvars.Token[str]:
    """Set the ``user_id`` for the current async task.

    Returns a reset token that can be used to restore the previous value.
    """
    return _user_id_var.set(value)
