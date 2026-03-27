"""Environment-aware SDK factories for the web app."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from app.config import get_config

if TYPE_CHECKING:
    from azure.cosmos import CosmosClient


def _ensure_cosmos_sdk_env(endpoint: str) -> None:
    """Patch around azure-cosmos 4.15 eager inference client init.

    azure-cosmos 4.15 constructs its semantic-reranking inference client during
    CosmosClient initialization and reads the endpoint from the
    AZURE_COSMOS_SEMANTIC_RERANKER_INFERENCE_ENDPOINT environment variable at
    import time. This app does not use Cosmos semantic reranking, but without a
    value the SDK raises during client construction and disables thread
    persistence entirely.

    Setting the variable before importing azure.cosmos keeps normal Cosmos DB
    operations working until the upstream SDK behavior is fixed.
    """
    os.environ.setdefault("AZURE_COSMOS_SEMANTIC_RERANKER_INFERENCE_ENDPOINT", endpoint.rstrip("/"))


def create_cosmos_client(endpoint: str | None = None) -> CosmosClient:
    cfg = get_config()
    cosmos_endpoint = endpoint or cfg.cosmos_endpoint
    _ensure_cosmos_sdk_env(cosmos_endpoint)

    from azure.cosmos import CosmosClient

    if cfg.is_dev:
        return CosmosClient(
            url=cosmos_endpoint,
            credential=cfg.cosmos_key,
            connection_verify=cfg.cosmos_verify_cert,
            enable_endpoint_discovery=False,
        )
    return CosmosClient(
        url=cosmos_endpoint,
        credential=DefaultAzureCredential(),
    )


def create_blob_service_client(account_url: str | None = None) -> BlobServiceClient:
    cfg = get_config()
    if cfg.is_dev and cfg.azurite_connection_string:
        return BlobServiceClient.from_connection_string(cfg.azurite_connection_string)
    return BlobServiceClient(
        account_url=(account_url or cfg.serving_blob_endpoint).rstrip("/"),
        credential=DefaultAzureCredential(),
    )