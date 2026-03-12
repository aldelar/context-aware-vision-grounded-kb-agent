"""Agent configuration — loads environment variables and validates required settings.

Usage:
    from agent.config import config
    print(config.ai_services_endpoint)
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _find_env_file() -> Path | None:
    """Search for .env file starting from this file's directory, then up."""
    current = Path(__file__).resolve().parent.parent  # src/agent/
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

    # Foundry project endpoint
    project_endpoint: str

    # Azure AI Services endpoint
    ai_services_endpoint: str

    # Agent model deployment name
    agent_model_deployment_name: str

    # Embedding model deployment name
    embedding_deployment_name: str

    # Azure AI Search
    search_endpoint: str
    search_index_name: str

    # Azure Blob Storage — serving account (images for vision)
    serving_blob_endpoint: str
    serving_container_name: str

    # Cosmos DB — agent session persistence (optional: empty = no persistence)
    cosmos_endpoint: str
    cosmos_database_name: str


def _load_config() -> Config:
    """Load and validate configuration from environment."""
    env_file = _find_env_file()
    if env_file:
        load_dotenv(env_file, override=False)

    required = {
        "AI_SERVICES_ENDPOINT": "ai_services_endpoint",
        "SEARCH_ENDPOINT": "search_endpoint",
        "SERVING_BLOB_ENDPOINT": "serving_blob_endpoint",
    }

    missing = [var for var in required if not os.environ.get(var)]
    if missing:
        print(
            f"Error: Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.sample to .env and fill in values, or run: make dev-setup-env",
            file=sys.stderr,
        )
        sys.exit(1)

    return Config(
        project_endpoint=os.environ.get(
            "PROJECT_ENDPOINT",
            os.environ.get("FOUNDRY_PROJECT_ENDPOINT", ""),
        ),
        ai_services_endpoint=os.environ["AI_SERVICES_ENDPOINT"],
        agent_model_deployment_name=os.environ.get("AGENT_MODEL_DEPLOYMENT_NAME", "gpt-4.1"),
        embedding_deployment_name=os.environ.get("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small"),
        search_endpoint=os.environ["SEARCH_ENDPOINT"],
        search_index_name=os.environ.get("SEARCH_INDEX_NAME", "kb-articles"),
        serving_blob_endpoint=os.environ.get("SERVING_BLOB_ENDPOINT", ""),
        serving_container_name=os.environ.get("SERVING_CONTAINER_NAME", "serving"),
        cosmos_endpoint=os.environ.get("COSMOS_ENDPOINT", ""),
        cosmos_database_name=os.environ.get("COSMOS_DATABASE_NAME", "kb-agent"),
    )


# Singleton — imported as `from agent.config import config`
config = _load_config()
