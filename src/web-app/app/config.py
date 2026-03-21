"""Web app configuration — loads environment variables and validates required settings.

Usage:
    from app.config import config
    print(config.agent_endpoint)
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _find_env_file() -> Path | None:
    """Search for .env file starting from this file's directory, then up."""
    current = Path(__file__).resolve().parent.parent  # src/web-app/
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

    # Agent endpoint (local: http://localhost:8088, deployed: Foundry endpoint)
    agent_endpoint: str

    # Azure Blob Storage — serving account (images)
    serving_blob_endpoint: str
    serving_container_name: str

    # Cosmos DB — conversation persistence (4-container model)
    cosmos_endpoint: str
    cosmos_database_name: str
    cosmos_sessions_container: str
    cosmos_conversations_container: str
    cosmos_messages_container: str
    cosmos_references_container: str


def _load_config() -> Config:
    """Load and validate configuration from environment."""
    env_file = _find_env_file()
    if env_file:
        load_dotenv(env_file, override=False)

    required = {
        "AGENT_ENDPOINT": "agent_endpoint",
        "SERVING_BLOB_ENDPOINT": "serving_blob_endpoint",
    }

    missing = [var for var in required if not os.environ.get(var)]
    if missing:
        print(
            f"Error: Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.sample to .env and fill in values, or run: azd env get-values > src/web-app/.env",
            file=sys.stderr,
        )
        sys.exit(1)

    return Config(
        agent_endpoint=os.environ["AGENT_ENDPOINT"],
        serving_blob_endpoint=os.environ["SERVING_BLOB_ENDPOINT"],
        serving_container_name=os.environ.get("SERVING_CONTAINER_NAME", "serving"),
        cosmos_endpoint=os.environ.get("COSMOS_ENDPOINT", ""),
        cosmos_database_name=os.environ.get("COSMOS_DATABASE_NAME", "kb-agent"),
        cosmos_sessions_container=os.environ.get("COSMOS_SESSIONS_CONTAINER", "agent-sessions"),
        cosmos_conversations_container=os.environ.get("COSMOS_CONVERSATIONS_CONTAINER", "conversations"),
        cosmos_messages_container=os.environ.get("COSMOS_MESSAGES_CONTAINER", "messages"),
        cosmos_references_container=os.environ.get("COSMOS_REFERENCES_CONTAINER", "references"),
    )


# Singleton — imported as `from app.config import config`
config = _load_config()
