"""Tests for agent scope configuration loading and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from agent.scope_config import AgentScopeConfig, load_scope_config


class TestLoadScopeConfig:
    """Test loading scope configuration from YAML files."""

    def test_loads_internal_search_agent_config(self) -> None:
        config = load_scope_config("internal-search-agent.yaml")

        assert isinstance(config, AgentScopeConfig)
        assert config.name == "InternalSearchAgent"
        assert config.id == "internal-search-agent"
        assert len(config.topics) >= 2
        assert "Azure AI Search" in config.topics
        assert "Azure Content Understanding" in config.topics
        assert config.description  # non-empty

    def test_config_has_example_questions(self) -> None:
        config = load_scope_config("internal-search-agent.yaml")

        assert isinstance(config.example_questions, list)
        assert len(config.example_questions) >= 1

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError, match="Scope config not found"):
            load_scope_config("nonexistent-agent.yaml")

    def test_config_fields_are_stripped(self) -> None:
        config = load_scope_config("internal-search-agent.yaml")

        assert config.name == config.name.strip()
        assert config.id == config.id.strip()
        for topic in config.topics:
            assert topic == topic.strip()


class TestScopeConfigValidation:
    """Test validation logic for scope configs."""

    def test_missing_required_fields_raises(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("name: Test\n")  # missing id, description, topics

        from agent.scope_config import _validate_scope_config

        import yaml
        raw = yaml.safe_load(bad_yaml.read_text())
        with pytest.raises(ValueError, match="missing required fields"):
            _validate_scope_config(raw, bad_yaml)

    def test_empty_topics_raises(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text(textwrap.dedent("""\
            name: Test
            id: test
            description: test description
            topics: []
        """))

        from agent.scope_config import _validate_scope_config

        import yaml
        raw = yaml.safe_load(bad_yaml.read_text())
        with pytest.raises(ValueError, match="non-empty list"):
            _validate_scope_config(raw, bad_yaml)

    def test_non_string_topic_raises(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text(textwrap.dedent("""\
            name: Test
            id: test
            description: test description
            topics:
              - 123
        """))

        from agent.scope_config import _validate_scope_config

        import yaml
        raw = yaml.safe_load(bad_yaml.read_text())
        with pytest.raises(ValueError, match="non-empty string"):
            _validate_scope_config(raw, bad_yaml)

    def test_frozen_config(self) -> None:
        config = load_scope_config("internal-search-agent.yaml")

        with pytest.raises(AttributeError):
            config.name = "changed"  # type: ignore[misc]
