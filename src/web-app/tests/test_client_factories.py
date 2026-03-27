"""Unit tests for web app client factories."""

from __future__ import annotations

import os
from unittest.mock import patch


def test_cosmos_factory_uses_emulator_key_in_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://localhost:8081/")
    monkeypatch.setenv("COSMOS_KEY", "emulator-key")
    monkeypatch.delenv("AZURE_COSMOS_SEMANTIC_RERANKER_INFERENCE_ENDPOINT", raising=False)

    from app import config as cfg_mod
    from app.client_factories import create_cosmos_client

    cfg_mod._config = None

    with patch("azure.cosmos.CosmosClient") as mock_client:
        create_cosmos_client()
        kwargs = mock_client.call_args.kwargs
        assert kwargs["credential"] == "emulator-key"
        assert kwargs["connection_verify"] is False
        assert kwargs["enable_endpoint_discovery"] is False
        assert os.environ["AZURE_COSMOS_SEMANTIC_RERANKER_INFERENCE_ENDPOINT"] == "https://localhost:8081"


def test_cosmos_factory_sets_sdk_inference_endpoint_in_prod(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://cosmos.example.com:443/")
    monkeypatch.delenv("AZURE_COSMOS_SEMANTIC_RERANKER_INFERENCE_ENDPOINT", raising=False)

    from app import config as cfg_mod
    from app.client_factories import create_cosmos_client

    cfg_mod._config = None

    with patch("azure.cosmos.CosmosClient") as mock_client:
        create_cosmos_client()
        kwargs = mock_client.call_args.kwargs
        assert kwargs["url"] == "https://cosmos.example.com:443/"
        assert os.environ["AZURE_COSMOS_SEMANTIC_RERANKER_INFERENCE_ENDPOINT"] == "https://cosmos.example.com:443"


def test_blob_factory_uses_connection_string_in_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("AZURITE_CONNECTION_STRING", "UseDevelopmentStorage=true")

    from app import config as cfg_mod
    from app.client_factories import create_blob_service_client

    cfg_mod._config = None

    with patch("app.client_factories.BlobServiceClient.from_connection_string") as mock_from_connection_string:
        create_blob_service_client()
        mock_from_connection_string.assert_called_once_with("UseDevelopmentStorage=true")