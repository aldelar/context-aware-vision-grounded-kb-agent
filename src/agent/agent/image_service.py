"""Image service — download article images from Azure Blob Storage.

The agent downloads images from the serving storage account so the
vision middleware can inject them into the LLM conversation as
``Content.from_data()`` items (base64 data URIs).

Unlike the web-app version, there are no proxy URL helpers here — the
agent outputs ``/api/images/...`` URLs that the web app proxy will serve.
"""

from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass
from urllib.parse import quote

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from agent.config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level blob client (config is available at import time)
# ---------------------------------------------------------------------------

_blob_service_client = BlobServiceClient(
    account_url=config.serving_blob_endpoint,
    credential=DefaultAzureCredential(),
)


# ---------------------------------------------------------------------------
# Image download (used by the vision middleware)
# ---------------------------------------------------------------------------

@dataclass
class ImageBlob:
    """Downloaded image content + metadata."""
    data: bytes
    content_type: str


def download_image(article_id: str, image_path: str) -> ImageBlob | None:
    """Download an image blob from the serving container.

    Returns ``None`` if the blob does not exist or cannot be read.
    """
    blob_path = f"{article_id}/{image_path}"
    try:
        blob_client = _blob_service_client.get_blob_client(
            container=config.serving_container_name,
            blob=blob_path,
        )
        download = blob_client.download_blob()
        data = download.readall()
        content_type = (
            download.properties.content_settings.content_type
            or mimetypes.guess_type(image_path)[0]
            or "application/octet-stream"
        )
        logger.debug("Downloaded blob %s (%d bytes)", blob_path, len(data))
        return ImageBlob(data=data, content_type=content_type)
    except Exception:
        logger.warning("Failed to download blob %s", blob_path, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Image URL helpers (for tool output — web app proxy URLs)
# ---------------------------------------------------------------------------

def get_image_url(article_id: str, image_path: str) -> str:
    """Return a proxy URL for the image.

    The URL points to ``/api/images/{article_id}/{image_path}`` which the
    web app serves via its image proxy endpoint.  The agent outputs these
    URLs in markdown so the browser can fetch them.
    """
    encoded_path = quote(image_path, safe="/")
    encoded_article = quote(article_id, safe="")
    return f"/api/images/{encoded_article}/{encoded_path}"
