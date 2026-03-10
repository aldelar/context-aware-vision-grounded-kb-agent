"""Content Understanding client factory.

Usage:
    from fn_convert_cu.cu_client import get_cu_client
    client = get_cu_client()
"""

from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.identity import DefaultAzureCredential

from shared.config import config

_client: ContentUnderstandingClient | None = None


def get_cu_client() -> ContentUnderstandingClient:
    """Return a shared ContentUnderstandingClient instance.

    Uses DefaultAzureCredential (falls back to ``az login`` for local dev)
    and reads the endpoint from shared config.
    """
    global _client
    if _client is None:
        _client = ContentUnderstandingClient(
            endpoint=config.ai_services_endpoint,
            credential=DefaultAzureCredential(),
        )
    return _client
