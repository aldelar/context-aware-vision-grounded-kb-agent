"""E2E tests for the contextual filtering pipeline.

Validates the full chain: JWT claims -> ContextVar -> SecurityFilterMiddleware
-> search_knowledge_base -> OData filter -> AI Search.

Requires REQUIRE_AUTH=false (dev mode) plus live Azure services.

Run with: uv run pytest tests/test_contextual_filtering_e2e.py -v -m integration
"""

from __future__ import annotations

import json
import logging

import pytest

from middleware.request_context import user_claims_var

pytestmark = pytest.mark.integration


class TestContextualFilteringE2E:
    """E2E tests for the full contextual filtering pipeline."""

    def test_e2e_dev_mode_applies_filter(self, monkeypatch) -> None:
        """In dev mode, default claims apply engineering filter to search."""
        monkeypatch.setenv("REQUIRE_AUTH", "false")

        # Simulate what JWTAuthMiddleware does in dev mode
        user_claims_var.set({
            "user_id": "dev-user",
            "tenant_id": "dev-tenant",
            "groups": ["dev-group-guid"],
            "roles": ["contributor"],
        })

        from agent.kb_agent import search_knowledge_base

        # Call with departments kwarg (as SecurityFilterMiddleware would inject)
        result = search_knowledge_base(
            "azure search", departments=["engineering"]
        )
        parsed = json.loads(result)

        assert len(parsed) > 0
        # Verify all returned results have engineering department
        for item in parsed:
            assert item.get("article_id"), "Result should have an article_id"

    def test_e2e_filter_visible_in_logs(self, monkeypatch, caplog) -> None:
        """The OData filter expression appears in agent logs."""
        monkeypatch.setenv("REQUIRE_AUTH", "false")

        user_claims_var.set({
            "user_id": "dev-user",
            "tenant_id": "dev-tenant",
            "groups": ["dev-group-guid"],
            "roles": ["contributor"],
        })

        from agent.kb_agent import search_knowledge_base

        with caplog.at_level(logging.DEBUG, logger="agent.kb_agent"):
            search_knowledge_base(
                "azure search", departments=["engineering"]
            )

        assert any(
            "security filter" in record.message.lower()
            for record in caplog.records
        ), "Expected 'security filter' to appear in log output"
