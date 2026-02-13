"""Configuration loader for the Content Understanding spike."""

import os
from dotenv import load_dotenv


def load_config() -> dict[str, str]:
    """Load configuration from .env file and environment variables.

    Returns a dict with all required settings. Raises if required vars are missing.
    """
    load_dotenv()

    required = ["CONTENTUNDERSTANDING_ENDPOINT", "MODELS_ENDPOINT"]
    optional = {
        "CONTENTUNDERSTANDING_KEY": None,
        "GPT_4_1_DEPLOYMENT": "gpt-4.1",
        "GPT_4_1_MINI_DEPLOYMENT": "gpt-4.1-mini",
        "TEXT_EMBEDDING_3_SMALL_DEPLOYMENT": "text-embedding-3-small",
    }

    config: dict[str, str] = {}

    for var in required:
        value = os.environ.get(var)
        if not value:
            raise EnvironmentError(f"Missing required environment variable: {var}")
        config[var] = value

    for var, default in optional.items():
        config[var] = os.environ.get(var, default)  # type: ignore[assignment]

    return config


def get_credential(config: dict[str, str]):
    """Return AzureKeyCredential if key is set, otherwise DefaultAzureCredential."""
    key = config.get("CONTENTUNDERSTANDING_KEY")
    if key:
        from azure.core.credentials import AzureKeyCredential
        return AzureKeyCredential(key)
    else:
        from azure.identity import DefaultAzureCredential
        return DefaultAzureCredential()
