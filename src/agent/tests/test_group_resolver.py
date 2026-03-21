"""Tests for group-to-department resolver."""

from __future__ import annotations

from agent.group_resolver import resolve_departments


class TestResolveDepartments:
    """Simulated group resolver maps GUIDs to department names."""

    def test_non_empty_groups_return_engineering(self):
        result = resolve_departments(["group-guid-1", "group-guid-2"])
        assert result == ["engineering"]

    def test_single_group_returns_engineering(self):
        result = resolve_departments(["single-guid"])
        assert result == ["engineering"]

    def test_empty_groups_return_empty(self):
        result = resolve_departments([])
        assert result == []
