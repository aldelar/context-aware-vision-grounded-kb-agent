"""Shared configuration — lazy-loaded, per-function validation.

Usage:
    from shared.config import get_config
    cfg = get_config()    # validates required env vars on first call
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _find_env_file() -> Path | None:
    """Search for .env file starting from this file's directory, then up."""
    current = Path(__file__).resolve().parent.parent  # src/functions/
    candidates = [
        current / ".env",
        current.parent.parent / ".env",  # repo root
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


@dataclass(frozen=True)
class Config:
    """Typed configuration loaded from environment variables."""

    # Azure AI Services (Content Understanding + Embeddings)
    ai_services_endpoint: str = ""

    # Embedding model deployment name
    embedding_deployment_name: str = "text-embedding-3-small"

    # Mistral Document AI deployment name
    mistral_deployment_name: str = "mistral-document-ai-2512"

    # Azure AI Search
    search_endpoint: str = ""
    search_index_name: str = "kb-articles"

    # Azure Blob Storage endpoints
    staging_blob_endpoint: str = ""
    serving_blob_endpoint: str = ""

    # Local paths (for local file I/O mode)
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent)

    @property
    def staging_path(self) -> Path:
        return self.project_root / "kb" / "staging"

    @property
    def serving_path(self) -> Path:
        return self.project_root / "kb" / "serving"

    @property
    def is_azure_mode(self) -> bool:
        """True when blob storage endpoints are configured (running in Azure)."""
        return bool(self.staging_blob_endpoint and self.serving_blob_endpoint)


_config: Config | None = None


def get_config() -> Config:
    """Load configuration from environment (lazy, cached).

    Returns a Config instance populated from environment variables.
    No validation of required vars here — each function validates
    what it needs at its own entry point.
    """
    global _config
    if _config is not None:
        return _config

    env_file = _find_env_file()
    if env_file:
        load_dotenv(env_file, override=False)

    _config = Config(
        ai_services_endpoint=os.environ.get("AI_SERVICES_ENDPOINT", ""),
        embedding_deployment_name=os.environ.get("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small"),
        mistral_deployment_name=os.environ.get("MISTRAL_DEPLOYMENT_NAME", "mistral-document-ai-2512"),
        search_endpoint=os.environ.get("SEARCH_ENDPOINT", ""),
        search_index_name=os.environ.get("SEARCH_INDEX_NAME", "kb-articles"),
        staging_blob_endpoint=os.environ.get("STAGING_BLOB_ENDPOINT", ""),
        serving_blob_endpoint=os.environ.get("SERVING_BLOB_ENDPOINT", ""),
    )
    return _config


# Backward compat: `from shared.config import config` still works.
# This is a lazy property that loads on first access.
class _ConfigProxy:
    """Proxy that loads config on first attribute access."""

    def __getattr__(self, name: str):
        return getattr(get_config(), name)


config = _ConfigProxy()
