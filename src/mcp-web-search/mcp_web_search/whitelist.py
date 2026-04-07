"""Site whitelist loader for the MCP web search server.

Loads allowed domains from ``config/whitelist.yaml``.
Only results from whitelisted domains are returned to callers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def load_whitelist(config_path: Path | None = None) -> list[str]:
    """Load and validate the site whitelist from YAML.

    Args:
        config_path: Override path for testing. Defaults to ``config/whitelist.yaml``.

    Returns:
        A list of allowed domain strings (lowercase, stripped).

    Raises:
        FileNotFoundError: If the whitelist file does not exist.
        ValueError: If the file is malformed or empty.
    """
    path = config_path or (_CONFIG_DIR / "whitelist.yaml")
    if not path.exists():
        raise FileNotFoundError(f"Whitelist config not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Whitelist config must be a YAML mapping: {path}")

    allowed = raw.get("allowed_sites")
    if not isinstance(allowed, list) or not allowed:
        raise ValueError(f"Whitelist config {path}: 'allowed_sites' must be a non-empty list")

    sites: list[str] = []
    for site in allowed:
        if not isinstance(site, str) or not site.strip():
            raise ValueError(f"Whitelist config {path}: each site must be a non-empty string")
        sites.append(site.strip().lower())

    logger.info("Loaded whitelist: %s", sites)
    return sites


def is_url_whitelisted(url: str, whitelist: list[str]) -> bool:
    """Check if a URL belongs to a whitelisted domain."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
    except Exception:
        return False

    return any(hostname == site or hostname.endswith(f".{site}") for site in whitelist)
