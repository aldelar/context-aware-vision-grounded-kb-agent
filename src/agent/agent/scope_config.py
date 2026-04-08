"""Agent scope configuration loader.

Loads YAML-based scope definitions that control which topics an agent covers.
Scope changes require only editing the YAML file — no code changes needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).with_name("config")


@dataclass(frozen=True)
class AgentScopeConfig:
    """Typed scope configuration for a specialist agent."""

    name: str
    id: str
    description: str
    topics: list[str]
    example_questions: list[str] = field(default_factory=list)


def load_scope_config(config_name: str) -> AgentScopeConfig:
    """Load and validate an agent scope config from YAML.

    Args:
        config_name: Filename (without directory) under ``agent/config/``,
            e.g. ``"internal-search-agent.yaml"``.

    Returns:
        A validated ``AgentScopeConfig`` instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If required fields are missing or invalid.
    """
    config_path = _CONFIG_DIR / config_name
    if not config_path.exists():
        raise FileNotFoundError(f"Scope config not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Scope config must be a YAML mapping: {config_path}")

    return _validate_scope_config(raw, config_path)


def _validate_scope_config(raw: dict[str, Any], source: Path) -> AgentScopeConfig:
    """Validate required fields and construct an ``AgentScopeConfig``."""
    missing = [f for f in ("name", "id", "description", "topics") if f not in raw]
    if missing:
        raise ValueError(f"Scope config {source} is missing required fields: {missing}")

    topics = raw["topics"]
    if not isinstance(topics, list) or not topics:
        raise ValueError(f"Scope config {source}: 'topics' must be a non-empty list")

    for topic in topics:
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError(f"Scope config {source}: each topic must be a non-empty string")

    example_questions = raw.get("example_questions", [])
    if not isinstance(example_questions, list):
        raise ValueError(f"Scope config {source}: 'example_questions' must be a list")

    config = AgentScopeConfig(
        name=str(raw["name"]).strip(),
        id=str(raw["id"]).strip(),
        description=str(raw["description"]).strip(),
        topics=[str(t).strip() for t in topics],
        example_questions=[str(q).strip() for q in example_questions],
    )
    logger.info(
        "Loaded scope config '%s': topics=%s",
        config.name,
        config.topics,
    )
    return config
