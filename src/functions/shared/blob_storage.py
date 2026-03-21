"""Azure Blob Storage helpers for fn-convert and fn-index.

Downloads article folders from blob containers to a local temp directory
so the existing pipeline code (which works with local file paths) can run
unchanged. Uploads results back to blob storage after processing.

Uses ``DefaultAzureCredential`` — managed identity in Azure, ``az login``
for local dev.
"""

from __future__ import annotations

import logging
import mimetypes
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient, ContentSettings

logger = logging.getLogger(__name__)


def _container_client(blob_endpoint: str, container_name: str) -> ContainerClient:
    """Create a ContainerClient from a blob endpoint URL and container name."""
    return ContainerClient(
        account_url=blob_endpoint.rstrip("/"),
        container_name=container_name,
        credential=DefaultAzureCredential(),
    )


def list_articles(
    blob_endpoint: str, container_name: str, *, depth: int = 1
) -> list[str]:
    """List article folder names in a container.

    Parameters
    ----------
    depth:
        Number of path segments that form the article ID.
        Use ``1`` for the flat serving container (``{article-id}/…``) and
        ``2`` for the nested staging container (``{dept}/{article-id}/…``).
    """
    client = _container_client(blob_endpoint, container_name)
    folders: set[str] = set()
    for blob in client.list_blobs():
        parts = blob.name.split("/")
        if len(parts) >= depth + 1:
            folders.add("/".join(parts[:depth]))
    return sorted(folders)


def download_article(
    blob_endpoint: str,
    container_name: str,
    article_id: str,
    dest_dir: Path | None = None,
) -> Path:
    """Download all blobs under ``article_id/`` to a local directory.

    Parameters
    ----------
    blob_endpoint:
        Blob storage account URL (e.g. ``https://st{project}stagingdev.blob.core.windows.net/``).
    container_name:
        Container name (``staging`` or ``serving``).
    article_id:
        Article folder name (top-level virtual directory prefix).
    dest_dir:
        Optional local directory to write into. If ``None``, creates a temp dir.

    Returns
    -------
    Path
        Local directory path containing the downloaded files.
    """
    client = _container_client(blob_endpoint, container_name)

    if dest_dir is None:
        dest_dir = Path(tempfile.mkdtemp(prefix=f"kb-{article_id}-"))
    else:
        dest_dir.mkdir(parents=True, exist_ok=True)

    prefix = f"{article_id}/"
    blob_count = 0
    for blob in client.list_blobs(name_starts_with=prefix):
        # Relative path within the article folder
        rel_path = blob.name[len(prefix) :]
        if not rel_path:
            continue

        local_path = dest_dir / rel_path
        local_path.parent.mkdir(parents=True, exist_ok=True)

        blob_client = client.get_blob_client(blob.name)
        with open(local_path, "wb") as f:
            data = blob_client.download_blob().readall()
            f.write(data)
        blob_count += 1

    logger.info(
        "Downloaded %d blobs from %s/%s → %s",
        blob_count,
        container_name,
        article_id,
        dest_dir,
    )
    return dest_dir


def upload_article(
    blob_endpoint: str,
    container_name: str,
    article_id: str,
    source_dir: Path,
) -> int:
    """Upload all files from ``source_dir`` to ``article_id/`` in the container.

    Parameters
    ----------
    blob_endpoint:
        Blob storage account URL.
    container_name:
        Container name (``serving``).
    article_id:
        Article folder name (used as blob prefix).
    source_dir:
        Local directory containing files to upload.

    Returns
    -------
    int
        Number of blobs uploaded.
    """
    client = _container_client(blob_endpoint, container_name)
    count = 0

    for local_path in sorted(source_dir.rglob("*")):
        if local_path.is_dir():
            continue

        rel_path = local_path.relative_to(source_dir)
        blob_name = f"{article_id}/{rel_path}"

        blob_client = client.get_blob_client(blob_name)
        content_type, _ = mimetypes.guess_type(str(local_path))
        kwargs: dict = {"overwrite": True}
        if content_type:
            kwargs["content_settings"] = ContentSettings(content_type=content_type)
        with open(local_path, "rb") as f:
            blob_client.upload_blob(f, **kwargs)
        count += 1

    logger.info(
        "Uploaded %d blobs to %s/%s",
        count,
        container_name,
        article_id,
    )
    return count


def get_article_ids(
    req: func.HttpRequest,
    blob_endpoint: str,
    container_name: str,
    *,
    depth: int = 1,
) -> list[str]:
    """Extract article IDs from request body, or list all from blob container.

    Checks the JSON request body for an ``article_id`` field.  If present,
    returns a single-element list.  Otherwise falls back to listing all
    article folders in the given blob container.

    Parameters
    ----------
    depth:
        Passed to :func:`list_articles` — ``1`` for flat serving,
        ``2`` for nested staging.
    """
    try:
        body = req.get_json()
        article_id = body.get("article_id")
        if article_id:
            return [article_id]
    except (ValueError, AttributeError):
        pass

    # No specific article — list all from blob
    return list_articles(blob_endpoint, container_name, depth=depth)
