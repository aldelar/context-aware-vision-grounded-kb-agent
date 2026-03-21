"""Integration tests for department-scoped AI Search queries.

These tests hit real Azure AI Search and require environment variables:
- SEARCH_ENDPOINT
- AI_SERVICES_ENDPOINT

Run with: uv run pytest tests/test_department_filter_integration.py -v -m integration
"""

from __future__ import annotations

import pytest

from agent.search_tool import search_kb


pytestmark = pytest.mark.integration


class TestDepartmentFilterIntegration:
    """Integration tests for search_kb with department OData filters."""

    def test_search_with_engineering_filter(self) -> None:
        """search_kb with engineering filter returns only engineering results."""
        results = search_kb(
            "azure search",
            security_filter="search.in(department, 'engineering', ',')",
        )
        assert len(results) > 0
        for r in results:
            assert r.department == "engineering", (
                f"Expected department='engineering', got '{r.department}' "
                f"for article {r.article_id}"
            )

    def test_search_without_filter(self) -> None:
        """search_kb without filter returns results (baseline)."""
        results = search_kb("azure search")
        assert len(results) > 0

    def test_search_with_nonexistent_department(self) -> None:
        """search_kb with nonexistent department returns zero results."""
        results = search_kb(
            "azure search",
            security_filter="search.in(department, 'nonexistent-dept-xyz', ',')",
        )
        assert len(results) == 0
